"""TDD RED — Bloc 6: SDK unit tests (default URL + payload correctness)."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(__file__))
from budgetforge_sdk import BudgetForgeLLM, BudgetForgeChat

PROD_URL = "https://llmbudget.maxiaworld.app"


# ── BudgetForgeLLM ────────────────────────────────────────────────────────────


class TestBudgetForgeLLMDefaults:
    def test_default_url_is_prod(self):
        """RED: default api_base_url must be the prod URL, not localhost."""
        llm = BudgetForgeLLM(api_key="test-key")
        assert llm.api_base_url == PROD_URL

    def test_default_model_is_gpt4(self):
        llm = BudgetForgeLLM(api_key="test-key")
        assert llm.model == "gpt-4"

    def test_default_provider_is_openai(self):
        llm = BudgetForgeLLM(api_key="test-key")
        assert llm.provider == "openai"

    def test_custom_url_overrides_default(self):
        llm = BudgetForgeLLM(api_key="k", api_base_url="http://localhost:8011")
        assert llm.api_base_url == "http://localhost:8011"


class TestBudgetForgeLLMInvoke:
    @pytest.mark.asyncio
    async def test_invoke_async_hits_correct_endpoint(self):
        llm = BudgetForgeLLM(
            api_key="key-abc", provider="openai", api_base_url="http://test"
        )
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "hello"}}]
        }

        with patch("budgetforge_sdk.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await llm.invoke_async("say hello")

        assert result == "hello"
        called_url = mock_client.post.call_args[0][0]
        assert called_url == "http://test/proxy/openai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_invoke_async_sends_api_key_in_header(self):
        llm = BudgetForgeLLM(api_key="MY-KEY", api_base_url="http://test")
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("budgetforge_sdk.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            await llm.invoke_async("hi")

        headers = mock_client.post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer MY-KEY"

    @pytest.mark.asyncio
    async def test_invoke_async_raises_on_error_status(self):
        llm = BudgetForgeLLM(api_key="k", api_base_url="http://test")
        fake_response = MagicMock()
        fake_response.status_code = 429
        fake_response.text = "rate limited"

        with patch("budgetforge_sdk.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="429"):
                await llm.invoke_async("hi")


# ── BudgetForgeChat ───────────────────────────────────────────────────────────


class TestBudgetForgeChatDefaults:
    def test_default_url_is_prod(self):
        """RED: default api_base_url must be the prod URL, not localhost."""
        chat = BudgetForgeChat(api_key="test-key")
        assert chat.api_base_url == PROD_URL

    def test_custom_url_overrides_default(self):
        chat = BudgetForgeChat(api_key="k", api_base_url="http://localhost:8011")
        assert chat.api_base_url == "http://localhost:8011"


class TestBudgetForgeChatInvoke:
    @pytest.mark.asyncio
    async def test_invoke_async_sends_messages(self):
        chat = BudgetForgeChat(
            api_key="key-abc", provider="anthropic", api_base_url="http://test"
        )
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }

        messages = [{"role": "user", "content": "ping"}]

        with patch("budgetforge_sdk.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await chat.invoke_async(messages)

        assert result["content"] == "pong"
        called_url = mock_client.post.call_args[0][0]
        assert "/proxy/anthropic/v1/chat/completions" in called_url
