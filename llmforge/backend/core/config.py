"""LLMForge — Central configuration via Pydantic Settings.

LLM Router Multi-Provider: one endpoint, intelligent routing, fallback auto.
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
    app_name: str = "LLMForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./llmforge.db"

    # ── Cache ────────────────────────────────────────────────────
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes
    cache_max_entries: int = 1000

    # ── Budget ───────────────────────────────────────────────────
    daily_budget_usd: float = 0.0  # 0 = unlimited
    per_key_daily_budget_usd: float = 0.0  # 0 = unlimited

    # ── LLM Providers ────────────────────────────────────────────
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    cerebras_api_key: str = ""
    cerebras_model: str = "qwen-3-32b"
    google_ai_key: str = ""
    google_ai_model: str = "gemini-2.5-flash-lite"
    groq_api_key: str = ""
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
