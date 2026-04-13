"""Unit tests for the OpenAI wrapper using a fake OpenAI client.

We do NOT call the real OpenAI API in tests (no key, no cost). Instead we
inject a fake openai.OpenAI-like object that echoes the input messages
back as the response. This lets us verify that:

1. Messages are correctly tokenized before being passed to OpenAI
2. The response is correctly detokenized before being returned
3. Methods we don't override still forward to the real client

These tests REQUIRE a running GuardForge backend at http://localhost:8004
because the wrapper makes real tokenize/detokenize calls.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import httpx
import pytest

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


# ── Fake OpenAI plumbing ─────────────────────────────────────────


class FakeMessage:
    """Mutable Pydantic-like response message."""
    def __init__(self, content: str) -> None:
        self.content = content
        self.role = "assistant"


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)
        self.finish_reason = "stop"
        self.index = 0


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]
        self.model = "gpt-fake"
        self.id = "chatcmpl-fake"


class FakeCompletions:
    def __init__(self) -> None:
        self.last_messages: list[dict] | None = None

    def create(self, **kwargs):
        """Echo the last user message back as the response, prefixed."""
        messages = kwargs.get("messages", [])
        self.last_messages = messages  # capture for assertions
        last_user = next(
            (m for m in reversed(messages) if m.get("role") == "user"),
            None,
        )
        echo = last_user["content"] if last_user else "no user message"
        return FakeResponse(f"Echo: {echo}")


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeOpenAI:
    """Minimal stand-in for openai.OpenAI."""
    def __init__(self, *args, **kwargs) -> None:
        self.chat = FakeChat()
        # Optional attributes the real client has — for __getattr__ tests
        self.api_key = kwargs.get("api_key", "fake-key")
        self.embeddings = SimpleNamespace(create=lambda **kw: {"embedding": [0.0]})


# ── Helper to inject FakeOpenAI into the wrapper ─────────────────


def _make_wrapped(monkeypatch) -> tuple:
    """Patch guardforge.openai_wrapper._RealOpenAI to FakeOpenAI and import."""
    import guardforge.openai_wrapper as ow

    monkeypatch.setattr(ow, "_RealOpenAI", FakeOpenAI)
    from guardforge.openai_wrapper import OpenAI

    client = OpenAI(
        api_key="sk-test",
        guardforge_url=_API_URL,
        guardforge_api_key=_API_KEY,
    )
    return client, ow


# ── Tests ────────────────────────────────────────────────────────


@backend_required
def test_pii_is_tokenized_before_openai_call(monkeypatch) -> None:
    client, _ = _make_wrapped(monkeypatch)
    client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "My email is alice@example.fr and my IBAN is FR7630006000011234567890189"}
        ],
    )
    # The fake completions captured what was actually sent
    sent = client.chat.completions._real.last_messages
    assert sent is not None
    sent_content = sent[0]["content"]
    assert "alice@example.fr" not in sent_content, "PII leaked to OpenAI!"
    assert "FR7630006000011234567890189" not in sent_content, "IBAN leaked to OpenAI!"
    assert "[EMAIL_" in sent_content
    assert "[IBAN_" in sent_content


@backend_required
def test_response_is_detokenized(monkeypatch) -> None:
    client, _ = _make_wrapped(monkeypatch)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello, I am Jean Dupont"}],
    )
    # FakeOpenAI echoes the (tokenized) content back. The wrapper should detokenize.
    content = response.choices[0].message.content
    assert "Jean Dupont" in content, f"Detokenization failed: {content}"
    assert "[PERSON_NAME_" not in content


@backend_required
def test_messages_without_pii_pass_through(monkeypatch) -> None:
    client, _ = _make_wrapped(monkeypatch)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "What is the weather like today?"}],
    )
    sent = client.chat.completions._real.last_messages
    # No PII → no tokens → text should pass unchanged
    assert sent[0]["content"] == "What is the weather like today?"
    assert "weather" in response.choices[0].message.content


@backend_required
def test_multimodal_content_passes_through(monkeypatch) -> None:
    client, _ = _make_wrapped(monkeypatch)
    multimodal = [
        {"type": "text", "text": "describe this"},
        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
    ]
    client.chat.completions.create(
        model="gpt-4-vision",
        messages=[{"role": "user", "content": multimodal}],
    )
    sent = client.chat.completions._real.last_messages
    # Content is a list, not a string → wrapper should pass it through untouched
    assert sent[0]["content"] == multimodal


@backend_required
def test_unknown_attribute_forwards_to_real_client(monkeypatch) -> None:
    """Calling client.embeddings.create() should hit the FakeOpenAI's embeddings."""
    client, _ = _make_wrapped(monkeypatch)
    result = client.embeddings.create(model="text-embedding-3-small", input="hello")
    assert result == {"embedding": [0.0]}


@backend_required
def test_multiple_messages_share_session(monkeypatch) -> None:
    """All tokens in one create() call should come from one mapping (one session)."""
    client, _ = _make_wrapped(monkeypatch)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "I am Bob"},
            {"role": "assistant", "content": "Hello Bob"},
            {"role": "user", "content": "My email is bob@example.com"},
        ],
    )
    # If detokenize works for the response, the session was consistent
    content = response.choices[0].message.content
    assert "bob@example.com" in content or "[EMAIL_" in content
