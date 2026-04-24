"""TDD — Phase 2: Fixes config (anthropic_model env var, validation startup).

Ces tests sont ROUGES jusqu'à ce que :
- Settings ajoute anthropic_model
- llm_router.py utilise settings.anthropic_model au lieu du hardcode
"""

from __future__ import annotations


import pytest
from unittest.mock import MagicMock

from core.config import Settings
from services.llm_router import LLMRouter, Tier


# ── Tests : anthropic_model dans Settings ────────────────────────


def test_anthropic_model_has_default():
    """Settings expose anthropic_model avec une valeur par défaut valide."""
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    assert hasattr(s, "anthropic_model")
    assert s.anthropic_model.startswith("claude-")


def test_anthropic_model_default_is_current_claude():
    """Le modèle par défaut est claude-sonnet-4-6 (modèle actuel production)."""
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    assert s.anthropic_model == "claude-sonnet-4-6"


def test_anthropic_model_overridable_via_env(monkeypatch):
    """ANTHROPIC_MODEL env var surcharge le défaut."""
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    assert s.anthropic_model == "claude-opus-4-7"


def test_anthropic_model_unset_env_uses_default(monkeypatch):
    """Sans ANTHROPIC_MODEL, le défaut est utilisé."""
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    assert s.anthropic_model == "claude-sonnet-4-6"


# ── Tests : LLMRouter utilise settings.anthropic_model ───────────


def test_llm_router_uses_settings_anthropic_model():
    """_call_anthropic envoie settings.anthropic_model, pas un hardcode."""
    s = Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        anthropic_api_key="sk-test",
        anthropic_model="claude-opus-4-7",
    )
    router = LLMRouter(settings=s, http_client=MagicMock())
    # Le modèle exposé pour STRATEGIC doit venir de settings
    assert router.model_for_tier(Tier.STRATEGIC) == "claude-opus-4-7"


def test_llm_router_default_strategic_model_matches_settings():
    """Sans override, le tier STRATEGIC utilise le même modèle que settings.anthropic_model."""
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    router = LLMRouter(settings=s, http_client=MagicMock())
    assert router.model_for_tier(Tier.STRATEGIC) == s.anthropic_model


@pytest.mark.asyncio
async def test_call_anthropic_sends_settings_model(monkeypatch):
    """_call_anthropic POST avec le model tiré de settings, pas hardcodé."""
    import httpx

    captured: dict = {}

    async def fake_post(url, headers, json, timeout):
        captured["model"] = json.get("model")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(
            return_value={"content": [{"type": "text", "text": "reply"}]}
        )
        return mock_resp

    http = MagicMock()
    http.post = fake_post

    s = Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        anthropic_api_key="sk-test",
        anthropic_model="claude-opus-4-7",
    )
    router = LLMRouter(settings=s, http_client=http)
    await router._call_anthropic(system="", prompt="hi", max_tokens=10)

    assert captured["model"] == "claude-opus-4-7"


# ── Tests : pas de valeur hardcodée dans la source ────────────────


def test_no_hardcoded_old_model_in_router_source():
    """llm_router.py ne contient plus la string claude-sonnet-4-20250514."""
    import inspect
    from services import llm_router as router_module

    source = inspect.getsource(router_module)
    assert "claude-sonnet-4-20250514" not in source, (
        "Supprimer le hardcode 'claude-sonnet-4-20250514' de llm_router.py "
        "et utiliser settings.anthropic_model à la place."
    )


# ── Tests : validation au démarrage ─────────────────────────────


def test_settings_requires_secret_key():
    """Settings lève une erreur si SECRET_KEY est absent ou trop court."""
    import pydantic

    with pytest.raises((pydantic.ValidationError, Exception)):
        Settings(secret_key="short")


def test_settings_requires_nonempty_secret_key():
    """SECRET_KEY vide lève une ValidationError."""
    import pydantic

    with pytest.raises((pydantic.ValidationError, Exception)):
        Settings(secret_key="")


def test_settings_database_url_has_default():
    """DATABASE_URL a un défaut SQLite pour le dev local."""
    s = Settings(secret_key="test-secret-key-32-chars-ok!!")
    assert "sqlite" in s.database_url or "postgresql" in s.database_url
