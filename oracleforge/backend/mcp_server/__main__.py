"""MAXIA Oracle — MCP server stdio entry point (Phase 5 Step 5).

Canonical way to install a MAXIA Oracle MCP server in a local Claude Desktop
/ Cursor / Zed / Continue configuration:

    {
      "mcpServers": {
        "maxia-oracle": {
          "command": "python",
          "args": ["-m", "mcp_server"],
          "env": {
            "ENV": "dev",
            "MAXIA_ORACLE_API_KEY": "mxo_..."
          }
        }
      }
    }

`ENV` defaults to `dev` when missing: the MCP binary runs inside the user's
desktop client, not on the MAXIA Oracle production VPS, so the
Phase 3 decision #8 startup guard would otherwise refuse to boot on a
freshly installed client. The user can override via the `env` block above.

`MAXIA_ORACLE_API_KEY` is accepted for forward compatibility with the Phase 6
SDK path where the MCP server will make HTTP round-trips to the remote
backend. V1 tools in `tools.py` call the oracle services directly as Python
functions, so the key is not required today.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Must be set BEFORE importing mcp_server.server, which transitively imports
# core.config — that module raises at import-time if ENV is absent.
os.environ.setdefault("ENV", "dev")

from mcp.server.stdio import stdio_server  # noqa: E402

from mcp_server.server import build_server  # noqa: E402


async def _run() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Synchronous entry point used by the `python -m mcp_server` shortcut."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
