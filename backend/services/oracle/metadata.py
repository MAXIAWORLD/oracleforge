"""MAXIA Oracle — Asset metadata via CoinGecko (V1.7).

Fetches market metadata (market_cap, volume_24h, circulating_supply,
total_supply, price_change_24h) from CoinGecko's /coins/markets endpoint.
Separate from price_oracle.py to keep concerns split: price_oracle returns
prices, this module returns metadata.

Cache TTL is 5 minutes (metadata changes slowly compared to prices).
Circuit breaker shared with nothing — CoinGecko rate limits are generous
on the /coins/markets endpoint (~10-30 req/min free tier).

Never raises. Returns ``{"error": str}`` on failure.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Final

from core.http_client import get_http_client
from services.oracle.price_oracle import SYM_TO_COINGECKO

logger = logging.getLogger(__name__)

_CACHE_TTL_S: Final[int] = 300  # 5 minutes
_CACHE_MAX: Final[int] = 200
_CB_MAX_FAILURES: Final[int] = 3
_CB_COOLDOWN_S: Final[int] = 120

_cache: dict[str, dict[str, Any]] = {}
_cb_failures: int = 0
_cb_open_until: float = 0.0


def _circuit_is_open() -> bool:
    if _cb_failures < _CB_MAX_FAILURES:
        return False
    return time.time() < _cb_open_until


def _record_success() -> None:
    global _cb_failures
    _cb_failures = 0


def _record_failure() -> None:
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_MAX_FAILURES:
        _cb_open_until = time.time() + _CB_COOLDOWN_S
        logger.warning("CoinGecko metadata circuit breaker OPEN")


def has_metadata(symbol: str) -> bool:
    """Return True if we know a CoinGecko ID for this symbol."""
    return symbol.upper() in SYM_TO_COINGECKO


def supported_symbols() -> list[str]:
    """Return sorted list of symbols with CoinGecko metadata support."""
    return sorted(SYM_TO_COINGECKO.keys())


def get_circuit_breaker_status() -> dict[str, Any]:
    return {
        "name": "coingecko_metadata",
        "state": "open" if _circuit_is_open() else "closed",
        "failures": _cb_failures,
        "max": _CB_MAX_FAILURES,
    }


async def get_metadata(symbol: str) -> dict[str, Any]:
    """Fetch asset metadata from CoinGecko for ``symbol``.

    Returns a dict with keys: symbol, name, market_cap_usd,
    volume_24h_usd, price_change_24h_pct, circulating_supply,
    total_supply, max_supply, market_cap_rank, source.

    On failure returns ``{"error": "...", "source": "coingecko", "symbol": symbol}``.
    """
    symbol = symbol.upper()
    cg_id = SYM_TO_COINGECKO.get(symbol)
    if not cg_id:
        return {
            "error": f"no CoinGecko mapping for {symbol}",
            "source": "coingecko",
            "symbol": symbol,
        }

    now = time.time()
    cached = _cache.get(symbol)
    if cached and now - cached.get("_ts", 0) < _CACHE_TTL_S:
        return {k: v for k, v in cached.items() if not k.startswith("_")}

    if _circuit_is_open():
        return {
            "error": "coingecko metadata circuit breaker open",
            "source": "coingecko",
            "symbol": symbol,
        }

    try:
        client = get_http_client()
        resp = await client.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": cg_id,
                "order": "market_cap_desc",
                "per_page": "1",
                "page": "1",
                "sparkline": "false",
            },
            timeout=12,
        )
        if resp.status_code != 200:
            _record_failure()
            return {
                "error": f"CoinGecko returned {resp.status_code}",
                "source": "coingecko",
                "symbol": symbol,
            }

        data = resp.json()
        if not data or not isinstance(data, list) or len(data) == 0:
            _record_failure()
            return {
                "error": f"CoinGecko returned empty data for {symbol}",
                "source": "coingecko",
                "symbol": symbol,
            }

        coin = data[0]
        _record_success()

        result: dict[str, Any] = {
            "symbol": symbol,
            "name": coin.get("name", ""),
            "market_cap_usd": coin.get("market_cap"),
            "volume_24h_usd": coin.get("total_volume"),
            "price_change_24h_pct": coin.get("price_change_percentage_24h"),
            "circulating_supply": coin.get("circulating_supply"),
            "total_supply": coin.get("total_supply"),
            "max_supply": coin.get("max_supply"),
            "market_cap_rank": coin.get("market_cap_rank"),
            "ath_usd": coin.get("ath"),
            "atl_usd": coin.get("atl"),
            "last_updated": coin.get("last_updated"),
            "source": "coingecko",
        }

        if len(_cache) >= _CACHE_MAX:
            oldest = min(_cache, key=lambda s: _cache[s].get("_ts", 0))
            del _cache[oldest]
        _cache[symbol] = {**result, "_ts": now}
        return result

    except Exception as exc:
        _record_failure()
        logger.error("CoinGecko metadata fetch error for %s: %s", symbol, exc)
        return {
            "error": f"CoinGecko metadata fetch failed: {type(exc).__name__}",
            "source": "coingecko",
            "symbol": symbol,
        }
