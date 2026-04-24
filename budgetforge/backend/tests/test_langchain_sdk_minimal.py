"""Tests TDD pour le SDK Langchain BudgetForge - Version minimale."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# Ajoute le chemin du SDK au PYTHONPATH
sdk_path = os.path.join(os.path.dirname(__file__), "..", "..", "langchain_budgetforge")
sys.path.insert(0, sdk_path)


class TestLangchainSDKMinimal:
    """Tests pour le SDK Langchain BudgetForge version minimale."""

    def test_budgetforge_llm_class_exists(self):
        """Teste que la classe BudgetForgeLLM existe."""
        try:
            from langchain_budgetforge import BudgetForgeLLM

            assert True, "BudgetForgeLLM devrait être importable"
        except ImportError:
            pytest.fail("BudgetForgeLLM n'existe pas encore")

    def test_budgetforge_chat_class_exists(self):
        """Teste que la classe BudgetForgeChat existe."""
        try:
            from langchain_budgetforge import BudgetForgeChat

            assert True, "BudgetForgeChat devrait être importable"
        except ImportError:
            pytest.fail("BudgetForgeChat n'existe pas encore")

    def test_budgetforge_llm_initialization(self):
        """Teste l'initialisation de BudgetForgeLLM."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")

        assert llm.api_key == "test-key"
        assert llm.model == "gpt-4"
        assert llm.provider == "openai"
        assert llm.api_base_url == "http://localhost:8000"

    def test_budgetforge_chat_initialization(self):
        """Teste l'initialisation de BudgetForgeChat."""
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(
            api_key="test-key", model="claude-3-sonnet", provider="anthropic"
        )

        assert chat.api_key == "test-key"
        assert chat.model == "claude-3-sonnet"
        assert chat.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_budgetforge_llm_invoke_success(self):
        """Teste l'appel réussi de BudgetForgeLLM."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")

        mock_response = {
            "choices": [{"message": {"content": "Paris is the capital of France."}}]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            response = await llm._acall("What is the capital of France?")

            assert response == "Paris is the capital of France."
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_budgetforge_llm_api_error(self):
        """Teste la gestion d'erreur API."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.text = "Unauthorized"

            with pytest.raises(ValueError, match="BudgetForge API error"):
                await llm._acall("Test prompt")

    @pytest.mark.asyncio
    async def test_budgetforge_chat_invoke_success(self):
        """Teste l'appel réussi de BudgetForgeChat."""
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(api_key="test-key", model="gpt-4", provider="openai")

        mock_response = {
            "choices": [{"message": {"content": "Hello! How can I help you today?"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            result = await chat._agenerate(messages)

            assert result["content"] == "Hello! How can I help you today?"
            assert "usage" in result

    def test_budgetforge_llm_streaming(self):
        """Teste le streaming de BudgetForgeLLM."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")

        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            "data: [DONE]",
        ]

        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = mock_response

            chunks = list(llm.stream("Say hello"))

            assert chunks == ["Hello", " world"]

    def test_budgetforge_chat_streaming(self):
        """Teste le streaming de BudgetForgeChat."""
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(api_key="test-key", model="gpt-4", provider="openai")

        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " there"}}]}',
            "data: [DONE]",
        ]

        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Greet me"}]
            generations = list(chat.stream(messages))

            assert len(generations) == 2
            assert generations[0]["content"] == "Hello"
            assert generations[1]["content"] == "Hello there"

    def test_budgetforge_llm_token_estimation(self):
        """Teste l'estimation de tokens."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")

        text = "This is a test sentence for token estimation."
        tokens = llm.get_num_tokens(text)

        # Estimation simple: ~4 chars par token
        expected_tokens = max(len(text) // 4, 1)
        assert tokens == expected_tokens

    def test_budgetforge_chat_token_estimation_messages(self):
        """Teste l'estimation de tokens pour les messages."""
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(api_key="test-key", model="gpt-4", provider="openai")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        tokens = chat.get_num_tokens_from_messages(messages)

        # Estimation basique
        total_content = sum(len(str(msg.get("content", ""))) for msg in messages)
        expected_tokens = max(total_content // 4, 1)
        assert tokens == expected_tokens

    def test_budgetforge_llm_identifying_params(self):
        """Teste les paramètres d'identification."""
        from langchain_budgetforge import BudgetForgeLLM

        llm = BudgetForgeLLM(
            api_key="test-key",
            model="gpt-4",
            provider="openai",
            temperature=0.5,
            max_tokens=100,
        )

        params = llm._identifying_params

        assert params["model"] == "gpt-4"
        assert params["provider"] == "openai"
        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 100

    def test_budgetforge_chat_identifying_params(self):
        """Teste les paramètres d'identification du chat."""
        from langchain_budgetforge import BudgetForgeChat

        chat = BudgetForgeChat(
            api_key="test-key",
            model="claude-3-sonnet",
            provider="anthropic",
            temperature=0.7,
        )

        params = chat._identifying_params

        assert params["model"] == "claude-3-sonnet"
        assert params["provider"] == "anthropic"
        assert params["temperature"] == 0.7
