"""MAXIA Oracle — Model Context Protocol server (Phase 5).

This package exposes the MAXIA Oracle API as a spec-compliant MCP server so
that AI agents running inside Claude Desktop, Cursor, Continue.dev, Zed, and
any other MCP-compatible client can discover and call the oracle tools
natively.

Architecture:
    - Built on the official `mcp>=1.0` Python SDK from Anthropic
    - 8 tools exposed (list in tools.py)
    - stdio transport for local installs (python -m mcp_server)
    - HTTP SSE transport for remote use (mounted at /mcp/sse via api/routes_mcp.py)

The tools call the oracle services directly (pyth_oracle, chainlink_oracle,
price_oracle) instead of making HTTP round-trips to the local FastAPI app.
This keeps latency low and avoids duplicating the request pipeline.

Phase 5 deliberately omits two tools from the original plan (§3 Phase 5):
    - get_price_history(symbol, period) — would require historical candle
      storage which was removed in Phase 1 Surgery C. Deferred to V1.1.
    - subscribe_price_stream(symbol) — requires the MCP notification
      subscribe primitive and upstream SSE wrapping. Deferred to V1.1.

Non-goals:
    - No marketplace tools (regulated, out of scope for MAXIA Oracle)
    - No custody, swap, DeFi, GPU, stocks, NFT, or agent-identity tools
    - No tier-based access control; only the free-tier / x402 parallel model
      already built in Phase 4 applies
"""
