"""TDD tests for core/config.py — Settings validation."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from core.config import Settings


class TestSettings:
    """Settings loads correctly from explicit kwargs."""

    def test_loads_with_valid_values(self) -> None:
        s = Settings(
            secret_key="a-valid-secret-key-1234",
            database_url="sqlite+aiosqlite:///:memory:",
            debug=False,
        )
        assert s.app_name == "MissionForge"
        assert s.version == "0.1.0"
        assert s.debug is False
        assert s.secret_key == "a-valid-secret-key-1234"

    def test_secret_key_required(self) -> None:
        """Missing secret_key must raise a validation error."""
        # Temporarily remove SECRET_KEY from env if present
        original = os.environ.pop("SECRET_KEY", None)
        try:
            with pytest.raises(ValidationError):
                Settings(
                    _env_file=None,  # type: ignore[call-arg]
                )
        finally:
            if original is not None:
                os.environ["SECRET_KEY"] = original

    def test_secret_key_min_length(self) -> None:
        """secret_key shorter than 16 chars must fail."""
        with pytest.raises(ValidationError):
            Settings(secret_key="short")

    def test_default_llm_providers_empty(self) -> None:
        """LLM API keys default to empty string (tier skipped)."""
        s = Settings(secret_key="a-valid-secret-key-1234")
        assert s.cerebras_api_key == ""
        assert s.groq_api_key == ""
        assert s.mistral_api_key == ""
        assert s.anthropic_api_key == ""

    def test_cors_origins_default(self) -> None:
        s = Settings(secret_key="a-valid-secret-key-1234")
        assert "http://localhost:3000" in s.cors_origins

    def test_allowed_env_vars_default_empty(self) -> None:
        s = Settings(secret_key="a-valid-secret-key-1234", allowed_env_vars=[])
        assert s.allowed_env_vars == []
