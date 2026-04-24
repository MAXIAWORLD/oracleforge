"""Fixtures pour les tests d'intégration complets."""

from unittest.mock import AsyncMock, patch
import pytest


@pytest.fixture
def mock_all_providers():
    """Mock complet pour tous les fournisseurs LLM."""
    with (
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openai",
            new_callable=AsyncMock,
        ) as mock_openai,
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_anthropic",
            new_callable=AsyncMock,
        ) as mock_anthropic,
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openrouter",
            new_callable=AsyncMock,
        ) as mock_openrouter,
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_together",
            new_callable=AsyncMock,
        ) as mock_together,
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_azure_openai",
            new_callable=AsyncMock,
        ) as mock_azure,
        patch(
            "services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock",
            new_callable=AsyncMock,
        ) as mock_bedrock,
    ):
        # Configurer les mocks avec des réponses réalistes
        mock_openai.return_value = {
            "id": "chatcmpl-integration",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Réponse d'intégration OpenAI",
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        mock_anthropic.return_value = {
            "id": "msg-integration",
            "content": [{"type": "text", "text": "Réponse d'intégration Anthropic"}],
            "usage": {"input_tokens": 12, "output_tokens": 8},
        }

        mock_openrouter.return_value = {
            "id": "chatcmpl-or-integration",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Réponse d'intégration OpenRouter",
                    }
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 6},
        }

        mock_together.return_value = {
            "id": "chatcmpl-together-integration",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Réponse d'intégration Together",
                    }
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10},
        }

        mock_azure.return_value = {
            "id": "chatcmpl-azure-integration",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Réponse d'intégration Azure",
                    }
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 7},
        }

        mock_bedrock.return_value = {
            "id": "msg-bedrock-integration",
            "content": [{"type": "text", "text": "Réponse d'intégration Bedrock"}],
            "usage": {"input_tokens": 11, "output_tokens": 9},
        }

        yield {
            "openai": mock_openai,
            "anthropic": mock_anthropic,
            "openrouter": mock_openrouter,
            "together": mock_together,
            "azure_openai": mock_azure,
            "aws_bedrock": mock_bedrock,
        }


@pytest.fixture
def integration_test_scenarios():
    """Scénarios de test d'intégration réalistes."""
    return [
        {
            "name": "Usage normal avec budget",
            "project_config": {
                "budget_usd": 100.0,
                "alert_threshold_pct": 80,
                "allowed_providers": ["openai", "anthropic"],
            },
            "requests": [
                {"provider": "openai", "tokens_in": 1000, "tokens_out": 500},
                {"provider": "anthropic", "tokens_in": 800, "tokens_out": 600},
            ],
            "expected": {"total_cost": "~0.10", "alerts_triggered": False},
        },
        {
            "name": "Dépassement de budget",
            "project_config": {
                "budget_usd": 0.05,
                "alert_threshold_pct": 50,
                "allowed_providers": ["openai"],
            },
            "requests": [{"provider": "openai", "tokens_in": 2000, "tokens_out": 1500}],
            "expected": {
                "total_cost": ">0.05",
                "alerts_triggered": True,
                "blocked_requests": True,
            },
        },
        {
            "name": "Usage illimité",
            "project_config": {
                "budget_usd": None,
                "allowed_providers": ["openrouter", "together"],
            },
            "requests": [
                {"provider": "openrouter", "tokens_in": 5000, "tokens_out": 3000},
                {"provider": "together", "tokens_in": 3000, "tokens_out": 2000},
            ],
            "expected": {
                "total_cost": ">0",
                "alerts_triggered": False,
                "all_requests_successful": True,
            },
        },
    ]


def run_integration_test(client, project, scenario, mock_providers):
    """Exécute un scénario de test d'intégration complet."""
    results = []

    for request_config in scenario["requests"]:
        provider = request_config["provider"]
        endpoint = f"/proxy/{provider}/v1/chat/completions"

        # Adapter l'endpoint pour Anthropic
        if provider == "anthropic":
            endpoint = "/proxy/anthropic/v1/messages"

        payload = {
            "model": "gpt-4o" if provider == "openai" else "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": "Test d'intégration"}],
            "max_tokens": 100,
        }

        response = client.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {project.api_key}"},
        )

        results.append(
            {
                "provider": provider,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
            }
        )

    return results
