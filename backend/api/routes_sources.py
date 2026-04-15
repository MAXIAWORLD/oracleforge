"""GET /api/sources and /api/cache/stats — read-only visibility into the oracle pipeline.

Both endpoints require a valid X-API-Key and count against the daily quota.
They expose circuit-breaker state and cache metrics so agent developers can
decide whether their failed call was upstream-wide or specific to them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from core.auth import require_api_key
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_daily
from services.oracle import chainlink_oracle, price_oracle, pyth_oracle

router = APIRouter(prefix="/api", tags=["sources"])


def _enforce_rate_limit(key_hash: str):
    db = get_db()
    decision = check_daily(db, key_hash)
    if not decision.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "rate limit exceeded",
                limit=decision.limit,
                window_seconds=decision.window_s,
                retry_after_seconds=decision.retry_after,
                reset_at_unix=decision.reset_at,
            ),
            headers={
                "Retry-After": str(decision.retry_after),
                "X-RateLimit-Limit": str(decision.limit),
                "X-RateLimit-Remaining": str(decision.remaining),
                "X-RateLimit-Reset": str(decision.reset_at),
            },
        )
    return None


@router.get("/sources")
async def list_sources(key_hash: str = Depends(require_api_key)):
    """List every price source with its current circuit-breaker state."""
    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    cb = {
        "helius_das":  price_oracle._cb_helius.get_status(),
        "coinpaprika": price_oracle._cb_coinpaprika.get_status(),
        "coingecko":   price_oracle._cb_coingecko.get_status(),
        "yahoo":       price_oracle._cb_yahoo.get_status(),
    }
    return wrap_with_disclaimer(
        {
            "sources": [
                {
                    "name": "pyth_hermes",
                    "type": "decentralized_oracle",
                    "endpoint": "https://hermes.pyth.network",
                    "feeds": {
                        "crypto": list(pyth_oracle.CRYPTO_FEEDS.keys()),
                        "equity": list(pyth_oracle.EQUITY_FEEDS.keys()),
                    },
                    "confidence_interval": True,
                    "circuit_breaker": None,
                },
                {
                    "name": "chainlink_base",
                    "type": "on_chain_oracle",
                    "endpoint": chainlink_oracle.BASE_RPC_URL,
                    "feeds": list(chainlink_oracle.CHAINLINK_FEEDS.keys()),
                    "update_frequency": "~1h heartbeat or 0.5% deviation",
                    "circuit_breaker": None,
                },
                {
                    "name": "helius_das",
                    "type": "rpc_metadata",
                    "protocol": "Solana JSON-RPC getAsset",
                    "circuit_breaker": cb["helius_das"],
                },
                {
                    "name": "coinpaprika",
                    "type": "exchange_aggregator",
                    "endpoint": "https://api.coinpaprika.com/v1/tickers",
                    "circuit_breaker": cb["coinpaprika"],
                },
                {
                    "name": "coingecko",
                    "type": "exchange_aggregator",
                    "endpoint": "https://api.coingecko.com/api/v3/simple/price",
                    "circuit_breaker": cb["coingecko"],
                },
                {
                    "name": "yahoo_finance",
                    "type": "market_data",
                    "endpoint": "https://query1.finance.yahoo.com/v8/finance/spark",
                    "circuit_breaker": cb["yahoo"],
                },
            ],
        }
    )


@router.get("/cache/stats")
async def cache_stats(key_hash: str = Depends(require_api_key)):
    """Return cache metrics and circuit-breaker state in one call."""
    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl
    return wrap_with_disclaimer(price_oracle.get_cache_stats())


@router.get("/symbols")
async def list_symbols(key_hash: str = Depends(require_api_key)):
    """Return the union of supported symbols grouped by upstream source.

    Mirrors the MCP `list_supported_symbols` tool (Phase 5) so the Python
    and TypeScript SDKs have parity with the MCP surface. No upstream
    calls — just reads the in-memory feed dictionaries.
    """
    rl = _enforce_rate_limit(key_hash)
    if rl is not None:
        return rl

    pyth_crypto = sorted(pyth_oracle.CRYPTO_FEEDS.keys())
    pyth_equity = sorted(pyth_oracle.EQUITY_FEEDS.keys())
    chainlink_base = sorted(chainlink_oracle.CHAINLINK_FEEDS.keys())
    price_oracle_mints = sorted(price_oracle.TOKEN_MINTS.keys())

    all_symbols = sorted(
        set(pyth_crypto)
        | set(pyth_equity)
        | set(chainlink_base)
        | set(price_oracle_mints)
    )

    return wrap_with_disclaimer(
        {
            "total_symbols": len(all_symbols),
            "all_symbols": all_symbols,
            "by_source": {
                "pyth_crypto": pyth_crypto,
                "pyth_equity": pyth_equity,
                "chainlink_base": chainlink_base,
                "price_oracle": price_oracle_mints,
            },
        }
    )
