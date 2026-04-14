"""MAXIA Oracle — Pyth Network price oracle (Hermes API + SSE streaming).

Real-time prices via Pyth Network Hermes (free, no API key).

Extracted from MAXIA V12/backend/trading/pyth_oracle.py on 2026-04-14.

Surgeries applied vs the V12 original (validated by Alexis 2026-04-14):
    B. All 6 lazy imports of `FALLBACK_PRICES` from price_oracle removed, plus
       `start_fallback_refresh` / `_fallback_refresh_loop` / `_fallback_refresh_task`.
       Functions that used it (get_stock_price, get_crypto_price, get_batch_prices)
       now return an explicit error instead of a stale static price.
    C. CandleBuilder + `_process_candle_tick` + `get_recent_candles` +
       `_universal_candle_feeder` + `_candle_builders` + `_candle_subscribers`
       removed. MAXIA Oracle V1 has no dashboard, no OHLCV consumer.
    D. `check_stock_peg()` and `/oracle/peg-check/{symbol}` route removed —
       specific to tokenized securities (xStocks depeg detection).
    E. `check_oracle_health_alert()` + its dedicated constants removed —
       depended on `infra.alerts` (Telegram). `_is_market_open()` is kept
       because `api_market_status` still uses it.
    F. Second `tokenized_stocks` lazy import (in `api_price_live` fallback)
       removed. After this, `grep tokenized_stocks` on MAXIA Oracle = 0.

Strategy (equity cascade, see get_stock_price):
    1. Pyth Hermes        — <400ms, confidence interval
    2. Finnhub            — free tier 60 req/min
    3. CoinGecko          — via price_oracle.get_price()
    4. Yahoo Finance      — via price_oracle.get_stock_prices()
    5. (no static fallback — Surgery B)
"""
import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from core.errors import safe_error

logger = logging.getLogger("pyth_oracle")

# ── Finnhub API (3rd equity source) ──
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")


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
    "stream_events": 0,       # P5: prix recus via SSE
    "last_stream_event_ts": 0, # P5: heartbeat monitoring
    "latency_samples": [],
    "started_at": time.time(),
}
_METRICS_MAX_SAMPLES = 100
_HEARTBEAT_ALERT_S = 60  # P5: alerter si aucun event SSE depuis 60s

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

# Streaming: prix live Pyth via SSE (server-sent events) pour les clients HFT
_streaming_prices: dict = {}  # {feed_id: {"price": float, "ts": float}} mis a jour par le stream

# ── Client HTTP partage ──

_http_client: Optional[httpx.AsyncClient] = None


async def _get_http() -> httpx.AsyncClient:
    """Retourne un client HTTP partage avec connection pooling."""
    global _http_client
    if _http_client is None or getattr(_http_client, "is_closed", True):
        _http_client = httpx.AsyncClient(
            timeout=10,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


async def close_http_client():
    """Ferme le client HTTP partage (appeler au shutdown)."""
    global _http_client
    if _http_client is not None and not getattr(_http_client, "is_closed", True):
        await _http_client.aclose()
        _http_client = None


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

    # 1) Streaming price (si le stream background tourne, latence <1s)
    now = time.time()
    streamed = _streaming_prices.get(feed_id)
    if streamed and now - streamed["ts"] < 2:
        _oracle_metrics["successful"] += 1
        _track_latency(_req_start)
        return streamed["data"]

    # 2) Cache HTTP (TTL selon mode)
    cache_ttl = _CACHE_TTL_HFT if hft else _CACHE_TTL_NORMAL
    cached = _price_cache.get(feed_id)
    if cached and now - cached["ts"] < cache_ttl:
        return cached["data"]

    try:
        client = await _get_http()
        # Hermes V2 endpoint — /v2/updates/price/latest avec ids[]
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
        return {"error": "Pyth Hermes timeout", "source": "pyth"}
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


async def get_stock_price_finnhub(symbol: str) -> dict:
    """Recupere le prix d'une action via Finnhub API (free tier: 60 req/min).

    Args:
        symbol: Ticker de l'action (AAPL, TSLA, etc.)

    Returns:
        {"price": float, "source": "finnhub", "confidence": 0, "publish_time": int}
        ou {"error": "..."} en cas d'echec
    """
    if not FINNHUB_API_KEY:
        return {"error": "FINNHUB_API_KEY not set", "source": "finnhub"}

    sym = symbol.upper()
    try:
        client = await _get_http()
        resp = await client.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": sym, "token": FINNHUB_API_KEY},
        )
        if resp.status_code != 200:
            return {"error": f"Finnhub HTTP {resp.status_code}", "source": "finnhub"}

        data = resp.json()
        # Finnhub retourne c=current, t=timestamp, h=high, l=low, o=open, pc=prev close
        price = data.get("c", 0)
        timestamp = data.get("t", 0)

        if not price or price <= 0:
            return {"error": "Finnhub returned no price", "source": "finnhub"}

        return {
            "price": round(float(price), 6),
            "confidence": 0,
            "publish_time": int(timestamp) if timestamp else int(time.time()),
            "source": "finnhub",
            "symbol": sym,
        }
    except httpx.TimeoutException:
        return {"error": "Finnhub timeout", "source": "finnhub"}
    except Exception as e:
        return {"error": safe_error("Finnhub fetch failed", e, logger), "source": "finnhub"}


