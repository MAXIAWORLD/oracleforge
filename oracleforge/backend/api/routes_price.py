"""GET /api/price/{symbol} and POST /api/prices/batch — live multi-source prices.

Both endpoints require a valid X-API-Key and consume daily quota. The
multi-source logic tries to hit at least two independent sources per symbol
and reports the inter-source divergence so callers can decide for themselves
whether the quote is trustworthy.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.auth import X402_KEY_HASH_SENTINEL, require_access
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_daily
from services.oracle import chainlink_oracle, pyth_oracle
from services.oracle.multi_source import collect_sources, compute_divergence

router = APIRouter(prefix="/api", tags=["price"])

_SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{1,10}$")
_MAX_BATCH_SYMBOLS = 50


# ── Helpers ─────────────────────────────────────────────────────────────────

def _enforce_rate_limit(key_hash: str, cost: int = 1) -> JSONResponse | None:
    """Apply the daily quota, optionally charging more than 1 for batch calls.

    Phase 4: x402-paid requests bypass the daily quota entirely. The
    pay-per-call model already prices each request, so compounding it with
    the free-tier quota would double-charge the caller.
    """
    if key_hash == X402_KEY_HASH_SENTINEL:
        return None
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


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/price/{symbol}")
async def get_single_price(symbol: str, key_hash: str = Depends(require_access)):
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

    sources = await collect_sources(symbol)
    if not sources:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("no live price available", symbol=symbol),
        )

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
    body: BatchRequest, key_hash: str = Depends(require_access)
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


@router.get("/chainlink/{symbol}")
async def get_chainlink_price_route(
    symbol: str, key_hash: str = Depends(require_access)
):
    """Return a single-source price directly from the Chainlink feed on Base.

    Mirrors the MCP `get_chainlink_onchain` tool (Phase 5) so SDK callers
    can force the on-chain single-source path for audit purposes. The
    symbol must be in `chainlink_oracle.CHAINLINK_FEEDS` — unsupported
    symbols return 404 with the list of supported tickers.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    if symbol not in chainlink_oracle.CHAINLINK_FEEDS:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "symbol has no Chainlink feed on Base",
                symbol=symbol,
                supported=sorted(chainlink_oracle.CHAINLINK_FEEDS.keys()),
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await chainlink_oracle.get_chainlink_price(symbol)
    if not isinstance(result, dict) or result.get("error"):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error(
                "chainlink fetch failed",
                symbol=symbol,
                detail=(
                    result.get("error") if isinstance(result, dict) else "unexpected"
                ),
            ),
        )
    return wrap_with_disclaimer(result)
