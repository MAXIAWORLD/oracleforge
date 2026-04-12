"""LLMForge — Multi-provider LLM Router with cache, budget caps, and fallback.

Adapted from MissionForge's llm_router.py with LLMForge-specific features:
- Response caching (configurable TTL)
- Per-key and global daily budget caps
- Provider health tracking
- Enhanced observability (latency P50/P95)
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import StrEnum

import httpx

from core.config import Settings
from services.cache import ResponseCache

logger = logging.getLogger(__name__)


class Tier(StrEnum):
    LOCAL = "local"
    FAST = "fast"
    FAST2 = "fast2"
    FAST3 = "fast3"
    MID = "mid"
    STRATEGIC = "strategic"


_TIER_KEYWORDS: dict[Tier, list[str]] = {
    Tier.LOCAL: [
        "classify", "parse", "extract", "summarize", "format",
        "count", "list", "filter", "monitor", "check", "translate", "tag",
    ],
    Tier.FAST: [
        "tweet", "write", "draft", "respond", "reply", "analyze",
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

TIER_COSTS: dict[Tier, tuple[float, float]] = {
    Tier.LOCAL: (0.0, 0.0),
    Tier.FAST: (0.0, 0.0),
    Tier.FAST2: (0.0, 0.0),
    Tier.FAST3: (0.0, 0.0),
    Tier.MID: (0.0002, 0.0006),
    Tier.STRATEGIC: (0.003, 0.015),
}

TIER_PROVIDERS: dict[Tier, str] = {
    Tier.LOCAL: "ollama", Tier.FAST: "cerebras", Tier.FAST2: "gemini",
    Tier.FAST3: "groq", Tier.MID: "mistral", Tier.STRATEGIC: "anthropic",
}

_FALLBACK_CHAIN: list[Tier] = list(Tier)


class LLMRouter:
    """Route LLM calls with caching, budget caps, and automatic fallback."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        cache: ResponseCache | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._cache = cache
        self._date = time.strftime("%Y-%m-%d")
        self._groq_last_call: float = 0.0
        self._groq_min_interval: float = 2.0
        self._stats: dict[str, dict] = {
            t.value: {"calls": 0, "cost": 0.0, "latency_ms_list": [], "errors": 0, "cache_hits": 0}
            for t in Tier
        }
        self._per_key_cost: dict[str, float] = {}

    # ── Classification ───────────────────────────────────────────

    def classify_complexity(self, task: str) -> Tier:
        desc = task.lower()
        scores: dict[Tier, int] = {t: 0 for t in Tier}
        for tier, keywords in _TIER_KEYWORDS.items():
            for kw in keywords:
                if kw in desc:
                    scores[tier] += 1
        if len(task) > 2000:
            scores[Tier.MID] += 1
        if len(task) > 5000:
            scores[Tier.STRATEGIC] += 1
        best = max(scores, key=lambda t: scores[t])
        return best if scores[best] > 0 else Tier.LOCAL

    # ── Budget check ─────────────────────────────────────────────

    def _check_budget(self, api_key: str = "") -> bool:
        self._reset_if_new_day()
        total_cost = sum(v["cost"] for v in self._stats.values())
        if self._settings.daily_budget_usd > 0 and total_cost >= self._settings.daily_budget_usd:
            return False
        if api_key and self._settings.per_key_daily_budget_usd > 0:
            key_cost = self._per_key_cost.get(api_key, 0.0)
            if key_cost >= self._settings.per_key_daily_budget_usd:
                return False
        return True

    # ── Main call ────────────────────────────────────────────────

    async def call(
        self,
        prompt: str,
        tier: Tier | None = None,
        system: str = "",
        max_tokens: int = 500,
        timeout: float = 30.0,
        api_key: str = "",
    ) -> tuple[str, str, bool]:
        """Call LLM. Returns (response, tier_used, cached)."""
        self._reset_if_new_day()

        if tier is None:
            tier = self.classify_complexity(prompt)

        # Check cache
        if self._cache:
            cached = self._cache.get(prompt, system, tier.value if tier else None)
            if cached:
                self._stats[cached.tier]["cache_hits"] += 1
                return cached.response, cached.tier, True

        # Check budget
        if not self._check_budget(api_key):
            return "", "", False

        # Fallback chain
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
                    self._track(t, len(prompt), len(result), latency_ms, api_key)
                    # Cache the result
                    if self._cache:
                        tokens_in = len(prompt) // 4
                        tokens_out = len(result) // 4
                        self._cache.put(prompt, system, tier.value, result, t.value, tokens_in, tokens_out)
                    return result, t.value, False
            except asyncio.TimeoutError:
                self._stats[t.value]["errors"] += 1
                logger.warning("[LLMForge] %s timeout (%.1fs)", t.value, timeout)
            except Exception as e:
                self._stats[t.value]["errors"] += 1
                logger.warning("[LLMForge] %s failed: %s", t.value, e)

        return "", "", False

    # ── Tier dispatcher ──────────────────────────────────────────

    async def _call_tier(self, tier: Tier, system: str, prompt: str, max_tokens: int) -> str:
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

    # ── Providers ────────────────────────────────────────────────

    async def _call_ollama(self, system: str, prompt: str, max_tokens: int) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        resp = await self._http.post(
            f"{self._settings.ollama_url}/api/generate",
            json={"model": self._settings.ollama_model, "prompt": full, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0.7}},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def _call_cerebras(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.cerebras_api_key:
            raise RuntimeError("No Cerebras API key")
        resp = await self._http.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.cerebras_api_key}"},
            json={"model": self._settings.cerebras_model,
                  "messages": self._msgs(system, prompt), "max_tokens": max_tokens, "temperature": 0.7},
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._oai(resp.json())

    async def _call_gemini(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.google_ai_key:
            raise RuntimeError("No Google AI key")
        resp = await self._http.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.google_ai_key}"},
            json={"model": self._settings.google_ai_model,
                  "messages": self._msgs(system, prompt), "max_tokens": max_tokens, "temperature": 0.7},
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._oai(resp.json())

    async def _call_groq(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.groq_api_key:
            raise RuntimeError("No Groq API key")
        now = time.time()
        elapsed = now - self._groq_last_call
        if elapsed < self._groq_min_interval:
            await asyncio.sleep(self._groq_min_interval - elapsed)
        self._groq_last_call = time.time()
        resp = await self._http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.groq_api_key}"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": self._msgs(system, prompt), "max_tokens": max_tokens, "temperature": 0.7},
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._oai(resp.json())

    async def _call_mistral(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.mistral_api_key:
            raise RuntimeError("No Mistral API key")
        resp = await self._http.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.mistral_api_key}"},
            json={"model": self._settings.mistral_model,
                  "messages": self._msgs(system, prompt), "max_tokens": max_tokens, "temperature": 0.7},
            timeout=25.0,
        )
        resp.raise_for_status()
        return self._oai(resp.json())

    async def _call_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        if not self._settings.anthropic_api_key:
            raise RuntimeError("No Anthropic API key")
        resp = await self._http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self._settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": max_tokens,
                  "system": system or "You are a helpful assistant.",
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30.0,
        )
        resp.raise_for_status()
        ct = resp.json().get("content", [])
        return ct[0].get("text", "") if ct else ""

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _msgs(system: str, prompt: str) -> list[dict]:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    @staticmethod
    def _oai(data: dict) -> str:
        choices = data.get("choices", [])
        return choices[0]["message"]["content"].strip() if choices else ""

    # ── Tracking ─────────────────────────────────────────────────

    def _track(self, tier: Tier, in_len: int, out_len: int, latency_ms: int, api_key: str) -> None:
        tokens_in, tokens_out = in_len // 4, out_len // 4
        rates = TIER_COSTS.get(tier, (0.0, 0.0))
        cost = (tokens_in / 1000 * rates[0]) + (tokens_out / 1000 * rates[1])
        s = self._stats[tier.value]
        s["calls"] += 1
        s["cost"] += cost
        s["latency_ms_list"].append(latency_ms)
        if len(s["latency_ms_list"]) > 100:
            s["latency_ms_list"] = s["latency_ms_list"][-100:]
        if api_key:
            self._per_key_cost[api_key] = self._per_key_cost.get(api_key, 0.0) + cost

    def _reset_if_new_day(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self._date != today:
            self._stats = {
                t.value: {"calls": 0, "cost": 0.0, "latency_ms_list": [], "errors": 0, "cache_hits": 0}
                for t in Tier
            }
            self._per_key_cost.clear()
            self._date = today

    def get_stats(self) -> dict:
        self._reset_if_new_day()
        total_calls = sum(v["calls"] for v in self._stats.values())
        total_cost = sum(v["cost"] for v in self._stats.values())
        total_cache = sum(v["cache_hits"] for v in self._stats.values())
        by_tier = {}
        for t, s in self._stats.items():
            lats = s["latency_ms_list"]
            by_tier[t] = {
                "calls": s["calls"],
                "cost": round(s["cost"], 6),
                "errors": s["errors"],
                "cache_hits": s["cache_hits"],
                "p50_ms": sorted(lats)[len(lats) // 2] if lats else 0,
                "p95_ms": sorted(lats)[int(len(lats) * 0.95)] if lats else 0,
            }
        return {
            "date": self._date,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "total_cache_hits": total_cache,
            "by_tier": by_tier,
        }

    def available_tiers(self) -> list[Tier]:
        available = [Tier.LOCAL]
        key_map = {
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
        model_map = {
            Tier.LOCAL: self._settings.ollama_model,
            Tier.FAST: self._settings.cerebras_model,
            Tier.FAST2: self._settings.google_ai_model,
            Tier.FAST3: "llama-3.3-70b-versatile",
            Tier.MID: self._settings.mistral_model,
            Tier.STRATEGIC: "claude-sonnet-4-20250514",
        }
        return {
            "tier": tier.value,
            "provider": TIER_PROVIDERS.get(tier, "unknown"),
            "model": model_map.get(tier, "unknown"),
            "cost_per_1k": {"input": TIER_COSTS[tier][0], "output": TIER_COSTS[tier][1]},
        }
