"""MissionForge — Multi-provider LLM Router with automatic fallback.

Extracted from MAXIA V12 backend/ai/llm_router.py and generalised:
- Settings injected via __init__ (no singletons, no core.config import)
- httpx client injected (no get_http_client dependency)
- AgentOps telemetry removed (replaced by latency_ms tracking)
- All API keys from Pydantic Settings

Tiers (fallback order):
  LOCAL      — Ollama (free, local GPU)
  FAST       — Cerebras (free tier, ~3000 tok/s)
  FAST2      — Gemini Flash-Lite (free tier, 1000 RPD)
  FAST3      — Groq Llama 3.3 70B (free tier, rate-limited)
  MID        — Mistral Small (low cost)
  STRATEGIC  — Anthropic Claude (highest quality)
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import StrEnum

import httpx

from core.config import Settings

logger = logging.getLogger(__name__)


class Tier(StrEnum):
    LOCAL = "local"
    FAST = "fast"
    FAST2 = "fast2"
    FAST3 = "fast3"
    MID = "mid"
    STRATEGIC = "strategic"


# Keywords for auto-classification (from MAXIA V12, works well in practice)
_TIER_KEYWORDS: dict[Tier, list[str]] = {
    Tier.LOCAL: [
        "classify", "parse", "extract", "summarize", "resume", "format",
        "count", "list", "filter", "monitor", "check", "health", "status",
        "translate", "categorize", "tag",
    ],
    Tier.FAST: [
        "tweet", "write", "draft", "respond", "reply", "analyze market",
        "negotiate", "prospect", "outreach", "content", "message",
    ],
    Tier.MID: [
        "swot", "strategy", "plan", "evaluate", "compare", "assess",
        "diagnose", "multi-step", "report", "weekly",
    ],
    Tier.STRATEGIC: [
        "vision", "expansion", "red team", "critical", "okr", "roadmap",
        "invest", "crisis", "long-term", "global",
    ],
}

# Cost per 1K tokens (input, output) — provider costs, not resale
TIER_COSTS: dict[Tier, tuple[float, float]] = {
    Tier.LOCAL: (0.0, 0.0),
    Tier.FAST: (0.0, 0.0),
    Tier.FAST2: (0.0, 0.0),
    Tier.FAST3: (0.0, 0.0),
    Tier.MID: (0.0002, 0.0006),
    Tier.STRATEGIC: (0.003, 0.015),
}

# Provider/model names per tier (for observability)
_TIER_PROVIDERS: dict[Tier, str] = {
    Tier.LOCAL: "ollama", Tier.FAST: "cerebras", Tier.FAST2: "gemini",
    Tier.FAST3: "groq", Tier.MID: "mistral", Tier.STRATEGIC: "anthropic",
}

_FALLBACK_CHAIN: list[Tier] = [
    Tier.LOCAL, Tier.FAST, Tier.FAST2, Tier.FAST3, Tier.MID, Tier.STRATEGIC,
]


class LLMRouter:
    """Route LLM calls to the optimal tier with automatic fallback."""

    # Groq rate limit: 30 RPM free tier → minimum 2s between calls
    _groq_last_call: float = 0.0
    _GROQ_MIN_INTERVAL: float = 2.0

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._date = time.strftime("%Y-%m-%d")
        self._stats: dict[str, dict] = {
            t.value: {"calls": 0, "cost": 0.0, "last_latency_ms": 0}
            for t in Tier
        }

    # ── Classification ───────────────────────────────────────────

    def classify_complexity(self, task_description: str) -> Tier:
        """Classify prompt complexity to select the optimal tier."""
        desc = task_description.lower()
        scores: dict[Tier, int] = {t: 0 for t in Tier}

        for tier, keywords in _TIER_KEYWORDS.items():
            for kw in keywords:
                if kw in desc:
                    scores[tier] += 1

        if len(task_description) > 2000:
            scores[Tier.MID] += 1
        if len(task_description) > 5000:
            scores[Tier.STRATEGIC] += 1

        best = max(scores, key=lambda t: scores[t])
        return best if scores[best] > 0 else Tier.LOCAL

    # ── Main call with fallback ──────────────────────────────────

    async def call(
        self,
        prompt: str,
        tier: Tier | None = None,
        system: str = "",
        max_tokens: int = 500,
        timeout: float = 30.0,
    ) -> str:
        """Call the LLM with automatic tier fallback on failure/timeout."""
        self._reset_if_new_day()

        if tier is None:
            tier = self.classify_complexity(prompt)

        start_idx = _FALLBACK_CHAIN.index(tier)
        for t in _FALLBACK_CHAIN[start_idx:]:
            try:
                t0 = time.monotonic()
                result = await asyncio.wait_for(
                    self._call_tier(t, system, prompt, max_tokens),
                    timeout=timeout,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                if result:
                    self._track(t, len(prompt), len(result), latency_ms)
                    return result
            except asyncio.TimeoutError:
                logger.warning("[LLMRouter] %s timeout (%.1fs), trying next...", t.value, timeout)
            except Exception as e:
                logger.warning("[LLMRouter] %s failed: %s, trying next...", t.value, e)

        return ""

    # ── Tier dispatcher ──────────────────────────────────────────

    async def _call_tier(
        self, tier: Tier, system: str, prompt: str, max_tokens: int
    ) -> str:
        dispatch = {
            Tier.LOCAL: self._call_ollama,
            Tier.FAST: self._call_cerebras,
            Tier.FAST2: self._call_gemini,
            Tier.FAST3: self._call_groq,
            Tier.MID: self._call_mistral,
            Tier.STRATEGIC: self._call_anthropic,
        }
        handler = dispatch.get(tier)
        if handler is None:
            return ""
        return await handler(system, prompt, max_tokens)

    # ── Provider implementations ─────────────────────────────────

    async def _call_ollama(self, system: str, prompt: str, max_tokens: int) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = await self._http.post(
            f"{self._settings.ollama_url}/api/generate",
            json={
                "model": self._settings.ollama_model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7},
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def _call_cerebras(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.cerebras_api_key:
            raise RuntimeError("No Cerebras API key")
        msgs = self._build_messages(system, prompt)
        resp = await self._http.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.cerebras_api_key}"},
            json={
                "model": self._settings.cerebras_model,
                "messages": msgs,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._extract_openai_content(resp.json())

    async def _call_gemini(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.google_ai_key:
            raise RuntimeError("No Google AI key")
        msgs = self._build_messages(system, prompt)
        resp = await self._http.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.google_ai_key}"},
            json={
                "model": self._settings.google_ai_model,
                "messages": msgs,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._extract_openai_content(resp.json())

    async def _call_groq(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.groq_api_key:
            raise RuntimeError("No Groq API key")
        # Rate limiting: 30 RPM free tier
        now = time.time()
        elapsed = now - LLMRouter._groq_last_call
        if elapsed < self._GROQ_MIN_INTERVAL:
            await asyncio.sleep(self._GROQ_MIN_INTERVAL - elapsed)
        LLMRouter._groq_last_call = time.time()

        msgs = self._build_messages(system, prompt)
        resp = await self._http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.groq_api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": msgs,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._extract_openai_content(resp.json())

    async def _call_mistral(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.mistral_api_key:
            raise RuntimeError("No Mistral API key")
        msgs = self._build_messages(system, prompt)
        resp = await self._http.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.mistral_api_key}"},
            json={
                "model": self._settings.mistral_model,
                "messages": msgs,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._extract_openai_content(resp.json())

    async def _call_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.anthropic_api_key:
            raise RuntimeError("No Anthropic API key")
        resp = await self._http.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "system": system or "You are a helpful assistant.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json().get("content", [])
        return content[0].get("text", "") if content else ""

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _build_messages(system: str, prompt: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    @staticmethod
    def _extract_openai_content(data: dict) -> str:
        choices = data.get("choices", [])
        return choices[0]["message"]["content"].strip() if choices else ""

    # ── Cost tracking ────────────────────────────────────────────

    def _track(
        self, tier: Tier, input_len: int, output_len: int, latency_ms: int
    ) -> None:
        tokens_in = input_len // 4
        tokens_out = output_len // 4
        rates = TIER_COSTS.get(tier, (0.0, 0.0))
        cost = (tokens_in / 1000 * rates[0]) + (tokens_out / 1000 * rates[1])
        self._stats[tier.value]["calls"] += 1
        self._stats[tier.value]["cost"] += cost
        self._stats[tier.value]["last_latency_ms"] = latency_ms

    def _reset_if_new_day(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self._date != today:
            self._stats = {
                t.value: {"calls": 0, "cost": 0.0, "last_latency_ms": 0}
                for t in Tier
            }
            self._date = today

    def get_stats(self) -> dict:
        """Return today's aggregated cost/usage stats."""
        self._reset_if_new_day()
        total_calls = sum(v["calls"] for v in self._stats.values())
        total_cost = sum(v["cost"] for v in self._stats.values())
        return {
            "date": self._date,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "by_tier": dict(self._stats),
        }

    def available_tiers(self) -> list[Tier]:
        """Return tiers that have configured API keys (LOCAL always available)."""
        available = [Tier.LOCAL]
        key_map: dict[Tier, str] = {
            Tier.FAST: self._settings.cerebras_api_key,
            Tier.FAST2: self._settings.google_ai_key,
            Tier.FAST3: self._settings.groq_api_key,
            Tier.MID: self._settings.mistral_api_key,
            Tier.STRATEGIC: self._settings.anthropic_api_key,
        }
        for tier, key in key_map.items():
            if key:
                available.append(tier)
        return available

    def get_tier_info(self, tier: Tier) -> dict:
        """Return provider/model info for a tier."""
        model_map: dict[Tier, str] = {
            Tier.LOCAL: self._settings.ollama_model,
            Tier.FAST: self._settings.cerebras_model,
            Tier.FAST2: self._settings.google_ai_model,
            Tier.FAST3: "llama-3.3-70b-versatile",
            Tier.MID: self._settings.mistral_model,
            Tier.STRATEGIC: "claude-sonnet-4-20250514",
        }
        return {
            "tier": tier.value,
            "provider": _TIER_PROVIDERS.get(tier, "unknown"),
            "model": model_map.get(tier, "unknown"),
            "cost_per_1k": {
                "input": TIER_COSTS[tier][0],
                "output": TIER_COSTS[tier][1],
            },
        }
