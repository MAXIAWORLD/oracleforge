"""TDD B1.6 — Turnstile fail-closed en production (audit H09).

Bug audit: signup.py:95-119 — si turnstile_secret_key vide, _verify_turnstile
return True meme en production (fail-OPEN), avec juste un warning logge.

main.py:71-75 confirme cet etat avec un autre warning trompeur:
'Turnstile absent en production - signups free seront bloques (fail-closed
anti-bot).'

C'est faux: le code actuel est fail-OPEN, pas fail-closed.

Fix: return False en production si secret vide (anti-bot vraiment fail-closed).
Compat dev: return True si secret vide ET app_env != production.
"""

import pytest


@pytest.mark.asyncio
async def test_verify_turnstile_fail_closed_in_production_without_secret(
    monkeypatch,
):
    """Production + turnstile_secret_key vide -> return False (fail-closed)."""
    from core.config import settings
    from routes.signup import _verify_turnstile

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")

    result = await _verify_turnstile(token="any-token", client_ip="1.2.3.4")
    assert result is False, (
        "En prod sans secret, _verify_turnstile doit return False (fail-closed). "
        f"Got: {result}"
    )


@pytest.mark.asyncio
async def test_verify_turnstile_pass_through_in_dev_without_secret(monkeypatch):
    """Dev mode + turnstile_secret_key vide -> return True (compat dev)."""
    from core.config import settings
    from routes.signup import _verify_turnstile

    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")

    result = await _verify_turnstile(token=None, client_ip="1.2.3.4")
    assert result is True, (
        "En dev sans secret, _verify_turnstile doit return True (compat). "
        f"Got: {result}"
    )


@pytest.mark.asyncio
async def test_verify_turnstile_returns_false_when_token_missing_in_prod(
    monkeypatch,
):
    """Prod + secret set + pas de token -> return False (deja le cas)."""
    from core.config import settings
    from routes.signup import _verify_turnstile

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "turnstile_secret_key", "real-secret")

    result = await _verify_turnstile(token=None, client_ip="1.2.3.4")
    assert result is False


@pytest.mark.asyncio
async def test_verify_turnstile_returns_true_when_cloudflare_validates(
    monkeypatch,
):
    """Prod + secret set + token valide selon Cloudflare -> return True."""
    from core.config import settings
    from routes.signup import _verify_turnstile
    import httpx

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "turnstile_secret_key", "real-secret")

    # Mock la response Cloudflare comme success=true
    class MockResp:
        def json(self):
            return {"success": True}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return MockResp()

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)

    result = await _verify_turnstile(token="valid-token", client_ip="1.2.3.4")
    assert result is True


@pytest.mark.asyncio
async def test_verify_turnstile_returns_false_when_cloudflare_rejects(
    monkeypatch,
):
    """Prod + secret set + token invalide selon Cloudflare -> return False."""
    from core.config import settings
    from routes.signup import _verify_turnstile
    import httpx

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "turnstile_secret_key", "real-secret")

    class MockResp:
        def json(self):
            return {"success": False, "error-codes": ["invalid-input-response"]}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return MockResp()

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)

    result = await _verify_turnstile(token="bad-token", client_ip="1.2.3.4")
    assert result is False
