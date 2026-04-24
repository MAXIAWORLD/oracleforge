"""MissionForge — Central configuration via Pydantic Settings.

Single source of truth for all environment variables.
Every service reads from Settings; zero hardcoded values.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "MissionForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./missionforge.db"

    # ── ChromaDB ─────────────────────────────────────────────────────
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_prefix: str = "mf"

    # ── Missions ─────────────────────────────────────────────────────
    missions_dir: str = "./missions"
    allowed_env_vars: list[str] = []

    # ── LLM Providers ────────────────────────────────────────────────
    # Tier LOCAL — Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # Tier FAST — Cerebras
    cerebras_api_key: str = ""
    cerebras_model: str = "qwen-3-32b"

    # Tier FAST2 — Google Gemini
    google_ai_key: str = ""
    google_ai_model: str = "gemini-2.5-flash-lite"

    # Tier FAST3 — Groq
    groq_api_key: str = ""

    # Tier MID — Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # Tier STRATEGIC — Anthropic Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (singleton per process)."""
    return Settings()
