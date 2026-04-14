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

from api import routes_health, routes_price, routes_register, routes_sources
from core.config import ENV, IS_PROD, LOG_LEVEL
from core.db import close_db, get_db, init_db
from core.disclaimer import wrap_error
from core.rate_limit import purge_old_windows
from core.security import SecurityHeadersMiddleware
from services.oracle.price_oracle import close_http_pool as close_price_oracle_http

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
        await close_price_oracle_http()
    except Exception:
        logger.warning("price_oracle HTTP pool close failed", exc_info=True)
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


# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(routes_health.router)
app.include_router(routes_register.router)
app.include_router(routes_sources.router)
app.include_router(routes_price.router)


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
