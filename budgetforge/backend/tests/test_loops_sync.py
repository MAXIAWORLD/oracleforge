"""TDD tests for Loops contact sync (audience push).

The signup flow must NEVER fail because Loops is misconfigured or down.
This test suite enforces fire-and-forget semantics: any error is swallowed
and logged, the function returns False instead of raising.
"""

from __future__ import annotations


import httpx
import pytest

from services import loops_sync


@pytest.mark.asyncio
async def test_no_api_key_is_noop(monkeypatch):
    monkeypatch.setattr(loops_sync.settings, "loops_api_key", "", raising=False)
    ok = await loops_sync.add_contact("alice@example.com", "BudgetForge Beta")
    assert ok is False


@pytest.mark.asyncio
async def test_success_returns_true(monkeypatch):
    monkeypatch.setattr(
        loops_sync.settings, "loops_api_key", "test_key_xxx", raising=False
    )
    captured: dict = {}

    class _MockResp:
        status_code = 200

        def json(self):
            return {"success": True, "id": "ct_123"}

    class _MockClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _MockResp()

    monkeypatch.setattr(loops_sync.httpx, "AsyncClient", _MockClient)
    ok = await loops_sync.add_contact("alice@example.com", "BudgetForge Beta")
    assert ok is True
    assert "loops.so" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer test_key_xxx"
    assert captured["json"]["email"] == "alice@example.com"
    assert captured["json"]["userGroup"] == "BudgetForge Beta"


@pytest.mark.asyncio
async def test_http_error_returns_false(monkeypatch):
    monkeypatch.setattr(
        loops_sync.settings, "loops_api_key", "test_key_xxx", raising=False
    )

    class _MockClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(loops_sync.httpx, "AsyncClient", _MockClient)
    ok = await loops_sync.add_contact("alice@example.com", "BudgetForge Beta")
    assert ok is False


@pytest.mark.asyncio
async def test_409_duplicate_returns_true(monkeypatch):
    """Loops returns 409 when the email already exists. We treat that as success
    (the contact is in the audience, which is what the caller wanted)."""
    monkeypatch.setattr(
        loops_sync.settings, "loops_api_key", "test_key_xxx", raising=False
    )

    class _MockResp:
        status_code = 409

        def json(self):
            return {"message": "Email already on list"}

    class _MockClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **kw):
            return _MockResp()

    monkeypatch.setattr(loops_sync.httpx, "AsyncClient", _MockClient)
    ok = await loops_sync.add_contact("alice@example.com", "BudgetForge Beta")
    assert ok is True