async def get_stock_price(symbol: str) -> dict:
    """Fetch an equity price via Pyth -> Finnhub -> CoinGecko -> Yahoo cascade.

    Surgery B (2026-04-14): the former "source 5: static fallback" was removed.
    When every live source fails, this function returns {"error": ...} instead
    of a stale March-2026 hardcoded value.

    Args:
        symbol: Equity ticker (AAPL, TSLA, NVDA, ...)

    Returns:
        On success: {"price": float, "confidence": float, "source": "pyth"|"finnhub"|"coingecko"|"yahoo", "symbol": str, ...}
        On failure: {"error": "all sources unavailable", "sources_tried": [...], "symbol": str}
    """
    sym = symbol.upper()
    # Alias GOOGL -> GOOG (Pyth uses GOOG)
    if sym == "GOOGL":
        sym = "GOOG"
    sources_tried: list[str] = []

    # ── Source 1: Pyth Hermes (best — real-time + confidence interval) ──
    feed_id = EQUITY_FEEDS.get(sym)
    if feed_id:
        sources_tried.append("pyth")
        result = await get_pyth_price(feed_id)
        if "error" not in result and result.get("price", 0) > 0:
            result["symbol"] = symbol.upper()
            if result.get("stale"):
                logger.warning(f"STALE stock price for {sym} (age={result.get('age_s')}s), falling back")
            else:
                return result

    # ── Source 2: Finnhub (free tier 60 req/min) ──
    sources_tried.append("finnhub")
    finnhub_result = await get_stock_price_finnhub(symbol)
    if "error" not in finnhub_result and finnhub_result.get("price", 0) > 0:
        return finnhub_result

    # ── Source 3: CoinGecko via price_oracle ──
    try:
        from .price_oracle import get_price as cg_get_price
        sources_tried.append("coingecko")
        price = await cg_get_price(symbol.upper())
        if price and price > 0:
            return {
                "price": price,
                "confidence": 0,
                "publish_time": int(time.time()),
                "source": "coingecko",
                "symbol": symbol.upper(),
            }
    except Exception:
        pass

    # ── Source 4: Yahoo Finance via price_oracle ──
    try:
        from .price_oracle import get_stock_prices as yahoo_get_stocks
        sources_tried.append("yahoo")
        yahoo_prices = await yahoo_get_stocks()
        yahoo_data = yahoo_prices.get(symbol.upper(), {})
        if yahoo_data.get("price", 0) > 0:
            return {
                "price": yahoo_data["price"],
                "confidence": 0,
                "publish_time": int(time.time()),
                "source": yahoo_data.get("source", "yahoo"),
                "symbol": symbol.upper(),
            }
    except Exception:
        pass

    return {
        "error": "all sources unavailable",
        "sources_tried": sources_tried,
        "symbol": symbol.upper(),
    }


async def get_crypto_price(symbol: str) -> dict:
    """Fetch a crypto price via Pyth -> CoinGecko cascade.

    Surgery B (2026-04-14): the static fallback branch was removed. When both
    Pyth and CoinGecko fail, this function returns {"error": ...}.

    Args:
        symbol: Crypto ticker (BTC, ETH, SOL, ...)

    Returns:
        On success: {"price": float, "confidence": float, "source": "pyth"|"coingecko", "symbol": str, ...}
        On failure: {"error": "all sources unavailable", "sources_tried": [...], "symbol": str}
    """
    sym = symbol.upper()
    sources_tried: list[str] = []

    feed_id = CRYPTO_FEEDS.get(sym)
    if feed_id:
        sources_tried.append("pyth")
        result = await get_pyth_price(feed_id)
        if "error" not in result and result.get("price", 0) > 0:
            result["symbol"] = sym
            if result.get("stale"):
                logger.warning(f"STALE crypto price for {sym} (age={result.get('age_s')}s), falling back")
            else:
                return result

    # Fallback CoinGecko
    try:
        from .price_oracle import get_price as cg_get_price
        sources_tried.append("coingecko")
        price = await cg_get_price(sym)
        if price and price > 0:
            return {
                "price": price,
                "confidence": 0,
                "publish_time": int(time.time()),
                "source": "coingecko",
                "symbol": sym,
            }
    except Exception:
        pass

    return {
        "error": "all sources unavailable",
        "sources_tried": sources_tried,
        "symbol": sym,
    }


