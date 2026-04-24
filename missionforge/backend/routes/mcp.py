"""MissionForge — MCP HTTP transports.

Two endpoints:
  GET  /mcp/sse   — SSE legacy (Claude Desktop, Cursor, Zed)
  GET/POST /mcp   — Streamable HTTP (new spec, Glama/modern clients)

Both require X-API-Key matching SECRET_KEY.
The MCP auth is handled here (before the SSE stream opens) so that
the ApiKeyAuthMiddleware exemption for /mcp/* is not needed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from core.config import get_settings

logger = logging.getLogger("missionforge.routes.mcp")

router = APIRouter(tags=["mcp"])

_SSE_PATH = "/mcp/messages/"
sse_transport = SseServerTransport(_SSE_PATH)


def _get_streamable_manager() -> StreamableHTTPSessionManager:
    """Lazy singleton — built on first request after lifespan is ready."""
    from mcp_server.server import build_server

    return StreamableHTTPSessionManager(
        build_server(),
        stateless=True,
        json_response=False,
    )


_http_manager: StreamableHTTPSessionManager | None = None


def _authenticate(request: Request) -> JSONResponse | None:
    """Return 401 JSONResponse if X-API-Key is missing or wrong, else None."""
    key = request.headers.get("X-API-Key", "")
    if key != get_settings().secret_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "X-API-Key required"},
            headers={"WWW-Authenticate": 'ApiKey realm="missionforge"'},
        )
    return None


def _resolve_deps(request: Request) -> tuple:
    """Extract engine/rag/llm from app state (set by lifespan)."""
    engine = getattr(request.app.state, "mission_engine", None)
    rag = getattr(request.app.state, "rag_service", None)
    llm = getattr(request.app.state, "llm_router", None)
    return engine, rag, llm


@router.get("/mcp/sse")
async def handle_sse(request: Request) -> Response:
    """Open an MCP SSE session (legacy transport for Claude Desktop / Cursor)."""
    if err := _authenticate(request):
        return err

    engine, rag, llm = _resolve_deps(request)

    from mcp_server.server import build_server

    server = build_server(engine=engine, rag=rag, llm=llm)

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
    return Response()


@router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def handle_streamable_http(request: Request) -> Response:
    """Streamable HTTP MCP transport (new spec, required by Glama)."""
    if err := _authenticate(request):
        return err

    global _http_manager
    if _http_manager is None:
        _http_manager = _get_streamable_manager()

    await _http_manager.handle_request(request.scope, request.receive, request._send)
    return Response()
