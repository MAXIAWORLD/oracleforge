"""GET /api/price/{symbol} and POST /api/prices/batch — live multi-source prices.

Both endpoints require a valid X-API-Key and consume daily quota. The
multi-source logic tries to hit at least two independent sources per symbol
and reports the inter-source divergence so callers can decide for themselves
whether the quote is trustworthy.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.auth import X402_KEY_HASH_SENTINEL, require_access
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_daily
from services.oracle import chainlink_oracle, pyth_oracle, pyth_solana_oracle, redstone_oracle
from services.oracle.multi_source import collect_sources, compute_divergence

router = APIRouter(prefix="/api", tags=["price"])

_SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{1,10}$")
_MAX_BATCH_SYMBOLS = 50
_CHAIN_PATTERN = r"^(base|ethereum|arbitrum)$"


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
    symbol: str,
    chain: str = Query(
        "base",
        pattern=_CHAIN_PATTERN,
        description="EVM chain on which to read the Chainlink feed.",
    ),
    key_hash: str = Depends(require_access),
):
    """Return a single-source Chainlink on-chain price on the requested chain.

    V1.1: the `chain` query parameter selects Base (default), Ethereum or
    Arbitrum. Default stays `base` for strict backward compatibility with
    V1.0 clients. Unsupported `symbol` + `chain` combinations return 404
    with the list of symbols available on the requested chain.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    if not chainlink_oracle.has_feed(symbol, chain):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "symbol has no Chainlink feed on requested chain",
                symbol=symbol,
                chain=chain,
                supported=chainlink_oracle.symbols_for(chain),
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await chainlink_oracle.get_chainlink_price(symbol, chain=chain)
    if not isinstance(result, dict) or result.get("error"):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error(
                "chainlink fetch failed",
                symbol=symbol,
                chain=chain,
                detail=(
                    result.get("error") if isinstance(result, dict) else "unexpected"
                ),
            ),
        )
    return wrap_with_disclaimer(result)


@router.get("/redstone/{symbol}")
async def get_redstone_price_route(
    symbol: str, key_hash: str = Depends(require_access)
):
    """Return a single-source RedStone REST price for `symbol`.

    V1.3: RedStone is the 4th independent upstream. Coverage is dynamic
    (400+ assets across crypto majors, long-tail, forex and equities) so
    unknown symbols return 404 rather than being pre-rejected on a hardcoded
    allow-list. Callers that want the multi-source median should use
    `/api/price/{symbol}` instead — this route is for audit / cross-check.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await redstone_oracle.get_redstone_price(symbol)
    if not isinstance(result, dict) or result.get("error"):
        detail = result.get("error") if isinstance(result, dict) else "unexpected"
        http_status = (
            status.HTTP_404_NOT_FOUND
            if isinstance(detail, str) and "not found" in detail
            else status.HTTP_502_BAD_GATEWAY
        )
        return JSONResponse(
            status_code=http_status,
            content=wrap_error(
                "redstone fetch failed",
                symbol=symbol,
                detail=detail,
            ),
        )
    return wrap_with_disclaimer(result)


@router.get("/pyth/solana/{symbol}")
async def get_pyth_solana_price_route(
    symbol: str, key_hash: str = Depends(require_access)
):
    """Return a single-source Pyth price read directly from Solana mainnet (V1.4).

    Reads the Price Feed Account for `symbol` on shard 0 of the Pyth Push
    Oracle program (`pythWSns...`) and decodes the Anchor `PriceUpdateV2`
    layout inline. Coverage is restricted to the majors that are sponsored
    by the Pyth Data Association on shard 0 — see
    `pyth_solana_oracle.PYTH_SOLANA_FEEDS`. Unknown symbols return 404.

    This route is intentionally independent of the multi-source path (see
    `/api/price/{symbol}`): Pyth is already reached via Hermes there, and
    aggregating the same publishers twice would bias the divergence metric.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    if not pyth_solana_oracle.has_feed(symbol):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "symbol not supported on Pyth Solana shard 0",
                symbol=symbol,
                supported=pyth_solana_oracle.list_supported_symbols(),
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await pyth_solana_oracle.get_pyth_solana_price(symbol)
    if not isinstance(result, dict) or result.get("error"):
        detail = result.get("error") if isinstance(result, dict) else "unexpected"
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error(
                "pyth_solana fetch failed",
                symbol=symbol,
                detail=detail,
            ),
        )
    return wrap_with_disclaimer(result)