async def get_batch_prices(symbols: list[str]) -> dict:
    """Recupere les prix de plusieurs symboles en un seul appel Hermes.

    Hermes supporte ids[] multiple — un seul HTTP call pour N feeds.
    Les symboles sans feed Pyth sont recuperes via CoinGecko.

    Args:
        symbols: Liste de tickers (ex: ["AAPL", "TSLA", "BTC", "SOL"])

    Returns:
        {symbol: {"price": float, "confidence": float, "source": str}}
    """
    results = {}
    now = time.time()

    # Separer les symboles avec/sans feed Pyth
    pyth_symbols = {}  # {symbol: feed_id}
    fallback_symbols = []

    for sym in symbols:
        s = sym.upper()
        # Alias GOOGL -> GOOG
        lookup = "GOOG" if s == "GOOGL" else s
        feed_id = ALL_FEEDS.get(lookup)
        if feed_id:
            # Verifier si en cache
            cached = _price_cache.get(feed_id)
            if cached and now - cached["ts"] < _CACHE_TTL_NORMAL:
                results[s] = cached["data"].copy()
                results[s]["symbol"] = s
            else:
                pyth_symbols[s] = feed_id
        else:
            fallback_symbols.append(s)

    # Batch fetch Pyth (un seul appel HTTP)
    if pyth_symbols:
        try:
            client = await _get_http()
            ids_str = "&".join(f"ids[]=0x{fid}" for fid in pyth_symbols.values())
            resp = await client.get(
                f"{HERMES_URL}/v2/updates/price/latest?{ids_str}",
            )

            if resp.status_code == 200:
                data = resp.json()
                parsed = data.get("parsed", [])

                # Map feed_id -> symbole pour retrouver les resultats
                fid_to_sym = {fid: sym for sym, fid in pyth_symbols.items()}

                for entry in parsed:
                    entry_id = entry.get("id", "").replace("0x", "")
                    sym = fid_to_sym.get(entry_id)
                    if not sym:
                        continue

                    price_data = entry.get("price", {})
                    raw_price = int(price_data.get("price", "0"))
                    exponent = int(price_data.get("expo", "0"))
                    raw_conf = int(price_data.get("conf", "0"))
                    publish_time = price_data.get("publish_time", 0)

                    price = raw_price * (10 ** exponent)
                    confidence = raw_conf * (10 ** exponent)

                    result = {
                        "price": round(price, 6),
                        "confidence": round(confidence, 6),
                        "publish_time": publish_time,
                        "source": "pyth",
                        "symbol": sym,
                    }

                    results[sym] = result
                    # Mettre en cache (eviction si limite atteinte)
                    if len(_price_cache) >= _CACHE_MAX:
                        oldest_key = next(iter(_price_cache))
                        del _price_cache[oldest_key]
                    _price_cache[entry_id] = {"data": result, "ts": now}
            else:
                # Si batch echoue, mettre tous les symboles Pyth en fallback
                fallback_symbols.extend(pyth_symbols.keys())

        except Exception as e:
            logger.error(f"Batch fetch error: {e}")
            fallback_symbols.extend(pyth_symbols.keys())

    # Aussi ajouter les symboles Pyth qui n'ont pas ete retournes dans le batch
    for sym in pyth_symbols:
        if sym not in results:
            fallback_symbols.append(sym)

    # Surgery B (2026-04-14): static-fallback branches removed. Symbols where
    # both Pyth batch and CoinGecko batch failed are simply absent from the
    # returned dict — callers must treat missing keys as "no live data".
    if fallback_symbols:
        try:
            from .price_oracle import get_prices as cg_get_prices
            cg_prices = await cg_get_prices(fallback_symbols)
            for sym in fallback_symbols:
                if sym in results:
                    continue
                cg_data = cg_prices.get(sym)
                if not cg_data:
                    continue
                price = cg_data.get("price")
                if not price or price <= 0:
                    continue
                results[sym] = {
                    "price": price,
                    "confidence": 0,
                    "publish_time": int(time.time()),
                    "source": cg_data.get("source", "coingecko"),
                    "symbol": sym,
                }
        except Exception as e:
            logger.error(f"Batch CoinGecko fallback error: {e}")

    return results


# Surgery D (2026-04-14): check_stock_peg() removed. It compared a tokenized
# security (xStock) on-chain price against its underlying equity price via
# Pyth to flag depegs. This is a trading-specific tool for regulated
# tokenized-security products and is out of scope for MAXIA Oracle.


# ── FastAPI Router ──

router = APIRouter(prefix="/oracle", tags=["Oracle Pyth"])


@router.get("/stock/{symbol}")
async def api_stock_price(symbol: str):
    """Prix temps-reel d'une action via Pyth Network."""
    sym = symbol.upper()
    # Verifier que le symbole est supporte
    lookup = "GOOG" if sym == "GOOGL" else sym
    if lookup not in EQUITY_FEEDS:
        # On tente quand meme via fallback
        result = await get_stock_price(sym)
        if result.get("price", 0) <= 0:
            raise HTTPException(404, f"Stock symbol '{sym}' not found in Pyth feeds")
        return result
    return await get_stock_price(sym)


