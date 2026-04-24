"""MissionForge MCP — tool implementations.

Each function is a thin async wrapper around existing services.
Return contract:
- Success : plain dict (always contains at least one meaningful key)
- Error   : {"error": str} — never raises, MCP clients always get a valid response
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("missionforge.mcp.tools")


# ── 1. list_missions ──────────────────────────────────────────────


async def tool_list_missions(*, engine: Any) -> dict[str, Any]:
    """Return all registered missions with metadata."""
    try:
        missions = engine.list_missions()
        return {
            "missions": [
                {
                    "name": m.name,
                    "description": m.description,
                    "schedule": m.schedule,
                    "steps_count": len(m.steps),
                    "llm_tier": m.agent.llm_tier,
                }
                for m in missions.values()
            ],
            "total": len(missions),
        }
    except Exception as exc:
        logger.error("tool_list_missions error: %s", exc)
        return {"error": str(exc)}


# ── 2. run_mission ────────────────────────────────────────────────


async def tool_run_mission(*, name: str, engine: Any) -> dict[str, Any]:
    """Trigger a mission by name and return the execution result."""
    try:
        log = await engine.run_mission(name)
        duration_ms = 0
        if log.finished_at and log.started_at:
            duration_ms = int((log.finished_at - log.started_at) * 1000)
        return {
            "run_id": log.run_id,
            "mission_name": log.mission_name,
            "status": log.status,
            "steps_completed": log.steps_completed,
            "total_steps": log.total_steps,
            "tokens_used": log.tokens_used,
            "cost_usd": log.cost_usd,
            "duration_ms": duration_ms,
            "logs": log.logs,
            "error_message": log.error_message,
        }
    except KeyError:
        return {
            "error": f"Mission '{name}' not found. Use list_missions to see available missions."
        }
    except Exception as exc:
        logger.error("tool_run_mission '%s' error: %s", name, exc)
        return {"error": str(exc)}


# ── 3. get_mission_history ────────────────────────────────────────


async def tool_get_mission_history(
    *, name: str, limit: int = 10, engine: Any
) -> dict[str, Any]:
    """Return recent execution history for a mission."""
    try:
        runs = await engine.get_run_history(mission_name=name, limit=limit)
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
                    if r.finished_at and r.started_at
                    else 0,
                }
                for r in runs
            ],
            "total": len(runs),
        }
    except Exception as exc:
        logger.error("tool_get_mission_history '%s' error: %s", name, exc)
        return {"error": str(exc)}


# ── 4. chat ───────────────────────────────────────────────────────


async def tool_chat(*, message: str, engine: Any, rag: Any, llm: Any) -> dict[str, Any]:
    """Send a message and get a RAG-grounded reply from the agent."""
    try:
        context = ""
        if rag is not None:
            try:
                context = rag.build_rag_context(message, max_chars=2000)
            except Exception:
                pass

        system = "You are MissionForge, an AI agent framework assistant. Help users understand and manage their AI missions."
        prompt = f"{message}\n\n{context}" if context else message

        reply = await llm.call(prompt=prompt, system=system, max_tokens=600)
        return {
            "reply": reply,
            "rag_context_used": bool(context),
        }
    except Exception as exc:
        logger.error("tool_chat error: %s", exc)
        return {"error": str(exc)}


# ── 5. get_observability ──────────────────────────────────────────


async def tool_get_observability(*, engine: Any, rag: Any, llm: Any) -> dict[str, Any]:
    """Return a summary of system metrics: missions, LLM usage, RAG stats."""
    try:
        missions = engine.list_missions()

        llm_stats: dict = {}
        if llm is not None and hasattr(llm, "get_stats"):
            try:
                llm_stats = llm.get_stats()
            except Exception:
                pass

        rag_stats: dict = {}
        if rag is not None and hasattr(rag, "stats"):
            try:
                rag_stats = rag.stats()
            except Exception:
                pass

        return {
            "total_missions": len(missions),
            "missions_loaded": len(missions),
            "llm": llm_stats,
            "rag": rag_stats,
        }
    except Exception as exc:
        logger.error("tool_get_observability error: %s", exc)
        return {"error": str(exc)}
