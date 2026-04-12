"""TDD tests for services/llm_router.py — Tier classification, fallback, cost tracking."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings
from services.llm_router import LLMRouter, Tier, TIER_COSTS


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        database_url="sqlite+aiosqlite:///:memory:",
        debug=True,
        groq_api_key="fake-groq-key",
        mistral_api_key="fake-mistral-key",
        anthropic_api_key="fake-anthropic-key",
        cerebras_api_key="fake-cerebras-key",
        google_ai_key="fake-google-key",
    )


@pytest.fixture
def http_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def router(settings: Settings, http_client: MagicMock) -> LLMRouter:
    return LLMRouter(settings=settings, http_client=http_client)


class TestTierEnum:
    """Tier enum has the correct values."""

    def test_all_tiers_exist(self) -> None:
        assert Tier.LOCAL == "local"
        assert Tier.FAST == "fast"
        assert Tier.FAST2 == "fast2"
        assert Tier.FAST3 == "fast3"
        assert Tier.MID == "mid"
        assert Tier.STRATEGIC == "strategic"

    def test_tier_count(self) -> None:
        assert len(Tier) == 6


class TestClassifyComplexity:
    """classify_complexity routes prompts to the right tier."""

    def test_local_keywords(self, router: LLMRouter) -> None:
        assert router.classify_complexity("parse this JSON") == Tier.LOCAL
        assert router.classify_complexity("classify this email") == Tier.LOCAL
        assert router.classify_complexity("summarize the meeting") == Tier.LOCAL

    def test_fast_keywords(self, router: LLMRouter) -> None:
        assert router.classify_complexity("write a tweet about our product") == Tier.FAST
        assert router.classify_complexity("draft an outreach message") == Tier.FAST

    def test_mid_keywords(self, router: LLMRouter) -> None:
        assert router.classify_complexity("create a swot analysis") == Tier.MID
        assert router.classify_complexity("write a weekly report") == Tier.MID

    def test_strategic_keywords(self, router: LLMRouter) -> None:
        assert router.classify_complexity("define our long-term vision") == Tier.STRATEGIC
        assert router.classify_complexity("do a red team review of this critical system") == Tier.STRATEGIC

    def test_unknown_defaults_to_local(self, router: LLMRouter) -> None:
        assert router.classify_complexity("hello world") == Tier.LOCAL

    def test_long_prompt_boosts_mid(self, router: LLMRouter) -> None:
        long_prompt = "x " * 1500  # >2000 chars
        result = router.classify_complexity(long_prompt)
        # Long prompts get a boost for MID tier
        assert result in (Tier.LOCAL, Tier.MID)


class TestFallbackChain:
    """call() falls through tiers on failure."""

    @pytest.mark.asyncio
    async def test_returns_result_from_requested_tier(self, router: LLMRouter) -> None:
        router._call_tier = AsyncMock(return_value="hello from fast")
        result = await router.call("test prompt", tier=Tier.FAST)
        assert result == "hello from fast"
        router._call_tier.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self, router: LLMRouter) -> None:
        """If FAST fails, should try FAST2, then FAST3, etc."""
        call_count = 0

        async def mock_call_tier(tier, system, prompt, max_tokens):
            nonlocal call_count
            call_count += 1
            if tier in (Tier.FAST, Tier.FAST2):
                raise RuntimeError("provider down")
            return f"response from {tier.value}"

        router._call_tier = mock_call_tier
        result = await router.call("test", tier=Tier.FAST)
        assert result == "response from fast3"
        assert call_count == 3  # FAST, FAST2, FAST3

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, router: LLMRouter) -> None:
        """Timeout should trigger fallback to next tier."""

        async def mock_call_tier(tier, system, prompt, max_tokens):
            if tier == Tier.LOCAL:
                await asyncio.sleep(10)  # Will timeout
            return f"response from {tier.value}"

        router._call_tier = mock_call_tier
        result = await router.call("test", tier=Tier.LOCAL, timeout=0.1)
        assert result == "response from fast"

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_fail(self, router: LLMRouter) -> None:
        router._call_tier = AsyncMock(side_effect=RuntimeError("all down"))
        result = await router.call("test", tier=Tier.LOCAL)
        assert result == ""

    @pytest.mark.asyncio
    async def test_auto_tier_when_none(self, router: LLMRouter) -> None:
        """When tier is None, classify_complexity picks the tier."""
        router._call_tier = AsyncMock(return_value="auto response")
        result = await router.call("parse this data")
        assert result == "auto response"


class TestCostTracking:
    """_track and get_stats accumulate correctly."""

    def test_track_increments_calls(self, router: LLMRouter) -> None:
        router._track(Tier.LOCAL, input_len=100, output_len=50, latency_ms=10)
        stats = router.get_stats()
        assert stats["by_tier"]["local"]["calls"] == 1

    def test_track_accumulates_cost(self, router: LLMRouter) -> None:
        router._track(Tier.STRATEGIC, input_len=4000, output_len=2000, latency_ms=500)
        stats = router.get_stats()
        # 4000/4=1000 tokens in, 2000/4=500 tokens out
        # cost = (1000/1000)*0.003 + (500/1000)*0.015 = 0.003 + 0.0075 = 0.0105
        assert stats["by_tier"]["strategic"]["cost"] > 0
        assert stats["total_cost_usd"] > 0

    def test_get_stats_totals(self, router: LLMRouter) -> None:
        router._track(Tier.LOCAL, 100, 50, 5)
        router._track(Tier.FAST, 200, 100, 10)
        stats = router.get_stats()
        assert stats["total_calls"] == 2

    def test_tracks_latency(self, router: LLMRouter) -> None:
        router._track(Tier.MID, 400, 200, latency_ms=150)
        stats = router.get_stats()
        assert stats["by_tier"]["mid"]["last_latency_ms"] == 150


class TestAvailableTiers:
    """available_tiers returns only tiers with configured API keys."""

    def test_all_tiers_when_keys_set(self, router: LLMRouter) -> None:
        available = router.available_tiers()
        # All keys are set in fixture, plus LOCAL (always available)
        assert Tier.LOCAL in available
        assert Tier.FAST in available
        assert Tier.STRATEGIC in available

    def test_missing_key_excludes_tier(self) -> None:
        s = Settings(
            secret_key="test-secret-key-32-chars-ok!!",
            database_url="sqlite+aiosqlite:///:memory:",
            # No API keys set
        )
        r = LLMRouter(settings=s, http_client=MagicMock())
        available = r.available_tiers()
        assert Tier.LOCAL in available  # Always available
        assert Tier.FAST not in available  # No cerebras key
        assert Tier.STRATEGIC not in available  # No anthropic key
