"""GET /api/price/{symbol} and POST /api/prices/batch — live multi-source prices.

Both endpoints require a valid X-API-Key and consume daily quota. The
multi-source logic tries to hit at least two independent sources per symbol
and reports the inter-source divergence so callers can decide for themselves
whether the quote is trustworthy.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Final

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.auth import X402_KEY_HASH_SENTINEL, require_access
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_batch, check_daily
from services.oracle import (
    chainlink_oracle,
    history,
    metadata,
    price_cascade,
    pyth_oracle,
    pyth_solana_oracle,
    redstone_oracle,
    uniswap_v3_oracle,
)
from services.oracle.intelligence import (
    build_price_context,
    classify_agreement,
    compute_confidence_score,
    detect_anomaly,
)
from services.oracle.multi_source import collect_sources, compute_divergence

router = APIRouter(prefix="/api", tags=["price"])

_SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{1,10}$")

# ── Public demo endpoint (no auth) ───────────────────────────────────────────
_DEMO_LIMIT: Final[int] = 10       # requests
_DEMO_WINDOW: Final[int] = 60      # seconds
_demo_hits: dict[str, list[float]] = defaultdict(list)


def _demo_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").strip()
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _demo_allowed(ip: str) -> bool:
    now = time.monotonic()
    cutoff = now - _DEMO_WINDOW
    hits = [t for t in _demo_hits[ip] if t > cutoff]
    if len(hits) >= _DEMO_LIMIT:
        return False
    hits.append(now)
    _demo_hits[ip] = hits
    return True


@router.get("/price/demo")
async def demo_price(request: Request) -> JSONResponse:
    """Live BTC price — no API key required. Rate-limited to 10 req/min per IP.

    Used by the landing page widget to show a real-time price without forcing
    visitors to register first.
    """
    if not _demo_allowed(_demo_client_ip(request)):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error("demo rate limit: 10 req/min per IP"),
        )
    sources = await collect_sources("BTC")
    if not sources:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=wrap_error("no live sources available"),
        )
    prices = [s["price"] for s in sources]
    median_price = sorted(prices)[len(prices) // 2]
    divergence_pct = compute_divergence(prices)
    return JSONResponse(content=wrap_with_disclaimer({
        "symbol": "BTC",
        "price": round(median_price, 2),
        "divergence_pct": round(divergence_pct, 4),
        "source_count": len(sources),
        "sources": [
            {
                "name": s.get("name", "unknown"),
                "price": round(s["price"], 2),
                "age_s": s.get("age_s"),
            }
            for s in sources
        ],
    }))
_MAX_BATCH_SYMBOLS = 50
_CHAIN_PATTERN = r"^(base|ethereum|arbitrum)$"
_TWAP_CHAIN_PATTERN = r"^(base|ethereum)$"

# V1.7 — Forex symbols that route to Pyth Solana instead of multi_source.
# Only symbols that are live on Pyth Solana shard 0 (verified V1.4).
_FOREX_SYMBOLS = frozenset({"EUR", "GBP"})

# Known forex tickers NOT yet supported on Pyth Solana shard 0 (no live PDA
# audit done). Return 404 with a hint instead of falling through to the crypto
# path, which would return a confusing "no live price available".
_KNOWN_FOREX_TICKERS = frozenset({"JPY", "CHF", "AUD", "CAD", "CNY", "NZD", "HKD", "SGD", "SEK", "NOK"})


# ── Helpers ─────────────────────────────────────────────────────────────────

def _enforce_rate_limit(key_hash: str, cost: int = 1) -> JSONResponse | None:
    """Apply the daily quota, optionally charging more than 1 for batch calls.

    Phase 4: x402-paid requests bypass the daily quota entirely. The
    pay-per-call model already prices each request, so compounding it with
    the free-tier quota would double-charge the caller.

    For cost > 1 we use check_batch() which atomically checks that the full
    cost fits before incrementing — a rejected batch never drains the quota.
    """
    if key_hash == X402_KEY_HASH_SENTINEL:
        return None
    db = get_db()
    if cost > 1:
        last = check_batch(db, key_hash, cost)
    else:
        last = check_daily(db, key_hash)
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

    # Known-but-unsupported forex tickers: return a clear 404 with hint.
    if symbol in _KNOWN_FOREX_TICKERS:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "forex symbol not supported — only EUR and GBP are live on Pyth Solana shard 0",
                symbol=symbol,
                supported_forex=sorted(_FOREX_SYMBOLS),
            ),
        )

    # V1.7 — Forex symbols dispatch directly to Pyth Solana.
    if symbol in _FOREX_SYMBOLS:
        result = await pyth_solana_oracle.get_pyth_solana_price(symbol)
        if not isinstance(result, dict) or result.get("error"):
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content=wrap_error(
                    "forex price fetch failed",
                    symbol=symbol,
                    detail=result.get("error") if isinstance(result, dict) else "unexpected",
                ),
            )
        return wrap_with_disclaimer({**result, "asset_class": "forex"})

    sources = await collect_sources(symbol)
    if not sources:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("no live price available", symbol=symbol),
        )

    prices = [s["price"] for s in sources]
    median_price = sorted(prices)[len(prices) // 2]
    divergence_pct = compute_divergence(prices)

    confidence_score = compute_confidence_score(sources, divergence_pct)
    anomaly_info = detect_anomaly(symbol, median_price, sources)
    agreement = classify_agreement(divergence_pct, len(sources))

    return wrap_with_disclaimer(
        {
            "symbol": symbol,
            "price": round(median_price, 6),
            "asset_class": "crypto",
            "confidence_score": confidence_score,
            "anomaly": anomaly_info["anomaly"],
            "sources_agreement": agreement,
            "sources": sources,
            "source_count": len(sources),
            "divergence_pct": divergence_pct,
        }
    )


@router.get("/price/{symbol}/context")
async def get_price_context(symbol: str, key_hash: str = Depends(require_access)):
    """Return price + confidence score + anomaly flag + agreement label in one call.

    V1.6 agent-native endpoint: everything an LLM agent needs to decide
    whether to act on a price, in a single tool call.
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

    ctx = await build_price_context(symbol)
    if ctx is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("no live price available", symbol=symbol),
        )

    return wrap_with_disclaimer(ctx)


