"""OutreachForge — Central configuration.

Email Outreach Automation: scoring, personalisation LLM, multi-langue, ramp-up.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OutreachForge"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(..., min_length=16)
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "sqlite+aiosqlite:///./outreachforge.db"

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "OutreachForge"
    smtp_from_email: str = ""

    # Rate limits
    max_emails_per_day: int = 100
    ramp_up_enabled: bool = True
    ramp_up_start: int = 10  # emails/day on day 1
    ramp_up_increment: int = 10  # +10/day


@lru_cache
def get_settings() -> Settings:
    return Settings()
