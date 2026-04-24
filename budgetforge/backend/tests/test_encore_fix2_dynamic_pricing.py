"""TDD RED — encore fix2 : dynamic pricing ne doit pas bypasser le budget.

Problème actuel :
  CostCalculator.get_price() appelle get_dynamic_price() en premier.
  Si l'API OpenRouter/Together retourne price=0, le coût calculé = $0.
  → Budget jamais consommé → accès illimité.

Fix requis :
  1. Les prix statiques (_PRICES) ont priorité sur les prix dynamiques.
  2. Les prix dynamiques = 0 (hors Ollama) sont rejetés avec ValueError.
  3. Les modèles inconnus des _PRICES peuvent utiliser le dynamic pricing
     UNIQUEMENT si le prix dynamic est > 0.
"""

import pytest
from unittest.mock import patch, AsyncMock

from services.cost_calculator import CostCalculator, _PRICES, ModelPrice


class TestStaticPricesPriority:
    """Les prix statiques doivent prendre le dessus sur les prix dynamiques."""

    @pytest.mark.asyncio
    async def test_known_model_uses_static_price_not_dynamic(self):
        """Pour gpt-4o (connu), le prix statique est utilisé, pas le dynamic."""
        fake_dynamic_price = ModelPrice(input_per_1m_usd=999.0, output_per_1m_usd=999.0)

        with patch(
            "services.cost_calculator.get_dynamic_price",
            new_callable=AsyncMock,
            return_value=fake_dynamic_price,
        ):
            price = await CostCalculator.get_price("gpt-4o")

        # Doit utiliser le prix statique (5.0 / 15.0), pas 999.0
        assert price.input_per_1m_usd == _PRICES["gpt-4o"].input_per_1m_usd, (
            f"Static price must take priority. Got {price.input_per_1m_usd}, "
            f"expected {_PRICES['gpt-4o'].input_per_1m_usd}. "
            "Current code calls get_dynamic_price first — invert priority."
        )

    @pytest.mark.asyncio
    async def test_known_model_static_price_even_when_dynamic_returns_zero(self):
        """Prix statique utilisé même si le dynamic retourne 0 (bypass attempt)."""
        zero_price = ModelPrice(input_per_1m_usd=0.0, output_per_1m_usd=0.0)

        with patch(
            "services.cost_calculator.get_dynamic_price",
            new_callable=AsyncMock,
            return_value=zero_price,
        ):
            price = await CostCalculator.get_price("claude-sonnet-4-6")

        # Anthropic Claude est dans _PRICES → doit utiliser le prix statique
        assert price.input_per_1m_usd > 0, (
            "Static price (>0) must be used for known model even if dynamic returns 0. "
            f"Got {price.input_per_1m_usd}. Budget bypass vector not blocked."
        )

    @pytest.mark.asyncio
    async def test_all_known_models_never_get_zero_cost(self):
        """Aucun modèle connu ne doit jamais avoir un coût calculé à 0 via bypass."""
        known_non_free_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-sonnet-4-6",
            "gemini-2.0-flash",
            "deepseek-chat",
            "anthropic.claude-v2",
        ]
        zero_price = ModelPrice(input_per_1m_usd=0.0, output_per_1m_usd=0.0)

        with patch(
            "services.cost_calculator.get_dynamic_price",
            new_callable=AsyncMock,
            return_value=zero_price,
        ):
            for model in known_non_free_models:
                cost = await CostCalculator.compute_cost(model, 1000, 500)
                assert cost > 0, (
                    f"Model {model} should never have $0 cost even if dynamic returns 0. "
                    f"compute_cost returned {cost}. Budget bypass not blocked."
                )


class TestUnknownModelDynamicPricing:
    """Les modèles inconnus peuvent utiliser le dynamic pricing si prix > 0."""

    @pytest.mark.asyncio
    async def test_unknown_model_uses_dynamic_when_positive(self):
        """Modèle inconnu de _PRICES : utilise dynamic si prix > 0."""
        fake_price = ModelPrice(input_per_1m_usd=2.5, output_per_1m_usd=10.0)

        with patch(
            "services.cost_calculator.get_dynamic_price",
            new_callable=AsyncMock,
            return_value=fake_price,
        ):
            price = await CostCalculator.get_price("new-model-not-in-static")

        assert price.input_per_1m_usd == 2.5
        assert price.output_per_1m_usd == 10.0

    @pytest.mark.asyncio
    async def test_unknown_model_raises_when_dynamic_returns_zero(self):
        """Modèle inconnu + dynamic price=0 → refus (pas de coût $0 non-Ollama)."""
        zero_price = ModelPrice(input_per_1m_usd=0.0, output_per_1m_usd=0.0)

        with patch(
            "services.cost_calculator.get_dynamic_price",
            new_callable=AsyncMock,
            return_value=zero_price,
        ):
            with pytest.raises(Exception):
                await CostCalculator.get_price("suspicious-model-zero-price")


class TestOllamaExempt:
    """Ollama (free local) est exempt de la validation de prix > 0."""

    @pytest.mark.asyncio
    async def test_ollama_model_allows_zero_price(self):
        """Ollama retourne légitimement $0 — ne doit pas lever d'exception."""
        price = await CostCalculator.get_price("ollama/llama2")
        assert price.input_per_1m_usd == 0.0
        assert price.output_per_1m_usd == 0.0
