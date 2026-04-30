"""GuardForge — Central configuration.

PII & AI Safety Kit: detection, anonymisation, vault, policy engine.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "GuardForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3003", "http://localhost:3000"]
    database_url: str = "sqlite+aiosqlite:///./guardforge.db"

    vault_database_url: str = Field(
        default="",
        description="Optional dedicated DB URL for vault persistence. Must be SQLite (sync). "
        "If empty, falls back to `database_url` (which only persists when it is SQLite). "
        "Set to sqlite+aiosqlite:////opt/guardforge/vault.db in production when main DB is PostgreSQL.",
    )

    # Vault encryption
    vault_encryption_key: str = Field(
        default="",
        description="AES-256 key (32 bytes base64). Auto-generated if empty.",
    )

    # PII Detection
    pii_languages: list[str] = ["en", "fr"]
    pii_confidence_threshold: float = 0.7

    # Policy
    default_policy: str = "strict"  # strict | moderate | permissive

    # Rate limiting (per IP, sliding window)
    rate_limit_max_requests: int = Field(
        default=60, ge=1, description="Max requests per IP per window"
    )
    rate_limit_window_seconds: int = Field(
        default=60, ge=1, description="Rate limit window duration"
    )

    # Payload hardening
    max_payload_bytes: int = Field(
        default=1_000_000,
        ge=1024,
        description="Max request payload size (defense in depth)",
    )
    enable_hsts: bool = Field(
        default=True,
        description="Enable Strict-Transport-Security header (keep True in production)",
    )
    docs_enabled: bool = Field(
        default=False,
        description="Expose /docs, /redoc, and /openapi.json. Auto-set to True when DEBUG=true.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
