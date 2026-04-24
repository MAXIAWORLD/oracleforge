"""TDD — Bloc 6: langchain-budgetforge import + invoke tests."""

import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── imports ───────────────────────────────────────────────────────────────────


class TestImports:
    def test_import_budgetforge_llm(self):
        from langchain_budgetforge import BudgetForgeLLM

        assert BudgetForgeLLM is not None

    def test_import_budgetforge_chat(self):
        from langchain_budgetforge import BudgetForgeChat

        assert BudgetForgeChat is not None

    def test_version_is_defined(self):
        import langchain_budgetforge

        assert hasattr(langchain_budgetforge, "__version__")
        assert langchain_budgetforge.__version__ == "0.1.0"


# ── BudgetForgeLLM (minimal) ──────────────────────────────────────────────────


class TestBudgetForgeLLMMinimal:
    def test_init_with_required_params(self):
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", api_base_url="http://test")
        assert llm.api_key == "test-key"
        assert llm.api_base_url == "http://test"

    def test_invoke_hits_correct_endpoint(self):
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="k", provider="openai", api_base_url="http://test")

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_resp)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            result = llm.invoke("hello")

        assert result == "hi"
        called_url = mock_client.post.call_args[0][0]
        assert "http://test/proxy/openai/v1/chat/completions" == called_url

    def test_invoke_sends_api_key_header(self):
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="MY-KEY", api_base_url="http://test")

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_resp)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            llm.invoke("hi")

        headers = mock_client.post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer MY-KEY"


# ── BudgetForgeChat (minimal) ─────────────────────────────────────────────────


class TestBudgetForgeChatMinimal:
    def test_init_with_required_params(self):
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(api_key="test-key", api_base_url="http://test")
        assert chat.api_key == "test-key"

    def test_invoke_sends_messages_list(self):
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(
            api_key="k", provider="anthropic", api_base_url="http://test"
        )

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"total_tokens": 10},
        }

        messages = [{"role": "user", "content": "ping"}]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_resp)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            result = chat.invoke(messages)

        assert result["content"] == "pong"
        called_url = mock_client.post.call_args[0][0]
        assert "/proxy/anthropic/v1/chat/completions" in called_url
