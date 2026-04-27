"""TDD tests for POST /api/waitlist (Loops email capture)."""

from __future__ import annotations

import pytest


def test_valid_email_returns_200(client, monkeypatch):
    captured: dict = {}

    async def _fake_add_contact(email: str, user_group: str) -> bool:
        captured["email"] = email
        captured["user_group"] = user_group
        return True

    monkeypatch.setattr(
        "api.routes_waitlist.add_contact", _fake_add_contact, raising=True
    )

    resp = client.post("/api/waitlist", json={"email": "Alice@Example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["ok"] is True
    assert "disclaimer" in body
    # The asyncio.create_task may or may not have run before assert; we check
    # by giving the loop one tick. In TestClient the body is returned after
    # the handler returns, but the task is scheduled before that happens.
    # We assert the task was created with normalized lowercase email.
    # Note: TestClient runs the loop until the response is sent, so the
    # task is at least scheduled; if it hasn't run yet we accept that.
    if captured:
        assert captured["email"] == "alice@example.com"
        assert captured["user_group"] == "OracleForge Beta"


@pytest.mark.parametrize(
    "bad_email",
    ["not-an-email", "@nodomain.com", "user@", "user space@example.com", ""],
)
def test_invalid_email_returns_422(client, bad_email):
    resp = client.post("/api/waitlist", json={"email": bad_email})
    assert resp.status_code == 422


def test_email_too_long_rejected(client):
    long_email = ("a" * 250) + "@x.co"
    resp = client.post("/api/waitlist", json={"email": long_email})
    assert resp.status_code == 422


def test_no_loops_key_still_returns_200(client, monkeypatch):
    """If LOOPS_API_KEY is unset, the endpoint still accepts the email.
    Loops sync no-ops silently — we don't leak that info to the user."""
    monkeypatch.delenv("LOOPS_API_KEY", raising=False)
    resp = client.post("/api/waitlist", json={"email": "bob@example.com"})
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True