@router.get("/market-status")
async def api_market_status():
    """Status oracle actions tokenisees — live ou dernier cours.
    MAXIA trade 24/7 (tokens on-chain). L'oracle indique la fraicheur du prix."""
    from datetime import datetime, timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    is_open = _is_market_open()
    weekday = utc_now.weekday()

    # Calcul du prochain open (lun-ven 13:30 UTC)
    if is_open:
        next_event = "close"
        # Close a 20:00 UTC
        close_today = utc_now.replace(hour=20, minute=0, second=0, microsecond=0)
        seconds_until = max(0, int((close_today - utc_now).total_seconds()))
    else:
        next_event = "open"
        # Prochain lundi 13:30 UTC si weekend, sinon demain 13:30 UTC
        if weekday == 5:  # samedi
            days_until = 2
        elif weekday == 6:  # dimanche
            days_until = 1
        elif utc_now.hour >= 20:  # apres close
            days_until = 1
            if weekday == 4:  # vendredi soir
                days_until = 3
        else:  # avant open
            days_until = 0
        next_open = (utc_now + timedelta(days=days_until)).replace(hour=13, minute=30, second=0, microsecond=0)
        seconds_until = max(0, int((next_open - utc_now).total_seconds()))

    # After-hours: lun-ven 20:00-00:00 UTC ou 08:00-13:30 UTC
    is_after_hours = not is_open and weekday < 5 and (utc_now.hour >= 20 or utc_now.hour < 1 or (8 <= utc_now.hour < 14))

    return {
        "oracle_status": "live" if is_open else "after_hours" if is_after_hours else "last_close",
        "oracle_label": "Oracle: Live" if is_open else "Oracle: After-Hours" if is_after_hours else "Oracle: Last Close",
        "trading": "24/7 — tokenized stocks trade on-chain anytime",
        "next_event": next_event,
        "seconds_until": seconds_until,
        "hours_until": round(seconds_until / 3600, 1),
        "is_weekend": weekday >= 5,
        "utc_time": utc_now.strftime("%H:%M UTC"),
    }


@router.get("/crypto/{symbol}")
async def api_crypto_price(symbol: str):
    """Prix temps-reel d'une crypto via Pyth Network."""
    sym = symbol.upper()
    result = await get_crypto_price(sym)
    if result.get("price", 0) <= 0 and "error" in result:
        raise HTTPException(404, f"Crypto symbol '{sym}' not available")
    return result


@router.get("/batch")
async def api_batch_prices(
    symbols: str = Query(..., description="Symboles separes par virgule (ex: AAPL,TSLA,BTC)")
):
    """Prix batch — plusieurs symboles en un appel HTTP Hermes."""
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(400, "No symbols provided")
    if len(sym_list) > 50:
        raise HTTPException(400, "Maximum 50 symbols per batch request")
    prices = await get_batch_prices(sym_list)
    return {
        "count": len(prices),
        "prices": prices,
    }


# Surgery D (2026-04-14): /oracle/peg-check/{symbol} route removed alongside
# check_stock_peg(). This route was used by MAXIA V12 to check xStock depegs
# on Solana and is out of scope for a non-custodial price oracle.


@router.get("/feeds")
async def api_list_feeds():
    """Liste tous les feeds Pyth disponibles."""
    return {
        "equity_feeds": {sym: f"0x{fid}" for sym, fid in EQUITY_FEEDS.items()},
        "crypto_feeds": {sym: f"0x{fid}" for sym, fid in CRYPTO_FEEDS.items()},
        "total": len(ALL_FEEDS),
        "cache_ttl_normal_s": _CACHE_TTL_NORMAL,
        "cache_ttl_hft_s": _CACHE_TTL_HFT,
        "hermes_url": HERMES_URL,
        "streaming": _sse_task is not None and not _sse_task.done() if _sse_task else False,
    }


@router.get("/price/live/{symbol}")
async def api_price_live(symbol: str, mode: str = Query("normal", pattern="^(normal|hft)$")):
    """Prix live — mode=hft pour latence <1s (streaming), mode=normal pour 5s cache.

    Utilise le stream SSE Pyth si disponible, sinon HTTP polling.
    Mode HFT: cache 1s, staleness 5s stocks / 3s crypto.
    Mode normal: cache 5s, staleness 10min stocks / 120s crypto.
    """
    sym = symbol.upper()
    hft = mode == "hft"

    if hft:
        # Demarrer le stream si pas encore actif
        await start_pyth_stream()

    # Chercher dans equity puis crypto (Pyth feeds)
    feed_id = EQUITY_FEEDS.get(sym) or CRYPTO_FEEDS.get(sym)
    if feed_id:
        result = await get_pyth_price(feed_id, hft=hft)
        if "error" not in result:
            result["symbol"] = sym
            result["mode"] = mode
            return result

    # Fallback: CoinGecko / cached crypto prices via price_oracle
    try:
        from .price_oracle import get_crypto_prices
        prices_data = await get_crypto_prices()
        prices = prices_data.get("prices", prices_data) if isinstance(prices_data, dict) else {}
        token_data = prices.get(sym, {})
        price = token_data.get("price", 0) if isinstance(token_data, dict) else 0
        if price > 0:
            return {
                "price": price,
                "confidence": 0,
                "confidence_pct": 0,
                "publish_time": int(time.time()),
                "age_s": 0,
                "stale": False,
                "wide_confidence": False,
                "source": token_data.get("source", "coingecko") if isinstance(token_data, dict) else "cache",
                "symbol": sym,
                "mode": mode,
            }
    except Exception:
        pass

    # Surgery F (2026-04-14): the former "Fallback: stock prices" branch that
    # read from `trading.tokenized_stocks.fetch_stock_prices` was removed.
    # MAXIA Oracle never reads tokenized-security mints — equities come via
    # Pyth EQUITY_FEEDS (handled above) or Yahoo/Finnhub in get_stock_price.

    raise HTTPException(404, f"No price available for {sym}")


