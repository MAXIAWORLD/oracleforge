"""AuthForge — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, init_db
from core.models import HealthResponse
from routes.auth import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    await init_db(settings.database_url)

    from services.auth_service import AuthService, RateLimiter
    app.state.auth_service = AuthService(settings=settings)
    app.state.rate_limiter = RateLimiter(
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )
    logger.info("[startup] AuthForge ready")
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
    # Security middleware (auth + rate limit + headers)
    from core.middleware import add_security_middleware
    add_security_middleware(app, settings.secret_key)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth_router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(version=settings.version)
    return app


app = create_app()
