"""GET /api/sources and /api/cache/stats — read-only visibility into the oracle pipeline.

Both endpoints require a valid X-API-Key and count against the daily quota.
They expose circuit-breaker state and cache metrics so agent developers can
decide whether their failed call was upstream-wide or specific to them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from core.auth import require_api_key
from core.config import CHAIN_RPC_URLS
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_daily
from services.oracle import (
    chainlink_oracle,
    price_oracle,
    pyth_oracle,
    pyth_solana_oracle,
    redstone_oracle,
)

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
    chainlink_sources = [
        {
            "name": f"chainlink_{chain}",
            "type": "on_chain_oracle",
            "chain": chain,
            "endpoint": CHAIN_RPC_URLS[chain][0],
            "feeds": chainlink_oracle.symbols_for(chain),
            "update_frequency": "~1h heartbeat or 0.5% deviation",
            "circuit_breaker": None,
        }
        for chain in chainlink_oracle.SUPPORTED_CHAINS
    ]
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
                *chainlink_sources,
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
                {
                    "name": "redstone",
                    "type": "rest_oracle",
                    "endpoint": redstone_oracle.REDSTONE_URL,
                    "provider": redstone_oracle.REDSTONE_PROVIDER,
                    "coverage_note": (
                        "Dynamic coverage — RedStone publishes 400+ assets "
                        "(crypto majors + long-tail + forex + equities). "
                        "Symbols are attempted on demand; unknown symbols "
                        "return a 404."
                    ),
                    "circuit_breaker": redstone_oracle.get_metrics()["circuit"],
                },
                {
                    "name": "pyth_solana",
                    "type": "on_chain_oracle",
                    "chain": "solana",
                    "program": pyth_solana_oracle.PUSH_ORACLE_PROGRAM_ID,
                    "shard": 0,
                    "feeds": pyth_solana_oracle.list_supported_symbols(),
                    "coverage_note": (
                        "On-chain read of Pyth Price Feed Accounts (shard 0 "
                        "sponsored by the Pyth Data Association). Verified "
                        "with full Wormhole guardian signatures. Stale > 60s "
                        "is flagged."
                    ),
                    "circuit_breaker": pyth_solana_oracle.get_metrics()["circuit"],
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
    chainlink_by_chain = chainlink_oracle.all_supported_symbols()
    price_oracle_mints = sorted(price_oracle.TOKEN_MINTS.keys())
    pyth_solana_syms = pyth_solana_oracle.list_supported_symbols()

    chainlink_union: set[str] = set()
    for syms in chainlink_by_chain.values():
        chainlink_union.update(syms)

    all_symbols = sorted(
        set(pyth_crypto)
        | set(pyth_equity)
        | chainlink_union
        | set(price_oracle_mints)
        | set(pyth_solana_syms)
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
                "redstone": [],
                "pyth_solana": pyth_solana_syms,
            },
            "coverage_notes": {
                "redstone": (
                    "Dynamic coverage — RedStone supports 400+ assets, "
                    "attempted on demand. See https://app.redstone.finance "
                    "for the live list."
                ),
                "pyth_solana": (
                    "On-chain Solana read, shard 0 sponsored feeds only. "
                    "Coverage is the curated list above -- any other symbol "
                    "returns 404 on /api/pyth/solana/{symbol}."
                ),
            },
        }
    )