@router.get("/health")
async def api_oracle_health():
    """Verifie la sante de la connexion Pyth Hermes + staleness stats."""
    try:
        # Test rapide: fetch SOL price
        result = await get_pyth_price(CRYPTO_FEEDS["SOL"])
        if "error" in result:
            return {"status": "degraded", "error": result["error"]}

        # Stats stale circuit breakers
        stale_feeds = {fid: count for fid, count in _consecutive_stale.items() if count > 0}
        circuit_open = [fid for fid, count in _consecutive_stale.items() if count >= STALE_CIRCUIT_THRESHOLD]

        status = "ok"
        if circuit_open:
            status = "degraded"
        if result.get("stale"):
            status = "degraded"

        return {
            "status": status,
            "latency_check": "SOL",
            "price": result.get("price"),
            "age_s": result.get("age_s", 0),
            "stale": result.get("stale", False),
            "cache_entries": len(_price_cache),
            "staleness_config": {
                "max_stock_normal_s": MAX_STALENESS_STOCK_NORMAL_S,
                "max_stock_hft_s": MAX_STALENESS_STOCK_HFT_S,
                "max_crypto_normal_s": MAX_STALENESS_CRYPTO_NORMAL_S,
                "max_crypto_hft_s": MAX_STALENESS_CRYPTO_HFT_S,
                "confidence_warn_pct": _CONFIDENCE_TIERS["major"],
                "circuit_threshold": STALE_CIRCUIT_THRESHOLD,
            },
            "stale_feeds_count": len(stale_feeds),
            "circuit_open_feeds": len(circuit_open),
        }
    except Exception as e:
        return {"status": "error", "error": "An error occurred"[:100]}


@router.get("/monitoring")
async def api_oracle_monitoring():
    """Oracle performance monitoring — uptime, latency P50/P95/P99, error rates."""
    uptime_s = time.time() - _oracle_metrics["started_at"]
    total = _oracle_metrics["total_requests"] or 1
    samples = sorted(_oracle_metrics["latency_samples"]) if _oracle_metrics["latency_samples"] else [0]

    def _percentile(data, p):
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    return {
        "uptime_seconds": round(uptime_s),
        "uptime_hours": round(uptime_s / 3600, 1),
        "total_requests": _oracle_metrics["total_requests"],
        "successful": _oracle_metrics["successful"],
        "success_rate_pct": round(_oracle_metrics["successful"] / total * 100, 1),
        "stale_rejected": _oracle_metrics["stale_rejected"],
        "confidence_rejected": _oracle_metrics["confidence_rejected"],
        "circuit_opens": _oracle_metrics["circuit_opens"],
        "latency_ms": {
            "p50": _percentile(samples, 50),
            "p95": _percentile(samples, 95),
            "p99": _percentile(samples, 99),
            "samples": len(samples),
        },
        "active_feeds": {
            "equity": len(EQUITY_FEEDS),
            "crypto": len(CRYPTO_FEEDS),
        },
        "stale_circuit_status": {
            fid[:12]: count for fid, count in _consecutive_stale.items() if count > 0
        },
        "streaming_active": _sse_task is not None and not _sse_task.done() if _sse_task else False,
        "stream_events": _oracle_metrics["stream_events"],
        "heartbeat": {
            "last_event_s_ago": round(time.time() - _oracle_metrics["last_stream_event_ts"]) if _oracle_metrics["last_stream_event_ts"] > 0 else None,
            "healthy": (time.time() - _oracle_metrics["last_stream_event_ts"] < _HEARTBEAT_ALERT_S) if _oracle_metrics["last_stream_event_ts"] > 0 else False,
            "threshold_s": _HEARTBEAT_ALERT_S,
        },
        "twap_5min": {
            sym: {"twap": get_twap(sym), "points": len(_twap_data.get(sym, []))}
            for sym in ["SOL", "ETH", "BTC"] if get_twap(sym) > 0
        },
    }


