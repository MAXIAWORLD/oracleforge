"""Integration tests for guardforge.client.GuardForgeClient.

These tests REQUIRE a running GuardForge backend on http://localhost:8004
with API key 'change-me-to-a-random-32-char-string'. They are skipped
automatically if the backend is unreachable.
"""

from __future__ import annotations

import os

import httpx
import pytest

from guardforge import GuardForgeClient, GuardForgeError


_API_URL = os.environ.get("GUARDFORGE_API_URL", "http://localhost:8004")
_API_KEY = os.environ.get("GUARDFORGE_API_KEY", "change-me-to-a-random-32-char-string")


def _backend_alive() -> bool:
    try:
        httpx.get(f"{_API_URL}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


backend_required = pytest.mark.skipif(
    not _backend_alive(),
    reason=f"GuardForge backend not reachable at {_API_URL}",
)


def test_missing_api_key_raises() -> None:
    """Without an API key, instantiation must fail with a clear error."""
    # Clear env var temporarily
    saved = os.environ.pop("GUARDFORGE_API_KEY", None)
    try:
        with pytest.raises(GuardForgeError, match="API key"):
            GuardForgeClient(url=_API_URL, api_key="")
    finally:
        if saved is not None:
            os.environ["GUARDFORGE_API_KEY"] = saved


@backend_required
def test_health() -> None:
    with GuardForgeClient(url=_API_URL, api_key=_API_KEY) as gf:
        h = gf.health()
        assert h["status"] == "ok"
        assert "version" in h


@backend_required
def test_tokenize_returns_session_id() -> None:
    with GuardForgeClient(url=_API_URL, api_key=_API_KEY) as gf:
        result = gf.tokenize("My email is jane@example.com")
        assert result.session_id
        assert "[EMAIL_" in result.tokenized_text
        assert "jane@example.com" not in result.tokenized_text
        assert result.token_count >= 1


@backend_required
def test_detokenize_roundtrip() -> None:
    with GuardForgeClient(url=_API_URL, api_key=_API_KEY) as gf:
        original = "Contact M. Jean Dupont at jean@example.fr"
        result = gf.tokenize(original)
        restored = gf.detokenize(result.tokenized_text, result.session_id)
        assert restored == original


@backend_required
def test_tokenize_with_existing_session_extends() -> None:
    """Re-using a session_id should add new tokens to the same mapping."""
    with GuardForgeClient(url=_API_URL, api_key=_API_KEY) as gf:
        first = gf.tokenize("First email: a@b.com")
        second = gf.tokenize("Second email: c@d.com", session_id=first.session_id)
        assert second.session_id == first.session_id
        # Now the second tokenized text should detokenize using same session
        restored = gf.detokenize(second.tokenized_text, second.session_id)
        assert "c@d.com" in restored


@backend_required
def test_invalid_api_key_raises_error() -> None:
    with GuardForgeClient(url=_API_URL, api_key="wrong-key") as gf:
        with pytest.raises(GuardForgeError):
            gf.tokenize("test text")
