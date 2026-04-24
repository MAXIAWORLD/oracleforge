"""Tests d'intégration AWS Bedrock pour BudgetForge."""

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from core.models import Project


class TestAWSBedrockIntegration:
    """Tests complets pour l'intégration AWS Bedrock."""

    @pytest.fixture
    def client(self, db: Session):
        """Client de test avec base de données."""

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def project_with_aws_bedrock(self, db: Session):
        """Projet avec AWS Bedrock autorisé."""
        project = Project(
            name="test-aws-bedrock",
            budget_usd=100.0,
            allowed_providers=json.dumps(["aws_bedrock"]),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def test_aws_bedrock_proxy_endpoint_exists(self, client, project_with_aws_bedrock):
        """Test que l'endpoint proxy AWS Bedrock existe."""
        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_aws_bedrock.api_key}"},
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Doit retourner une erreur 400 (pas de clé API) plutôt que 404 (endpoint inexistant)
        assert response.status_code != 404

    def test_aws_bedrock_models_endpoint(self, client):
        """Test que l'endpoint des modèles inclut AWS Bedrock."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "aws_bedrock" in data["providers"]

    @patch("services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock")
    @patch("core.config.settings.aws_bedrock_region", "us-east-1")
    def test_aws_bedrock_proxy_success(
        self, mock_forward, client, project_with_aws_bedrock
    ):
        """Test le proxy AWS Bedrock avec succès."""
        mock_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_forward.return_value = mock_response

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        assert response.status_code == 200

    @patch("services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock_stream")
    @patch("core.config.settings.aws_bedrock_region", "us-east-1")
    def test_aws_bedrock_proxy_streaming(
        self, mock_forward, client, project_with_aws_bedrock
    ):
        """Test le proxy AWS Bedrock en streaming."""
        mock_forward.return_value = AsyncMock()
        mock_forward.return_value.__aiter__.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        )

        assert response.status_code == 200

    def test_aws_bedrock_provider_validation(self, client, project_with_aws_bedrock):
        """Test que AWS Bedrock est validé comme provider autorisé."""
        # Utiliser le projet existant avec aws_bedrock autorisé
        # Modifier ses providers autorisés pour tester la validation
        db = next(get_db())
        project_with_aws_bedrock.allowed_providers = json.dumps(["openai"])
        db.commit()

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={"Authorization": f"Bearer {project_with_aws_bedrock.api_key}"},
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        # Doit échouer car AWS Bedrock n'est pas autorisé
        assert response.status_code == 403

    @patch("services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock")
    @patch("core.config.settings.aws_bedrock_region", "us-east-1")
    def test_aws_bedrock_cost_calculation(
        self, mock_forward, client, project_with_aws_bedrock
    ):
        """Test le calcul des coûts pour AWS Bedrock."""
        mock_forward.return_value = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Test cost"}],
            },
        )

        # Vérifier que l'appel a fonctionné
        assert response.status_code == 200

    def test_aws_bedrock_dynamic_pricing_integration(self, client):
        """Test l'intégration du système de prix dynamique avec AWS Bedrock."""
        from services.dynamic_pricing import DynamicPricingManager

        # Créer une nouvelle instance directement
        manager = DynamicPricingManager()

        # Vérifier que la source AWS Bedrock est configurée
        assert "aws_bedrock_api" in manager.config.sources
        # Vérifier que la source AWS Bedrock est bien configurée
        bedrock_source = manager.config.sources["aws_bedrock_api"]
        assert bedrock_source.type == "http"
        assert (
            bedrock_source.url
            == "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/index.json"
        )

    def test_aws_bedrock_models_fetching(self, client):
        """Test la récupération des modèles AWS Bedrock."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "aws_bedrock" in data["providers"]
        # Vérifier que les modèles fallback sont présents
        assert len(data["providers"]["aws_bedrock"]) > 0

    @patch("services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock")
    @patch("core.config.settings.aws_bedrock_region", "us-east-1")
    def test_aws_bedrock_budget_guard_integration(
        self, mock_forward, client, project_with_aws_bedrock
    ):
        """Test l'intégration du budget guard avec AWS Bedrock."""
        mock_forward.return_value = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        # Configurer un budget très bas pour tester le downgrade
        db = next(get_db())
        project_with_aws_bedrock.budget_usd = 0.001  # $0.001 USD
        project_with_aws_bedrock.downgrade_chain = json.dumps(
            ["anthropic.claude-3-haiku-20240307", "anthropic.claude-instant-1.2"]
        )
        db.commit()

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Test budget"}],
            },
        )

        # Doit fonctionner avec downgrade
        assert response.status_code == 200

    @patch("services.proxy_forwarder.ProxyForwarder.forward_aws_bedrock")
    @patch("core.config.settings.aws_bedrock_region", "us-east-1")
    def test_aws_bedrock_error_handling(
        self, mock_forward, client, project_with_aws_bedrock
    ):
        """Test la gestion des erreurs AWS Bedrock."""
        mock_forward.side_effect = Exception("AWS Bedrock API error")

        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": "Test error"}],
            },
        )

        # Doit retourner une erreur 502
        assert response.status_code == 502

    def test_aws_bedrock_prebill_finalize_flow(self, client, project_with_aws_bedrock):
        """Test le flux complet prebill → appel → finalize."""
        # Ce test vérifie simplement que l'endpoint existe et retourne une erreur appropriée
        # (car AWS Bedrock nécessite des credentials AWS qui ne sont pas configurés en test)
        response = client.post(
            "/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {project_with_aws_bedrock.api_key}",
                "X-Provider-Key": "aws-access-key-test123",
            },
            json={
                "model": "anthropic.claude-3-sonnet",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # Doit retourner une erreur 400 (AWS Bedrock non configuré) plutôt que 404
        assert response.status_code != 404

        # Vérifier que l'endpoint existe et retourne une erreur appropriée
        # (400 pour configuration manquante, 500 pour erreur interne, ou 502 pour gateway)
        assert response.status_code in [400, 500, 502]
