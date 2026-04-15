"""MAXIA Oracle — FastAPI application entry point (Phase 3).

Run locally (dev):
    ENV=dev uvicorn main:app --reload --port 8003

Run prod (Phase 7 deploy):
    ENV=prod API_KEY_PEPPER=... DB_PATH=/var/lib/maxia-oracle/db.sqlite \
      uvicorn main:app --host 127.0.0.1 --port 8003 --workers 2

Swagger docs are exposed at /docs only when ENV != prod (V12 audit H11).
Security headers are injected on every response (V12 audit H9). A daily
rate-limit counter is enforced DB-backed (V12 audit H7). Configuration
secrets are validated at import time, process refuses to start otherwise
(V12 audit C5).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api import routes_health, routes_mcp, routes_price, routes_register, routes_sources
from core.config import ENV, IS_PROD, LOG_LEVEL
from core.db import close_db, get_db, init_db
from core.disclaimer import wrap_error
from core.http_client import close_http_client
from core.rate_limit import purge_old_windows
from core.security import SecurityHeadersMiddleware
from x402.middleware import x402_middleware

API_VERSION = "0.1.0"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
)
logger = logging.getLogger("maxia_oracle.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init DB + purge stale rate-limit rows. Shutdown: close HTTP + DB."""
    logger.info("Starting MAXIA Oracle %s (env=%s)", API_VERSION, ENV)
    init_db()
    purge_old_windows(get_db())
    yield
    logger.info("Shutting down MAXIA Oracle")
    try:
        await close_http_client()
    except Exception:
        logger.warning("shared HTTP client close failed", exc_info=True)
    close_db()


# Swagger endpoints are disabled in prod to reduce attack surface (V12 H11).
_docs_url = None if IS_PROD else "/docs"
_redoc_url = None if IS_PROD else "/redoc"
_openapi_url = None if IS_PROD else "/openapi.json"

app = FastAPI(
    title="MAXIA Oracle",
    description=(
        "Multi-source price data feed for AI agents. "
        "Data feed only. Not investment advice. No custody. No KYC."
    ),
    version=API_VERSION,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    lifespan=lifespan,
)

# Security headers middleware must be registered BEFORE any other middleware
# that modifies the response, so its setdefault() calls run last.
app.add_middleware(SecurityHeadersMiddleware, api_version=API_VERSION)


# x402 Phase 4 middleware — Base mainnet direct-sale payment path.
# Registered via the function-based middleware decorator so Starlette wraps
# it AFTER the security-headers ASGI middleware above. The x402 handler
# reads `request.url.path` and either emits a 402 challenge, verifies a
# payment, or passes through unchanged for non-priced paths.
app.middleware("http")(x402_middleware)


# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(routes_health.router)
app.include_router(routes_register.router)
app.include_router(routes_sources.router)
app.include_router(routes_price.router)
app.include_router(routes_mcp.router)

# Mount the SSE message receiver as an ASGI sub-application so the MCP SDK
# handles session routing by `session_id` query parameter. Must use the same
# SseServerTransport instance as the GET /mcp/sse handler above.
app.mount("/mcp/messages/", app=routes_mcp.sse_transport.handle_post_message)


# ── Generic JSON error handler ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc: Exception):  # type: ignore[no-untyped-def]
    """Never leak raw exception messages to the client (V12 H12 defense-in-depth).

    The granular call sites in services/oracle/* already wrap errors with
    safe_error(), but this is the last line of defense in case a route raises
    an exception that wasn't caught earlier in the stack.
    """
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content=wrap_error("internal error", type=type(exc).__name__),
    )
