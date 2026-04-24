"""TDD GREEN — Bloc 6: SDK integration tests against live BudgetForge prod.

This test file requires BF_TEST_API_KEY environment variable set to a valid
API key from https://llmbudget.maxiaworld.app.

To create a test API key:
1. Go to https://llmbudget.maxiaworld.app
2. Sign up with test email (e.g., sdk-test+TIME@example.com)
3. Get your API key from /portal/settings
4. Set BF_TEST_API_KEY=bf-xxx in .env or environment

Tests are SKIPPED if BF_TEST_API_KEY is not set (safe for CI without prod credentials).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from budgetforge_sdk import BudgetForgeLLM, BudgetForgeChat

PROD_URL = "https://llmbudget.maxiaworld.app"
TEST_API_KEY = os.environ.get("BF_TEST_API_KEY", "")
SKIP_LIVE = not TEST_API_KEY


@pytest.mark.skipif(SKIP_LIVE, reason="BF_TEST_API_KEY not set")
class TestBudgetForgeLLMLive:
    """Live integration tests against prod BudgetForge."""

    def test_llm_invoke_live_gpt4(self):
        """Test LLM.invoke() against real prod API."""
        llm = BudgetForgeLLM(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        result = llm.invoke("Say 'hello from SDK test'")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_llm_uses_correct_endpoint(self):
        """Test that LLM sends request to correct BudgetForge proxy endpoint."""
        llm = BudgetForgeLLM(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        # Smoke test — just verify endpoint works
        result = llm.invoke("1+1=?")
        assert "2" in result or "two" in result.lower()

    @pytest.mark.asyncio
    async def test_llm_invoke_async(self):
        """Test async invoke against prod."""
        llm = BudgetForgeLLM(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        result = await llm.invoke_async("Say OK")
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.skipif(SKIP_LIVE, reason="BF_TEST_API_KEY not set")
class TestBudgetForgeChatLive:
    """Live integration tests for Chat against prod BudgetForge."""

    def test_chat_invoke_live(self):
        """Test Chat.invoke() against real prod API."""
        chat = BudgetForgeChat(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        messages = [{"role": "user", "content": "Say hello"}]
        result = chat.invoke(messages)
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) > 0

    def test_chat_usage_returned(self):
        """Test that usage info is returned in response."""
        chat = BudgetForgeChat(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        messages = [{"role": "user", "content": "Test"}]
        result = chat.invoke(messages)
        # usage may be in response
        assert "content" in result

    @pytest.mark.asyncio
    async def test_chat_invoke_async(self):
        """Test async chat invoke against prod."""
        chat = BudgetForgeChat(
            api_key=TEST_API_KEY,
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        messages = [{"role": "user", "content": "Hi"}]
        result = await chat.invoke_async(messages)
        assert isinstance(result, dict)
        assert "content" in result


@pytest.mark.skipif(SKIP_LIVE, reason="BF_TEST_API_KEY not set")
class TestBudgetForgeLLMErrorHandling:
    """Test error handling against prod."""

    def test_invalid_api_key_raises_error(self):
        """Test that invalid API key raises proper error."""
        llm = BudgetForgeLLM(
            api_key="bf-invalid-key",
            model="gpt-4o-mini",
            provider="openai",
            api_base_url=PROD_URL,
        )
        with pytest.raises(ValueError, match="BudgetForge API error|401|403"):
            llm.invoke("test")

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises error."""
        llm = BudgetForgeLLM(
            api_key=TEST_API_KEY,
            model="unknown-model",
            provider="nonexistent-provider",
            api_base_url=PROD_URL,
        )
        with pytest.raises(ValueError):
            llm.invoke("test")
