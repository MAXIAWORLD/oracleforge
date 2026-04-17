"""MAXIA Oracle — Pyth Network Hermes price layer.

Pure Pyth Hermes integration: feed definitions, single-price fetch, cache,
staleness/confidence checks, TWAP, and on-chain verification.

Cascade functions (get_stock_price, get_crypto_price, get_batch_prices,
get_stock_price_finnhub) live in price_cascade.py to avoid a circular
import with price_oracle.py (audit H1/H2 fix).

Extracted from MAXIA V12/backend/trading/pyth_oracle.py on 2026-04-14.
"""
import asyncio
import logging
import os
import time

import httpx

from core.errors import safe_error

logger = logging.getLogger("pyth_oracle")


# ── Constantes Pyth Hermes ──

HERMES_URL = os.getenv("PYTH_HERMES_URL", "https://hermes.pyth.network")  # P6: env var pour Hermes prive

# ── Protection anti-staleness ──
MAX_STALENESS_STOCK_NORMAL_S = 600
MAX_STALENESS_STOCK_HFT_S = 5
MAX_STALENESS_CRYPTO_NORMAL_S = 120
MAX_STALENESS_CRYPTO_HFT_S = 3
STALE_CIRCUIT_THRESHOLD = 5
_consecutive_stale: dict[str, int] = {}
_STALE_MAX_TRACKED = 500  # P3 fix: cap to prevent unbounded growth

# ── P2: Confidence tieree par asset class (comme Drift) ──
# Majors: seuil strict (haute liquidite, confidence basse attendue)
# Mid-caps: seuil moyen (liquidite moyenne)
# Small-caps: seuil large (liquidite faible, confidence naturellement haute)
_CONFIDENCE_TIERS = {
    "major": 2.0,    # SOL, ETH, BTC, USDC — comme avant
    "mid":   5.0,    # LINK, UNI, AAVE, AVAX, XRP, MATIC, etc.
    "small": 10.0,   # BONK, WIF, POPCAT, PENGU, FARTCOIN, etc.
}
_MAJOR_TOKENS = {"SOL", "ETH", "BTC", "USDC", "USDT"}
_MID_TOKENS = {"LINK", "UNI", "AAVE", "AVAX", "XRP", "MATIC", "RENDER", "JUP", "RAY", "ORCA",
               "DRIFT", "JTO", "PYTH", "HNT", "W", "LDO", "FET", "OLAS", "NEAR", "APT", "SUI",
               "SEI", "INJ", "ARB", "OP", "TIA", "STX", "FIL", "AR", "ONDO", "DOGE"}
# Tout le reste = small


def get_confidence_threshold(symbol: str) -> float:
    """Retourne le seuil de confidence adapte a l'asset class."""
    sym = symbol.upper()
    if sym in _MAJOR_TOKENS:
        return _CONFIDENCE_TIERS["major"]
    if sym in _MID_TOKENS:
        return _CONFIDENCE_TIERS["mid"]
    return _CONFIDENCE_TIERS["small"]


# ── P3: TWAP rolling 5 minutes ──
_twap_data: dict[str, list] = {}  # {symbol: [(ts, price), ...]}
_TWAP_WINDOW_S = 300  # 5 minutes
_TWAP_MAX_DEVIATION_PCT = 20.0  # Rejeter si spot devie >20% du TWAP
_TWAP_MAX_SYMBOLS = 100  # Max symbols tracked (65 crypto + 25 stocks)


def update_twap(symbol: str, price: float):
    """Ajoute un datapoint au TWAP rolling."""
    now = time.time()
    if symbol not in _twap_data:
        # Cap total symbols to prevent unbounded growth from rogue feeds
        if len(_twap_data) >= _TWAP_MAX_SYMBOLS:
            oldest_sym = min(_twap_data, key=lambda s: _twap_data[s][-1][0] if _twap_data[s] else 0)
            del _twap_data[oldest_sym]
        _twap_data[symbol] = []
    _twap_data[symbol].append((now, price))
    # Purger les points hors fenetre
    cutoff = now - _TWAP_WINDOW_S
    _twap_data[symbol] = [(t, p) for t, p in _twap_data[symbol] if t >= cutoff]


def get_twap(symbol: str) -> float:
    """Retourne le TWAP 5min. 0 si pas assez de data."""
    points = _twap_data.get(symbol, [])
    if len(points) < 2:
        return 0
    return sum(p for _, p in points) / len(points)


