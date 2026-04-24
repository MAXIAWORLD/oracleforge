"""Tests de prix dynamique Together AI pour BudgetForge."""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime

from services.dynamic_pricing import (
    DynamicPricingManager,
    DynamicPricingConfig,
    PricingSourceConfig,
    PriceConfig,
)


class TestTogetherPricing:
    """Tests de prix dynamique pour Together AI."""

    def test_together_pricing_source_configuration(self):
        """Test la configuration de la source de prix Together AI."""
        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http",
                    url="https://api.together.xyz/v1/models",
                    refresh_interval=3600,
                    enabled=True,
                )
            }
        )

        manager = DynamicPricingManager(config)
        assert "together_api" in manager.config.sources
        assert manager.config.sources["together_api"].enabled
        assert (
            manager.config.sources["together_api"].url
            == "https://api.together.xyz/v1/models"
        )

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_together_pricing_fetch_success(self, mock_client_class):
        """Test la récupération réussie des prix depuis Together AI."""
        # Mock de la réponse Together AI
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "togethercomputer/LLaMA-2-7B-32K",
                    "pricing": {
                        "prompt": 0.15,  # $0.15 par million de tokens d'entrée
                        "completion": 0.20,  # $0.20 par million de tokens de sortie
                    },
                },
                {
                    "id": "togethercomputer/LLaMA-2-70B",
                    "pricing": {"prompt": 0.70, "completion": 0.80},
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http", url="https://api.together.xyz/v1/models", enabled=True
                )
            }
        )

        manager = DynamicPricingManager(config)

        # Test avec un modèle Together AI
        price_config = await manager.get_price("togethercomputer/LLaMA-2-7B-32K")

        assert price_config.input_per_1m_usd == 0.15
        assert price_config.output_per_1m_usd == 0.20
        assert price_config.provider == "together"
        assert "together" in price_config.source

    @patch("services.dynamic_pricing.httpx.AsyncClient")
    async def test_together_pricing_fetch_fallback(self, mock_client_class):
        """Test le fallback vers les prix statiques en cas d'échec."""
        # Mock d'une erreur d'API
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("API error")

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http", url="https://api.together.xyz/v1/models", enabled=True
                )
            },
            fallback_to_static=True,
        )

        manager = DynamicPricingManager(config)

        # Doit utiliser le fallback statique
        price_config = await manager.get_price("togethercomputer/LLaMA-2-7B-32K")

        assert price_config.source == "static_fallback"

    def test_together_cost_calculation_integration(self):
        """Test l'intégration du calcul de coût avec Together AI."""
        from services.cost_calculator import CostCalculator

        calculator = CostCalculator()

        # Test avec des prix Together AI
        cost = calculator.calculate_cost(
            provider="together",
            model="togethercomputer/LLaMA-2-7B-32K",
            tokens_in=1000,
            tokens_out=500,
        )

        assert isinstance(cost, float)
        assert cost >= 0

    def test_together_provider_detection(self):
        """Test la détection automatique du fournisseur Together AI."""
        from services.dynamic_pricing import DynamicPricingManager

        manager = DynamicPricingManager()

        # Test avec différents formats de modèles Together AI
        test_cases = [
            ("togethercomputer/LLaMA-2-7B-32K", "together"),
            ("togethercomputer/LLaMA-2-70B", "together"),
            ("togethercomputer/Mistral-7B", "together"),
            ("llama-2-7b", "unknown"),  # Pas Together AI
            ("gpt-4", "openai"),  # Pas Together AI
        ]

        for model, expected_provider in test_cases:
            detected = manager._detect_provider(model)
            assert detected == expected_provider, (
                f"Erreur pour {model}: attendu {expected_provider}, obtenu {detected}"
            )

    async def test_together_pricing_cache(self):
        """Test le système de cache pour les prix Together AI."""
        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http", url="https://api.together.xyz/v1/models", enabled=True
                )
            },
            cache_duration=300,  # 5 minutes
        )

        manager = DynamicPricingManager(config)

        # Premier appel - devrait mettre en cache
        with patch(
            "services.dynamic_pricing.DynamicPricingManager._fetch_from_sources"
        ) as mock_fetch:
            mock_fetch.return_value = PriceConfig(
                input_per_1m_usd=0.15,
                output_per_1m_usd=0.20,
                provider="together",
                source="test",
            )

            price1 = await manager.get_price("togethercomputer/LLaMA-2-7B-32K")
            assert mock_fetch.call_count == 1

            # Deuxième appel - devrait utiliser le cache
            price2 = await manager.get_price("togethercomputer/LLaMA-2-7B-32K")
            assert mock_fetch.call_count == 1  # Pas d'appel supplémentaire
            assert price1 == price2

    def test_together_pricing_config_validation(self):
        """Test la validation de la configuration des prix Together AI."""
        # Configuration valide
        valid_config = PricingSourceConfig(
            type="http",
            url="https://api.together.xyz/v1/models",
            refresh_interval=3600,
            enabled=True,
        )
        assert valid_config.type == "http"
        assert valid_config.url == "https://api.together.xyz/v1/models"

        # Configuration invalide (URL manquante)
        with pytest.raises(ValueError):
            PricingSourceConfig(type="http", url=None, enabled=True)

    async def test_together_unknown_model_handling(self):
        """Test la gestion des modèles Together AI inconnus."""
        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http", url="https://api.together.xyz/v1/models", enabled=True
                )
            },
            fallback_to_static=True,
        )

        manager = DynamicPricingManager(config)

        # Test avec un modèle Together AI qui n'existe pas dans la réponse mockée
        with patch(
            "services.dynamic_pricing.DynamicPricingManager._fetch_from_sources"
        ) as mock_fetch:
            mock_fetch.return_value = None  # Modèle non trouvé

            # Doit utiliser le fallback statique
            price_config = await manager.get_price("togethercomputer/UNKNOWN-MODEL")
            assert price_config.source == "static_fallback"

    async def test_together_pricing_rate_limiting(self):
        """Test la limitation de taux pour les appels API Together AI."""
        config = DynamicPricingConfig(
            sources={
                "together_api": PricingSourceConfig(
                    type="http",
                    url="https://api.together.xyz/v1/models",
                    refresh_interval=3600,  # 1 heure
                    enabled=True,
                )
            }
        )

        manager = DynamicPricingManager(config)

        # Simuler un appel récent
        manager._cache_timestamps["togethercomputer/LLaMA-2-7B-32K"] = datetime.now()
        manager._cache["togethercomputer/LLaMA-2-7B-32K"] = PriceConfig(
            input_per_1m_usd=0.15,
            output_per_1m_usd=0.20,
            provider="together",
            source="cache",
        )

        # Appel dans l'intervalle de rafraîchissement - devrait utiliser le cache
        price = await manager.get_price("togethercomputer/LLaMA-2-7B-32K")
        assert price.source == "cache"
