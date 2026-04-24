"""Tests pour le système de prix dynamique OpenRouter."""

import pytest
from unittest.mock import patch, AsyncMock

from services.dynamic_pricing import (
    DynamicPricingManager,
    DynamicPricingConfig,
    PricingSourceConfig,
)
from services.cost_calculator import CostCalculator


class TestOpenRouterPricing:
    """Tests spécifiques pour la gestion des prix OpenRouter."""

    def test_openrouter_pricing_source_configuration(self):
        """Test que la source OpenRouter est correctement configurée."""
        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http",
                    url="https://openrouter.ai/api/v1/models",
                    refresh_interval=3600,  # 1 heure
                    enabled=True,
                )
            }
        )

        manager = DynamicPricingManager(config)
        assert "openrouter" in manager.config.sources
        source_config = manager.config.sources["openrouter"]
        assert source_config.type == "http"
        assert source_config.url == "https://openrouter.ai/api/v1/models"
        assert source_config.enabled

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_openrouter_pricing_fetch_success(self, mock_client_class):
        """Test la récupération réussie des prix depuis OpenRouter."""
        # Mock de la réponse OpenRouter
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "openrouter/anthropic/claude-3.5-sonnet",
                    "pricing": {
                        "prompt": 3.0,  # $3.0 par million de tokens d'entrée
                        "completion": 15.0,  # $15.0 par million de tokens de sortie
                    },
                },
                {
                    "id": "openrouter/openai/gpt-4",
                    "pricing": {"prompt": 30.0, "completion": 60.0},
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http", url="https://openrouter.ai/api/v1/models", enabled=True
                )
            }
        )

        manager = DynamicPricingManager(config)

        # Test avec un modèle OpenRouter
        price_config = await manager.get_price("openrouter/anthropic/claude-3.5-sonnet")

        assert price_config.input_per_1m_usd == 3.0
        assert price_config.output_per_1m_usd == 15.0
        assert price_config.provider == "openrouter"
        assert "openrouter" in price_config.source

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_openrouter_pricing_fetch_fallback(self, mock_client_class):
        """Test le fallback quand l'API OpenRouter échoue."""
        # Mock d'une erreur API
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("API unavailable")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http", url="https://openrouter.ai/api/v1/models", enabled=True
                )
            },
            fallback_to_static=True,
        )

        manager = DynamicPricingManager(config)

        # Le fallback devrait utiliser les prix statiques
        # Ajoutons d'abord un prix statique pour test
        from services.cost_calculator import _PRICES

        _PRICES["openrouter/anthropic/claude-3.5-sonnet"] = type(
            "ModelPrice", (), {"input_per_1m_usd": 2.5, "output_per_1m_usd": 12.5}
        )()

        price_config = await manager.get_price("openrouter/anthropic/claude-3.5-sonnet")

        assert price_config.input_per_1m_usd == 2.5
        assert price_config.output_per_1m_usd == 12.5
        assert price_config.source == "static_fallback"

    async def test_openrouter_cost_calculation_integration(self):
        """Test l'intégration du calcul de coût avec OpenRouter."""
        with patch(
            "services.cost_calculator.CostCalculator.get_price"
        ) as mock_get_price:
            # Mock du prix OpenRouter
            from services.cost_calculator import ModelPrice

            mock_get_price.return_value = ModelPrice(
                input_per_1m_usd=3.0, output_per_1m_usd=15.0
            )

            # Calcul du coût pour 1000 tokens d'entrée et 500 tokens de sortie
            cost = await CostCalculator.compute_cost(
                "openrouter/anthropic/claude-3.5-sonnet", tokens_in=1000, tokens_out=500
            )

            # Calcul attendu : (1000 * 3.0 + 500 * 15.0) / 1,000,000
            expected_cost = (1000 * 3.0 + 500 * 15.0) / 1_000_000
            assert abs(cost - expected_cost) < 0.0001

    def test_openrouter_provider_detection(self):
        """Test la détection automatique du fournisseur OpenRouter."""
        from services.dynamic_pricing import DynamicPricingManager

        manager = DynamicPricingManager()

        # Test avec différents formats de modèles OpenRouter
        test_cases = [
            ("openrouter/anthropic/claude-3.5-sonnet", "openrouter"),
            ("openrouter/openai/gpt-4", "openrouter"),
            ("openrouter/google/gemini-pro", "openrouter"),
            ("anthropic/claude-3.5-sonnet", "anthropic"),  # Pas OpenRouter
            ("gpt-4", "openai"),  # Pas OpenRouter
        ]

        for model, expected_provider in test_cases:
            detected = manager._detect_provider(model)
            assert detected == expected_provider, (
                f"Erreur pour {model}: attendu {expected_provider}, obtenu {detected}"
            )

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_openrouter_pricing_cache(self, mock_client_class):
        """Test le cache des prix OpenRouter."""
        import time
        from datetime import datetime

        # Mock de la réponse
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "openrouter/anthropic/claude-3.5-sonnet",
                    "pricing": {"prompt": 3.0, "completion": 15.0},
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http", url="https://openrouter.ai/api/v1/models", enabled=True
                )
            },
            cache_duration=300,  # 5 minutes
        )

        manager = DynamicPricingManager(config)

        # Premier appel - devrait appeler l'API
        price1 = await manager.get_price("openrouter/anthropic/claude-3.5-sonnet")
        assert mock_client.get.call_count == 1

        # Deuxième appel - devrait utiliser le cache
        price2 = await manager.get_price("openrouter/anthropic/claude-3.5-sonnet")
        assert mock_client.get.call_count == 1  # Pas d'appel supplémentaire
        assert price1.input_per_1m_usd == price2.input_per_1m_usd

        # Forcer l'expiration du cache
        manager._cache_timestamps["openrouter/anthropic/claude-3.5-sonnet"] = (
            datetime.fromtimestamp(time.time() - 400)
        )  # Expiré

        # Troisième appel - devrait rappeler l'API
        price3 = await manager.get_price("openrouter/anthropic/claude-3.5-sonnet")
        assert mock_client.get.call_count == 2

    def test_openrouter_pricing_config_validation(self):
        """Test la validation de la configuration des prix OpenRouter."""
        # Configuration valide
        valid_config = PricingSourceConfig(
            type="http",
            url="https://openrouter.ai/api/v1/models",
            refresh_interval=3600,
            enabled=True,
        )
        assert valid_config.type == "http"
        assert valid_config.url == "https://openrouter.ai/api/v1/models"

        # Configuration invalide (URL manquante)
        with pytest.raises(ValueError):
            PricingSourceConfig(type="http", enabled=True)

    async def test_openrouter_unknown_model_handling(self):
        """Test la gestion des modèles OpenRouter inconnus."""
        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http", url="https://openrouter.ai/api/v1/models", enabled=True
                )
            },
            fallback_to_static=False,  # Désactiver le fallback
        )

        manager = DynamicPricingManager(config)

        # Modèle inconnu sans fallback
        with pytest.raises(ValueError, match="Prix non trouvé"):
            await manager.get_price("openrouter/unknown/model")

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_openrouter_pricing_rate_limiting(self, mock_client_class):
        """Test la gestion du rate limiting d'OpenRouter."""

        # Mock d'une réponse rate limit
        mock_response = AsyncMock()
        mock_response.status_code = 429  # Too Many Requests

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "openrouter": PricingSourceConfig(
                    type="http",
                    url="https://openrouter.ai/api/v1/models",
                    enabled=True,
                    refresh_interval=3600,  # Long interval pour éviter les appels fréquents
                )
            }
        )

        manager = DynamicPricingManager(config)

        # Devrait échouer silencieusement et utiliser le fallback si configuré
        # Test avec fallback activé
        config.fallback_to_static = True

        # Ajouter un prix statique pour le fallback
        from services.cost_calculator import _PRICES

        _PRICES["openrouter/test/model"] = type(
            "ModelPrice", (), {"input_per_1m_usd": 1.0, "output_per_1m_usd": 2.0}
        )()

        price = await manager.get_price("openrouter/test/model")
        assert price.input_per_1m_usd == 1.0
        assert price.source == "static_fallback"
