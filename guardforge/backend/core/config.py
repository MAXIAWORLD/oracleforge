"""GuardForge — Central configuration.

PII & AI Safety Kit: detection, anonymisation, vault, policy engine.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GuardForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "sqlite+aiosqlite:///./guardforge.db"

    # Vault encryption
    vault_encryption_key: str = Field(default="", description="AES-256 key (32 bytes base64). Auto-generated if empty.")

    # PII Detection
    pii_languages: list[str] = ["en", "fr"]
    pii_confidence_threshold: float = 0.7

    # Policy
    default_policy: str = "strict"  # strict | moderate | permissive


@lru_cache
def get_settings() -> Settings:
    return Settings()
