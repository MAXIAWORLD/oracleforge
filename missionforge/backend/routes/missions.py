"""MissionForge — Mission management + RAG API routes.

Endpoints:
  GET  /api/missions                    — list all missions
  GET  /api/missions/{name}             — get mission detail
  POST /api/missions/{name}/run         — trigger manual execution
  GET  /api/missions/{name}/history     — execution history
  GET  /api/missions/{name}/run/stream  — SSE live run with logs
  GET  /api/missions/history/all        — global history
  POST /api/missions/reload             — hot-reload YAML from disk
  POST /api/rag/ingest                  — ingest documents into RAG
  GET  /api/rag/stats                   — RAG collection stats
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse
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

    duration_ms = (
        int((log.finished_at - log.started_at) * 1000) if log.finished_at else 0
    )
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


@router.get("/api/missions/{name}/run/stream")
async def run_mission_stream(name: str, request: Request):
    """Run a mission and stream execution logs via SSE."""
    engine = _get_engine(request)
    if name not in engine.list_missions():
        raise HTTPException(404, f"Mission '{name}' not found")

    async def event_generator():
        yield f"data: {json.dumps({'event': 'start', 'mission': name})}\n\n"
        try:
            log = await engine.run_mission(name)
            for line in log.logs:
                yield f"data: {json.dumps({'event': 'log', 'message': line})}\n\n"
            duration = (
                int((log.finished_at - log.started_at) * 1000) if log.finished_at else 0
            )
            yield f"data: {json.dumps({'event': 'complete', 'status': log.status, 'steps': log.steps_completed, 'total': log.total_steps, 'tokens': log.tokens_used, 'duration_ms': duration, 'error': log.error_message})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/missions/{name}/history")
async def mission_history(
    name: str,
    request: Request,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
) -> dict:
    """Get execution history for a mission."""
    engine = _get_engine(request)
    runs = await engine.get_run_history(
        mission_name=name, limit=limit, offset=offset, status=status
    )
    return {
        "mission": name,
        "runs": [
            {
                "run_id": r.run_id,
                "status": r.status,
                "steps_completed": r.steps_completed,
                "total_steps": r.total_steps,
                "tokens_used": r.tokens_used,
                "cost_usd": r.cost_usd,
                "duration_ms": int((r.finished_at - r.started_at) * 1000)
                if r.finished_at
                else 0,
                "logs": r.logs,
                "error_message": r.error_message,
            }
            for r in runs
        ],
        "total": len(runs),
    }


@router.get("/api/missions/history/all")
async def all_history(request: Request, limit: int = 50) -> dict:
    """Get global execution history across all missions."""
    engine = _get_engine(request)
    runs = await engine.get_run_history(limit=limit)
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "mission_name": r.mission_name,
                "status": r.status,
                "steps_completed": r.steps_completed,
                "total_steps": r.total_steps,
                "tokens_used": r.tokens_used,
                "duration_ms": int((r.finished_at - r.started_at) * 1000)
                if r.finished_at
                else 0,
            }
            for r in runs
        ],
        "total": len(runs),
    }


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


class IngestSource(BaseModel):
    path: str
    tag: str


@router.post("/api/rag/ingest")
async def ingest_docs(req: IngestRequest, request: Request) -> dict:
    """Ingest documents into the RAG knowledge base."""
    import os
    from core.config import get_settings

    settings = get_settings()
    base_dir = os.path.realpath(settings.missions_dir)

    rag = _get_rag(request)
    sources: list[tuple[str, str]] = []
    for s in req.sources:
        path = s.get("path", "") if isinstance(s, dict) else ""
        tag = s.get("tag", "") if isinstance(s, dict) else ""
        if not path or not tag:
            continue
        # Path traversal protection
        real = os.path.realpath(path)
        if not real.startswith(base_dir):
            raise HTTPException(
                403, f"Path not allowed: must be under {settings.missions_dir}"
            )
        sources.append((real, tag))
    if not sources:
        raise HTTPException(400, "No valid sources provided")
    return rag.ingest_docs(sources, force=req.force)


@router.get("/api/rag/stats")
async def rag_stats(request: Request) -> dict:
    """Get RAG collection statistics."""
    rag = _get_rag(request)
    return rag.stats()
