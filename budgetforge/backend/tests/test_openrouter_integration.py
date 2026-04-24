"""Tests d'intégration OpenRouter pour BudgetForge."""

import pytest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from core.models import Project, Usage


class TestOpenRouterIntegration:
    """Tests complets pour l'intégration OpenRouter."""

    @pytest.fixture
    def client(self, db: Session):
        """Client de test avec base de données."""

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def project_with_openrouter(self, db: Session):
        """Projet avec OpenRouter autorisé."""
        project = Project(
            name="test-openrouter",
            budget_usd=100.0,
            allowed_providers=json.dumps(["openrouter"]),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def test_openrouter_proxy_endpoint_exists(self, client, project_with_openrouter):
        """Test que l'endpoint proxy OpenRouter existe."""
        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_openrouter.api_key}"},
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Doit retourner une erreur 400 (pas de clé API) plutôt que 404 (endpoint inexistant)
        assert response.status_code != 404

    def test_openrouter_models_endpoint(self, client):
        """Test que l'endpoint des modèles OpenRouter fonctionne."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        # OpenRouter devrait être dans la liste des providers
        assert "openrouter" in data["providers"]

    @patch("services.proxy_forwarder.ProxyForwarder.forward_openrouter")
    def test_openrouter_proxy_success(
        self, mock_forward, client, project_with_openrouter
    ):
        """Test proxy OpenRouter avec réponse simulée."""
        # Mock de la réponse OpenRouter
        mock_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "openrouter/anthropic/claude-3.5-sonnet",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_openrouter.api_key}",
                "X-Provider-Key": "sk-or-test123",
            },
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you?"
        mock_forward.assert_called_once()

    @patch("services.proxy_forwarder.ProxyForwarder.forward_openrouter_stream")
    def test_openrouter_proxy_streaming(
        self, mock_stream, client, project_with_openrouter
    ):
        """Test proxy OpenRouter en mode streaming."""

        # Mock du streaming
        async def mock_stream_generator():
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
            yield b'data: {"choices":[{"delta":{"content":" world!"}}]}\n'
            yield b"data: [DONE]\n"

        mock_stream.return_value = mock_stream_generator()

        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_openrouter.api_key}",
                "X-Provider-Key": "sk-or-test123",
            },
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "max_tokens": 100,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        content = response.content.decode()
        assert "Hello" in content
        assert "world" in content

    def test_openrouter_provider_validation(self, client, project_with_openrouter):
        """Test que OpenRouter est validé comme provider autorisé."""
        # Utiliser le projet existant avec openrouter autorisé
        # Modifier ses providers autorisés pour tester la validation
        db = next(get_db())
        project_with_openrouter.allowed_providers = json.dumps(["openai"])
        db.commit()

        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_openrouter.api_key}"},
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 403
        assert "not allowed" in response.json()["detail"]

    @patch("services.cost_calculator.CostCalculator.get_price")
    def test_openrouter_cost_calculation(
        self, mock_get_price, client, project_with_openrouter
    ):
        """Test du calcul des coûts pour les modèles OpenRouter."""
        from services.cost_calculator import ModelPrice

        # Mock du prix OpenRouter
        mock_get_price.return_value = ModelPrice(
            input_per_1m_usd=1.0, output_per_1m_usd=2.0
        )

        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_openrouter.api_key}",
                "X-Provider-Key": "sk-or-test123",
            },
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Test message"}],
            },
        )

        # Vérifier que le calcul de prix a été appelé avec le bon modèle
        mock_get_price.assert_called_once_with("openrouter/anthropic/claude-3.5-sonnet")

    def test_openrouter_dynamic_pricing_integration(self, client):
        """Test l'intégration du système de prix dynamique avec OpenRouter."""
        # Ce test vérifie que OpenRouter est bien intégré au système de prix dynamique
        from services.dynamic_pricing import get_pricing_manager

        manager = get_pricing_manager()

        # Vérifier que la source OpenRouter est configurée
        assert "openrouter_api" in manager.config.sources

        # Vérifier que la configuration est correcte
        source_config = manager.config.sources["openrouter_api"]
        assert source_config.url == "https://openrouter.ai/api/v1/models"
        assert source_config.type == "http"

    def test_openrouter_models_fetching(self, client):
        """Test la récupération des modèles OpenRouter."""
        with patch("routes.models._fetch_openrouter_models") as mock_fetch:
            mock_fetch.return_value = [
                "openrouter/anthropic/claude-3.5-sonnet",
                "openrouter/openai/gpt-4",
                "openrouter/google/gemini-pro",
            ]

            response = client.get("/api/models")
            assert response.status_code == 200
            data = response.json()

            assert "openrouter" in data["providers"]
            models = data["providers"]["openrouter"]
            assert len(models) > 0
            assert "openrouter/anthropic/claude-3.5-sonnet" in models

    @patch("services.proxy_forwarder.ProxyForwarder.forward_openrouter")
    def test_openrouter_budget_guard_integration(
        self, mock_forward, client, project_with_openrouter
    ):
        """Test l'intégration avec le système de garde-budget."""
        # Créer un usage pour tester la garde-budget
        from core.models import Usage

        db = next(get_db())

        # Simuler un usage existant
        usage = Usage(
            project_id=project_with_openrouter.id,
            provider="openrouter",
            model="openrouter/anthropic/claude-3.5-sonnet",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.75,
        )
        db.add(usage)
        db.commit()

        # Mock de la réponse OpenRouter
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/openrouter/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_openrouter.api_key}",
                "X-Provider-Key": "sk-or-test123",
            },
            json={
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # Le budget n'est pas dépassé, donc devrait passer
        assert response.status_code == 200

    def test_openrouter_error_handling(self, client, project_with_openrouter):
        """Test la gestion des erreurs OpenRouter."""
        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openrouter"
        ) as mock_forward:
            mock_forward.side_effect = Exception("OpenRouter API error")

            response = client.post(
                "/proxy/openrouter/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {project_with_openrouter.api_key}",
                    "X-Provider-Key": "sk-or-test123",
                },
                json={
                    "model": "openrouter/anthropic/claude-3.5-sonnet",
                    "messages": [{"role": "user", "content": "Test"}],
                },
            )

            # Doit retourner une erreur 502 (bad gateway)
            assert response.status_code == 502
            assert "LLM provider unavailable" in response.json()["detail"]

    def test_openrouter_prebill_finalize_flow(self, client, project_with_openrouter):
        """Test le flux complet prebill → appel → finalize."""
        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openrouter"
        ) as mock_forward:
            mock_response = {
                "id": "test-123",
                "choices": [{"message": {"role": "assistant", "content": "Response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_forward.return_value = mock_response

            response = client.post(
                "/proxy/openrouter/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {project_with_openrouter.api_key}",
                    "X-Provider-Key": "sk-or-test123",
                },
                json={
                    "model": "openrouter/anthropic/claude-3.5-sonnet",
                    "messages": [{"role": "user", "content": "Test"}],
                },
            )

            assert response.status_code == 200

            # Vérifier qu'un usage a été créé
            db = next(get_db())
            usage = (
                db.query(Usage).filter_by(project_id=project_with_openrouter.id).first()
            )
            assert usage is not None
            assert usage.provider == "openrouter"
            assert usage.model == "openrouter/anthropic/claude-3.5-sonnet"
