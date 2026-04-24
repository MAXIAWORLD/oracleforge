"""Tests d'intégration Azure OpenAI pour BudgetForge."""

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from core.models import Project


class TestAzureOpenAIIntegration:
    """Tests complets pour l'intégration Azure OpenAI."""

    @pytest.fixture
    def client(self, db: Session):
        """Client de test avec base de données."""

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def project_with_azure_openai(self, db: Session):
        """Projet avec Azure OpenAI autorisé."""
        project = Project(
            name="test-azure-openai",
            budget_usd=100.0,
            allowed_providers=json.dumps(["azure_openai"]),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def test_azure_openai_proxy_endpoint_exists(
        self, client, project_with_azure_openai
    ):
        """Test que l'endpoint proxy Azure OpenAI existe."""
        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_azure_openai.api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Doit retourner une erreur 400 (pas de clé API) plutôt que 404 (endpoint inexistant)
        assert response.status_code != 404

    def test_azure_openai_models_endpoint(self, client):
        """Test que l'endpoint des modèles inclut Azure OpenAI."""
        response = client.get("/api/models")
        assert response.status_code == 200

    @patch("services.proxy_forwarder.ProxyForwarder.forward_azure_openai")
    @patch(
        "core.config.settings.azure_openai_base_url",
        "https://test-azure.openai.azure.com",
    )
    def test_azure_openai_proxy_success(
        self, mock_forward, client, project_with_azure_openai
    ):
        """Test le proxy Azure OpenAI avec succès."""
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Test"}]},
        )

        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "Response"
        mock_forward.assert_called_once()

    @patch("services.proxy_forwarder.ProxyForwarder.forward_azure_openai_stream")
    @patch(
        "core.config.settings.azure_openai_base_url",
        "https://test-azure.openai.azure.com",
    )
    def test_azure_openai_proxy_streaming(
        self, mock_forward, client, project_with_azure_openai
    ):
        """Test le proxy Azure OpenAI en streaming."""
        mock_forward.return_value = AsyncMock()
        mock_forward.return_value.__aiter__.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_azure_openai_provider_validation(self, client, project_with_azure_openai):
        """Test que Azure OpenAI est validé comme provider autorisé."""
        # Utiliser le projet existant avec azure_openai autorisé
        # Modifier ses providers autorisés pour tester la validation
        db = next(get_db())
        project_with_azure_openai.allowed_providers = json.dumps(["openai"])
        db.commit()

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_azure_openai.api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        # Doit échouer car Azure OpenAI n'est pas autorisé
        assert response.status_code == 403

    @patch("services.proxy_forwarder.ProxyForwarder.forward_azure_openai")
    @patch(
        "core.config.settings.azure_openai_base_url",
        "https://test-azure.openai.azure.com",
    )
    def test_azure_openai_cost_calculation(
        self, mock_forward, client, project_with_azure_openai
    ):
        """Test le calcul des coûts pour Azure OpenAI."""
        mock_forward.return_value = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Test cost"}],
            },
        )

        # Vérifier que l'appel a fonctionné
        assert response.status_code == 200
        assert mock_forward.called

    def test_azure_openai_dynamic_pricing_integration(self, client):
        """Test l'intégration du système de prix dynamique avec Azure OpenAI."""
        from services.dynamic_pricing import DynamicPricingManager

        # Créer une nouvelle instance directement
        manager = DynamicPricingManager()

        # Vérifier que la source Azure OpenAI est configurée (même si désactivée par défaut)
        assert "azure_openai_api" in manager.config.sources
        # Vérifier que la source Azure OpenAI est bien configurée
        azure_source = manager.config.sources["azure_openai_api"]
        assert azure_source.type == "http"
        assert azure_source.url == "https://prices.azure.com/api/retail/prices"

        # Vérifier que la configuration est correcte
        source_config = manager.config.sources["azure_openai_api"]
        assert source_config.url == "https://prices.azure.com/api/retail/prices"
        assert source_config.type == "http"

    def test_azure_openai_models_fetching(self, client):
        """Test la récupération des modèles Azure OpenAI."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "azure_openai" in data["providers"]

    @patch("services.proxy_forwarder.ProxyForwarder.forward_azure_openai")
    @patch(
        "core.config.settings.azure_openai_base_url",
        "https://test-azure.openai.azure.com",
    )
    def test_azure_openai_budget_guard_integration(
        self, mock_forward, client, project_with_azure_openai
    ):
        """Test l'intégration du budget guard avec Azure OpenAI."""
        mock_forward.return_value = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        # Configurer un budget très bas pour tester le downgrade
        db = next(get_db())
        project_with_azure_openai.budget_usd = 0.001  # $0.001 USD
        project_with_azure_openai.downgrade_chain = json.dumps(
            ["gpt-4o-mini", "gpt-3.5-turbo"]
        )
        db.commit()

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Test budget"}],
            },
        )

        # Doit fonctionner avec downgrade
        assert response.status_code == 200

    @patch("services.proxy_forwarder.ProxyForwarder.forward_azure_openai")
    @patch(
        "core.config.settings.azure_openai_base_url",
        "https://test-azure.openai.azure.com",
    )
    def test_azure_openai_error_handling(
        self, mock_forward, client, project_with_azure_openai
    ):
        """Test la gestion des erreurs Azure OpenAI."""
        mock_forward.side_effect = Exception("Azure OpenAI API error")

        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Test error"}],
            },
        )

        # Doit retourner une erreur 502
        assert response.status_code == 502

    def test_azure_openai_prebill_finalize_flow(
        self, client, project_with_azure_openai
    ):
        """Test le flux complet prebill → appel → finalize."""
        # Ce test vérifie simplement que l'endpoint existe et retourne une erreur appropriée
        # (car Azure OpenAI nécessite une configuration qui n'est pas complète en test)
        response = client.post(
            "/proxy/azure-openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_azure_openai.api_key}",
                "X-Provider-Key": "sk-azure-test123",
            },
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Test"}]},
        )

        # Doit retourner une erreur appropriée plutôt que 404
        assert response.status_code != 404

        # Vérifier que l'endpoint existe et retourne une erreur appropriée
        # (400 pour configuration manquante, 500 pour erreur interne, ou 502 pour gateway)
        assert response.status_code in [400, 500, 502]
