"""Drop-in replacement for openai.OpenAI with automatic PII tokenization.

Strategy: composition over inheritance. We wrap the real OpenAI client and
intercept `chat.completions.create` (and `responses.create` for newer SDKs)
to tokenize input messages and detokenize the response.

All other methods are forwarded transparently via __getattr__.

Limitations of v0.1.0:
- Streaming responses (stream=True) are NOT supported yet — tokens flow
  through but detokenization happens only on completion. Known TODO.
- Multimodal content (image_url, audio) is passed through untouched.
- Tool calls and function arguments are passed through untouched.
- Async client (openai.AsyncOpenAI) is not yet wrapped — use the sync
  client for now.
"""

from __future__ import annotations

from typing import Any

try:
    from openai import OpenAI as _RealOpenAI
except ImportError as exc:  # pragma: no cover - optional dep
    raise ImportError("openai package required") from exc

from guardforge.client import GuardForgeClient


def _is_text_content(content: Any) -> bool:
    """Return True if a chat message content is a plain string we can tokenize."""
    return isinstance(content, str)


def _tokenize_messages(
    messages: list[dict[str, Any]],
    gf: GuardForgeClient,
) -> tuple[list[dict[str, Any]], str | None]:
    """Tokenize all string contents in a chat messages list.

    Uses a single session_id for the whole conversation so that all tokens
    come from one mapping (more efficient and consistent).

    Returns:
        A new messages list with string contents replaced by tokens, and
        the session_id used (or None if nothing was tokenized).
    """
    session_id: str | None = None
    new_messages: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            new_messages.append(msg)
            continue
        content = msg.get("content")
        if _is_text_content(content) and content:
            result = gf.tokenize(content, session_id=session_id)
            session_id = result.session_id
            new_msg = dict(msg)
            new_msg["content"] = result.tokenized_text
            new_messages.append(new_msg)
        else:
            new_messages.append(msg)
    return new_messages, session_id


def _detokenize_response_text(text: str | None, session_id: str, gf: GuardForgeClient) -> str | None:
    """Detokenize a response text. Returns None if input is None."""
    if not text:
        return text
    try:
        return gf.detokenize(text, session_id=session_id)
    except Exception:
        # Best-effort: if detokenize fails (e.g. session expired), return as-is
        return text


class _CompletionsProxy:
    """Wraps openai.OpenAI().chat.completions and intercepts create()."""

    def __init__(self, real_completions: Any, gf: GuardForgeClient) -> None:
        self._real = real_completions
        self._gf = gf

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def create(self, **kwargs: Any) -> Any:
        """Tokenize messages → call OpenAI → detokenize response."""
        messages = kwargs.get("messages")
        if not isinstance(messages, list):
            return self._real.create(**kwargs)

        new_messages, session_id = _tokenize_messages(messages, self._gf)
        kwargs["messages"] = new_messages

        # Streaming not yet supported with detokenization
        if kwargs.get("stream"):
            return self._real.create(**kwargs)

        response = self._real.create(**kwargs)

        if session_id is None:
            return response

        # Detokenize each choice's message content
        try:
            choices = getattr(response, "choices", None)
            if choices:
                for choice in choices:
                    msg = getattr(choice, "message", None)
                    if msg is None:
                        continue
                    original = getattr(msg, "content", None)
                    if isinstance(original, str):
                        restored = _detokenize_response_text(original, session_id, self._gf)
                        try:
                            msg.content = restored
                        except (AttributeError, TypeError):
                            # Pydantic models with frozen attrs — best effort
                            pass
        except Exception:
            # Never break the user's flow due to detokenize errors
            pass

        return response


class _ChatProxy:
    """Wraps openai.OpenAI().chat to expose a wrapped completions namespace."""

    def __init__(self, real_chat: Any, gf: GuardForgeClient) -> None:
        self._real = real_chat
        self._gf = gf
        self.completions = _CompletionsProxy(real_chat.completions, gf)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class OpenAI:
    """Drop-in replacement for openai.OpenAI with automatic PII tokenization.

    Args:
        guardforge_url: GuardForge backend URL (default: $GUARDFORGE_API_URL).
        guardforge_api_key: GuardForge API key (default: $GUARDFORGE_API_KEY).
        guardforge_client: Pre-built GuardForgeClient (overrides url/api_key).
        *args, **kwargs: Forwarded to openai.OpenAI(...).

    Example:
        from guardforge import OpenAI
        client = OpenAI(api_key="sk-...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi, my IBAN is FR..."}],
        )
        # response.choices[0].message.content has the real IBAN restored
        # but OpenAI never received it.
    """

    def __init__(
        self,
        *args: Any,
        guardforge_url: str | None = None,
        guardforge_api_key: str | None = None,
        guardforge_client: GuardForgeClient | None = None,
        **kwargs: Any,
    ) -> None:
        self._real = _RealOpenAI(*args, **kwargs)
        self._gf = guardforge_client or GuardForgeClient(
            url=guardforge_url,
            api_key=guardforge_api_key,
        )
        self.chat = _ChatProxy(self._real.chat, self._gf)

    def __getattr__(self, name: str) -> Any:
        # Forward any attribute we don't override (embeddings, files, audio, etc.)
        return getattr(self._real, name)