_VALID_RANGES = frozenset(history.VALID_RANGES)
_VALID_INTERVALS = frozenset(history.VALID_INTERVALS)


@router.get("/price/{symbol}/history")
async def get_price_history_route(
    symbol: str,
    range: str = Query("24h", alias="range", description="Time range: 24h, 7d, or 30d."),
    interval: str | None = Query(None, description="Bucket interval: 5m, 1h, or 1d. Auto-selected if omitted."),
    key_hash: str = Depends(require_access),
):
    """V1.8 — Return historical price snapshots for a symbol.

    The background sampler captures multi-source prices every 5 minutes.
    Data is downsampled to the requested interval via averaging. Retention
    is 30 days.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )
    if range not in _VALID_RANGES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error(
                "invalid range",
                valid=sorted(_VALID_RANGES),
            ),
        )
    if interval is not None and interval not in _VALID_INTERVALS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error(
                "invalid interval",
                valid=sorted(_VALID_INTERVALS),
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = history.get_history(symbol, range_key=range, interval_key=interval)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid range or interval combination"),
        )
    return wrap_with_disclaimer(result)


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

    results = await price_cascade.get_batch_prices(body.symbols)
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


@router.get("/twap/{symbol}")
async def get_twap_price_route(
    symbol: str,
    chain: str = Query(
        "ethereum",
        pattern=_TWAP_CHAIN_PATTERN,
        description="EVM chain on which to read the Uniswap v3 pool.",
    ),
    window: int = Query(
        uniswap_v3_oracle.DEFAULT_WINDOW_S,
        ge=uniswap_v3_oracle.MIN_WINDOW_S,
        le=uniswap_v3_oracle.MAX_WINDOW_S,
        description=(
            "TWAP window in seconds. Default 1800 (30 minutes). "
            "Range: 60 - 86400."
        ),
    ),
    key_hash: str = Depends(require_access),
):
    """V1.5 - Uniswap v3 time-weighted average price (TWAP) for `symbol`.

    Reads tickCumulatives from a curated, high-TVL Uniswap v3 pool on
    the requested EVM chain and returns the human-readable price
    computed from the slope over `window` seconds. Independently
    verifiable on-chain by any EVM client calling `observe()` on the
    same pool.

    Coverage is intentionally narrow (high-liquidity pairs only -- ETH on
    Base/Ethereum + BTC on Ethereum). Listing more pairs requires a
    manual audit per `docs/v1.5_uniswap_twap.md`.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    if not uniswap_v3_oracle.has_pool(symbol, chain):
        supported = uniswap_v3_oracle.all_supported_symbols().get(chain, [])
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "no Uniswap v3 pool configured for this symbol on this chain",
                symbol=symbol,
                chain=chain,
                supported=supported,
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await uniswap_v3_oracle.get_twap_price(symbol, chain=chain, window_s=window)
    if not isinstance(result, dict) or result.get("error"):
        detail = result.get("error") if isinstance(result, dict) else "unexpected"
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error(
                "uniswap_v3 fetch failed",
                symbol=symbol,
                chain=chain,
                detail=detail,
            ),
        )
    return wrap_with_disclaimer(result)


@router.get("/metadata/{symbol}")
async def get_metadata_route(
    symbol: str, key_hash: str = Depends(require_access)
):
    """V1.7 — Return asset metadata from CoinGecko (market cap, volume, supply).

    Coverage: all symbols mapped in ``price_oracle.SYM_TO_COINGECKO`` (~80
    crypto assets). Forex and equity symbols are not covered (no CoinGecko
    ID mapping). Unknown symbols return 404.
    """
    symbol = symbol.upper()
    if not _is_valid_symbol(symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    if not metadata.has_metadata(symbol):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "no metadata available for this symbol",
                symbol=symbol,
                supported_count=len(metadata.supported_symbols()),
            ),
        )

    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    result = await metadata.get_metadata(symbol)
    if not isinstance(result, dict) or result.get("error"):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error(
                "metadata fetch failed",
                symbol=symbol,
                detail=result.get("error") if isinstance(result, dict) else "unexpected",
            ),
        )
    return wrap_with_disclaimer(result)
