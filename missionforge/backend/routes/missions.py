"""MissionForge — Mission management + RAG API routes.

Endpoints:
  GET  /api/missions              — list all missions
  GET  /api/missions/{name}       — get mission detail
  POST /api/missions/{name}/run   — trigger manual execution
  POST /api/missions/reload       — hot-reload YAML from disk
  POST /api/rag/ingest            — ingest documents into RAG
  GET  /api/rag/stats             — RAG collection stats
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["missions"])


# ── Request/Response models ──────────────────────────────────────


class IngestRequest(BaseModel):
    sources: list[dict]  # [{"path": "...", "tag": "..."}]
    force: bool = False


class RunResponse(BaseModel):
    mission_name: str
    run_id: str
    status: str
    steps_completed: int
    total_steps: int
    tokens_used: int
    cost_usd: float
    error_message: str | None
    logs: list[str]
    duration_ms: int


# ── Dependencies ─────────────────────────────────────────────────


def _get_engine(request: Request):
    """Get the MissionEngine from app state."""
    engine = getattr(request.app.state, "mission_engine", None)
    if engine is None:
        raise HTTPException(503, "Mission engine not initialised")
    return engine


def _get_rag(request: Request):
    """Get the RagService from app state."""
    rag = getattr(request.app.state, "rag_service", None)
    if rag is None:
        raise HTTPException(503, "RAG service not initialised")
    return rag


# ── Mission endpoints ────────────────────────────────────────────


@router.get("/api/missions")
async def list_missions(request: Request) -> dict:
    """List all registered missions with their status."""
    engine = _get_engine(request)
    missions = engine.list_missions()
    return {
        "missions": [
            {
                "name": m.name,
                "description": m.description,
                "schedule": m.schedule,
                "steps_count": len(m.steps),
                "agent_tier": m.agent.llm_tier,
            }
            for m in missions.values()
        ],
        "total": len(missions),
    }


@router.get("/api/missions/{name}")
async def get_mission(name: str, request: Request) -> dict:
    """Get detailed info about a specific mission."""
    engine = _get_engine(request)
    missions = engine.list_missions()
    if name not in missions:
        raise HTTPException(404, f"Mission '{name}' not found")
    m = missions[name]
    return {
        "name": m.name,
        "description": m.description,
        "schedule": m.schedule,
        "agent": m.agent.model_dump(),
        "steps": [s.model_dump(exclude_none=True) for s in m.steps],
    }


@router.post("/api/missions/{name}/run", response_model=RunResponse)
async def run_mission(name: str, request: Request) -> RunResponse:
    """Trigger a manual execution of a mission."""
    engine = _get_engine(request)
    try:
        log = await engine.run_mission(name)
    except KeyError:
        raise HTTPException(404, f"Mission '{name}' not found")

    duration_ms = int((log.finished_at - log.started_at) * 1000) if log.finished_at else 0
    return RunResponse(
        mission_name=log.mission_name,
        run_id=log.run_id,
        status=log.status,
        steps_completed=log.steps_completed,
        total_steps=log.total_steps,
        tokens_used=log.tokens_used,
        cost_usd=log.cost_usd,
        error_message=log.error_message,
        logs=log.logs,
        duration_ms=duration_ms,
    )


@router.post("/api/missions/reload")
async def reload_missions(request: Request) -> dict:
    """Hot-reload missions from the missions directory."""
    engine = _get_engine(request)
    from core.config import get_settings
    settings = get_settings()
    loaded = engine.load_all_missions(settings.missions_dir)
    return {
        "loaded": len(loaded),
        "missions": [m.name for m in loaded],
    }


# ── RAG endpoints ────────────────────────────────────────────────


@router.post("/api/rag/ingest")
async def ingest_docs(req: IngestRequest, request: Request) -> dict:
    """Ingest documents into the RAG knowledge base."""
    rag = _get_rag(request)
    sources = [(s["path"], s["tag"]) for s in req.sources if "path" in s and "tag" in s]
    if not sources:
        raise HTTPException(400, "No valid sources provided")
    return rag.ingest_docs(sources, force=req.force)


@router.get("/api/rag/stats")
async def rag_stats(request: Request) -> dict:
    """Get RAG collection statistics."""
    rag = _get_rag(request)
    return rag.stats()
