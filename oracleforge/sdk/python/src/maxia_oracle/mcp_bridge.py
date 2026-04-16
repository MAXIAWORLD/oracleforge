"""MAXIA Oracle SDK — stdio MCP bridge for Claude Desktop / Cursor / Zed.

Exposes the 8 V1 MAXIA Oracle MCP tools to any MCP client that speaks
stdio, by forwarding each `tools/call` to the remote REST API via the
`MaxiaOracleClient`. This is what `pip install maxia-oracle` ships as
the `maxia-oracle-mcp` entry point — install once, configure Claude
Desktop, and the tools appear natively with no backend to run locally.

The design goal is exact parity with the Phase 5 stdio server that
lives inside `oracleforge/backend/mcp_server/` — same 8 tools, same
JSON schemas, same `isError=True` propagation. The only difference is
the transport between the tool handler and the oracle service: the
backend server calls Python functions directly, the SDK bridge sends
HTTP requests.

Configuration:

    MAXIA_ORACLE_API_KEY    Required. Register one at
                            https://oracle.maxiaworld.app/api/register
    MAXIA_ORACLE_BASE_URL   Optional. Defaults to
                            https://oracle.maxiaworld.app. Set this to
                            http://127.0.0.1:8003 for a local backend.

Claude Desktop config snippet:

    {
      "mcpServers": {
        "maxia-oracle": {
          "command": "maxia-oracle-mcp",
          "env": {
            "MAXIA_ORACLE_API_KEY": "mxo_..."
          }
        }
      }
    }

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Awaitable, Callable, Final

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .client import MaxiaOracleClient
from .exceptions import (
    MaxiaOracleAuthError,
    MaxiaOracleError,
    MaxiaOracleRateLimitError,
    MaxiaOracleTransportError,
    MaxiaOracleUpstreamError,
    MaxiaOracleValidationError,
)

SERVER_NAME = "maxia-oracle"
SERVER_VERSION = "0.1.0"
SERVER_INSTRUCTIONS = (
    "MAXIA Oracle exposes multi-source crypto and equity price feeds as MCP "
    "tools. Data feed only. Not investment advice. No custody. No KYC."
)

_DISCLAIMER_LINE: Final[str] = (
    "Data feed only. Not investment advice. No custody. No KYC."
)

_SYMBOL_SCHEMA: Final[dict[str, Any]] = {
    "type": "string",
    "pattern": "^[A-Z0-9]{1,10}$",
    "description": (
        "Asset ticker, 1 to 10 uppercase alphanumeric characters "
        "(e.g. 'BTC', 'ETH', 'SOL', 'AAPL')."
    ),
}


def _tool_definitions() -> list[types.Tool]:
    """Return the 8 V1 tool definitions with strict JSON schemas.

    Kept in sync with `oracleforge/backend/mcp_server/server.py` — the
    two servers expose the same surface so switching between them is
    transparent for the MCP client.
    """
    return [
        types.Tool(
            name="get_price",
            description=(
                "Return a cross-validated multi-source live price for a "
                "single asset. Queries Pyth, Chainlink and the aggregator "
                "in parallel, computes the median and the inter-source "
                "divergence in percent. " + _DISCLAIMER_LINE
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
                "Return live prices for up to 50 symbols in a single "
                "upstream batch call via the Pyth Hermes endpoint. "
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
                "Probe each upstream oracle source and report up/down "
                "status. Liveness probe only. " + _DISCLAIMER_LINE
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
                "Return the aggregator in-memory cache hit rate and "
                "circuit-breaker state. " + _DISCLAIMER_LINE
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
                "Return the multi-source divergence for a symbol as a "
                "compact metric ('do the sources agree?') without the "
                "per-source breakdown. " + _DISCLAIMER_LINE
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
                "Return the union of all asset symbols supported by "
                "MAXIA Oracle, grouped by source. " + _DISCLAIMER_LINE
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
                "Fetch a single-source price directly from a Chainlink "
                "on-chain feed on the requested EVM chain (base, ethereum, "
                "or arbitrum). Independently verifiable on-chain. "
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
            name="health_check",
            description=(
                "Minimal liveness probe for the MAXIA Oracle backend. "
                + _DISCLAIMER_LINE
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
    ]


def _error_result(payload: dict[str, Any]) -> types.CallToolResult:
    """Wrap an error dict as a CallToolResult with isError=True."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        isError=True,
    )