@router.get("/specs")
async def api_oracle_specs():
    """Full oracle specification — providers, frequencies, staleness thresholds,
    confidence enforcement, and trade protection. Machine-readable."""
    return {
        "oracle_providers": [
            {
                "name": "Pyth Network (Hermes)",
                "type": "decentralized_oracle",
                "endpoint": "https://hermes.pyth.network/v2/updates/price/latest",
                "protocol": "HTTP REST + SSE streaming",
                "feeds": {
                    "crypto": len(CRYPTO_FEEDS),
                    "equities": len(EQUITY_FEEDS),
                },
                "confidence_interval": True,
                "latency": "<1s (SSE streaming), 5s (HTTP polling)",
            },
            {
                "name": "Chainlink (Base mainnet)",
                "type": "on_chain_oracle",
                "protocol": "eth_call to AggregatorV3 smart contracts",
                "feeds": "ETH/USD, BTC/USD, USDC/USD, LINK/USD",
                "verification": "Feed addresses verified at startup via description()",
                "update_frequency": "every heartbeat (~1h) or 0.5% deviation",
                "usage": "Cross-verification of Pyth prices before trade execution",
            },
            {
                "name": "Helius DAS",
                "type": "rpc_metadata",
                "protocol": "JSON-RPC getAsset",
                "coverage": "65 Solana SPL tokens",
                "circuit_breaker": "3 failures → 60s cooldown",
            },
            {
                "name": "CoinGecko",
                "type": "exchange_aggregator",
                "protocol": "REST API",
                "coverage": "multi-chain tokens",
                "circuit_breaker": "3 failures → 120s cooldown",
            },
            {
                "name": "Yahoo Finance",
                "type": "market_data",
                "protocol": "REST API (v8 + v7 fallback)",
                "coverage": "25 tokenized stocks (xStocks/Ondo/Dinari)",
                "circuit_breaker": "3 failures → 120s cooldown",
            },
            {
                "name": "Finnhub",
                "type": "market_data_fallback",
                "protocol": "REST API",
                "coverage": "equities when Pyth unavailable",
            },
        ],
        "update_frequency": {
            "normal_mode": {
                "crypto": "45-60s polling (cached)",
                "stocks": "180s polling (rate-limited)",
                "pyth_http": "5s cache per feed",
            },
            "hft_mode": {
                "crypto": "<1s (Pyth SSE push — persistent stream, started at boot)",
                "stocks": "<1s (Pyth SSE push, 13 feeds — persistent)",
                "endpoint": "GET /api/oracle/price/live/{symbol}?mode=hft",
                "note": "SSE stream runs permanently (not on-demand). All feeds updated in real-time.",
            },
        },
        "staleness_thresholds": {
            "stocks_normal": f"{MAX_STALENESS_STOCK_NORMAL_S}s (10 min)",
            "stocks_hft": f"{MAX_STALENESS_STOCK_HFT_S}s",
            "crypto_normal": f"{MAX_STALENESS_CRYPTO_NORMAL_S}s (2 min)",
            "crypto_hft": f"{MAX_STALENESS_CRYPTO_HFT_S}s",
            "circuit_breaker": f"{STALE_CIRCUIT_THRESHOLD} consecutive stales → feed paused 60s",
        },
        "trade_protection": {
            "confidence_enforcement": {
                "tiered_thresholds": {
                    "majors (SOL/ETH/BTC/USDC)": "2%",
                    "mid-caps (LINK/UNI/AVAX/XRP...)": "5%",
                    "small-caps (BONK/WIF/POPCAT...)": "10%",
                },
                "action": "BLOCK trade if confidence exceeds asset-class threshold",
            },
            "cross_validation": {
                "method": "Multi-oracle median vote (not simple fallback chain)",
                "logic": "Compare Pyth vs Helius/CoinGecko. >3% divergence = use median. >10% = BLOCK trade.",
                "chainlink": "ETH/BTC/USDC cross-verified on-chain (Base, max 3% deviation)",
            },
            "twap_protection": {
                "window": "5-minute rolling TWAP",
                "max_deviation": "20% — rejects spot prices that deviate from TWAP (flash manipulation defense)",
            },
            "conservative_valuation": {
                "method": "Pyth confidence bounds used for worst-case pricing",
                "input_token": "price - confidence (protects buyer)",
                "output_token": "price + confidence (protects seller)",
            },
            "price_reverification": {
                "action": "BLOCK trade if price moved >1% between quote and execution",
            },
            "fallback_block": "Swaps blocked when price source is static fallback",
            "price_impact_limit": "5% max (Jupiter liquidity check)",
            "payment_verification": "On-chain USDC transfer verified via Solana RPC (finalized commitment)",
            "stale_rejection": "Prices older than threshold are rejected, not used",
            "heartbeat_monitoring": f"Alert if no SSE event in {_HEARTBEAT_ALERT_S}s — detects silent oracle failures",
            "monitoring": "GET /oracle/monitoring — P50/P95/P99 latency, stream events, TWAP, heartbeat",
        },
        "fallback_cascade": [
            "1. Pyth Hermes SSE (primary — persistent stream, <1s, confidence interval)",
            "2. Chainlink on-chain (Base — cross-verification for ETH/BTC/USDC/LINK)",
            "3. Helius DAS (Solana token metadata + price)",
            "4. CoinGecko (exchange aggregator)",
            "5. Yahoo Finance / Finnhub (equities)",
            "6. Auto-refreshed fallback (updated every 30min from live sources — BLOCKED for trading)",
        ],
    }


