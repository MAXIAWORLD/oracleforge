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

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api import routes_alerts, routes_health, routes_mcp, routes_price, routes_register, routes_sources
from core.config import ENV, IS_PROD, LOG_LEVEL
from core.db import close_db, get_db, init_db
from core.disclaimer import wrap_error
from core.http_client import close_http_client
from core.rate_limit import purge_old_windows
from core.request_id import RequestIDMiddleware, request_id_var
from core.security import SecurityHeadersMiddleware
from services.oracle.history import start_sampler, stop_sampler
from x402.middleware import x402_middleware

API_VERSION: Final[str] = "0.1.9"


class _JSONLogFormatter(logging.Formatter):
    """Structured JSON log formatter for prod — one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class _RequestIDFilter(logging.Filter):
    """Injects request_id into every LogRecord for text-format logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")  # type: ignore[attr-defined]
        return True


_handler = logging.StreamHandler()
_handler.addFilter(_RequestIDFilter())
if IS_PROD:
    _handler.setFormatter(_JSONLogFormatter())
else:
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-5s %(name)s [%(request_id)s] — %(message)s")
    )
logging.basicConfig(level=LOG_LEVEL, handlers=[_handler], force=True)
logger = logging.getLogger("maxia_oracle.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init DB + purge stale rate-limit rows. Shutdown: close HTTP + DB."""
    logger.info("Starting MAXIA Oracle %s (env=%s)", API_VERSION, ENV)
    init_db()
    purge_old_windows(get_db())
    start_sampler()
    yield
    logger.info("Shutting down MAXIA Oracle")
    stop_sampler()
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

# Middleware registration order: last-added = outermost (runs first).
# Request flow: RequestID → x402 → SecurityHeaders → routes.
app.add_middleware(SecurityHeadersMiddleware, api_version=API_VERSION)
app.middleware("http")(x402_middleware)
app.add_middleware(RequestIDMiddleware)


# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(routes_health.router)
app.include_router(routes_register.router)
app.include_router(routes_sources.router)
app.include_router(routes_price.router)
app.include_router(routes_alerts.router)
app.include_router(routes_mcp.router)

# Mount the SSE message receiver as an ASGI sub-application so the MCP SDK
# handles session routing by `session_id` query parameter. Must use the same
# SseServerTransport instance as the GET /mcp/sse handler above.
app.mount("/mcp/messages/", app=routes_mcp.sse_transport.handle_post_message)


# ── Generic JSON error handler ──────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
    """Wrap FastAPI 422 Pydantic errors with the disclaimer field.

    FastAPI's default handler emits {"detail": [...]} without disclaimer,
    inconsistent with every other error response in the API.
    """
    from core.disclaimer import DISCLAIMER_TEXT
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors()), "disclaimer": DISCLAIMER_TEXT},
    )


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
