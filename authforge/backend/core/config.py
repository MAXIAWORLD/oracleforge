"""AuthForge — Central configuration.

Complete auth kit for FastAPI: JWT, OAuth, 2FA, roles, rate limiting.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AuthForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "sqlite+aiosqlite:///./authforge.db"

    # JWT
    jwt_secret: str = Field(default="", description="JWT signing key. Uses secret_key if empty.")
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 7

    # OAuth
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
