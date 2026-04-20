"""MAXIA Oracle — MCP HTTP SSE transport (Phase 5 Step 6).

Exposes the `build_server()` MCP server over an HTTP Server-Sent-Events
transport so that remote clients (agent frameworks, Claude Desktop via the
remote MCP config, etc.) can reach the 8 V1 tools through
`oracle.maxiaworld.app/mcp/sse`.

Two endpoints are wired:

    GET  /mcp/sse            opens a long-lived SSE session. The X-API-Key
                             header is validated on connect; rejected
                             connections get a 401 before any stream is
                             opened. A fresh `Server` instance is built
                             per session so that the tool call handler
                             carries the caller's key_hash in its closure
                             and can charge the daily rate-limit on each
                             `tools/call`.

    POST /mcp/messages/...   mounted ASGI app from `SseServerTransport`.
                             The SDK routes incoming JSON-RPC messages to
                             the correct session by its `session_id` query
                             parameter. This endpoint is mounted in
                             `main.py`, not declared as a normal route
                             here, because it needs the raw ASGI scope.

Auth model (Phase 5 decision #5, option A):
    API-Key only, no x402 on MCP SSE. The x402 middleware passes `/mcp/*`
    through untouched because those paths are not listed in the
    `X402_PRICE_MAP`. The `_authenticate_mcp_request` helper uses the
    Phase 3 `lookup_key` directly (not `require_api_key`) so that a
    missing/invalid key does not raise an HTTPException DURING the SSE
    handshake — it returns a plain JSONResponse 401 instead.

Rate limit model:
    Every `tools/call` inside the session ticks the Phase 3 daily counter
    (100 req/day per key). The `build_server(rate_limit_key_hash=...)`
    closure performs the check before dispatching to the tool handler.
    A quota-cramped user gets an `isError=True` response on the specific
    call (the session itself is not closed — agents can keep listing
    tools or retry later).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from core.auth import lookup_key
from core.db import get_db
from core.disclaimer import wrap_error
from mcp_server.server import build_server

logger = logging.getLogger("maxia_oracle.routes_mcp")

router = APIRouter(tags=["mcp"])

# Legacy SSE transport (kept for Claude Desktop / Cursor backwards compat).
_SSE_ENDPOINT_PATH = "/mcp/messages/"
sse_transport: SseServerTransport = SseServerTransport(_SSE_ENDPOINT_PATH)

# Streamable HTTP session manager — stateless, one server per request.
_http_manager = StreamableHTTPSessionManager(
    build_server(),
    stateless=True,
    json_response=False,
)


def _unauthorized(message: str) -> JSONResponse:
    """Return a 401 JSON response with the mandatory disclaimer."""
    return JSONResponse(
        status_code=401,
        content=wrap_error(message),
        headers={"WWW-Authenticate": 'ApiKey realm="maxia-oracle"'},
    )


def _authenticate_mcp_request(request: Request) -> tuple[str | None, JSONResponse | None]:
    """Validate X-API-Key at SSE handshake time.

    Returns `(key_hash, None)` on success, or `(None, response)` on failure
    so the caller can return the JSONResponse directly instead of raising.
    """
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        return None, _unauthorized(
            "missing X-API-Key header — register a free key via POST /api/register"
        )

    db = get_db()
    row = lookup_key(db, raw_key)
    if row is None:
        return None, _unauthorized("invalid or inactive API key")

    return row["key_hash"], None


@router.get("/mcp/sse")
async def handle_sse(request: Request) -> Response:
    """Open a new MCP SSE session after validating the caller's X-API-Key.

    The SSE stream stays open until the client disconnects. Each
    `tools/call` arriving on the companion `POST /mcp/messages/?session_id=...`
    endpoint runs through the per-session server built below, which
    enforces the daily quota on the caller's key.
    """
    key_hash, error_response = _authenticate_mcp_request(request)
    if error_response is not None:
        return error_response

    logger.info("MCP SSE session opening key_hash=%s…", (key_hash or "")[:16])

    server = build_server(rate_limit_key_hash=key_hash)

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        read_stream, write_stream = streams
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

    # The SSE SDK docs explicitly require returning a Response here to avoid
    # a "NoneType is not callable" error when the client disconnects.
    return Response()


@router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def handle_streamable_http(request: Request) -> Response:
    """Streamable HTTP MCP transport (new spec, required by Glama/modern clients).

    Accepts GET (SSE stream init), POST (JSON-RPC message), DELETE (session end).
    Auth via X-API-Key header; unauthenticated requests are rejected with 401.
    """
    key_hash, error_response = _authenticate_mcp_request(request)
    if error_response is not None:
        return error_response

    logger.info("MCP streamable-HTTP request method=%s key_hash=%s", request.method, (key_hash or "")[:16])

    await _http_manager.handle_request(request.scope, request.receive, request._send)
    return Response()
