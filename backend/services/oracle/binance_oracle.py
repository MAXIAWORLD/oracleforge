"""MAXIA Oracle — Binance public spot price reader (V2.4).

Binance publishes spot mid-prices for thousands of pairs through an
unauthenticated REST endpoint. We use it as an independent upstream
because Binance is the largest spot venue by volume — its quote is a
direct market signal, not an aggregator average.

Endpoint
    GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT

No API key required for public ticker reads. Rate limits are
weight-based; a single ticker request costs 1 weight, the public
budget is 1200 weight per minute per IP. We cache 10s per symbol so a
30s page refresh hits Binance at most ~6 times per minute for the full
23-token grid.

Failures never raise — the helper returns ``{"error": ..., "source":
"binance"}`` so ``multi_source.collect_sources()`` drops the entry
silently.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("binance_oracle")

BINANCE_URL: Final[str] = "https://api.binance.com/api/v3/ticker/price"
BINANCE_TIMEOUT_S: Final[float] = 6.0

_CACHE_TTL_S: Final[int] = 10
_cache: dict[str, dict[str, Any]] = {}

# Most cryptos pair against USDT on Binance. A few exceptions:
#   - DAI/USDC pair against USDT but the result is essentially 1.0
#   - WSTETH not listed on Binance (skip)
# Map oracle symbol -> Binance pair. Symbols missing from this map are
# skipped — no implicit guess to avoid hitting BTCUSDT-style typos.
_SYMBOL_TO_PAIR: Final[dict[str, str]] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "USDC": "USDCUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "AVAX": "AVAXUSDT",
    "DOT": "DOTUSDT",
    "POL": "POLUSDT",
    "LTC": "LTCUSDT",
    "TRX": "TRXUSDT",
    "NEAR": "NEARUSDT",
    "SUI": "SUIUSDT",
    "APT": "APTUSDT",
    "INJ": "INJUSDT",
    "SEI": "SEIUSDT",
    "RENDER": "RENDERUSDT",
    "FET": "FETUSDT",
    "TAO": "TAOUSDT",
    "DAI": "DAIUSDT",
    "KAS": "KASUSDT",
}


def has_pair(symbol: str) -> bool:
    return symbol.upper() in _SYMBOL_TO_PAIR


def _cache_get(symbol: str) -> dict[str, Any] | None:
    entry = _cache.get(symbol)
    if entry is None:
        return None
    if time.time() - entry["fetched_at"] > _CACHE_TTL_S:
        return None
    return entry["payload"]


def _cache_set(symbol: str, payload: dict[str, Any]) -> None:
    _cache[symbol] = {"payload": payload, "fetched_at": time.time()}


async def get_binance_price(symbol: str) -> dict[str, Any]:
    """Return ``{price, source, symbol}`` or ``{error, source}`` on failure."""
    sym = (symbol or "").upper()
    pair = _SYMBOL_TO_PAIR.get(sym)
    if not pair:
        return {"error": "symbol not supported", "source": "binance"}

    cached = _cache_get(sym)
    if cached is not None:
        return cached

    try:
        client = get_http_client()
        resp = await client.get(
            BINANCE_URL,
            params={"symbol": pair},
            timeout=BINANCE_TIMEOUT_S,
        )
        if resp.status_code == 400:
            # Binance returns 400 with {"code":-1121,"msg":"Invalid symbol."}
            return {"error": "invalid pair", "source": "binance"}
        if resp.status_code >= 400:
            return {"error": f"http {resp.status_code}", "source": "binance"}
        data = resp.json()
        price_raw = data.get("price")
        if price_raw is None:
            return {"error": "missing price", "source": "binance"}
        price = float(price_raw)
        if price <= 0:
            return {"error": "non-positive price", "source": "binance"}
        payload = {
            "symbol": sym,
            "price": price,
            "source": "binance",
            "age_s": 0,
        }
        _cache_set(sym, payload)
        return payload
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"error": safe_error("binance fetch failed", exc, logger), "source": "binance"}
    except Exception as exc:
        return {"error": safe_error("binance fetch failed", exc, logger), "source": "binance"}
