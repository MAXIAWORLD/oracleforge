"""LangChain tool wrappers for the MAXIA Oracle Python SDK.

Each tool subclasses :class:`langchain_core.tools.BaseTool` and delegates
to a shared :class:`maxia_oracle.MaxiaOracleClient` instance. The thirteen
tools exposed here mirror the MCP tools of the MAXIA Oracle server
and the non-register methods of the Python SDK.

The tools are deliberately synchronous. ``BaseTool`` falls back to running
``_run`` in a thread for ``ainvoke``, which is correct for the blocking
httpx client underneath.

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

import json
import os
from typing import Any, Final

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Literal

from maxia_oracle import MaxiaOracleClient

DISCLAIMER: Final[str] = (
    "Data feed only. Not investment advice. No custody. No KYC."
)

# V1.1: EVM chains supported by the Chainlink on-chain reader.
ChainLiteral = Literal["base", "ethereum", "arbitrum"]

# V1.5: EVM chains supported by the Uniswap v3 TWAP reader.
TwapChainLiteral = Literal["base", "ethereum"]


def _fmt(data: Any) -> str:
    """Render an SDK response as a compact JSON string for the LLM."""
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, ensure_ascii=False)
    return str(data)


# ── Pydantic input schemas ─────────────────────────────────────────────────


class SymbolInput(BaseModel):
    """Single asset ticker input."""

    symbol: str = Field(
        description=(
            "Asset ticker, 1 to 10 uppercase alphanumeric characters "
            "(e.g. 'BTC', 'ETH', 'SOL', 'AAPL')."
        ),
    )


class SymbolsBatchInput(BaseModel):
    """Batch input with a list of asset tickers, 1 to 50 items."""

    symbols: list[str] = Field(
        description=(
            "List of 1 to 50 asset ticker symbols, each 1 to 10 uppercase "
            "alphanumeric characters."
        ),
        min_length=1,
        max_length=50,
    )


class EmptyInput(BaseModel):
    """No input required."""


class ChainlinkInput(BaseModel):
    """Single-asset Chainlink input with optional EVM chain selector (V1.1)."""

    symbol: str = Field(
        description=(
            "Asset ticker, 1 to 10 uppercase alphanumeric characters "
            "(e.g. 'BTC', 'ETH', 'USDC')."
        ),
    )
    chain: ChainLiteral = Field(
        default="base",
        description=(
            "EVM chain on which to read the Chainlink feed. One of "
            "'base' (default, for backward compatibility), 'ethereum', "
            "or 'arbitrum'."
        ),
    )


class TwapInput(BaseModel):
    """Single-asset Uniswap v3 TWAP input with chain + window (V1.5)."""

    symbol: str = Field(
        description=(
            "Asset ticker, 1 to 10 uppercase alphanumeric characters "
            "(e.g. 'ETH', 'BTC')."
        ),
    )
    chain: TwapChainLiteral = Field(
        default="ethereum",
        description="EVM chain on which to read the Uniswap v3 pool.",
    )
    window_s: int = Field(
        default=1800,
        ge=60,
        le=86400,
        description=(
            "TWAP window in seconds. Default 1800 (30 min), range 60-86400."
        ),
    )


# ── Tool base class ────────────────────────────────────────────────────────


class _MaxiaOracleTool(BaseTool):
    """Shared base: holds the optional ``MaxiaOracleClient`` instance.

    The client is a plain ``Any`` field so that pydantic-v2 does not try
    to validate ``MaxiaOracleClient`` — it is injected at construction
    time by ``get_all_tools`` or built lazily from env vars.
    """

    client: Any = None

    def _get_client(self) -> MaxiaOracleClient:
        if self.client is None:
            self.client = MaxiaOracleClient(
                api_key=os.environ.get("MAXIA_ORACLE_API_KEY"),
                base_url=os.environ.get("MAXIA_ORACLE_BASE_URL"),
            )
        return self.client


# ── Tool implementations (8 tools) ─────────────────────────────────────────


class MaxiaOracleGetPriceTool(_MaxiaOracleTool):
    """Cross-validated multi-source live price for a single asset."""

    name: str = "maxia_oracle_get_price"
    description: str = (
        "Return a cross-validated multi-source live price for a single asset. "
        "Queries Pyth, Chainlink and the aggregator in parallel, computes the "
        "median and the inter-source divergence in percent. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().price(symbol))


class MaxiaOracleGetPricesBatchTool(_MaxiaOracleTool):
    """Batched live prices for up to 50 symbols in one upstream call."""

    name: str = "maxia_oracle_get_prices_batch"
    description: str = (
        "Return live prices for up to 50 symbols in a single upstream batch "
        "call via the Pyth Hermes endpoint. Dramatically cheaper than issuing "
        "one get_price per symbol. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolsBatchInput

    def _run(self, symbols: list[str]) -> str:
        return _fmt(self._get_client().prices_batch(symbols))


class MaxiaOracleGetSourcesStatusTool(_MaxiaOracleTool):
    """Liveness probe across all upstream oracle sources."""

    name: str = "maxia_oracle_get_sources_status"
    description: str = (
        "Probe each upstream oracle source (Pyth, Chainlink, aggregator) and "
        "report up/down status. Liveness probe only — does not validate the "
        "correctness of returned prices. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = EmptyInput

    def _run(self) -> str:
        return _fmt(self._get_client().sources())


class MaxiaOracleGetCacheStatsTool(_MaxiaOracleTool):
    """Aggregator cache hit rate and circuit-breaker state."""

    name: str = "maxia_oracle_get_cache_stats"
    description: str = (
        "Return the aggregator in-memory cache hit rate and circuit-breaker "
        "state. Debug tool for agents that want to introspect their own "
        "latency amplification. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = EmptyInput

    def _run(self) -> str:
        return _fmt(self._get_client().cache_stats())


class MaxiaOracleGetConfidenceTool(_MaxiaOracleTool):
    """Compact multi-source divergence metric for a symbol."""

    name: str = "maxia_oracle_get_confidence"
    description: str = (
        "Return the multi-source divergence for a symbol as a compact metric "
        "('do the sources agree?') without the per-source price breakdown. "
        "Lighter than get_price when only the agreement signal is needed. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().confidence(symbol))


class MaxiaOracleListSupportedSymbolsTool(_MaxiaOracleTool):
    """Full list of supported assets grouped by upstream source."""

    name: str = "maxia_oracle_list_supported_symbols"
    description: str = (
        "Return the union of all asset symbols supported by MAXIA Oracle, "
        "grouped by source (Pyth crypto, Pyth equity, Chainlink Base, "
        "aggregator). No upstream calls — cheap metadata read. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = EmptyInput

    def _run(self) -> str:
        return _fmt(self._get_client().list_symbols())


class MaxiaOracleGetChainlinkOnchainTool(_MaxiaOracleTool):
    """Single-source price straight from a Chainlink feed on Base / Ethereum / Arbitrum."""

    name: str = "maxia_oracle_get_chainlink_onchain"
    description: str = (
        "Fetch a single-source price directly from a Chainlink on-chain "
        "feed on the requested EVM chain (base, ethereum, or arbitrum). "
        "Independently verifiable on-chain; useful to cross-check the "
        "median returned by get_price or to see the exact value a smart "
        "contract on that chain will read. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = ChainlinkInput

    def _run(self, symbol: str, chain: str = "base") -> str:
        return _fmt(self._get_client().chainlink_onchain(symbol, chain=chain))


class MaxiaOracleGetRedstoneTool(_MaxiaOracleTool):
    """V1.3 — Single-source price from the RedStone public REST API."""

    name: str = "maxia_oracle_get_redstone_price"
    description: str = (
        "Fetch a single-source price from the RedStone public REST API (V1.3). "
        "RedStone is the 4th independent upstream in MAXIA Oracle, covering "
        "400+ assets (crypto majors, long-tail, forex, equities). Useful to "
        "cross-check the multi-source median. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().redstone(symbol))


class MaxiaOracleGetPythSolanaTool(_MaxiaOracleTool):
    """V1.4 — Single-source Pyth on-chain Solana read (shard 0 sponsored feeds)."""

    name: str = "maxia_oracle_get_pyth_solana_onchain"
    description: str = (
        "Fetch a single-source Pyth price directly from a Solana mainnet "
        "Price Feed Account (V1.4, shard 0 sponsored feeds). Only fully "
        "Wormhole-verified updates are returned. Coverage: BTC, ETH, SOL, "
        "USDT, USDC, WIF, BONK, PYTH, JTO, JUP, RAY, EUR, GBP. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().pyth_solana(symbol))


class MaxiaOracleGetTwapTool(_MaxiaOracleTool):
    """V1.5 — Uniswap v3 time-weighted average price (TWAP) on-chain."""

    name: str = "maxia_oracle_get_twap_onchain"
    description: str = (
        "Fetch a Uniswap v3 time-weighted average price (TWAP) on-chain "
        "(V1.5). Reads curated high-liquidity pools on Base or Ethereum "
        "with a caller-chosen window (60 s to 24 h, default 30 min). "
        "Coverage: ETH on base/ethereum, BTC on ethereum. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = TwapInput

    def _run(self, symbol: str, chain: str = "ethereum", window_s: int = 1800) -> str:
        return _fmt(self._get_client().twap(symbol, chain=chain, window_s=window_s))


class MaxiaOracleGetPriceContextTool(_MaxiaOracleTool):
    """V1.6 — Price + confidence score + anomaly flag + sources agreement."""

    name: str = "maxia_oracle_get_price_context"
    description: str = (
        "Return price + confidence score (0-100) + anomaly flag + sources "
        "agreement in one call (V1.6). Agent-native: everything an LLM "
        "agent needs to decide whether to act on a price. Includes TWAP "
        "deviation, source outliers, and anomaly reasons. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().price_context(symbol))


class MaxiaOracleHealthCheckTool(_MaxiaOracleTool):
    """Minimal liveness probe on the MAXIA Oracle backend."""

    name: str = "maxia_oracle_health_check"
    description: str = (
        "Minimal liveness probe for the MAXIA Oracle backend. Does not touch "
        "upstream sources — cheap enough for monitoring agents to call every "
        "few seconds. "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = EmptyInput

    def _run(self) -> str:
        return _fmt(self._get_client().health())


class MaxiaOracleGetMetadataTool(_MaxiaOracleTool):
    """V1.7 — CoinGecko asset metadata (market cap, volume, supply, rank, ATH/ATL)."""

    name: str = "maxia_oracle_get_metadata"
    description: str = (
        "Fetch asset metadata from CoinGecko (market cap, volume, supply, rank, ATH/ATL). "
        + DISCLAIMER
    )
    args_schema: type[BaseModel] = SymbolInput

    def _run(self, symbol: str) -> str:
        return _fmt(self._get_client().metadata(symbol))


# ── Convenience factory ────────────────────────────────────────────────────


MAXIA_ORACLE_TOOL_CLASSES: Final[tuple[type[_MaxiaOracleTool], ...]] = (
    MaxiaOracleGetPriceTool,
    MaxiaOracleGetPricesBatchTool,
    MaxiaOracleGetSourcesStatusTool,
    MaxiaOracleGetCacheStatsTool,
    MaxiaOracleGetConfidenceTool,
    MaxiaOracleListSupportedSymbolsTool,
    MaxiaOracleGetChainlinkOnchainTool,
    MaxiaOracleGetRedstoneTool,
    MaxiaOracleGetPythSolanaTool,
    MaxiaOracleGetTwapTool,
    MaxiaOracleGetPriceContextTool,
    MaxiaOracleHealthCheckTool,
    MaxiaOracleGetMetadataTool,
)


def get_all_tools(
    api_key: str | None = None,
    base_url: str | None = None,
    client: MaxiaOracleClient | None = None,
) -> list[BaseTool]:
    """Instantiate the 8 MAXIA Oracle tools around a single shared client.

    Parameters
    ----------
    api_key:
        MAXIA Oracle API key (``mxo_...``). Ignored if ``client`` is given.
        Falls back to the ``MAXIA_ORACLE_API_KEY`` environment variable.
    base_url:
        Backend base URL. Ignored if ``client`` is given. Falls back to
        ``MAXIA_ORACLE_BASE_URL`` or the SDK default
        (``https://oracle.maxiaworld.app``).
    client:
        Pre-built :class:`maxia_oracle.MaxiaOracleClient` instance. Takes
        precedence over ``api_key``/``base_url`` — use this when you want
        to inject a mock or a custom transport.

    Returns
    -------
    list[BaseTool]
        All 13 MAXIA Oracle tools, ready to pass to a LangChain agent.
    """
    shared = client if client is not None else MaxiaOracleClient(
        api_key=api_key,
        base_url=base_url,
    )
    return [cls(client=shared) for cls in MAXIA_ORACLE_TOOL_CLASSES]
