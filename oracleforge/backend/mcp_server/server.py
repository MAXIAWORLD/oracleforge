"""MAXIA Oracle — MCP server instance and tool registration.

Creates the `mcp.server.lowlevel.Server` instance, registers the 17 tools
declared in `tools.py`, and exposes a `build_server()` factory that both the
stdio entry point (`__main__.py`) and the HTTP SSE transport
(`api/routes_mcp.py`) reuse.

The factory returns a fresh server on each call so that two different
transports can run side by side without sharing internal state.

Return contract (aligned with `tools.py`):
    - Tool functions return a plain `dict`. The `lowlevel` framework wraps it
      into a `CallToolResult` with `TextContent` + `structuredContent`
      automatically and `isError=False`.
    - When a tool dict contains an `"error"` key, this module rebuilds the
      result as `CallToolResult(isError=True, ...)` so MCP clients
      (Claude Desktop, Cursor, Zed) can visually distinguish failures.
    - Unknown tool names and arity mismatches also surface as `isError=True`
      with a JSON-encoded error body.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from mcp import types
from mcp.server.lowlevel import Server

from . import tools

SERVER_NAME = "maxia-oracle"
SERVER_VERSION = "0.1.9"
SERVER_INSTRUCTIONS = (
    "MAXIA Oracle exposes multi-source crypto and equity price feeds as MCP tools. "
    "Each result is a read-only live data point intended for AI agents that need "
    "market data from Pyth, Chainlink and aggregator sources. "
    "Data feed only. Not investment advice. No custody. No KYC."
)

_DISCLAIMER_LINE = "Data feed only. Not investment advice. No custody. No KYC."

_SYMBOL_SCHEMA: dict[str, Any] = {
    "type": "string",
    "pattern": "^[A-Z0-9]{1,10}$",
    "description": (
        "Asset ticker, 1 to 10 uppercase alphanumeric characters "
        "(e.g. 'BTC', 'ETH', 'SOL', 'AAPL')."
    ),
}


_TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="get_price",
        description=(
            "Return a cross-validated multi-source live price for a single asset. "
            "Queries Pyth, Chainlink and the aggregator in parallel, computes the "
            "median and the inter-source divergence in percent. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_prices_batch",
        description=(
            "Return live prices for up to 50 symbols in a single upstream batch "
            "call via the Pyth Hermes endpoint. Dramatically cheaper than issuing "
            "one get_price per symbol. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": _SYMBOL_SCHEMA,
                    "minItems": 1,
                    "maxItems": 50,
                    "description": "List of 1 to 50 asset ticker symbols.",
                },
            },
            "required": ["symbols"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_sources_status",
        description=(
            "Probe each upstream oracle source (Pyth, Chainlink, aggregator) with "
            "BTC and report up/down status. Liveness probe only — does not "
            "validate correctness of returned prices. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_cache_stats",
        description=(
            "Return the aggregator in-memory cache hit rate and circuit-breaker "
            "state. Debug tool for agents that want to introspect their own "
            "latency amplification. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_confidence",
        description=(
            "Return the multi-source divergence for a symbol as a compact metric "
            "('do the sources agree?') without the per-source price breakdown. "
            "Lighter than get_price when only the agreement signal is needed. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="list_supported_symbols",
        description=(
            "Return the union of all asset symbols supported by MAXIA Oracle, "
            "grouped by source (Pyth crypto, Pyth equity, Chainlink Base, "
            "aggregator). "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_chainlink_onchain",
        description=(
            "Fetch a single-source price directly from a Chainlink on-chain "
            "feed on the requested EVM chain (base, ethereum, or arbitrum). "
            "Independently verifiable on-chain; useful to cross-check the "
            "median returned by get_price or to see the exact value a "
            "smart contract on that chain will read. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": _SYMBOL_SCHEMA,
                "chain": {
                    "type": "string",
                    "enum": ["base", "ethereum", "arbitrum"],
                    "default": "base",
                    "description": (
                        "EVM chain on which to read the Chainlink feed. "
                        "Defaults to 'base' for backward compatibility."
                    ),
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_redstone_price",
        description=(
            "Fetch a single-source price directly from the RedStone public "
            "REST API (V1.3). RedStone covers 400+ assets (crypto majors, "
            "long-tail, forex, equities) and is the 4th independent upstream "
            "in the MAXIA Oracle pipeline. Useful to cross-check the median "
            "returned by get_price. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_pyth_solana_onchain",
        description=(
            "Fetch a single-source price directly from a Pyth on-chain price "
            "feed account on Solana mainnet (V1.4, shard 0 sponsored feeds). "
            "Reads the PriceUpdateV2 account maintained by the Pyth Push "
            "Oracle program and rejects updates that are not fully verified "
            "by the Wormhole guardian set. Coverage is limited to the curated "
            "majors (BTC, ETH, SOL, USDT, USDC, WIF, BONK, PYTH, JTO, JUP, "
            "RAY, EUR, GBP). "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_twap_onchain",
        description=(
            "Fetch a Uniswap v3 time-weighted average price (TWAP) read "
            "directly from a curated high-liquidity pool on Base or "
            "Ethereum mainnet (V1.5). Default 30-minute window, configurable "
            "from 60 s to 24 h. Returns an independently verifiable number: "
            "any caller can replay observe() on the same pool to reproduce it. "
            "Coverage: ETH on base/ethereum, BTC on ethereum. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": _SYMBOL_SCHEMA,
                "chain": {
                    "type": "string",
                    "enum": ["base", "ethereum"],
                    "default": "ethereum",
                    "description": (
                        "EVM chain on which to read the Uniswap v3 pool."
                    ),
                },
                "window_s": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 86400,
                    "default": 1800,
                    "description": (
                        "TWAP window in seconds. Default 1800 (30 minutes)."
                    ),
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_price_context",
        description=(
            "Return price + confidence score (0-100) + anomaly flag + sources "
            "agreement in one call (V1.6). Agent-native: everything an LLM "
            "agent needs to decide whether to act on a price. Includes TWAP "
            "deviation, source outliers, and anomaly reasons. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_asset_metadata",
        description=(
            "Fetch asset metadata from CoinGecko: market cap, 24h volume, "
            "circulating supply, total supply, max supply, market cap rank, "
            "ATH, ATL, and 24h price change. Coverage: ~80 crypto assets "
            "with CoinGecko mapping. Forex and equities are not covered. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {"symbol": _SYMBOL_SCHEMA},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_price_history",
        description=(
            "Return historical price snapshots for a symbol (V1.8). "
            "The background sampler captures prices every 5 minutes. "
            "Data is downsampled to the requested interval via averaging. "
            "Retention: 30 days. Ranges: 24h, 7d, 30d. "
            "Intervals: 5m, 1h, 1d (auto-selected if omitted). "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": _SYMBOL_SCHEMA,
                "range": {
                    "type": "string",
                    "enum": ["24h", "7d", "30d"],
                    "default": "24h",
                    "description": "Time range for history. Defaults to '24h'.",
                },
                "interval": {
                    "type": "string",
                    "enum": ["5m", "1h", "1d"],
                    "description": (
                        "Bucket interval for downsampling. "
                        "Auto-selected if omitted: 24h→5m, 7d→1h, 30d→1d."
                    ),
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="create_price_alert",
        description=(
            "Create a one-shot price alert with a webhook callback (V1.9). "
            "The alert fires once when the condition is met (checked every "
            "~5 min), POSTs to callback_url, then deactivates. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": _SYMBOL_SCHEMA,
                "condition": {
                    "type": "string",
                    "enum": ["above", "below"],
                    "description": "Trigger when price goes 'above' or 'below' the threshold.",
                },
                "threshold": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Price threshold that triggers the alert.",
                },
                "callback_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "HTTPS webhook URL to POST when triggered.",
                },
            },
            "required": ["symbol", "condition", "threshold", "callback_url"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="list_price_alerts",
        description=(
            "List all price alerts for the current session (V1.9). "
            "Shows both active and triggered alerts. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="delete_price_alert",
        description=(
            "Delete a price alert by its id (V1.9). "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "alert_id": {
                    "type": "integer",
                    "description": "The id of the alert to delete.",
                },
            },
            "required": ["alert_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="health_check",
        description=(
            "Minimal liveness probe for the MAXIA Oracle MCP server. Does not "
            "touch upstream sources — meant to be cheap enough for monitoring "
            "agents to call every few seconds. "
            + _DISCLAIMER_LINE
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
]


_ToolHandler = Callable[..., Awaitable[dict[str, Any]]]

_TOOL_DISPATCH: dict[str, _ToolHandler] = {
    "get_price": tools.get_price,
    "get_prices_batch": tools.get_prices_batch,
    "get_sources_status": tools.get_sources_status,
    "get_cache_stats": tools.get_cache_stats,
    "get_confidence": tools.get_confidence,
    "list_supported_symbols": tools.list_supported_symbols,
    "get_chainlink_onchain": tools.get_chainlink_onchain,
    "get_redstone_price": tools.get_redstone_price,
    "get_pyth_solana_onchain": tools.get_pyth_solana_onchain,
    "get_twap_onchain": tools.get_twap_onchain,
    "get_price_context": tools.get_price_context,
    "get_asset_metadata": tools.get_asset_metadata,
    "get_price_history": tools.get_price_history,
    "create_price_alert": tools.create_price_alert,
    "list_price_alerts": tools.list_price_alerts,
    "delete_price_alert": tools.delete_price_alert,
    "health_check": tools.health_check,
}


def _error_result(payload: dict[str, Any]) -> types.CallToolResult:
    """Wrap an error dict in a CallToolResult with isError=True.

    MCP clients use isError to visually distinguish tool failures from
    successful responses; keeping the payload as JSON text preserves the
    full error context for the agent.
    """
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        isError=True,
    )


def build_server(rate_limit_key_hash: str | None = None) -> Server:
    """Create a fresh MCP server instance with all 17 tools registered.

    Args:
        rate_limit_key_hash: If provided, every `tools/call` invocation
            counts against the Phase 3 daily quota (100 req/day per key)
            via `core.rate_limit.check_daily`. Meant for the HTTP SSE
            transport, where each connected agent is authenticated by its
            `X-API-Key`. The stdio transport calls `build_server()` without
            this argument so that local installs run with no quota.
    """
    server: Server = Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list(_TOOL_DEFINITIONS)

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | types.CallToolResult:
        if rate_limit_key_hash is not None:
            # Imported lazily so stdio installs that never touch the daily
            # quota do not pay the SQLite bootstrap cost on import.
            from core.db import get_db
            from core.rate_limit import check_daily

            decision = check_daily(get_db(), rate_limit_key_hash)
            if not decision.allowed:
                return _error_result(
                    {
                        "error": "rate limit exceeded",
                        "limit": decision.limit,
                        "window_s": decision.window_s,
                        "retry_after_s": decision.retry_after,
                        "reset_at": decision.reset_at,
                    }
                )

        handler = _TOOL_DISPATCH.get(name)
        if handler is None:
            return _error_result({"error": f"unknown tool: {name}"})

        try:
            result = await handler(**(arguments or {}))
        except TypeError:
            return _error_result({"error": "invalid arguments"})

        if isinstance(result, dict) and "error" in result:
            return _error_result(result)

        return result

    return server