def _build_dispatch(
    client: MaxiaOracleClient,
) -> dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]:
    """Build an async dispatch table over the sync client.

    Every entry runs the sync HTTP call in a worker thread via
    `asyncio.to_thread` so the MCP event loop is never blocked on a
    network round-trip.
    """

    async def get_price(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.price, args["symbol"])

    async def get_prices_batch(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.prices_batch, args["symbols"])

    async def get_sources_status(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.sources)

    async def get_cache_stats(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.cache_stats)

    async def get_confidence(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.confidence, args["symbol"])

    async def list_supported_symbols(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.list_symbols)

    async def get_chainlink_onchain(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(
            client.chainlink_onchain,
            args["symbol"],
            args.get("chain", "base"),
        )

    async def health_check(args: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(client.health)

    return {
        "get_price": get_price,
        "get_prices_batch": get_prices_batch,
        "get_sources_status": get_sources_status,
        "get_cache_stats": get_cache_stats,
        "get_confidence": get_confidence,
        "list_supported_symbols": list_supported_symbols,
        "get_chainlink_onchain": get_chainlink_onchain,
        "health_check": health_check,
    }


def build_bridge_server(client: MaxiaOracleClient) -> Server:
    """Create an MCP server that forwards every tool call to the REST backend."""
    server: Server = Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
    )
    tool_defs = _tool_definitions()
    dispatch = _build_dispatch(client)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list(tool_defs)

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | types.CallToolResult:
        handler = dispatch.get(name)
        if handler is None:
            return _error_result({"error": f"unknown tool: {name}"})

        try:
            result = await handler(arguments or {})
        except MaxiaOracleAuthError as exc:
            return _error_result(
                {
                    "error": "authentication failed",
                    "detail": str(exc),
                    "hint": "set MAXIA_ORACLE_API_KEY or call POST /api/register",
                }
            )
        except MaxiaOracleRateLimitError as exc:
            return _error_result(
                {
                    "error": "rate limit exceeded",
                    "detail": str(exc),
                    "retry_after_seconds": exc.retry_after_seconds,
                    "limit": exc.limit,
                }
            )
        except MaxiaOracleValidationError as exc:
            return _error_result(
                {"error": "validation error", "detail": str(exc)}
            )
        except MaxiaOracleUpstreamError as exc:
            return _error_result(
                {"error": "upstream unavailable", "detail": str(exc)}
            )
        except MaxiaOracleTransportError as exc:
            return _error_result(
                {"error": "transport error", "detail": str(exc)}
            )
        except MaxiaOracleError as exc:
            return _error_result({"error": "maxia oracle error", "detail": str(exc)})

        if isinstance(result, dict) and "error" in result:
            return _error_result(result)
        return result

    return server


async def _run() -> None:
    base_url = os.environ.get("MAXIA_ORACLE_BASE_URL")
    api_key = os.environ.get("MAXIA_ORACLE_API_KEY")
    if not api_key:
        print(
            "[maxia-oracle-mcp] MAXIA_ORACLE_API_KEY is not set. "
            "Register a free key via POST /api/register on the backend, "
            "then pass it in the MCP client `env` block.",
            file=sys.stderr,
        )

    with MaxiaOracleClient(api_key=api_key, base_url=base_url) as client:
        server = build_bridge_server(client)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


def main() -> None:
    """Console-script entry point for `maxia-oracle-mcp`."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