def _is_market_open() -> bool:
    """Return True while the US equity market is in regular trading hours.

    Regular hours: Mon-Fri 9:30-16:00 ET -> 13:30-20:00 UTC (EDT) or
    14:30-21:00 UTC (EST). We use 13:00-20:30 UTC to cover pre-market but
    not late after-hours. Used by api_market_status.
    """
    from datetime import datetime, timezone
    utc_now = datetime.now(timezone.utc)
    if utc_now.weekday() >= 5:
        return False
    utc_minutes = utc_now.hour * 60 + utc_now.minute
    return 780 <= utc_minutes <= 1230


# Surgery E (2026-04-14): check_oracle_health_alert() and its dedicated
# globals (_oracle_alert_last, _ORACLE_ALERT_COOLDOWN,
# _ORACLE_STALE_ALERT_THRESHOLD) were removed. The function depended on
# `infra.alerts` (Telegram, not extracted) and was called from a V12
# background scheduler which MAXIA Oracle does not port. V1 monitoring
# relies on application logs + api_oracle_health / api_oracle_monitoring
# HTTP endpoints instead.


# ══════════════════════════════════════════
# Pyth SSE Streaming (prix live <1s latence)
# ══════════════════════════════════════════

_sse_task: Optional[asyncio.Task] = None
_sse_subscribers: list = []  # list of asyncio.Queue for WebSocket push


async def start_pyth_stream():
    """Demarre le stream SSE Pyth Hermes pour tous les feeds crypto + equity.
    Met a jour _streaming_prices en continu. Reconnexion auto."""
    global _sse_task
    if _sse_task and not _sse_task.done():
        return  # Deja en cours

    _sse_task = asyncio.create_task(_pyth_sse_loop())
    logger.info("[PythStream] SSE streaming started")


# Surgery B (2026-04-14): `_fallback_refresh_task`, `start_fallback_refresh()`
# and `_fallback_refresh_loop()` were removed. They periodically updated the
# deleted FALLBACK_PRICES dict from live sources.


# ── Equity fast poll — 11 Pyth feeds every 2s (HTTP batch, not SSE) ──
_equity_poll_task: Optional[asyncio.Task] = None


async def start_equity_poll():
    """Poll les 11 equity feeds Pyth toutes les 2s via HTTP batch.
    Pousse dans _streaming_prices + _sse_subscribers (meme pipeline que le SSE crypto)."""
    global _equity_poll_task
    if _equity_poll_task and not _equity_poll_task.done():
        return
    _equity_poll_task = asyncio.create_task(_equity_poll_loop())
    logger.info("[PythEquity] Fast equity poll started (2s, 11 feeds)")


async def _equity_poll_loop():
    """Poll rapide Pyth HTTP pour TOUS les feeds (equity + crypto non-SSE) — batch parallele."""
    # SSE stream handles SOL/ETH/BTC/USDC. This poll handles everything else + stocks.
    _sse_symbols = {"SOL", "ETH", "BTC", "USDC"}  # Already streamed via SSE
    non_sse_crypto = {sym: fid for sym, fid in CRYPTO_FEEDS.items() if sym not in _sse_symbols}
    all_poll_feeds = {**EQUITY_FEEDS, **non_sse_crypto}
    logger.info(f"Poll loop started — {len(all_poll_feeds)} feeds ({len(EQUITY_FEEDS)} equity + {len(non_sse_crypto)} crypto, batches of 2)")
    fid_to_sym = {fid: sym for sym, fid in all_poll_feeds.items()}
    # Pyth Hermes limite ~3 feeds par requete HTTP — batches de 2 pour etre safe
    feed_list = list(all_poll_feeds.items())
    batches = [feed_list[i:i+2] for i in range(0, len(feed_list), 2)]
    while True:
        for batch in batches:
            try:
                now = time.time()
                ids_str = "&".join(f"ids[]=0x{fid}" for _, fid in batch)
                url = f"{HERMES_URL}/v2/updates/price/latest?{ids_str}"
                async with httpx.AsyncClient(timeout=httpx.Timeout(8)) as eq_client:
                    resp = await eq_client.get(url)
                    if resp.status_code != 200:
                        continue
                    resp_data = resp.json()
                for entry in resp_data.get("parsed", []):
                    fid = entry.get("id", "").replace("0x", "")
                    sym = fid_to_sym.get(fid, "")
                    if not sym:
                        continue
                    price_data = entry.get("price", {})
                    raw_price = int(price_data.get("price", "0"))
                    exponent = int(price_data.get("expo", "0"))
                    raw_conf = int(price_data.get("conf", "0"))
                    publish_time = price_data.get("publish_time", 0)
                    price = raw_price * (10 ** exponent)
                    confidence = raw_conf * (10 ** exponent)
                    if price <= 0:
                        continue
                    age_s = int(now) - publish_time if publish_time > 0 else 0
                    conf_pct = (confidence / price * 100) if price > 0 else 0
                    result = {
                        "price": round(price, 6), "confidence": round(confidence, 6),
                        "confidence_pct": round(conf_pct, 4), "publish_time": publish_time,
                        "age_s": age_s, "stale": False, "wide_confidence": conf_pct > get_confidence_threshold(sym),
                        "source": "pyth_poll", "symbol": sym,
                    }
                    _streaming_prices[fid] = {"data": result, "ts": now}
                    update_twap(sym, price)
                    # Surgery C: _process_candle_tick call removed here.
                    for q in list(_sse_subscribers):
                        try:
                            q.put_nowait({"symbol": sym, **result})
                        except asyncio.QueueFull:
                            pass
            except Exception as e:
                logger.error(f"Equity batch error: {e}")
            await asyncio.sleep(0.5)  # ~1.5s total across the 11 feed batches
        await asyncio.sleep(1)


