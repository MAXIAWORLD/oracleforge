"""TDD tests for LLMForge services/llm_router.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Settings
from services.cache import ResponseCache
from services.llm_router import LLMRouter, Tier


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        database_url="sqlite+aiosqlite:///:memory:",
        groq_api_key="fake-key",
        cerebras_api_key="fake-key",
        daily_budget_usd=0,
    )


@pytest.fixture
def router(settings) -> LLMRouter:
    return LLMRouter(settings=settings, http_client=MagicMock(), cache=ResponseCache())


class TestClassification:
    def test_local_keywords(self, router) -> None:
        assert router.classify_complexity("parse this JSON") == Tier.LOCAL

    def test_strategic_keywords(self, router) -> None:
        assert router.classify_complexity("long-term vision and roadmap") == Tier.STRATEGIC

    def test_default_local(self, router) -> None:
        assert router.classify_complexity("hello") == Tier.LOCAL


class TestCallWithCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self, router) -> None:
        router._call_tier = AsyncMock(return_value="first call")
        r1, t1, c1 = await router.call("test prompt", tier=Tier.FAST)
        assert r1 == "first call"
        assert c1 is False

        # Second call should hit cache
        r2, t2, c2 = await router.call("test prompt", tier=Tier.FAST)
        assert r2 == "first call"
        assert c2 is True
        # _call_tier should only be called once
        router._call_tier.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback(self, router) -> None:
        async def mock_tier(tier, system, prompt, max_tokens):
            if tier == Tier.FAST:
                raise RuntimeError("down")
            return f"from {tier.value}"

        router._call_tier = mock_tier
        r, t, c = await router.call("test", tier=Tier.FAST)
        assert "fast2" in t or "fast3" in t or "mid" in t

    @pytest.mark.asyncio
    async def test_empty_when_all_fail(self, router) -> None:
        router._call_tier = AsyncMock(side_effect=RuntimeError("down"))
        r, t, c = await router.call("test", tier=Tier.LOCAL)
        assert r == ""


class TestBudget:
    @pytest.mark.asyncio
    async def test_budget_exceeded(self) -> None:
        s = Settings(
            secret_key="test-secret-key-32-chars-ok!!",
            database_url="sqlite+aiosqlite:///:memory:",
            daily_budget_usd=0.001,
        )
        router = LLMRouter(settings=s, http_client=MagicMock())
        # Simulate spending
        router._stats["strategic"]["cost"] = 0.002
        r, t, c = await router.call("test", tier=Tier.LOCAL)
        assert r == ""  # Budget exceeded


class TestStats:
    def test_stats_structure(self, router) -> None:
        stats = router.get_stats()
        assert "date" in stats
        assert "total_calls" in stats
        assert "total_cache_hits" in stats
        assert "by_tier" in stats
        for tier_stats in stats["by_tier"].values():
            assert "p50_ms" in tier_stats
            assert "p95_ms" in tier_stats

    def test_available_tiers(self, router) -> None:
        available = router.available_tiers()
        assert Tier.LOCAL in available
        assert Tier.FAST in available  # cerebras key set
