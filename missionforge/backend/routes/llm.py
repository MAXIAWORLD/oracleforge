"""MissionForge — LLM API routes (OpenAI-compatible).

Extracted from MAXIA V12 backend/ai/llm_service.py and generalised:
- No singleton LLMRouter — injected via dependency
- No in-memory usage dict — stats from LLMRouter.get_stats()
- Removed X-API-Key auth (will be added with AuthForge integration)
- Dynamic model listing based on configured tiers
"""

from __future__ import annotations

import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.config import get_settings, Settings
from services.llm_router import LLMRouter, Tier

router = APIRouter(prefix="/api/llm", tags=["llm"])


# ── Request/Response models ──────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None  # auto, local, fast, fast2, fast3, mid, strategic
    max_tokens: int = Field(default=500, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class CompletionRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int = Field(default=500, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


# ── Dependency ───────────────────────────────────────────────────


def get_llm_router(request: Request) -> LLMRouter:
    """Return the shared LLMRouter from app state (preserves stats + budget)."""
    engine = getattr(request.app.state, "mission_engine", None)
    if engine and hasattr(engine, "_llm"):
        return engine._llm
    # Fallback: create new (should not happen if lifespan ran)
    settings = get_settings()
    http_client: httpx.AsyncClient = request.app.state.http_client
    return LLMRouter(settings=settings, http_client=http_client)


# ── Helpers ──────────────────────────────────────────────────────


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return max(1, len(text) // 4)


def _parse_tier(model: str | None) -> Tier | None:
    """Parse a model string to a Tier, or None for auto."""
    if not model or model == "auto":
        return None
    try:
        return Tier(model)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model}. Use: auto, local, fast, fast2, fast3, mid, strategic",
        )


def _build_prompt(messages: list[ChatMessage]) -> tuple[str, str]:
    """Extract system prompt and user prompt from chat messages."""
    system = ""
    user_parts: list[str] = []
    for msg in messages:
        if msg.role == "system":
            system = msg.content
        elif msg.role == "user":
            user_parts.append(msg.content)
        elif msg.role == "assistant":
            user_parts.append(f"[Previous response: {msg.content[:200]}]")
    return system, "\n".join(user_parts).strip()


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/models")
async def list_models(request: Request) -> dict:
    """List available LLM tiers with pricing (only tiers with configured keys)."""
    llm = get_llm_router(request)
    available = llm.available_tiers()

    models = [
        {
            "id": "auto",
            "name": "Auto-route (optimal tier for your request)",
            "description": "Automatically selects based on prompt complexity",
        },
    ]
    for tier in available:
        info = llm.get_tier_info(tier)
        models.append({
            "id": tier.value,
            "name": f"{info['provider'].title()} ({info['model']})",
            "provider": info["provider"],
            "model": info["model"],
            "pricing_per_1k_tokens": info["cost_per_1k"],
        })

    return {"models": models}


@router.post("/chat")
async def chat_completion(req: ChatRequest, request: Request) -> dict:
    """OpenAI-compatible chat completion — routes to optimal LLM tier."""
    system, user_prompt = _build_prompt(req.messages)
    if not user_prompt:
        raise HTTPException(400, "At least one user message required")

    tier = _parse_tier(req.model)
    llm = get_llm_router(request)

    result = await llm.call(
        prompt=user_prompt,
        tier=tier,
        system=system,
        max_tokens=req.max_tokens,
    )
    if not result:
        raise HTTPException(503, "All LLM providers unavailable")

    used_tier = str(tier or llm.classify_complexity(user_prompt))
    input_tokens = _estimate_tokens(system + user_prompt)
    output_tokens = _estimate_tokens(result)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": f"mf-{used_tier}",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result},
                "finish_reason": "stop",
            },
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        "tier": used_tier,
    }


@router.post("/completions")
async def text_completion(req: CompletionRequest, request: Request) -> dict:
    """Simple text completion endpoint."""
    tier = _parse_tier(req.model)
    llm = get_llm_router(request)

    result = await llm.call(
        prompt=req.prompt,
        tier=tier,
        max_tokens=req.max_tokens,
    )
    if not result:
        raise HTTPException(503, "All LLM providers unavailable")

    used_tier = str(tier or llm.classify_complexity(req.prompt))
    input_tokens = _estimate_tokens(req.prompt)
    output_tokens = _estimate_tokens(result)

    return {
        "id": f"cmpl-{uuid.uuid4().hex[:12]}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": f"mf-{used_tier}",
        "choices": [{"text": result, "index": 0, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        "tier": used_tier,
    }


@router.get("/usage")
async def get_usage(request: Request) -> dict:
    """Get today's LLM usage and cost stats."""
    llm = get_llm_router(request)
    return llm.get_stats()
