"""MAXIA Oracle — multi-source price aggregation helper (Phase 5 Step 2).

Extracted from `api/routes_price.py` so both the HTTP route
`GET /api/price/{symbol}` and the MCP tool `get_price(symbol)` can reuse
the same cross-validation logic without duplicating 60 lines of code.

The helper:
    1. Fans out concurrent requests to every applicable upstream source
       (Pyth crypto/equity, Chainlink on-chain Base, price_oracle aggregator).
    2. Normalizes per-source dicts into a uniform shape.
    3. Computes the inter-source divergence as a convenience summary for
       callers that want a one-number "trust the quote?" metric.

Design notes:
    - Error handling is per-source: a dead upstream is silently dropped
      from the result list. The caller decides how to interpret an empty
      list (typically 404 on the HTTP path).
    - The helper does not apply any authentication, rate-limit, or
      disclaimer wrapping — those are concerns of the transport layer
      (FastAPI route or MCP tool).
    - Functions are pure (side-effect free) except for the upstream
      network I/O which is already gated by the shared http_client pool
      and by each service's own caching.
"""
from __future__ import annotations

import asyncio
from typing import Any

from services.oracle import chainlink_oracle, price_oracle, pyth_oracle, redstone_oracle


def compute_divergence(prices: list[float]) -> float:
    """Return the max/min - 1 ratio in percent, or 0 if fewer than 2 prices.

    This is a coarse "do the sources agree?" signal: 0.0 means every
    source returned the same price, 0.35 means 0.35 % spread between
    the highest and lowest quote. Values under ~0.5 % are typical for
    crypto majors, higher values mean the caller should investigate
    which source is stale before acting on the number.
    """
    positive = [p for p in prices if p > 0]
    if len(positive) < 2:
        return 0.0
    return round((max(positive) / min(positive) - 1.0) * 100, 4)


async def collect_sources(symbol: str) -> list[dict[str, Any]]:
    """Gather prices for `symbol` from every applicable source concurrently.

    Returns a list of per-source dicts in the form:
        {
            "name": "pyth_crypto",
            "price": 74287.07,
            "age_s": 1,
            "confidence_pct": 0.02,
            "stale": False,
        }

    A source is omitted from the result list if it has no feed for this
    symbol, if the upstream call raised an exception, or if the returned
    payload contained an `"error"` field or a missing price. The caller
    treats an empty list as "no live price available".
    """
    tasks: list[tuple[str, Any]] = []

    # Pyth — crypto feed
    if symbol in pyth_oracle.CRYPTO_FEEDS:
        tasks.append(
            ("pyth_crypto", pyth_oracle.get_pyth_price(pyth_oracle.CRYPTO_FEEDS[symbol]))
        )
    # Pyth — equity feed
    lookup_eq = "GOOG" if symbol == "GOOGL" else symbol
    if lookup_eq in pyth_oracle.EQUITY_FEEDS:
        tasks.append(
            ("pyth_equity", pyth_oracle.get_pyth_price(pyth_oracle.EQUITY_FEEDS[lookup_eq]))
        )
    # Chainlink — on-chain Base (multi-source aggregator stays Base-only by design:
    # mixing chains into a single "median" is semantically wrong, same symbol can
    # legitimately diverge by a few bps across chains because of heartbeat timing).
    if chainlink_oracle.has_feed(symbol, "base"):
        tasks.append(
            ("chainlink_base", chainlink_oracle.get_chainlink_price(symbol, chain="base"))
        )
    # price_oracle — Helius/CoinPaprika/CoinGecko aggregator
    tasks.append(("price_oracle", price_oracle.get_prices([symbol])))
    # V1.3 — RedStone public REST (4th independent upstream). Every symbol
    # is attempted; `symbol not found` replies are silent-dropped below.
    tasks.append(("redstone", redstone_oracle.get_redstone_price(symbol)))

    results = await asyncio.gather(
        *(coro for _, coro in tasks), return_exceptions=True
    )

    out: list[dict[str, Any]] = []
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception) or not isinstance(result, dict):
            continue
        if name == "price_oracle":
            entry = result.get(symbol)
            if not entry or not entry.get("price"):
                continue
            out.append(
                {
                    "name": entry.get("source", "price_oracle"),
                    "price": float(entry["price"]),
                    "age_s": None,
                }
            )
            continue
        if "error" in result or not result.get("price"):
            continue
        out.append(
            {
                "name": result.get("source", name),
                "price": float(result["price"]),
                "age_s": result.get("age_s"),
                "confidence_pct": result.get("confidence_pct"),
                "stale": result.get("stale", False),
            }
        )
    return out
