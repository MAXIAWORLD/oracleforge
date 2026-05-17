"""Price cascade functions — multi-source fallback chains.

Extracted from pyth_oracle.py (H1/H2 audit fix) to break the circular
import between pyth_oracle and price_oracle.

Dependency graph (all one-way, no cycles):
    price_cascade → pyth_oracle  (feeds, get_pyth_price, cache, HTTP)
    price_cascade → price_oracle (CoinGecko/Yahoo fallbacks, lazy imports)
    price_oracle  → pyth_oracle  (EQUITY_FEEDS, get_pyth_price)
    price_oracle  → price_cascade (get_stock_price_finnhub)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx

from core.errors import safe_error
from .pyth_oracle import (
    ALL_FEEDS,
    CRYPTO_FEEDS,
    EQUITY_FEEDS,
    HERMES_URL,
    _CACHE_MAX,
    _CACHE_TTL_NORMAL,
    _get_http,
    _price_cache,
    get_pyth_price,
)

logger = logging.getLogger("pyth_oracle.cascade")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

_finnhub_call_timestamps: list[float] = []
_FINNHUB_RATE_LIMIT = 55


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

    now = time.time()
    _finnhub_call_timestamps[:] = [t for t in _finnhub_call_timestamps if now - t < 60]
    if len(_finnhub_call_timestamps) >= _FINNHUB_RATE_LIMIT:
        return {"error": "Finnhub rate limit (55/min server-side)", "source": "finnhub"}
    _finnhub_call_timestamps.append(now)

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
    if sym == "GOOGL":
        sym = "GOOG"
    sources_tried: list[str] = []

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

    sources_tried.append("finnhub")
    finnhub_result = await get_stock_price_finnhub(symbol)
    if "error" not in finnhub_result and finnhub_result.get("price", 0) > 0:
        return finnhub_result

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
        logger.warning("Cascade fallback failed for %s", symbol, exc_info=True)

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
        logger.warning("Cascade fallback failed for %s", symbol, exc_info=True)

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
        logger.warning("Cascade fallback failed for %s", symbol, exc_info=True)

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

    pyth_symbols: dict[str, str] = {}
    fallback_symbols: list[str] = []

    for sym in symbols:
        s = sym.upper()
        lookup = "GOOG" if s == "GOOGL" else s
        feed_id = ALL_FEEDS.get(lookup)
        if feed_id:
            cached = _price_cache.get(feed_id)
            if cached and now - cached["ts"] < _CACHE_TTL_NORMAL:
                results[s] = cached["data"].copy()
                results[s]["symbol"] = s
            else:
                pyth_symbols[s] = feed_id
        else:
            fallback_symbols.append(s)

    if pyth_symbols:
        try:
            client = await _get_http()
            ids_str = "&".join(f"ids[]=0x{fid}" for fid in pyth_symbols.values())
            batch_url = f"{HERMES_URL}/v2/updates/price/latest?{ids_str}"
            try:
                resp = await client.get(batch_url)
            except httpx.TimeoutException:
                await asyncio.sleep(0.5)
                resp = await client.get(batch_url)

            if resp.status_code == 200:
                data = resp.json()
                parsed = data.get("parsed", [])
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
                    if len(_price_cache) >= _CACHE_MAX:
                        oldest_key = next(iter(_price_cache))
                        del _price_cache[oldest_key]
                    _price_cache[entry_id] = {"data": result, "ts": now}
            else:
                fallback_symbols.extend(pyth_symbols.keys())

        except Exception as e:
            logger.error(f"Batch fetch error: {e}")
            fallback_symbols.extend(pyth_symbols.keys())

    for sym in pyth_symbols:
        if sym not in results:
            fallback_symbols.append(sym)

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
