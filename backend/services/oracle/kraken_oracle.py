"""MAXIA Oracle — Kraken public spot price reader (V2.4).

Kraken is the largest US-friendly fiat on-ramp. Its public ticker is
unauthenticated and provides an independent market quote that does NOT
share liquidity with Binance — useful as the second independent CEX
upstream.

Endpoint
    GET https://api.kraken.com/0/public/Ticker?pair=XBTUSD

Quirks
    - BTC is "XBT" on Kraken (legacy ticker). Map applied transparently.
    - Pair names are returned with a dot wrapping in the JSON keys
      (e.g. "XXBTZUSD"); we flatten by reading the first key from the
      result dict.

Rate limits: ~1 req/sec for unauthenticated endpoints. Cache TTL 10s
keeps us well within budget for a 23-token grid refreshed every 30s.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("kraken_oracle")

KRAKEN_URL: Final[str] = "https://api.kraken.com/0/public/Ticker"
KRAKEN_TIMEOUT_S: Final[float] = 6.0

_CACHE_TTL_S: Final[int] = 10
_cache: dict[str, dict[str, Any]] = {}

# Kraken USD pairs — mapping from oracle symbol to Kraken pair string.
# Symbols absent from this map are skipped (no implicit guess).
_SYMBOL_TO_PAIR: Final[dict[str, str]] = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "USDC": "USDCUSD",
    "XRP": "XRPUSD",
    "ADA": "ADAUSD",
    "DOGE": "DOGEUSD",
    "AVAX": "AVAXUSD",
    "DOT": "DOTUSD",
    "POL": "POLUSD",
    "LTC": "LTCUSD",
    "TRX": "TRXUSD",
    "NEAR": "NEARUSD",
    "SUI": "SUIUSD",
    "APT": "APTUSD",
    "INJ": "INJUSD",
    "SEI": "SEIUSD",
    "RENDER": "RENDERUSD",
    "FET": "FETUSD",
    "TAO": "TAOUSD",
    "DAI": "DAIUSD",
    "KAS": "KASUSD",
    "WSTETH": "WSTETHUSD",
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


async def get_kraken_price(symbol: str) -> dict[str, Any]:
    """Return ``{price, source, symbol}`` or ``{error, source}`` on failure.

    Kraken response shape:
        {"error": [...], "result": {"XXBTZUSD": {"c": ["68234.5", "0.001"], ...}}}
    where ``c`` is [last_trade_price, last_trade_volume]. We use the last
    trade price as the spot quote.
    """
    sym = (symbol or "").upper()
    pair = _SYMBOL_TO_PAIR.get(sym)
    if not pair:
        return {"error": "symbol not supported", "source": "kraken"}

    cached = _cache_get(sym)
    if cached is not None:
        return cached

    try:
        client = get_http_client()
        resp = await client.get(
            KRAKEN_URL,
            params={"pair": pair},
            timeout=KRAKEN_TIMEOUT_S,
        )
        if resp.status_code >= 400:
            return {"error": f"http {resp.status_code}", "source": "kraken"}
        data = resp.json()
        if data.get("error"):
            return {"error": "kraken api error", "source": "kraken"}
        result = data.get("result") or {}
        if not result:
            return {"error": "empty result", "source": "kraken"}
        # Take the first (and usually only) ticker entry. Kraken keys are
        # like "XXBTZUSD" or "POLUSD" — independent of the requested pair.
        first_ticker = next(iter(result.values()))
        last_trade = first_ticker.get("c")
        if not last_trade or not isinstance(last_trade, list) or len(last_trade) == 0:
            return {"error": "missing last trade", "source": "kraken"}
        price = float(last_trade[0])
        if price <= 0:
            return {"error": "non-positive price", "source": "kraken"}
        payload = {
            "symbol": sym,
            "price": price,
            "source": "kraken",
            "age_s": 0,
        }
        _cache_set(sym, payload)
        return payload
    except (httpx.HTTPError, ValueError, KeyError, StopIteration) as exc:
        return {"error": safe_error("kraken fetch failed", exc, logger), "source": "kraken"}
    except Exception as exc:
        return {"error": safe_error("kraken fetch failed", exc, logger), "source": "kraken"}
