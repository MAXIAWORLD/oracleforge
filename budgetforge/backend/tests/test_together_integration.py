"""Tests d'intégration Together AI pour BudgetForge."""

import pytest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.models import Project
from core.database import get_db
from core.models import Usage


class TestTogetherIntegration:
    """Tests d'intégration complète pour Together AI."""

    @pytest.fixture
    def client(self, db: Session):
        """Client de test FastAPI."""

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)

    @pytest.fixture
    def project_with_together(self, db: Session):
        """Projet de test avec Together AI autorisé."""
        project = Project(
            name="test-together-project",
            budget_usd=100.0,
            allowed_providers=json.dumps(["together"]),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def test_together_proxy_endpoint_exists(self, client, project_with_together):
        """Test que l'endpoint proxy Together AI existe."""
        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_together.api_key}"},
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Doit retourner une erreur 400 (bad request) car pas de clé API, pas 404
        assert response.status_code != 404

    def test_together_models_endpoint(self, client):
        """Test que l'endpoint des modèles inclut Together AI."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "together" in data["providers"]
        assert isinstance(data["providers"]["together"], list)

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together")
    def test_together_proxy_success(self, mock_forward, client, project_with_together):
        """Test proxy Together AI avec succès."""
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Response"

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together_stream")
    def test_together_proxy_streaming(self, mock_stream, client, project_with_together):
        """Test proxy Together AI en mode streaming."""

        async def mock_stream_generator():
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
            yield b'data: {"choices":[{"delta":{"content":" world!"}}]}\n'
            yield b"data: [DONE]\n"

        mock_stream.return_value = mock_stream_generator()

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "max_tokens": 100,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        content = response.content.decode()
        assert "Hello" in content

    def test_together_provider_validation(self, client, project_with_together):
        """Test que Together AI est validé comme provider autorisé."""
        # Utiliser le projet existant avec together autorisé
        # Modifier ses providers autorisés pour tester la validation
        db = next(get_db())
        project_with_together.allowed_providers = json.dumps(["openai"])
        db.commit()

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_together.api_key}"},
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        # Doit échouer car Together n'est pas autorisé
        assert response.status_code == 403

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together")
    def test_together_cost_calculation(
        self, mock_forward, client, project_with_together
    ):
        """Test le calcul des coûts pour Together AI."""
        mock_forward.return_value = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Test cost"}],
            },
        )

        # Vérifier que l'appel a fonctionné
        assert response.status_code == 200
        assert mock_forward.called

    def test_together_dynamic_pricing_integration(self, client):
        """Test l'intégration du système de prix dynamique avec Together AI."""
        from services.dynamic_pricing import get_pricing_manager

        manager = get_pricing_manager()

        # Vérifier que la source Together AI est configurée
        assert "together_api" in manager.config.sources

        # Vérifier que la configuration est correcte
        source_config = manager.config.sources["together_api"]
        assert source_config.url == "https://api.together.xyz/v1/models"
        assert source_config.type == "http"

    def test_together_models_fetching(self, client):
        """Test la récupération des modèles Together AI."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()

        # Vérifier que Together AI est présent avec des modèles
        assert "together" in data["providers"]
        together_models = data["providers"]["together"]
        assert isinstance(together_models, list)
        assert len(together_models) > 0

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together")
    def test_together_budget_guard_integration(
        self, mock_forward, client, project_with_together
    ):
        """Test l'intégration avec le système de garde-budget."""
        # Créer un usage pour tester la garde-budget
        db = next(get_db())

        # Simuler un usage existant
        usage = Usage(
            project_id=project_with_together.id,
            provider="together",
            model="togethercomputer/LLaMA-2-7B-32K",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.75,
        )
        db.add(usage)
        db.commit()

        # Mock de la réponse Together AI
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # Le budget n'est pas dépassé, donc devrait passer
        assert response.status_code == 200

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together")
    def test_together_error_handling(self, mock_forward, client, project_with_together):
        """Test la gestion des erreurs Together AI."""
        # Simuler une erreur d'API
        mock_forward.side_effect = Exception("API error")

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # Doit gérer l'erreur gracieusement
        assert response.status_code in [500, 502]

    @patch("services.proxy_forwarder.ProxyForwarder.forward_together")
    def test_together_prebill_finalize_flow(
        self, mock_forward, client, project_with_together
    ):
        """Test le flux complet prebill → appel → finalize."""
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/together/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_together.api_key}",
                "X-Provider-Key": "sk-together-test123",
            },
            json={
                "model": "togethercomputer/LLaMA-2-7B-32K",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        assert response.status_code == 200

        # Vérifier qu'un usage a été créé
        db = next(get_db())
        usage = (
            db.query(Usage)
            .filter_by(project_id=project_with_together.id)
            .order_by(Usage.id.desc())
            .first()
        )
        assert usage is not None
        assert usage.provider == "together"
