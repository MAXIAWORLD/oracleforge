"""GuardForge — FastAPI application entry point.

PII & AI Safety Kit: detection, anonymisation, vault, policy engine.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, init_db
from core.models import HealthResponse
from routes.scanner import router as scanner_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    await init_db(settings.database_url)

    from services.pii_detector import PIIDetector
    from services.vault import Vault
    from services.policy_engine import PolicyEngine

    app.state.pii_detector = PIIDetector(confidence_threshold=settings.pii_confidence_threshold)
    app.state.vault = Vault(encryption_key=settings.vault_encryption_key)
    app.state.policy_engine = PolicyEngine(default_policy=settings.default_policy)

    logger.info("[startup] GuardForge ready — vault=%s, policies=%d",
                "on" if app.state.vault.is_available else "off",
                len(app.state.policy_engine.list_policies()))
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(scanner_router)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        vault = getattr(app.state, "vault", None)
        pe = getattr(app.state, "policy_engine", None)
        return HealthResponse(
            version=settings.version,
            vault_entries=len(vault.list_keys()) if vault else 0,
            policies_loaded=len(pe.list_policies()) if pe else 0,
        )
    return app


app = create_app()
