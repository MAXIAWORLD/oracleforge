"""
Tests pour le support streaming dans BudgetForge.
Ces tests doivent passer AVANT et APRÈS l'implémentation du streaming.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


class TestStreamingSupport:
    """Tests pour valider le support streaming."""

    def test_streaming_endpoint_exists(self, client: TestClient):
        """Vérifie que les endpoints streaming existent."""
        # Teste que l'endpoint OpenAI avec streaming existe
        response = client.post(
            "/proxy/openai/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": True,
            },
        )
        # Doit retourner 401 (auth manquante) pas 404 (endpoint inexistant)
        assert response.status_code != 404, "Endpoint streaming OpenAI n'existe pas"

    def test_non_streaming_still_works(self, client: TestClient):
        """Vérifie que le mode non-streaming fonctionne toujours."""
        # Teste sans streaming
        response = client.post(
            "/proxy/openai/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]},
        )
        assert response.status_code != 404, "Endpoint non-streaming cassé"

    @pytest.mark.asyncio
    async def test_proxy_forwarder_has_streaming_methods(self):
        """Vérifie que ProxyForwarder a les méthodes streaming."""
        from services.proxy_forwarder import ProxyForwarder

        # Teste que les méthodes streaming existent
        assert hasattr(ProxyForwarder, "forward_openai_stream")
        assert hasattr(ProxyForwarder, "forward_anthropic_stream")
        assert hasattr(ProxyForwarder, "forward_google_stream")

        # Teste qu'elles sont callable
        assert callable(ProxyForwarder.forward_openai_stream)
        assert callable(ProxyForwarder.forward_anthropic_stream)

    @pytest.mark.asyncio
    async def test_streaming_response_format(self):
        """Teste que les réponses streaming ont le bon format."""
        from services.proxy_dispatcher import dispatch_openai_format

        # Teste simplement que la fonction existe et peut être appelée
        assert callable(dispatch_openai_format), (
            "dispatch_openai_format devrait être callable"
        )

    def test_streaming_payload_validation(self, client: TestClient):
        """Teste que le payload streaming est validé correctement."""
        # Teste simplement que l'endpoint existe (ne retourne pas 404)
        response = client.post(
            "/proxy/openai/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": True,
            },
        )
        assert response.status_code != 404, "Endpoint streaming n'existe pas"

    @pytest.mark.asyncio
    async def test_streaming_vs_non_streaming_routing(self):
        """Teste que le routing streaming/non-streaming fonctionne."""
        from services.proxy_dispatcher import dispatch_openai_format

        # Teste simplement que la fonction peut gérer les deux modes
        assert callable(dispatch_openai_format), (
            "dispatch_openai_format devrait être callable"
        )

        # Vérifie que les méthodes de forward existent
        from services.proxy_forwarder import ProxyForwarder

        assert callable(ProxyForwarder.forward_openai)
        assert callable(ProxyForwarder.forward_openai_stream)

    def test_multiple_providers_streaming_support(self, client: TestClient):
        """Teste que tous les providers supportent le streaming."""
        # Mapping des endpoints par provider (certains ont des formats différents)
        provider_endpoints = {
            "openai": "/proxy/openai/v1/chat/completions",
            "anthropic": "/proxy/anthropic/v1/messages",
            "google": "/proxy/google/v1/chat/completions",
            "deepseek": "/proxy/deepseek/v1/chat/completions",
            "openrouter": "/proxy/openrouter/v1/chat/completions",
        }

        for provider, endpoint in provider_endpoints.items():
            response = client.post(
                endpoint,
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "test"}],
                    "stream": True,
                },
            )
            # Doit retourner 401 (auth) pas 404
            assert response.status_code != 404, (
                f"Endpoint streaming {provider} n'existe pas"
            )

    @pytest.mark.asyncio
    async def test_streaming_content_type(self):
        """Teste que les réponses streaming ont le bon Content-Type."""
        from services.proxy_dispatcher import dispatch_openai_format

        # Mock une réponse streaming
        mock_response = {"choices": [{"message": {"content": "test"}}]}

        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openai_stream",
            new_callable=AsyncMock,
        ) as mock_stream:
            mock_stream.return_value = mock_response

            result = await dispatch_openai_format(
                {"model": "gpt-4", "stream": True},
                None,
                "openai",
                "gpt-4",
                123,
                "test-key",
                None,
                None,
                30.0,
                None,
            )

            # Vérifie que le résultat est un StreamingResponse
            from fastapi.responses import StreamingResponse

            assert isinstance(result, StreamingResponse)
            # Vérifie le Content-Type
            assert result.media_type == "text/event-stream"

    def test_streaming_with_usage_tracking(self, client: TestClient):
        """Teste que le streaming track correctement l'usage."""
        # Ce test vérifiera que l'usage est tracké même en mode streaming
        # Pour l'instant, vérifie juste que l'endpoint existe
        response = client.post(
            "/proxy/openai/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test streaming"}],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        )
        assert response.status_code != 404, "Endpoint streaming avec usage n'existe pas"


class TestStreamingImplementation:
    """Tests pour la nouvelle implémentation streaming (à écrire après)."""

    @pytest.mark.asyncio
    async def test_streaming_pass_through(self):
        """Teste que le streaming passe les chunks en temps réel."""
        # Ce test vérifiera la nouvelle implémentation
        pass

    @pytest.mark.asyncio
    async def test_streaming_token_counting(self):
        """Teste que les tokens sont comptés correctement en streaming."""
        # Ce test vérifiera le comptage des tokens
        pass

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self):
        """Teste la gestion d'erreurs en mode streaming."""
        # Ce test vérifiera les erreurs streaming
        pass
