"""OracleForge — Central configuration.

Multi-Source Price Oracle with cross-verification and confidence scoring.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────
    app_name: str = "OracleForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./oracleforge.db"

    # ── Cache ────────────────────────────────────────────────────
    price_cache_ttl: int = 30  # seconds
    stock_cache_ttl: int = 60

    # ── Sources ──────────────────────────────────────────────────
    # CoinGecko (free tier: 10-30 calls/min)
    coingecko_enabled: bool = True

    # Pyth Network (free, real-time SSE)
    pyth_enabled: bool = True
    pyth_hermes_url: str = "https://hermes.pyth.network"

    # Chainlink (free, on-chain via RPC)
    chainlink_enabled: bool = True
    base_rpc_url: str = "https://mainnet.base.org"

    # Finnhub (free tier: 60 calls/min)
    finnhub_api_key: str = ""
    finnhub_enabled: bool = False

    # Yahoo Finance (unofficial, no key needed)
    yahoo_enabled: bool = True

    # ── Circuit Breaker ──────────────────────────────────────────
    circuit_breaker_threshold: int = 3  # failures before open
    circuit_breaker_ttl: int = 60  # seconds before half-open


@lru_cache
def get_settings() -> Settings:
    return Settings()