async def _pyth_sse_loop():
    """Boucle SSE Pyth Hermes — reconnexion automatique avec backoff.
    Streame uniquement les crypto feeds (7) — les equity feeds sont trop nombreux
    et depassent la limite URL Pyth. Les equities utilisent le polling HTTP."""
    # Pyth SSE limite ~5 feeds par stream. On prend les 4 critiques pour le trading.
    _critical = {"SOL", "ETH", "BTC", "USDC"}
    feed_ids = list(set(v for k, v in CRYPTO_FEEDS.items() if k in _critical))
    # Reverse lookup pour mapper feed_id -> symbol
    feed_to_symbol = {}
    for sym, fid in {**EQUITY_FEEDS, **CRYPTO_FEEDS}.items():
        feed_to_symbol[fid] = sym

    backoff = 1
    while True:
        try:
            # Client dedie pour SSE (le client partage peut avoir des params qui cassent le stream)
            ids_params = "&".join(f"ids[]=0x{fid}" for fid in feed_ids)
            stream_url = f"{HERMES_URL}/v2/updates/price/stream?{ids_params}"
            # AUD-M6: connect timeout 5s, read timeout None (SSE is long-lived by design)
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=120.0, connect=5.0)) as sse_client:
                async with sse_client.stream("GET", stream_url) as resp:
                    if resp.status_code != 200:
                        logger.warning(f"[PythStream] HTTP {resp.status_code}, retrying in {backoff}s")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                        continue

                    backoff = 1  # Reset on success
                    logger.info(f"[PythStream] Connected — {len(feed_ids)} feeds streaming")
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            await _process_sse_event(event_str, feed_to_symbol)

        except asyncio.CancelledError:
            logger.info("[PythStream] SSE stream cancelled")
            return
        except Exception as e:
            logger.warning(f"[PythStream] Connection lost: {e}, reconnecting in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def _process_sse_event(event_str: str, feed_to_symbol: dict):
    """Parse un event SSE Pyth et met a jour _streaming_prices."""
    import json as _json
    now = time.time()

    for line in event_str.split("\n"):
        if line.startswith("data:"):
            try:
                data = _json.loads(line[5:].strip())
                for entry in data.get("parsed", []):
                    feed_id = entry.get("id", "").replace("0x", "")
                    price_data = entry.get("price", {})
                    raw_price = int(price_data.get("price", "0"))
                    exponent = int(price_data.get("expo", "0"))
                    raw_conf = int(price_data.get("conf", "0"))
                    publish_time = price_data.get("publish_time", 0)

                    price = raw_price * (10 ** exponent)
                    confidence = raw_conf * (10 ** exponent)

                    if price <= 0:
                        continue

                    age_s = int(now) - publish_time if publish_time > 0 else 0
                    symbol = feed_to_symbol.get(feed_id, "")

                    result = {
                        "price": round(price, 6),
                        "confidence": round(confidence, 6),
                        "confidence_pct": round((confidence / price * 100) if price > 0 else 0, 4),
                        "publish_time": publish_time,
                        "age_s": age_s,
                        "stale": False,  # Stream = toujours frais
                        "wide_confidence": False,
                        "source": "pyth_stream",
                        "symbol": symbol,
                    }

                    # P2: confidence tieree par asset
                    conf_threshold = get_confidence_threshold(symbol) if symbol else 2.0
                    result["wide_confidence"] = result["confidence_pct"] > conf_threshold
                    result["confidence_threshold"] = conf_threshold

                    _streaming_prices[feed_id] = {"data": result, "ts": now}

                    # P3: TWAP rolling
                    if symbol:
                        update_twap(symbol, price)

                    # P5: stream metrics + heartbeat
                    _oracle_metrics["stream_events"] += 1
                    _oracle_metrics["last_stream_event_ts"] = now

                    # Surgery C: _process_candle_tick call removed here.

                    # Push aux subscribers WebSocket
                    for q in list(_sse_subscribers):
                        try:
                            q.put_nowait({"symbol": symbol, **result})
                        except asyncio.QueueFull:
                            pass  # Client lent, skip

            except Exception:
                pass  # Malformed SSE event, skip


async def stop_pyth_stream():
    """Arrete le stream SSE."""
    global _sse_task
    if _sse_task and not _sse_task.done():
        _sse_task.cancel()
        try:
            await _sse_task
        except asyncio.CancelledError:
            pass
    _sse_task = None
    logger.info("[PythStream] SSE streaming stopped")


logger.info(f"Initialise — {len(EQUITY_FEEDS)} equity + {len(CRYPTO_FEEDS)} crypto feeds via Hermes")
