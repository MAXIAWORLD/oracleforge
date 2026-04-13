"""GuardForge Python SDK — drop-in PII redaction for LLM SDKs.

Usage:
    # Replace this:
    # from openai import OpenAI

    # With this:
    from guardforge import OpenAI

    client = OpenAI(api_key="sk-...")
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "My name is Jean Dupont"}],
    )
    # PII never leaves your infrastructure. Original values are restored
    # in the response so your end user still sees "Jean Dupont".

Configure the GuardForge backend via environment variables:
    GUARDFORGE_API_URL   (default: http://localhost:8004)
    GUARDFORGE_API_KEY   (required)

Or pass them explicitly:
    client = OpenAI(
        api_key="sk-...",
        guardforge_url="https://api.guardforge.io",
        guardforge_api_key="gf_...",
    )
"""

from __future__ import annotations

from guardforge.client import GuardForgeClient, GuardForgeError
from guardforge._lazy import LazyOpenAI as OpenAI
from guardforge._lazy import LazyAnthropic as Anthropic

__version__ = "0.1.0"

__all__ = [
    "OpenAI",
    "Anthropic",
    "GuardForgeClient",
    "GuardForgeError",
    "__version__",
]
