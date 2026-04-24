"""MissionForge — FastAPI application entry point.

Lifespan manages: database, ChromaDB, httpx, VectorMemory, RagService, MissionEngine.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, init_db
import core.database as _db_module
from core.models import HealthResponse
from routes.llm import router as llm_router
from routes.missions import router as missions_router
from routes.chat import router as chat_router
from routes.observability import router as observability_router
from routes.mcp import router as mcp_router, sse_transport

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # Database
    await init_db(settings.database_url)

    # Shared httpx client (connection pool)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)

    # ChromaDB
    app.state.chroma_client = None
    try:
        import chromadb
        import chromadb.config as chroma_config

        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        app.state.chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=chroma_config.Settings(anonymized_telemetry=False),
        )
        logger.info("[startup] ChromaDB ready (%s)", settings.chroma_persist_dir)
    except ImportError:
        logger.warning("[startup] chromadb not installed — RAG disabled")

    # VectorMemory + RagService
    app.state.memory = None
    app.state.rag_service = None
    if app.state.chroma_client:
        from services.memory import VectorMemory
        from services.rag_service import RagService

        app.state.memory = VectorMemory(
            client=app.state.chroma_client,
            prefix=settings.chroma_collection_prefix,
        )
        app.state.rag_service = RagService(
            chroma_client=app.state.chroma_client,
            memory=app.state.memory,
            prefix=settings.chroma_collection_prefix,
        )

    # MissionEngine
    from services.mission_engine import MissionEngine
    from services.llm_router import LLMRouter

    llm = LLMRouter(settings=settings, http_client=app.state.http_client)
    app.state.llm_router = llm
    app.state.mission_engine = MissionEngine(
        llm_router=llm,
        rag_service=app.state.rag_service,
        memory=app.state.memory,
        http_client=app.state.http_client,
        allowed_env_vars=settings.allowed_env_vars,
        db_session_factory=_db_module._session_factory,
    )

    # Load missions from disk
    missions_dir = settings.missions_dir
    if os.path.isdir(missions_dir):
        loaded = app.state.mission_engine.load_all_missions(missions_dir)
        logger.info("[startup] loaded %d missions from %s", len(loaded), missions_dir)

    yield

    # Shutdown
    if hasattr(app.state, "mission_engine") and app.state.mission_engine:
        await app.state.mission_engine.stop()
    await app.state.http_client.aclose()
    await close_db()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # Security middleware (auth + rate limit + headers)
    from core.middleware import add_security_middleware

    add_security_middleware(app, settings.secret_key)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────
    app.include_router(llm_router)
    app.include_router(missions_router)
    app.include_router(chat_router)
    app.include_router(observability_router)
    app.include_router(mcp_router)

    # SSE messages endpoint — mounted as raw ASGI app
    app.mount("/mcp/messages", sse_transport.handle_post_message)

    # ── Health endpoint ──────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        engine = getattr(app.state, "mission_engine", None)
        count = len(engine.list_missions()) if engine else 0
        return HealthResponse(version=settings.version, missions_loaded=count)

    return app


app = create_app()
