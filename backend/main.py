"""OracleForge — FastAPI application entry point.

Multi-Source Price Oracle with cross-verification and confidence scoring.
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
from routes.prices import router as prices_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    await init_db(settings.database_url)
    app.state.http_client = httpx.AsyncClient(timeout=15.0)

    from services.price_engine import PriceEngine
    app.state.price_engine = PriceEngine(
        settings=settings,
        http_client=app.state.http_client,
    )
    logger.info("[startup] OracleForge ready — sources: coingecko=%s pyth=%s chainlink=%s",
                settings.coingecko_enabled, settings.pyth_enabled, settings.chainlink_enabled)

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

    app.include_router(prices_router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        engine = getattr(app.state, "price_engine", None)
        statuses = engine.get_source_statuses() if engine else []
        healthy = sum(1 for s in statuses if s["enabled"] and s["healthy"])
        total = sum(1 for s in statuses if s["enabled"])
        return HealthResponse(
            version=settings.version,
            sources_healthy=healthy,
            sources_total=total,
        )

    return app


app = create_app()
