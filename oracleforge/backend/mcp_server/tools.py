"""MAXIA Oracle — MCP tool implementations (Phase 5 Step 3).

Each public function in this module is a thin wrapper around the existing
oracle services. `mcp_server/server.py` registers them as MCP tools with
JSON schemas; this module holds only the business logic.

Return contract:
    - Every public function returns a plain `dict[str, Any]`.
    - Errors are returned as `{"error": "...", "disclaimer": "..."}` —
      they never raise out of the tool body. The MCP client always
      receives a well-formed JSON response.
    - Successful responses are wrapped in
      `{"data": ..., "disclaimer": "..."}` via `wrap_with_disclaimer` so
      the disclaimer rule from Phase 3 decision #6 is preserved across
      transports.

These functions are intentionally async: the HTTP SSE transport
(`api/routes_mcp.py`) runs them inside the FastAPI event loop, and the
stdio transport (`mcp_server/__main__.py`) runs them inside its own
asyncio event loop. A sync helper would force a blocking adapter on one
of the two paths.

Phase 5 Step 3 scope: 8 tools listed below. Two tools from the original
plan (`get_price_history`, `subscribe_price_stream`) are deferred to
V1.1 and are not exposed here.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Final

from core.disclaimer import wrap_error, wrap_with_disclaimer
from services.oracle import (
    chainlink_oracle,
    price_oracle,
    pyth_oracle,
    redstone_oracle,
)
from services.oracle.multi_source import collect_sources, compute_divergence

_SYMBOL_REGEX: Final[re.Pattern[str]] = re.compile(r"^[A-Z0-9]{1,10}$")
_MAX_BATCH_SYMBOLS: Final[int] = 50


def _is_valid_symbol(symbol: str) -> bool:
    """Return True iff `symbol` matches the shared MAXIA Oracle ticker format."""
    return bool(_SYMBOL_REGEX.match(symbol))


# ── 1. get_price ─────────────────────────────────────────────────────────────


async def get_price(symbol: str) -> dict[str, Any]:
    """Return a multi-source live price for a single symbol.

    The result includes the cross-validated median price, each source's
    individual quote, and the inter-source divergence in percent. An
    empty source list yields `{"error": "no live price available"}`.
    """
    if not isinstance(symbol, str):
        return wrap_error("symbol must be a string")
    symbol = symbol.strip().upper()
    if not _is_valid_symbol(symbol):
        return wrap_error("invalid symbol format", symbol=symbol)

    sources = await collect_sources(symbol)
    if not sources:
        return wrap_error("no live price available", symbol=symbol)

    prices = [s["price"] for s in sources]
    median_price = sorted(prices)[len(prices) // 2]
    divergence_pct = compute_divergence(prices)

    return wrap_with_disclaimer(
        {
            "symbol": symbol,
            "price": round(median_price, 6),
            "sources": sources,
            "source_count": len(sources),
            "divergence_pct": divergence_pct,
        }
    )


# ── 2. get_prices_batch ──────────────────────────────────────────────────────


async def get_prices_batch(symbols: list[str]) -> dict[str, Any]:
    """Return prices for up to 50 symbols in a single upstream call.

    Uses Pyth Hermes batch endpoint under the hood, which is dramatically
    cheaper than issuing one `get_price` per symbol. Falls back to an
    empty result for symbols that have no Pyth feed.
    """
    if not isinstance(symbols, list):
        return wrap_error("symbols must be a list of strings")
    if not symbols:
        return wrap_error("symbols must contain at least one entry")
    if len(symbols) > _MAX_BATCH_SYMBOLS:
        return wrap_error(
            f"batch size exceeds {_MAX_BATCH_SYMBOLS}",
            requested=len(symbols),
            max_allowed=_MAX_BATCH_SYMBOLS,
        )

    cleaned: list[str] = []
    for raw in symbols:
        if not isinstance(raw, str):
            return wrap_error("every symbol must be a string", invalid=repr(raw))
        sym = raw.strip().upper()
        if not _is_valid_symbol(sym):
            return wrap_error("invalid symbol format", symbol=raw)
        if sym not in cleaned:
            cleaned.append(sym)

    results = await pyth_oracle.get_batch_prices(cleaned)
    return wrap_with_disclaimer(
        {
            "requested": len(cleaned),
            "count": len(results) if isinstance(results, dict) else 0,
            "prices": results,
        }
    )


# ── 3. get_sources_status ────────────────────────────────────────────────────


async def get_sources_status() -> dict[str, Any]:
    """Probe each upstream source with BTC and report up/down status.

    Runs the 3 main sources concurrently so the tool returns in at most
    one upstream round-trip. This is a lightweight "is my oracle
    working?" check — it does NOT validate correctness of the returned
    prices, only that each source responded without error.
    """
    probe_symbol = "BTC"
    pyth_feed = pyth_oracle.CRYPTO_FEEDS.get(probe_symbol)
    chainlink_probe = probe_symbol if chainlink_oracle.has_feed(probe_symbol, "base") else None

    tasks: list[tuple[str, Any]] = []
    if pyth_feed:
        tasks.append(("pyth", pyth_oracle.get_pyth_price(pyth_feed)))
    if chainlink_probe:
        tasks.append(("chainlink", chainlink_oracle.get_chainlink_price(chainlink_probe)))
    tasks.append(("price_oracle", price_oracle.get_prices([probe_symbol])))

    results = await asyncio.gather(
        *(coro for _, coro in tasks), return_exceptions=True
    )

    sources: dict[str, dict[str, Any]] = {}
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            sources[name] = {"status": "error", "detail": type(result).__name__}
            continue
        if not isinstance(result, dict):
            sources[name] = {"status": "error", "detail": "unexpected response type"}
            continue
        if name == "price_oracle":
            entry = result.get(probe_symbol)
            if entry and entry.get("price"):
                sources[name] = {"status": "up", "latest_source": entry.get("source")}
            else:
                sources[name] = {"status": "down"}
            continue
        if result.get("error") or not result.get("price"):
            sources[name] = {"status": "down", "detail": result.get("error", "no price")}
        else:
            sources[name] = {"status": "up", "age_s": result.get("age_s")}

    total = len(sources)
    up = sum(1 for s in sources.values() if s.get("status") == "up")
    return wrap_with_disclaimer(
        {
            "probe_symbol": probe_symbol,
            "sources": sources,
            "up": up,
            "total": total,
            "all_healthy": up == total,
        }
    )


# ── 4. get_cache_stats ───────────────────────────────────────────────────────


async def get_cache_stats() -> dict[str, Any]:
    """Return the price_oracle in-memory cache and circuit-breaker metrics.

    Debug-oriented tool: lets an agent introspect its own latency
    amplification by checking hit rates, or understand why a source is
    returning errors (open circuit breaker).
    """
    return wrap_with_disclaimer(price_oracle.get_cache_stats())


# ── 5. get_confidence ────────────────────────────────────────────────────────


async def get_confidence(symbol: str) -> dict[str, Any]:
    """Return the multi-source divergence for `symbol` as a compact metric.

    This is a lightweight variant of `get_price` for callers that only
    care about "do the sources agree?" and not about the individual
    quotes. Returns the same `divergence_pct` that `get_price` embeds
    but without the per-source breakdown.
    """
    if not isinstance(symbol, str):
        return wrap_error("symbol must be a string")
    symbol = symbol.strip().upper()
    if not _is_valid_symbol(symbol):
        return wrap_error("invalid symbol format", symbol=symbol)

    sources = await collect_sources(symbol)
    if not sources:
        return wrap_error("no live price available", symbol=symbol)

    prices = [s["price"] for s in sources]
    divergence_pct = compute_divergence(prices)
    return wrap_with_disclaimer(
        {
            "symbol": symbol,
            "source_count": len(sources),
            "divergence_pct": divergence_pct,
            "interpretation": _interpret_divergence(divergence_pct),
        }
    )


def _interpret_divergence(div: float) -> str:
    """Translate a numeric divergence into a short human-readable hint."""
    if div == 0.0:
        return "perfect agreement"
    if div < 0.1:
        return "tight agreement"
    if div < 0.5:
        return "normal spread"
    if div < 2.0:
        return "wider than usual — investigate stale source"
    return "suspicious — likely stale or wrong source"


# ── 6. list_supported_symbols ────────────────────────────────────────────────


async def list_supported_symbols() -> dict[str, Any]:
    """Return the union of supported symbols across Pyth, Chainlink, price_oracle.

    V1.1: Chainlink is reported per chain (base, ethereum, arbitrum) so
    callers can see which chains can answer a given symbol. The
    `all_symbols` union folds every source and every chain into one
    flat deduplicated list.
    """
    pyth_crypto = sorted(pyth_oracle.CRYPTO_FEEDS.keys())
    pyth_equity = sorted(pyth_oracle.EQUITY_FEEDS.keys())
    chainlink_by_chain = chainlink_oracle.all_supported_symbols()
    price_oracle_mints = sorted(price_oracle.TOKEN_MINTS.keys())

    chainlink_union: set[str] = set()
    for syms in chainlink_by_chain.values():
        chainlink_union.update(syms)

    all_symbols = sorted(
        set(pyth_crypto)
        | set(pyth_equity)
        | chainlink_union
        | set(price_oracle_mints)
    )

    return wrap_with_disclaimer(
        {
            "total_symbols": len(all_symbols),
            "all_symbols": all_symbols,
            "by_source": {
                "pyth_crypto": pyth_crypto,
                "pyth_equity": pyth_equity,
                "chainlink_base": chainlink_by_chain.get("base", []),
                "chainlink_ethereum": chainlink_by_chain.get("ethereum", []),
                "chainlink_arbitrum": chainlink_by_chain.get("arbitrum", []),
                "price_oracle": price_oracle_mints,
            },
        }
    )


# ── 7. get_chainlink_onchain ─────────────────────────────────────────────────


async def get_chainlink_onchain(
    symbol: str, chain: str = "base"
) -> dict[str, Any]:
    """Fetch a price directly from a Chainlink on-chain feed.

    V1.1: accepts `chain` = base (default), ethereum, or arbitrum. Forces
    Chainlink (bypassing Pyth and the aggregator sources) so the caller
    gets a quote that is independently verifiable on-chain via the
    corresponding EVM RPC. Useful for audit or cross-checking the median
    returned by `get_price`.
    """
    if not isinstance(symbol, str):
        return wrap_error("symbol must be a string")
    if not isinstance(chain, str):
        return wrap_error("chain must be a string")
    symbol = symbol.strip().upper()
    chain = chain.strip().lower()
    if not _is_valid_symbol(symbol):
        return wrap_error("invalid symbol format", symbol=symbol)
    if chain not in chainlink_oracle.SUPPORTED_CHAINS:
        return wrap_error(
            "unsupported chain",
            chain=chain,
            supported=list(chainlink_oracle.SUPPORTED_CHAINS),
        )
    if not chainlink_oracle.has_feed(symbol, chain):
        return wrap_error(
            "symbol has no Chainlink feed on requested chain",
            symbol=symbol,
            chain=chain,
            supported=chainlink_oracle.symbols_for(chain),
        )

    result = await chainlink_oracle.get_chainlink_price(symbol, chain=chain)
    if not isinstance(result, dict) or result.get("error"):
        return wrap_error(
            "chainlink fetch failed",
            symbol=symbol,
            chain=chain,
            detail=result.get("error") if isinstance(result, dict) else "unexpected",
        )
    return wrap_with_disclaimer(result)


# ── 9. get_redstone_price (V1.3) ─────────────────────────────────────────────


async def get_redstone_price(symbol: str) -> dict[str, Any]:
    """Fetch a single-source price directly from the RedStone public REST API.

    V1.3: RedStone is the 4th independent upstream. Coverage is dynamic
    (400+ assets: crypto majors + long-tail + forex + equities). Unknown
    symbols return an error rather than being pre-rejected on a hardcoded
    allow-list. Useful to cross-check the median returned by `get_price`.
    """
    if not isinstance(symbol, str):
        return wrap_error("symbol must be a string")
    symbol = symbol.strip().upper()
    if not _is_valid_symbol(symbol):
        return wrap_error("invalid symbol format", symbol=symbol)

    result = await redstone_oracle.get_redstone_price(symbol)
    if not isinstance(result, dict) or result.get("error"):
        return wrap_error(
            "redstone fetch failed",
            symbol=symbol,
            detail=result.get("error") if isinstance(result, dict) else "unexpected",
        )
    return wrap_with_disclaimer(result)


# ── 10. health_check ─────────────────────────────────────────────────────────


async def health_check() -> dict[str, Any]:
    """Return a minimal `status: ok` payload for liveness probes.

    Does NOT touch upstream sources — this is a liveness check only,
    meant to be cheap enough for a monitoring agent to call every
    few seconds without wasting oracle budget. For a deeper readiness
    check, call `get_sources_status()` instead.
    """
    return wrap_with_disclaimer(
        {
            "status": "ok",
            "service": "maxia-oracle-mcp",
        }
    )
