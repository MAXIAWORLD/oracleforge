"""LLMForge — FastAPI application entry point.

LLM Router Multi-Provider: one endpoint, intelligent routing, fallback auto.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, init_db
from core.models import HealthResponse
from routes.router import router as api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    await init_db(settings.database_url)

    app.state.http_client = httpx.AsyncClient(timeout=30.0)

    # Cache
    from services.cache import ResponseCache
    app.state.cache = ResponseCache(
        ttl_seconds=settings.cache_ttl_seconds,
        max_entries=settings.cache_max_entries,
    ) if settings.cache_enabled else None

    # LLM Router
    from services.llm_router import LLMRouter
    app.state.llm_router = LLMRouter(
        settings=settings,
        http_client=app.state.http_client,
        cache=app.state.cache,
    )
    logger.info(
        "[startup] LLMForge ready — %d providers configured, cache=%s",
        len(app.state.llm_router.available_tiers()),
        "on" if settings.cache_enabled else "off",
    )

    yield

    await app.state.http_client.aclose()
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        llm = getattr(app.state, "llm_router", None)
        count = len(llm.available_tiers()) if llm else 0
        cache = getattr(app.state, "cache", None)
        return HealthResponse(
            version=settings.version,
            providers_configured=count,
            cache_enabled=cache is not None,
        )

    return app


app = create_app()