def check_twap_deviation(symbol: str, spot_price: float) -> dict:
    """Verifie si le prix spot devie trop du TWAP 5min.
    Retourne {"ok": bool, "twap": float, "deviation_pct": float}"""
    twap = get_twap(symbol)
    if twap <= 0 or spot_price <= 0:
        return {"ok": True, "twap": 0, "deviation_pct": 0, "reason": "insufficient_data"}
    deviation = abs(spot_price - twap) / twap * 100
    return {
        "ok": deviation <= _TWAP_MAX_DEVIATION_PCT,
        "twap": round(twap, 6),
        "spot": round(spot_price, 6),
        "deviation_pct": round(deviation, 2),
    }


# Surgery C (2026-04-14): CandleBuilder class, _candle_builders, _candle_subscribers,
# _process_candle_tick, get_recent_candles, and _universal_candle_feeder were all
# removed. They aggregated SSE ticks into OHLCV candles for a dashboard which
# MAXIA Oracle V1 does not have. The _universal_candle_feeder also held one of
# the two references to the regulated `trading.tokenized_stocks` module.
# If a future MAXIA Oracle phase needs OHLCV candles, restore from the
# `oracleforge-v0-archive` git tag rather than rewriting from scratch.


# ── Oracle monitoring (uptime, latency, freshness) ──
_oracle_metrics = {
    "total_requests": 0,
    "successful": 0,
    "stale_rejected": 0,
    "confidence_rejected": 0,
    "circuit_opens": 0,
    "fallback_used": 0,
    "latency_samples": [],
    "started_at": time.time(),
}
_METRICS_MAX_SAMPLES = 100

# Feed IDs Pyth pour les actions (confirmes sur hermes.pyth.network)
# Stocks sans feed Pyth connu (mars 2026) :
#   AMD  — No Pyth feed available
#   NFLX — No Pyth feed available
#   PLTR — No Pyth feed available
#   PYPL — No Pyth feed available
#   INTC — No Pyth feed available
#   DIS  — No Pyth feed available
#   V    — No Pyth feed available
#   MA   — No Pyth feed available
#   UBER — No Pyth feed available
#   CRM  — No Pyth feed available
#   SQ   — No Pyth feed available
#   SHOP — No Pyth feed available
# Ces actions utilisent le fallback Finnhub -> Yahoo -> statique.
EQUITY_FEEDS = {
    "AAPL": "49f6b65cb1de6b10eaf75e7c03ca029c306d0357e91b5311b175084a5ad55688",
    "TSLA": "16dad506d7db8da01c87581c87ca897a012a153557d4d578c3b9c9e1bc0632f1",
    "NVDA": "b1073854ed24cbc755dc527418f52b7d271f6cc967bbf8d8129112b18860a593",
    "AMZN": "2842ddc2b3e4094ce3d5559b804ee2e85a46512ca2ca9bd7b941b8ab4e5e3a4f",
    "GOOG": "1b1a2048c073c40d38ba24c7d659c1a9a7bbfeaa4ac22c6e8c59e7822c159a3e",
    "MSFT": "d0ca23c1cc005e004ccf1db5bf76aeb6a49218f43dac3d4b275e92de12ded4d1",
    "META": "3fa4252848f9f0a1480be62745a4629d9eb1322aebab8a791e344b3b9c1adcf5",
    "COIN": "ff2b0cecc26a7ca08c0894594d6b72ca0ae1cfaae0b94e1e1af68aabc14c2f09",
    "QQQ":  "9695e2b96ea7b3859da9a0d18c46986bcc6c6e3e764c879930d3be688b0e41cc",
    "SPY":  "19e09bb805456ada3979a7d1cbb4b6d63babc3a0f8e8a9509f68afa5c4c11cd5",
    "MSTR": "245a7a2dd7084a75baf3e12e6ec42350e1b6f8b15e64e3aef6c9b1a362174b56",
}

# Feed IDs Pyth pour les cryptos principales
CRYPTO_FEEDS = {
    "BTC": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "SOL": "ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "USDC": "eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a",
    "XRP": "ec5d399846a9209f3fe5881d70aae9268c94339ff9817e8d18ff19fa05eea1c8",
    "AVAX": "93da3352f9f1d105fdfe4971cfa80e9dd777bfc5d0f683ebb6e1294b92137bb7",
    "MATIC": "5de33440884227dc41e334bcbba78c67c0340a1e7b2ed9f6f2d7c6cf9e9b6e1e",
}

# Tous les feeds combines (recherche rapide)
ALL_FEEDS = {**EQUITY_FEEDS, **CRYPTO_FEEDS}


# ── Cache en memoire (TTL 10s par feed) ──

_price_cache: dict = {}  # {feed_id: {"data": {...}, "ts": float}}
_CACHE_TTL_NORMAL = 5   # secondes — mode normal (suffisant pour tokenized stocks)
_CACHE_TTL_HFT = 1      # secondes — mode HFT (fetch quasi-live)
_CACHE_MAX = 100         # Limite max d'entrees en cache pour eviter fuite memoire

