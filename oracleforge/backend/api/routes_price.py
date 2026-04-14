"""GET /api/price/{symbol} and POST /api/prices/batch — live multi-source prices.

Both endpoints require a valid X-API-Key and consume daily quota. The
multi-source logic tries to hit at least two independent sources per symbol
and reports the inter-source divergence so callers can decide for themselves
whether the quote is trustworthy.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.auth import require_api_key
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_daily
from services.oracle import chainlink_oracle, price_oracle, pyth_oracle

router = APIRouter(prefix="/api", tags=["price"])

_SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{1,10}$")
_MAX_BATCH_SYMBOLS = 50


# ── Helpers ─────────────────────────────────────────────────────────────────

def _enforce_rate_limit(key_hash: str, cost: int = 1) -> JSONResponse | None:
    """Apply the daily quota, optionally charging more than 1 for batch calls."""
    db = get_db()
    decisions = [check_daily(db, key_hash) for _ in range(cost)]
    last = decisions[-1]
    if not last.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "rate limit exceeded",
                limit=last.limit,
                window_seconds=last.window_s,
                retry_after_seconds=last.retry_after,
                reset_at_unix=last.reset_at,
            ),
            headers={
                "Retry-After": str(last.retry_after),
                "X-RateLimit-Limit": str(last.limit),
                "X-RateLimit-Remaining": str(last.remaining),
                "X-RateLimit-Reset": str(last.reset_at),
            },
        )
    return None


def _is_valid_symbol(symbol: str) -> bool:
    """Accept only uppercase alphanumeric tickers (1-10 chars) — matches Pyth/Chainlink feed IDs."""
    return bool(_SYMBOL_REGEX.match(symbol))


def _compute_divergence(prices: list[float]) -> float:
    """Return the max/min - 1 ratio in percent, or 0 if fewer than 2 prices."""
    positive = [p for p in prices if p > 0]
    if len(positive) < 2:
        return 0.0
    return round((max(positive) / min(positive) - 1.0) * 100, 4)


async def _collect_sources(symbol: str) -> list[dict[str, Any]]:
    """Gather prices for `symbol` from every applicable source concurrently.

    Returns a list of per-source dicts in the form:
        {"name": "pyth", "price": 74287.07, "age_s": 1, "source_meta": {...}}
    A source is omitted if it has no feed for this symbol or returned an error.
    """
    tasks: list[tuple[str, Any]] = []

    # Pyth — crypto feed
    if symbol in pyth_oracle.CRYPTO_FEEDS:
        tasks.append(("pyth_crypto", pyth_oracle.get_pyth_price(pyth_oracle.CRYPTO_FEEDS[symbol])))
    # Pyth — equity feed
    lookup_eq = "GOOG" if symbol == "GOOGL" else symbol
    if lookup_eq in pyth_oracle.EQUITY_FEEDS:
        tasks.append(
            ("pyth_equity", pyth_oracle.get_pyth_price(pyth_oracle.EQUITY_FEEDS[lookup_eq]))
        )
    # Chainlink — on-chain Base
    if symbol in chainlink_oracle.CHAINLINK_FEEDS:
        tasks.append(("chainlink_base", chainlink_oracle.get_chainlink_price(symbol)))
    # price_oracle — Helius/CoinPaprika/CoinGecko aggregator
    tasks.append(("price_oracle", price_oracle.get_prices([symbol])))

    results = await asyncio.gather(*(coro for _, coro in tasks), return_exceptions=True)
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


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/price/{symbol}")
async def get_single_price(symbol: str, key_hash: str = Depends(require_api_key)):
    """Return a multi-source live price for a single symbol."""
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    sources = await _collect_sources(symbol)
    if not sources:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("no live price available", symbol=symbol),
        )

    prices = [s["price"] for s in sources]
    median_price = sorted(prices)[len(prices) // 2]
    divergence_pct = _compute_divergence(prices)

    return wrap_with_disclaimer(
        {
            "symbol": symbol,
            "price": round(median_price, 6),
            "sources": sources,
            "source_count": len(sources),
            "divergence_pct": divergence_pct,
        }
    )


class BatchRequest(BaseModel):
    """POST /api/prices/batch request body."""

    symbols: list[str] = Field(..., min_length=1, max_length=_MAX_BATCH_SYMBOLS)

    @field_validator("symbols")
    @classmethod
    def _uppercase_and_validate(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in value:
            sym = (raw or "").strip().upper()
            if not _is_valid_symbol(sym):
                raise ValueError(f"invalid symbol format: {raw!r}")
            cleaned.append(sym)
        # Deduplicate while preserving order
        seen: set[str] = set()
        dedup: list[str] = []
        for sym in cleaned:
            if sym not in seen:
                seen.add(sym)
                dedup.append(sym)
        return dedup


@router.post("/prices/batch")
async def get_batch_prices_route(
    body: BatchRequest, key_hash: str = Depends(require_api_key)
):
    """Return prices for up to 50 symbols in a single Pyth Hermes call.

    Each symbol counts for 1 unit against the daily quota to keep the
    incentive aligned with the underlying upstream cost.
    """
    rl = _enforce_rate_limit(key_hash, cost=len(body.symbols))
    if rl is not None:
        return rl

    results = await pyth_oracle.get_batch_prices(body.symbols)
    return wrap_with_disclaimer(
        {
            "count": len(results),
            "requested": len(body.symbols),
            "prices": results,
        }
    )
