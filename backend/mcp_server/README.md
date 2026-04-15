# MAXIA Oracle — MCP Server

Spec-compliant [Model Context Protocol](https://modelcontextprotocol.io) server
exposing MAXIA Oracle's multi-source crypto and equity price feeds as native
tools for Claude Desktop, Cursor, Continue, Zed, and any other MCP client.

**Data feed only. Not investment advice. No custody. No KYC.**

## What this gives an agent

Eight tools that surface the MAXIA Oracle aggregator (Pyth, Chainlink on Base
mainnet, CoinPaprika, CoinGecko, Yahoo Finance, Helius DAS) directly inside
the agent's tool-use loop — no manual HTTP, no API wrappers to maintain:

| Tool | Purpose |
|---|---|
| `get_price(symbol)` | Cross-validated median price across every available source, with the per-source breakdown and the inter-source divergence in percent. |
| `get_prices_batch(symbols)` | Up to 50 symbols in a single upstream call via Pyth Hermes. Order-of-magnitude cheaper than N × `get_price`. |
| `get_sources_status()` | Liveness probe of every upstream source, using BTC as the probe ticker. |
| `get_cache_stats()` | Aggregator cache hit-rate and circuit-breaker state — lets an agent introspect its own latency amplification. |
| `get_confidence(symbol)` | Divergence metric only (without the per-source breakdown). Lighter than `get_price` when all you want is "do the sources agree?". |
| `list_supported_symbols()` | Union of all symbols supported, grouped by source (Pyth crypto, Pyth equity, Chainlink Base, aggregator). |
| `get_chainlink_onchain(symbol)` | Forces a single-source fetch from the Chainlink feed on Base mainnet. Independently verifiable on-chain. |
| `health_check()` | Minimal liveness probe. Cheap enough for monitoring agents to call every few seconds. |

Every successful response carries a mandatory disclaimer
(`"Data feed only. Not investment advice. No custody. No KYC."`). Every
error is surfaced as `isError: true` so the client can render it distinctly.

## Two ways to connect

### 1. Local — `stdio`

Best for installing MAXIA Oracle inside Claude Desktop, Cursor, Zed or any
MCP client that spawns child processes. Zero network, zero auth: the server
runs inside your own desktop session and calls the oracle Python services
directly.

Paste this in your `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "maxia-oracle": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/absolute/path/to/oracleforge/backend",
      "env": {
        "ENV": "dev"
      }
    }
  }
}
```

The `cwd` must point at the `oracleforge/backend` directory so Python picks
up the `mcp_server` package. `ENV=dev` is the default that the server sets
itself if the client does not provide it — it is included here to be
explicit.

Restart the client and the 8 tools appear in its tool picker.

### 2. Remote — HTTP SSE

Best for agents that run on a server (LangChain, CrewAI, AutoGen, ElizaOS)
and need to reach MAXIA Oracle over the network. Mounted at:

    GET  /mcp/sse
    POST /mcp/messages/?session_id=...

Authentication uses the same X-API-Key header as the REST API. Register a
free key with `POST /api/register` — 100 tool calls per day, no KYC.

```python
import httpx

headers = {"X-API-Key": "mxo_your_key_here"}
async with httpx.AsyncClient() as client:
    async with client.stream(
        "GET", "https://oracle.maxiaworld.app/mcp/sse", headers=headers
    ) as stream:
        # The first SSE event is the companion endpoint URL, e.g.
        # /mcp/messages/?session_id=abc123
        # Subsequent POSTs on that URL are JSON-RPC 2.0 requests
        # (initialize, notifications/initialized, tools/list, tools/call).
        ...
```

A local dev server lives on `http://127.0.0.1:8003/mcp/sse` when you run
uvicorn from `oracleforge/backend`:

```bash
ENV=dev API_KEY_PEPPER=your-dev-pepper-32-chars-minimum \
  uvicorn main:app --port 8003
```

### Rate limit model

- stdio transport: no quota at all. You run the server locally, you pay
  your own upstream costs. Do what you want.
- HTTP SSE transport: 100 `tools/call` invocations per day per API key
  (rolling UTC day window). `initialize` and `tools/list` are free — agents
  can discover the tool set without burning their quota. A request at the
  limit receives an `isError=true` result with the reset timestamp embedded
  as JSON, but the SSE session stays open so the agent can keep browsing.

## Verifying the install

Round-trip smoke test against the stdio server (runs locally, no network):

```bash
cd oracleforge/backend
source venv/bin/activate   # or venv/Scripts/activate on Windows
python -m mcp_server
# Then pipe this JSON-RPC batch into stdin (one request per line):
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"0.0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"health_check","arguments":{}}}
```

`tools/list` returns the 8 tools listed above. `health_check` returns the
liveness payload without touching any upstream source.

Pytest coverage lives in `tests/test_phase5_mcp.py`:

```bash
ENV=dev API_KEY_PEPPER=test-pepper-that-is-more-than-32-chars-long \
  python -m pytest tests/test_phase5_mcp.py -v
```

## Architecture notes

- `tools.py` — the 8 async tool functions. Each wraps an oracle service
  (`pyth_oracle`, `chainlink_oracle`, `price_oracle`, or the aggregator
  helper `services/oracle/multi_source.py`) and returns a dict with either
  `{"data": ..., "disclaimer": ...}` or `{"error": ..., "disclaimer": ...}`.
  Tools never raise — every exception is captured and converted to an error
  dict.
- `server.py` — `build_server()` factory. Instantiates
  `mcp.server.lowlevel.Server`, registers the 8 tools via `@list_tools()`
  and `@call_tool()`. Accepts an optional `rate_limit_key_hash` that
  carries the daily quota into the handler closure. A fresh server is
  built per HTTP SSE session so each connected agent gets its own quota.
- `__main__.py` — stdio entry point used by `python -m mcp_server`.
- `../api/routes_mcp.py` — HTTP SSE route and ASGI mount for the companion
  `/mcp/messages/` endpoint. Validates the caller's X-API-Key at the SSE
  handshake (returns 401 otherwise) and builds a rate-limited server for
  the session.

## What this server deliberately does NOT expose

MAXIA Oracle is a data feed. It is not a broker, a marketplace, a custodian,
or a regulated investment service. The MCP server reflects that scope:

- No order routing, no execution, no settlement.
- No wallet custody, no private keys, no signing.
- No KYC, no onboarding beyond a free API key.
- No tokenized-stock mints, no xStocks, no regulated security paths.
- No "investment advice" tools — no position sizing, no buy/sell signals,
  no portfolio construction.

The two tools from the original Phase 5 plan that are **not** shipped in
V1 — `get_price_history(symbol, period)` and `subscribe_price_stream(symbol)` —
are deferred to V1.1 (historical candles were dropped in Phase 1 as part of
the "no speculative UI" surgery; streaming subscriptions require the MCP
notification primitive and upstream SSE wrapping).