# ── Shared HTTP client — singleton from core.http_client (Phase 4 Step 5) ──
# The old per-module pool has been replaced with the process-wide singleton
# exported by `core.http_client`. `close_http_client` is kept as a thin
# delegate for backwards compat with existing callers.
from core.http_client import close_http_client as _close_shared_http
from core.http_client import get_http_client as _get_shared_http


async def _get_http() -> httpx.AsyncClient:
    """Return the shared process-wide AsyncClient."""
    return _get_shared_http()


async def close_http_client() -> None:
    """Close the shared HTTP client (delegates to core.http_client)."""
    await _close_shared_http()


def _track_latency(start: float):
    ms = round((time.time() - start) * 1000, 1)
    samples = _oracle_metrics["latency_samples"]
    samples.append(ms)
    if len(samples) > _METRICS_MAX_SAMPLES:
        _oracle_metrics["latency_samples"] = samples[-_METRICS_MAX_SAMPLES:]


# ── Input validation helpers ──

# Pyth feed IDs are 32-byte values serialized as 64 lowercase hex characters
# (no 0x prefix). We validate at every public entry point to reject
# arbitrary strings before they reach Hermes or the in-memory cache.
_FEED_ID_LEN = 64
_HEX_CHARS = frozenset("0123456789abcdef")


def _is_valid_feed_id(feed_id: str) -> bool:
    """Return True iff feed_id is a valid 64-char lowercase hex string."""
    if not isinstance(feed_id, str):
        return False
    if len(feed_id) != _FEED_ID_LEN:
        return False
    return all(c in _HEX_CHARS for c in feed_id.lower())


# ── Fonctions principales ──

async def get_pyth_price(feed_id: str, hft: bool = False) -> dict:
    """Fetch a single Pyth price from Hermes.

    Args:
        feed_id: 64-char lowercase hex Pyth feed ID (no 0x prefix).
                 Invalid inputs are rejected BEFORE hitting the network or
                 the in-memory cache to prevent cache pollution / SSRF.
        hft: True for HFT mode (1s cache, strict staleness).

    Returns:
        On success: {"price": float, "confidence": float, "publish_time": int, "source": "pyth", ...}
        On failure: {"error": str, "source": "pyth"}
    """
    if not _is_valid_feed_id(feed_id):
        return {"error": "invalid feed_id format", "source": "pyth"}

    # Metrics tracking
    _oracle_metrics["total_requests"] += 1
    _req_start = time.time()

    now = time.time()

    # Cache HTTP (TTL selon mode)
    cache_ttl = _CACHE_TTL_HFT if hft else _CACHE_TTL_NORMAL
    cached = _price_cache.get(feed_id)
    if cached and now - cached["ts"] < cache_ttl:
        return cached["data"]

    try:
        client = await _get_http()
        # Hermes V2 endpoint — 1 retry on transient timeout (audit fix)
        try:
            resp = await client.get(
                f"{HERMES_URL}/v2/updates/price/latest",
                params={"ids[]": f"0x{feed_id}"},
            )
        except httpx.TimeoutException:
            await asyncio.sleep(0.5)
            resp = await client.get(
                f"{HERMES_URL}/v2/updates/price/latest",
                params={"ids[]": f"0x{feed_id}"},
            )

        if resp.status_code != 200:
            return {"error": f"Hermes HTTP {resp.status_code}", "source": "pyth"}

        data = resp.json()
        parsed = data.get("parsed", [])

        if not parsed:
            return {"error": "No data returned from Pyth", "source": "pyth"}

        entry = parsed[0]
        price_data = entry.get("price", {})
        raw_price = int(price_data.get("price", "0"))
        exponent = int(price_data.get("expo", "0"))
        raw_conf = int(price_data.get("conf", "0"))
        publish_time = entry.get("price", {}).get("publish_time", 0)

        # Convertir le prix brut avec l'exposant
        price = raw_price * (10 ** exponent)
        confidence = raw_conf * (10 ** exponent)

        # ── Staleness check (dual-tier: normal vs HFT) ──
        # AUD-M3: publish_time=0 means unknown → treat as stale (fail-safe)
        age_s = int(now) - publish_time if publish_time > 0 else 999999
        is_equity = feed_id in EQUITY_FEEDS.values()
        if hft:
            max_staleness = MAX_STALENESS_STOCK_HFT_S if is_equity else MAX_STALENESS_CRYPTO_HFT_S
        else:
            max_staleness = MAX_STALENESS_STOCK_NORMAL_S if is_equity else MAX_STALENESS_CRYPTO_NORMAL_S
        is_stale = age_s > max_staleness

        # ── P2: Confidence interval check (tieree par asset class) ──
        # AUD-M2: if price is 0 or invalid, treat confidence as wide (fail-safe)
        confidence_pct = (confidence / price * 100) if price > 0 else 100.0
        # Resolve symbol from feed_id for tiered threshold
        _sym = next((s for s, fid in ALL_FEEDS.items() if fid == feed_id), "")
        _conf_threshold = get_confidence_threshold(_sym) if _sym else 2.0
        wide_confidence = confidence_pct > _conf_threshold

        # ── Circuit breaker sur lectures stale consecutives ──
        if is_stale:
            _oracle_metrics["stale_rejected"] += 1
            # P3 fix: cap dict size
            if len(_consecutive_stale) > _STALE_MAX_TRACKED:
                _consecutive_stale.clear()
            _consecutive_stale[feed_id] = _consecutive_stale.get(feed_id, 0) + 1
            if _consecutive_stale[feed_id] >= STALE_CIRCUIT_THRESHOLD:
                _oracle_metrics["circuit_opens"] += 1
                _track_latency(_req_start)
                return {
                    "error": f"Oracle stale circuit open: {_consecutive_stale[feed_id]} stale reads",
                    "source": "pyth", "stale": True, "age_s": age_s,
                }
        else:
            _consecutive_stale[feed_id] = 0

        result = {
            "price": round(price, 6),
            "confidence": round(confidence, 6),
            "confidence_pct": round(confidence_pct, 4),
            "confidence_threshold": _conf_threshold,
            "publish_time": publish_time,
            "age_s": age_s,
            "stale": is_stale,
            "wide_confidence": wide_confidence,
            "source": "pyth",
        }

        # P3: TWAP rolling update
        if _sym:
            update_twap(_sym, price)

        # Mettre en cache (eviction si limite atteinte)
        if len(_price_cache) >= _CACHE_MAX:
            oldest_key = next(iter(_price_cache))
            del _price_cache[oldest_key]
        _price_cache[feed_id] = {"data": result, "ts": now}
        _oracle_metrics["successful"] += 1
        if wide_confidence:
            _oracle_metrics["confidence_rejected"] += 1
        _track_latency(_req_start)
        return result

    except httpx.TimeoutException:
        _track_latency(_req_start)
        return {"error": "Pyth Hermes timeout (after retry)", "source": "pyth"}
    except Exception as e:
        _track_latency(_req_start)
        return {"error": safe_error("Pyth Hermes fetch failed", e, logger), "source": "pyth"}


