"""Système de configuration dynamique des prix avec support multi-sources."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx
import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UnknownModelError(Exception):
    """Exception pour les modèles inconnus (compatibilité)."""

    pass


class PriceConfig(BaseModel):
    """Configuration des prix pour un modèle."""

    input_per_1m_usd: float
    output_per_1m_usd: float
    provider: str
    last_updated: Optional[datetime] = None
    source: str = "local"


class PricingSourceConfig(BaseModel):
    """Configuration d'une source de prix."""

    type: str  # file, http, database
    url: Optional[str] = None
    path: Optional[str] = None
    refresh_interval: int = 3600  # seconds
    enabled: bool = True


class DynamicPricingConfig(BaseModel):
    """Configuration globale du système de prix dynamique."""

    sources: Dict[str, PricingSourceConfig] = {}
    fallback_to_static: bool = True
    cache_duration: int = 300  # seconds
    max_cache_size: int = 1000


@dataclass(frozen=True)
class ModelPrice:
    """Compatibilité avec l'interface existante."""

    input_per_1m_usd: float
    output_per_1m_usd: float


class DynamicPricingManager:
    """Gestionnaire de prix dynamique avec cache et multi-sources."""

    def __init__(self, config: Optional[DynamicPricingConfig] = None):
        self.config = config or DynamicPricingConfig()
        self._cache: Dict[str, PriceConfig] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._last_refresh: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

        # Sources par défaut
        if not self.config.sources:
            self.config.sources = {
                "local_file": PricingSourceConfig(
                    type="file",
                    path=str(Path(__file__).parent / "pricing_config.yaml"),
                    refresh_interval=3600,
                ),
                "openai_api": PricingSourceConfig(
                    type="http",
                    url="https://api.openai.com/v1/models",
                    refresh_interval=86400,  # 24h
                    enabled=False,  # Désactivé par défaut (nécessite auth)
                ),
                "openrouter_api": PricingSourceConfig(
                    type="http",
                    url="https://openrouter.ai/api/v1/models",
                    refresh_interval=7200,  # 2h - plus fréquent car prix peuvent changer
                    enabled=True,
                ),
                "together_api": PricingSourceConfig(
                    type="http",
                    url="https://api.together.xyz/v1/models",
                    refresh_interval=7200,  # 2h - prix peuvent changer
                    enabled=True,
                ),
                "azure_openai_api": PricingSourceConfig(
                    type="http",
                    url="https://prices.azure.com/api/retail/prices",
                    refresh_interval=86400,  # 24h - prix Azure changent rarement
                    enabled=False,  # Désactivé par défaut (nécessite parsing spécifique)
                ),
                "aws_bedrock_api": PricingSourceConfig(
                    type="http",
                    url="https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/index.json",
                    refresh_interval=86400,  # 24h - prix AWS changent rarement
                    enabled=True,
                ),
            }

    async def close(self) -> None:
        """Close any persistent HTTP client if present."""
        client = getattr(self, "_http_client", None)
        if client is not None:
            await client.aclose()
            self._http_client = None

    async def get_price(self, model: str) -> PriceConfig:
        """Obtient le prix pour un modèle, avec cache et fallback."""
        normalized_model = model.lower()

        # Vérifier le cache d'abord
        if normalized_model in self._cache:
            if self._is_cache_valid(normalized_model):
                return self._cache[normalized_model]

        async with self._lock:
            # Re-vérifier après acquisition du lock (double-check)
            if normalized_model in self._cache and self._is_cache_valid(
                normalized_model
            ):
                return self._cache[normalized_model]

            # Essayer chaque source activée
            price = await self._fetch_from_sources(normalized_model)

            if price:
                self._cache[normalized_model] = price
                self._cache_timestamps[normalized_model] = datetime.now(timezone.utc)
                return price

            # Fallback vers les prix statiques
            if self.config.fallback_to_static:
                from .cost_calculator import _PRICES

                static_price = _PRICES.get(normalized_model)
                if static_price:
                    price = PriceConfig(
                        input_per_1m_usd=static_price.input_per_1m_usd,
                        output_per_1m_usd=static_price.output_per_1m_usd,
                        provider=self._detect_provider(normalized_model),
                        source="static_fallback",
                    )
                    self._cache[normalized_model] = price
                    self._cache_timestamps[normalized_model] = datetime.now(
                        timezone.utc
                    )
                    return price

            raise ValueError(f"Prix non trouvé pour le modèle: {model}")

    async def _fetch_from_sources(self, model: str) -> Optional[PriceConfig]:
        """Tente de récupérer le prix depuis les sources configurées."""
        for source_name, source_config in self.config.sources.items():
            if not source_config.enabled:
                continue

            # Vérifier si la source doit être rafraîchie
            if not self._should_refresh_source(source_name):
                continue

            try:
                price = await self._fetch_from_source(source_name, source_config, model)
                if price:
                    self._last_refresh[source_name] = datetime.now(timezone.utc)
                    return price
            except Exception as e:
                logger.warning(f"Échec de la source {source_name} pour {model}: {e}")

        return None

    async def _fetch_from_source(
        self, source_name: str, config: PricingSourceConfig, model: str
    ) -> Optional[PriceConfig]:
        """Récupère le prix depuis une source spécifique."""
        if config.type == "file":
            return await self._load_from_file(config.path, model)
        elif config.type == "http":
            return await self._load_from_http(config.url, model)
        elif config.type == "database":
            return await self._load_from_database(model)
        else:
            logger.warning(f"Type de source non supporté: {config.type}")
            return None

    async def _load_from_file(
        self, file_path: str, model: str
    ) -> Optional[PriceConfig]:
        """Charge les prix depuis un fichier YAML/JSON."""
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if file_path.endswith(".yaml") or file_path.endswith(".yml"):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            prices = data.get("prices", {})
            model_data = prices.get(model.lower())

            if model_data:
                return PriceConfig(
                    input_per_1m_usd=model_data.get("input_per_1m_usd"),
                    output_per_1m_usd=model_data.get("output_per_1m_usd"),
                    provider=model_data.get("provider", "unknown"),
                    source=f"file:{file_path}",
                )
        except Exception as e:
            logger.error(f"Erreur lecture fichier {file_path}: {e}")

        return None

    async def _load_from_http(self, url: str, model: str) -> Optional[PriceConfig]:
        """Charge les prix depuis une API HTTP."""
        if not url:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                # Adapter selon le format de l'API
                if "prices" in data:
                    model_data = data["prices"].get(model.lower())
                elif "data" in data and urlparse(url).netloc == "openrouter.ai":
                    # Format OpenRouter
                    model_data = self._parse_openrouter_format(data, model)
                elif "data" in data and urlparse(url).netloc == "api.together.xyz":
                    # Format Together AI
                    model_data = self._parse_together_format(data, model)
                elif "pricing.us-east-1.amazonaws.com" in url:
                    # Format AWS Bedrock Pricing
                    model_data = self._parse_aws_bedrock_format(data, model)
                else:
                    # Format OpenAI-like
                    model_data = self._parse_openai_format(data, model)

                if model_data:
                    return PriceConfig(
                        input_per_1m_usd=model_data.get("input_per_1m_usd"),
                        output_per_1m_usd=model_data.get("output_per_1m_usd"),
                        provider=model_data.get("provider", "unknown"),
                        source=f"http:{urlparse(url).netloc}",
                    )
        except Exception as e:
            logger.error(f"Erreur API HTTP {url}: {e}")

        return None

    async def _load_from_database(self, model: str) -> Optional[PriceConfig]:
        """Charge les prix depuis une base de données."""
        # Implémentation à venir si nécessaire
        return None

    def _parse_openai_format(self, data: dict, model: str) -> Optional[dict]:
        """Parse le format de réponse de l'API OpenAI."""
        # Cette méthode devrait être adaptée selon le format réel de l'API
        # Pour l'instant, retourne None car l'API OpenAI ne fournit pas les prix directement
        return None

    def _parse_openrouter_format(self, data: dict, model: str) -> Optional[dict]:
        """Parse le format de réponse de l'API OpenRouter."""
        # Format OpenRouter: data contient une liste de modèles avec pricing
        if "data" not in data:
            return None

        for model_data in data["data"]:
            if model_data.get("id") == model:
                pricing = model_data.get("pricing", {})
                if pricing:
                    return {
                        "input_per_1m_usd": pricing.get("prompt", 0),
                        "output_per_1m_usd": pricing.get("completion", 0),
                        "provider": "openrouter",
                    }
        return None

    def _parse_together_format(self, data: dict, model: str) -> Optional[dict]:
        """Parse le format de réponse de l'API Together AI."""
        # Format Together AI: data contient une liste de modèles avec pricing
        if "data" not in data:
            return None

        for model_data in data["data"]:
            if model_data.get("id") == model:
                # Together AI expose les prix dans le champ pricing
                pricing = model_data.get("pricing", {})
                if pricing:
                    return {
                        "input_per_1m_usd": pricing.get("prompt", 0),
                        "output_per_1m_usd": pricing.get("completion", 0),
                        "provider": "together",
                    }
        return None

    def _parse_aws_bedrock_format(self, data: dict, model: str) -> Optional[dict]:
        """Parse le format de réponse de l'API AWS Bedrock Pricing."""
        # Format AWS Bedrock: JSON complexe avec produits et prix
        if "products" not in data or "terms" not in data:
            return None

        # Chercher le produit correspondant au modèle
        for product_id, product_data in data["products"].items():
            attributes = product_data.get("attributes", {})
            service_code = attributes.get("servicecode")
            usage_type = attributes.get("usagetype")

            # Filtrer les produits Bedrock
            if service_code != "AmazonBedrock":
                continue

            # Identifier le modèle basé sur l'usage type
            if "Input" in usage_type:
                # C'est un prix d'entrée
                if model.lower() in usage_type.lower():
                    # Trouver le prix correspondant dans les termes
                    for term_key, term_data in (
                        data["terms"].get("OnDemand", {}).items()
                    ):
                        if product_id in term_key:
                            price_dimensions = term_data.get("priceDimensions", {})
                            for dim_key, dim_data in price_dimensions.items():
                                price_per_unit = dim_data.get("pricePerUnit", {})
                                usd_price = price_per_unit.get("USD", 0)
                                if usd_price:
                                    return {
                                        "input_per_1m_usd": float(usd_price)
                                        * 1000000,  # Convertir par million
                                        "output_per_1m_usd": 0,
                                        "provider": "aws_bedrock",
                                    }
            elif "Output" in usage_type:
                # C'est un prix de sortie
                if model.lower() in usage_type.lower():
                    for term_key, term_data in (
                        data["terms"].get("OnDemand", {}).items()
                    ):
                        if product_id in term_key:
                            price_dimensions = term_data.get("priceDimensions", {})
                            for dim_key, dim_data in price_dimensions.items():
                                price_per_unit = dim_data.get("pricePerUnit", {})
                                usd_price = price_per_unit.get("USD", 0)
                                if usd_price:
                                    return {
                                        "input_per_1m_usd": 0,
                                        "output_per_1m_usd": float(usd_price)
                                        * 1000000,  # Convertir par million
                                        "provider": "aws_bedrock",
                                    }

        return None

    def _should_refresh_source(self, source_name: str) -> bool:
        """Détermine si une source doit être rafraîchie."""
        last_refresh = self._last_refresh.get(source_name)
        if not last_refresh:
            return True

        source_config = self.config.sources[source_name]
        refresh_interval = timedelta(seconds=source_config.refresh_interval)
        return datetime.now(timezone.utc) - last_refresh > refresh_interval

    def _is_cache_valid(self, model: str) -> bool:
        """Vérifie si l'entrée du cache est encore valide."""
        timestamp = self._cache_timestamps.get(model)
        if not timestamp:
            return False

        cache_duration = timedelta(seconds=self.config.cache_duration)
        return datetime.now(timezone.utc) - timestamp < cache_duration

    def _detect_provider(self, model: str) -> str:
        """Détecte le fournisseur basé sur le nom du modèle."""
        model_lower = model.lower()

        if model_lower.startswith("openrouter/"):
            return "openrouter"
        elif model_lower.startswith("gpt-"):
            return "openai"
        elif model_lower.startswith("claude-"):
            return "anthropic"
        elif model_lower.startswith("gemini-"):
            return "google"
        elif model_lower.startswith("deepseek-"):
            return "deepseek"
        elif model_lower.startswith("ollama/"):
            return "ollama"
        elif model_lower.startswith("togethercomputer/"):
            return "together"
        elif model_lower.startswith("azure/"):
            return "azure_openai"
        elif model_lower.startswith("anthropic.claude-"):
            return "aws_bedrock"
        elif model_lower.startswith("meta.llama-"):
            return "aws_bedrock"
        else:
            return "unknown"

    async def refresh_all_sources(self):
        """Rafraîchit toutes les sources activées."""
        async with self._lock:
            for source_name, config in self.config.sources.items():
                if config.enabled:
                    self._last_refresh[source_name] = datetime.now(timezone.utc)
            # Invalider le cache pour forcer le rechargement
            self._cache.clear()
            self._cache_timestamps.clear()

    def get_cache_stats(self) -> dict:
        """Retourne les statistiques du cache."""
        return {
            "cache_size": len(self._cache),
            "cache_hits": sum(
                1
                for ts in self._cache_timestamps.values()
                if self._is_cache_valid_from_ts(ts)
            ),
            "last_refresh": self._last_refresh.copy(),
        }

    def _is_cache_valid_from_ts(self, timestamp: datetime) -> bool:
        """Vérifie la validité du cache depuis un timestamp donné."""
        cache_duration = timedelta(seconds=self.config.cache_duration)
        return datetime.now(timezone.utc) - timestamp < cache_duration


# Singleton global
_pricing_manager: Optional[DynamicPricingManager] = None


def get_pricing_manager() -> DynamicPricingManager:
    """Obtient l'instance singleton du gestionnaire de prix."""
    global _pricing_manager
    if _pricing_manager is None:
        _pricing_manager = DynamicPricingManager()
    return _pricing_manager


async def get_dynamic_price(model: str) -> ModelPrice:
    """Fonction de compatibilité avec l'interface existante."""
    manager = get_pricing_manager()
    price_config = await manager.get_price(model)
    return ModelPrice(
        input_per_1m_usd=price_config.input_per_1m_usd,
        output_per_1m_usd=price_config.output_per_1m_usd,
    )


def set_pricing_config(config: DynamicPricingConfig):
    """Configure le gestionnaire de prix dynamique."""
    global _pricing_manager
    _pricing_manager = DynamicPricingManager(config)
