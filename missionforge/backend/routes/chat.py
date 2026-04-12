"""MissionForge — Chat API route.

Send messages to an agent with optional RAG context grounding.

Endpoints:
  POST /api/chat — send a message, get a grounded reply
"""

from __future__ import annotations

import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.config import get_settings
from services.llm_router import LLMRouter, Tier

router = APIRouter(tags=["chat"])


# ── Request/Response models ──────────────────────────────────────


class ChatMessageIn(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mission_name: str | None = None
    history: list[ChatMessageIn] = []
    use_rag: bool = True


class ChatResponse(BaseModel):
    reply: str
    latency_ms: int
    tier_used: str
    rag_context_used: bool
    tokens_estimated: int


# ── Endpoint ─────────────────────────────────────────────────────


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Send a message to the agent with optional RAG grounding."""
    t0 = time.monotonic()

    # Reuse shared LLMRouter from MissionEngine (preserves stats)
    engine = getattr(request.app.state, "mission_engine", None)
    llm = engine._llm if engine and hasattr(engine, "_llm") else LLMRouter(
        settings=get_settings(), http_client=request.app.state.http_client
    )

    # Build system prompt
    system = "You are MissionForge, a helpful AI assistant."
    if req.mission_name:
        engine = getattr(request.app.state, "mission_engine", None)
        if engine:
            missions = engine.list_missions()
            mission = missions.get(req.mission_name)
            if mission:
                system = mission.agent.system_prompt

    # RAG context
    rag_context = ""
    rag_used = False
    if req.use_rag:
        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service:
            rag_context = rag_service.build_rag_context(req.message, max_chars=2000)
            rag_used = bool(rag_context)

    # Build prompt with history + RAG
    prompt_parts: list[str] = []
    if rag_context:
        prompt_parts.append(f"## Relevant Knowledge\n{rag_context}\n")
    for msg in req.history[-6:]:  # Last 3 exchanges
        prefix = "User" if msg.role == "user" else "Assistant"
        prompt_parts.append(f"{prefix}: {msg.content[:500]}")
    prompt_parts.append(f"User: {req.message}")
    full_prompt = "\n\n".join(prompt_parts)

    # Call LLM
    result = await llm.call(
        prompt=full_prompt,
        system=system,
        max_tokens=800,
    )
    if not result:
        raise HTTPException(503, "All LLM providers unavailable")

    tier_used = str(llm.classify_complexity(full_prompt))
    latency_ms = int((time.monotonic() - t0) * 1000)
    tokens = (len(full_prompt) + len(system) + len(result)) // 4

    return ChatResponse(
        reply=result,
        latency_ms=latency_ms,
        tier_used=tier_used,
        rag_context_used=rag_used,
        tokens_estimated=tokens,
    )
