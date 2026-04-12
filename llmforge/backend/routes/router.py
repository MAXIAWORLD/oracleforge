"""LLMForge — API routes (OpenAI-compatible + observability).

Endpoints:
  GET  /api/models              — list available tiers
  POST /api/chat                — OpenAI-compatible chat completion
  POST /api/completions         — text completion
  GET  /api/usage               — today's stats
  GET  /api/usage/tiers         — per-tier breakdown with P50/P95
  GET  /api/cache/stats         — cache hit/miss stats
  POST /api/cache/clear         — clear response cache
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.config import get_settings
from services.llm_router import LLMRouter, Tier, TIER_PROVIDERS, TIER_COSTS

router = APIRouter(prefix="/api", tags=["llm"])


# ── Models ───────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    max_tokens: int = Field(default=500, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class CompletionRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int = Field(default=500, ge=1, le=8192)


# ── Helpers ──────────────────────────────────────────────────────


def _get_router(request: Request) -> LLMRouter:
    return request.app.state.llm_router


def _parse_tier(model: str | None) -> Tier | None:
    if not model or model == "auto":
        return None
    try:
        return Tier(model)
    except ValueError:
        raise HTTPException(400, f"Unknown model: {model}. Use: auto, local, fast, fast2, fast3, mid, strategic")


def _build_prompt(messages: list[ChatMessage]) -> tuple[str, str]:
    system = ""
    parts: list[str] = []
    for m in messages:
        if m.role == "system":
            system = m.content
        elif m.role == "user":
            parts.append(m.content)
        elif m.role == "assistant":
            parts.append(f"[Previous: {m.content[:200]}]")
    return system, "\n".join(parts).strip()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/models")
async def list_models(request: Request) -> dict:
    llm = _get_router(request)
    available = llm.available_tiers()
    models = [{"id": "auto", "name": "Auto-route (optimal tier)", "description": "Routes based on prompt complexity"}]
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
async def chat(req: ChatRequest, request: Request) -> dict:
    system, user_prompt = _build_prompt(req.messages)
    if not user_prompt:
        raise HTTPException(400, "At least one user message required")
    tier = _parse_tier(req.model)
    llm = _get_router(request)
    api_key = request.headers.get("X-API-Key", "anonymous")

    result, tier_used, cached = await llm.call(
        prompt=user_prompt, tier=tier, system=system,
        max_tokens=req.max_tokens, api_key=api_key,
    )
    if not result:
        raise HTTPException(503, "All LLM providers unavailable or budget exceeded")

    in_tok = _estimate_tokens(system + user_prompt)
    out_tok = _estimate_tokens(result)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": f"llmforge-{tier_used}",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": result}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok, "total_tokens": in_tok + out_tok},
        "tier": tier_used,
        "cached": cached,
    }


@router.post("/completions")
async def completions(req: CompletionRequest, request: Request) -> dict:
    tier = _parse_tier(req.model)
    llm = _get_router(request)
    api_key = request.headers.get("X-API-Key", "anonymous")

    result, tier_used, cached = await llm.call(
        prompt=req.prompt, tier=tier, max_tokens=req.max_tokens, api_key=api_key,
    )
    if not result:
        raise HTTPException(503, "All LLM providers unavailable or budget exceeded")

    in_tok = _estimate_tokens(req.prompt)
    out_tok = _estimate_tokens(result)
    return {
        "id": f"cmpl-{uuid.uuid4().hex[:12]}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": f"llmforge-{tier_used}",
        "choices": [{"text": result, "index": 0, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok, "total_tokens": in_tok + out_tok},
        "tier": tier_used,
        "cached": cached,
    }


@router.get("/usage")
async def usage(request: Request) -> dict:
    llm = _get_router(request)
    return llm.get_stats()


@router.get("/usage/tiers")
async def usage_tiers(request: Request) -> dict:
    llm = _get_router(request)
    stats = llm.get_stats()
    return {"date": stats["date"], "tiers": stats["by_tier"]}


@router.get("/cache/stats")
async def cache_stats(request: Request) -> dict:
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        return {"enabled": False}
    return {"enabled": True, **cache.stats()}


@router.post("/cache/clear")
async def cache_clear(request: Request) -> dict:
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        return {"cleared": 0}
    count = cache.clear()
    return {"cleared": count}


# ── Streaming chat (SSE) ────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """SSE streaming chat — sends tokens as they arrive."""
    import json as _json
    from starlette.responses import StreamingResponse

    system, user_prompt = _build_prompt(req.messages)
    if not user_prompt:
        raise HTTPException(400, "At least one user message required")
    tier = _parse_tier(req.model)
    llm = _get_router(request)
    api_key = request.headers.get("X-API-Key", "anonymous")

    async def generate():
        result, tier_used, cached = await llm.call(
            prompt=user_prompt, tier=tier, system=system,
            max_tokens=req.max_tokens, api_key=api_key,
        )
        if not result:
            yield f"data: {_json.dumps({'error': 'All providers unavailable'})}\n\n"
            return

        # Simulate streaming by chunking the response
        words = result.split(" ")
        buffer = ""
        for i, word in enumerate(words):
            buffer += word + " "
            if i % 3 == 2 or i == len(words) - 1:  # Send every 3 words
                yield f"data: {_json.dumps({'content': buffer.strip(), 'tier': tier_used, 'cached': cached})}\n\n"
                buffer = ""

        in_tok = _estimate_tokens(system + user_prompt)
        out_tok = _estimate_tokens(result)
        yield f"data: {_json.dumps({'done': True, 'usage': {'prompt_tokens': in_tok, 'completion_tokens': out_tok}})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
