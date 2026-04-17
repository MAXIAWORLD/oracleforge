"""LlamaIndex (``llama-index-core``) tool wrappers for the MAXIA Oracle SDK.

LlamaIndex 0.11+ exposes tools via :class:`llama_index.core.tools.FunctionTool`,
which takes a plain Python callable and introspects its signature to build
a JSON schema. We build thirteen ``FunctionTool`` instances — one per MAXIA
Oracle SDK method — each closing over a shared
:class:`maxia_oracle.MaxiaOracleClient` instance.

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

import json
import os
from typing import Any, Final

from llama_index.core.tools import FunctionTool

from maxia_oracle import MaxiaOracleClient

DISCLAIMER: Final[str] = (
    "Data feed only. Not investment advice. No custody. No KYC."
)

TOOL_NAMES: Final[tuple[str, ...]] = (
    "maxia_oracle_get_price",
    "maxia_oracle_get_prices_batch",
    "maxia_oracle_get_sources_status",
    "maxia_oracle_get_cache_stats",
    "maxia_oracle_get_confidence",
    "maxia_oracle_list_supported_symbols",
    "maxia_oracle_get_chainlink_onchain",
    "maxia_oracle_get_redstone_price",
    "maxia_oracle_get_pyth_solana_onchain",
    "maxia_oracle_get_twap_onchain",
    "maxia_oracle_get_price_context",
    "maxia_oracle_health_check",
    "maxia_oracle_get_metadata",
)


def _fmt(data: Any) -> str:
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, ensure_ascii=False)
    return str(data)


def _default_client() -> MaxiaOracleClient:
    return MaxiaOracleClient(
        api_key=os.environ.get("MAXIA_ORACLE_API_KEY"),
        base_url=os.environ.get("MAXIA_ORACLE_BASE_URL"),
    )


def get_all_tools(
    api_key: str | None = None,
    base_url: str | None = None,
    client: MaxiaOracleClient | None = None,
) -> list[FunctionTool]:
    """Instantiate the 13 MAXIA Oracle tools around a single shared client.

    Each returned :class:`FunctionTool` closes over the same client so
    that the httpx connection pool is reused across tool calls.

    Parameters
    ----------
    api_key:
        MAXIA Oracle API key (``mxo_...``). Ignored if ``client`` is given.
    base_url:
        Backend base URL. Ignored if ``client`` is given.
    client:
        Pre-built :class:`maxia_oracle.MaxiaOracleClient` instance.
    """
    shared = client if client is not None else (
        MaxiaOracleClient(api_key=api_key, base_url=base_url)
        if api_key is not None or base_url is not None
        else _default_client()
    )

    def maxia_oracle_get_price(symbol: str) -> str:
        """Return a cross-validated multi-source live price for a single asset.

        Queries Pyth, Chainlink and the aggregator in parallel, computes the
        median and the inter-source divergence in percent.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.price(symbol))

    def maxia_oracle_get_prices_batch(symbols: list[str]) -> str:
        """Return live prices for up to 50 symbols in a single upstream call.

        Uses the Pyth Hermes batch endpoint. Dramatically cheaper than
        issuing one get_price per symbol.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.prices_batch(symbols))

    def maxia_oracle_get_sources_status() -> str:
        """Probe each upstream oracle source and report up/down status.

        Liveness probe only — does not validate the correctness of prices.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.sources())

    def maxia_oracle_get_cache_stats() -> str:
        """Return the aggregator cache hit rate and circuit-breaker state.

        Debug tool for agents that want to introspect their own latency
        amplification.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.cache_stats())

    def maxia_oracle_get_confidence(symbol: str) -> str:
        """Return the multi-source divergence for a symbol as a compact metric.

        ('do the sources agree?') without the per-source price breakdown.
        Lighter than get_price when only the agreement signal is needed.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.confidence(symbol))

    def maxia_oracle_list_supported_symbols() -> str:
        """Return the union of asset symbols supported by MAXIA Oracle.

        Grouped by source (Pyth crypto, Pyth equity, Chainlink Base,
        aggregator). No upstream calls — cheap metadata read.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.list_symbols())

    def maxia_oracle_get_chainlink_onchain(symbol: str, chain: str = "base") -> str:
        """Fetch a single-source price directly from a Chainlink on-chain feed.

        V1.1: accepts chain = 'base' (default), 'ethereum', or 'arbitrum'.
        Independently verifiable on-chain via the corresponding EVM RPC.
        Useful to cross-check the median returned by get_price or to see
        the exact value a smart contract on that chain will read.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.chainlink_onchain(symbol, chain=chain))

    def maxia_oracle_get_redstone_price(symbol: str) -> str:
        """V1.3 — Single-source RedStone REST price.

        RedStone is the 4th independent upstream in MAXIA Oracle (400+
        assets: crypto majors, long-tail, forex, equities). Useful to
        cross-check the multi-source median.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.redstone(symbol))

    def maxia_oracle_get_pyth_solana_onchain(symbol: str) -> str:
        """V1.4 -- Single-source Pyth on-chain Solana read (shard 0 sponsored).

        Reads a Pyth Price Feed Account on Solana mainnet directly (Push
        Oracle program, shard 0). Rejects partial Wormhole verifications.
        Coverage: BTC, ETH, SOL, USDT, USDC, WIF, BONK, PYTH, JTO, JUP,
        RAY, EUR, GBP.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.pyth_solana(symbol))

    def maxia_oracle_get_twap_onchain(
        symbol: str, chain: str = "ethereum", window_s: int = 1800,
    ) -> str:
        """V1.5 -- Uniswap v3 time-weighted average price on-chain.

        Reads a curated high-liquidity Uniswap v3 pool on `chain`
        ('base' or 'ethereum') and returns the TWAP over `window_s`
        seconds (default 1800 = 30 min, range 60-86400). Coverage:
        ETH on base/ethereum, BTC on ethereum.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.twap(symbol, chain=chain, window_s=window_s))

    def maxia_oracle_get_price_context(symbol: str) -> str:
        """Return price + confidence score (0-100) + anomaly flag + sources agreement in one call (V1.6). Agent-native: everything an LLM agent needs to decide whether to act on a price. Data feed only. Not investment advice. No custody. No KYC."""
        return _fmt(shared.price_context(symbol))

    def maxia_oracle_health_check() -> str:
        """Minimal liveness probe for the MAXIA Oracle backend.

        Does not touch upstream sources — cheap enough for monitoring
        agents to call every few seconds.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.health())

    def maxia_oracle_get_metadata(symbol: str) -> str:
        """V1.7 — Fetch asset metadata from CoinGecko.

        Returns market cap, 24h volume, circulating supply, market rank,
        all-time high (ATH) and all-time low (ATL) for the given symbol.
        Data feed only. Not investment advice. No custody. No KYC.
        """
        return _fmt(shared.metadata(symbol))

    callables = (
        maxia_oracle_get_price,
        maxia_oracle_get_prices_batch,
        maxia_oracle_get_sources_status,
        maxia_oracle_get_cache_stats,
        maxia_oracle_get_confidence,
        maxia_oracle_list_supported_symbols,
        maxia_oracle_get_chainlink_onchain,
        maxia_oracle_get_redstone_price,
        maxia_oracle_get_pyth_solana_onchain,
        maxia_oracle_get_twap_onchain,
        maxia_oracle_get_price_context,
        maxia_oracle_health_check,
        maxia_oracle_get_metadata,
    )

    return [
        FunctionTool.from_defaults(
            fn=func,
            name=func.__name__,
            description=(func.__doc__ or "").strip(),
        )
        for func in callables
    ]
