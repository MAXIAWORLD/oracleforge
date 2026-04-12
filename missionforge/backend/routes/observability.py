"""MissionForge — Observability API routes.

Metrics aggregated from LLMRouter stats and MissionEngine execution logs.

Endpoints:
  GET /api/observability/summary    — today's overview (cost, calls, success rate)
  GET /api/observability/tiers      — per-tier breakdown
  GET /api/observability/missions   — per-mission stats
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/observability", tags=["observability"])


def _get_engine(request: Request):
    engine = getattr(request.app.state, "mission_engine", None)
    if engine is None:
        raise HTTPException(503, "Mission engine not initialised")
    return engine


@router.get("/summary")
async def summary(request: Request) -> dict:
    """Today's aggregated overview."""
    engine = _get_engine(request)
    missions = engine.list_missions()

    # LLM stats from the router (if accessible via engine)
    llm_stats = {}
    if hasattr(engine, "_llm") and hasattr(engine._llm, "get_stats"):
        llm_stats = engine._llm.get_stats()

    # RAG stats
    rag_stats = {}
    rag = getattr(request.app.state, "rag_service", None)
    if rag:
        rag_stats = rag.stats()

    # Memory stats
    mem_stats = {}
    mem = getattr(request.app.state, "memory", None)
    if mem:
        mem_stats = mem.stats()

    return {
        "missions": {
            "total": len(missions),
            "scheduled": sum(1 for m in missions.values() if m.schedule),
            "manual": sum(1 for m in missions.values() if not m.schedule),
        },
        "llm": llm_stats,
        "rag": rag_stats,
        "memory": mem_stats,
    }


@router.get("/tiers")
async def tier_breakdown(request: Request) -> dict:
    """Per-tier LLM usage breakdown."""
    engine = _get_engine(request)
    if hasattr(engine, "_llm") and hasattr(engine._llm, "get_stats"):
        stats = engine._llm.get_stats()
        return {
            "date": stats.get("date", ""),
            "total_calls": stats.get("total_calls", 0),
            "total_cost_usd": stats.get("total_cost_usd", 0.0),
            "tiers": stats.get("by_tier", {}),
        }
    return {"date": "", "total_calls": 0, "total_cost_usd": 0.0, "tiers": {}}


@router.get("/missions")
async def mission_stats(request: Request) -> dict:
    """Per-mission summary info."""
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
    }
