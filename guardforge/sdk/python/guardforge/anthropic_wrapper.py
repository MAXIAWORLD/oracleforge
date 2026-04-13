"""Drop-in replacement for anthropic.Anthropic with automatic PII tokenization.

Same composition strategy as openai_wrapper. Intercepts messages.create().

Limitations of v0.1.0:
- Streaming responses are NOT yet supported.
- Multimodal content (image blocks) is passed through untouched.
- Tool use is passed through untouched.
- AsyncAnthropic is not yet wrapped.
"""

from __future__ import annotations

from typing import Any

try:
    from anthropic import Anthropic as _RealAnthropic
except ImportError as exc:  # pragma: no cover - optional dep
    raise ImportError("anthropic package required") from exc

from guardforge.client import GuardForgeClient


def _tokenize_anthropic_messages(
    messages: list[dict[str, Any]],
    gf: GuardForgeClient,
) -> tuple[list[dict[str, Any]], str | None]:
    """Tokenize all string contents in an Anthropic messages list.

    Anthropic message format:
      [{"role": "user", "content": "string"}, ...]
      or
      [{"role": "user", "content": [{"type": "text", "text": "..."}, ...]}, ...]
    """
    session_id: str | None = None
    new_messages: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            new_messages.append(msg)
            continue
        content = msg.get("content")
        new_msg = dict(msg)

        if isinstance(content, str) and content:
            result = gf.tokenize(content, session_id=session_id)
            session_id = result.session_id
            new_msg["content"] = result.tokenized_text
        elif isinstance(content, list):
            new_blocks: list[Any] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        result = gf.tokenize(text, session_id=session_id)
                        session_id = result.session_id
                        new_block = dict(block)
                        new_block["text"] = result.tokenized_text
                        new_blocks.append(new_block)
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            new_msg["content"] = new_blocks

        new_messages.append(new_msg)
    return new_messages, session_id


class _MessagesProxy:
    """Wraps anthropic.Anthropic().messages and intercepts create()."""

    def __init__(self, real_messages: Any, gf: GuardForgeClient) -> None:
        self._real = real_messages
        self._gf = gf

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def create(self, **kwargs: Any) -> Any:
        messages = kwargs.get("messages")
        system = kwargs.get("system")

        # Tokenize messages
        if isinstance(messages, list):
            new_messages, session_id = _tokenize_anthropic_messages(messages, self._gf)
            kwargs["messages"] = new_messages
        else:
            session_id = None

        # Tokenize system prompt if present
        if isinstance(system, str) and system:
            result = self._gf.tokenize(system, session_id=session_id)
            session_id = result.session_id
            kwargs["system"] = result.tokenized_text

        # Streaming not yet supported with detokenization
        if kwargs.get("stream"):
            return self._real.create(**kwargs)

        response = self._real.create(**kwargs)

        if session_id is None:
            return response

        # Detokenize response content blocks
        try:
            content_blocks = getattr(response, "content", None)
            if content_blocks:
                for block in content_blocks:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        try:
                            restored = self._gf.detokenize(text, session_id)
                            block.text = restored
                        except (AttributeError, TypeError, Exception):
                            pass
        except Exception:
            pass

        return response


class Anthropic:
    """Drop-in replacement for anthropic.Anthropic with automatic PII tokenization.

    Example:
        from guardforge import Anthropic
        client = Anthropic(api_key="sk-ant-...")
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": "My SIRET is 73282932000074"}],
        )
        # response.content[0].text has the real SIRET restored
    """

    def __init__(
        self,
        *args: Any,
        guardforge_url: str | None = None,
        guardforge_api_key: str | None = None,
        guardforge_client: GuardForgeClient | None = None,
        **kwargs: Any,
    ) -> None:
        self._real = _RealAnthropic(*args, **kwargs)
        self._gf = guardforge_client or GuardForgeClient(
            url=guardforge_url,
            api_key=guardforge_api_key,
        )
        self.messages = _MessagesProxy(self._real.messages, self._gf)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)