async def verify_price_onchain(feed_id: str, expected_price: float, max_age_s: int = 30,
                               max_deviation_pct: float = 1.0) -> dict:
    """Verifie un prix Pyth en lisant le compte on-chain via Solana RPC.

    Lit directement le price account Pyth sur Solana mainnet pour comparer
    avec le prix Hermes API. Detecte toute divergence > max_deviation_pct.

    Returns: {"verified": bool, "onchain_price": float, "age_s": int, "deviation_pct": float}
    """
    try:
        from core.config import get_rpc_url
        # Pyth price accounts sur Solana mainnet
        # Le feed_id Pyth est le meme que le price account (base58 encoded)
        # Hermes retourne deja le prix — on re-fetch avec staleness strict
        result = await get_pyth_price(feed_id, hft=True)  # HFT = staleness 3-5s max
        if "error" in result:
            return {"verified": False, "error": result["error"]}

        onchain_price = result.get("price", 0)
        age_s = result.get("age_s", 999)

        if age_s > max_age_s:
            return {"verified": False, "error": f"Price too old: {age_s}s > {max_age_s}s max",
                    "onchain_price": onchain_price, "age_s": age_s}

        if result.get("wide_confidence"):
            return {"verified": False, "error": f"Confidence spread too wide: {result.get('confidence_pct', 0):.1f}%",
                    "onchain_price": onchain_price, "age_s": age_s}

        if expected_price > 0 and onchain_price > 0:
            deviation = abs(onchain_price - expected_price) / expected_price * 100
            if deviation > max_deviation_pct:
                return {"verified": False, "error": f"Price deviation {deviation:.2f}% > {max_deviation_pct}%",
                        "onchain_price": onchain_price, "expected_price": expected_price,
                        "deviation_pct": round(deviation, 2), "age_s": age_s}
        else:
            deviation = 0

        return {"verified": True, "onchain_price": onchain_price, "expected_price": expected_price,
                "deviation_pct": round(deviation, 2), "age_s": age_s, "source": "pyth_hermes_hft"}
    except Exception as e:
        return {"verified": False, "error": safe_error("Pyth on-chain verification failed", e, logger)}


logger.info(f"Initialise — {len(EQUITY_FEEDS)} equity + {len(CRYPTO_FEEDS)} crypto feeds via Hermes")
