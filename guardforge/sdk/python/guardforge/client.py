"""GuardForge HTTP client — talks to the GuardForge backend API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


class GuardForgeError(RuntimeError):
    """Base exception for GuardForge SDK errors."""


@dataclass(frozen=True)
class TokenizeResult:
    """Result of a tokenize call."""
    tokenized_text: str
    session_id: str
    token_count: int
    entities: list[dict[str, Any]]


class GuardForgeClient:
    """Synchronous HTTP client for the GuardForge backend.

    Args:
        url: Base URL of the GuardForge API (default: $GUARDFORGE_API_URL or http://localhost:8004).
        api_key: API key for X-API-Key authentication (default: $GUARDFORGE_API_KEY).
        timeout: HTTP timeout in seconds (default: 10).

    Raises:
        GuardForgeError: if API key is missing.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._url = (url or os.environ.get("GUARDFORGE_API_URL") or "http://localhost:8004").rstrip("/")
        self._api_key = api_key or os.environ.get("GUARDFORGE_API_KEY") or ""
        if not self._api_key:
            raise GuardForgeError(
                "GuardForge API key is required. Pass api_key= or set GUARDFORGE_API_KEY env var."
            )
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._url,
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
                "User-Agent": "guardforge-python/0.1.0",
            },
            timeout=timeout,
        )

    def __enter__(self) -> GuardForgeClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def tokenize(
        self,
        text: str,
        session_id: str | None = None,
        policy: str | None = None,
    ) -> TokenizeResult:
        """Tokenize text. Replaces PII with [TYPE_xxxx] tokens.

        If session_id is provided, the existing session mapping is extended.
        Otherwise, a new session is created and returned in the result.
        """
        payload: dict[str, Any] = {"text": text}
        if session_id is not None:
            payload["session_id"] = session_id
        if policy is not None:
            payload["policy"] = policy
        try:
            res = self._client.post("/api/tokenize", json=payload)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise GuardForgeError(f"tokenize failed: {exc}") from exc
        data = res.json()
        return TokenizeResult(
            tokenized_text=data["tokenized_text"],
            session_id=data["session_id"],
            token_count=data.get("token_count", 0),
            entities=data.get("entities", []),
        )

    def detokenize(self, text: str, session_id: str) -> str:
        """Detokenize text using the given session mapping. Returns original."""
        try:
            res = self._client.post(
                "/api/detokenize",
                json={"text": text, "session_id": session_id},
            )
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise GuardForgeError(f"detokenize failed: {exc}") from exc
        return res.json()["original_text"]

    def health(self) -> dict[str, Any]:
        """Check backend health. Useful for connection validation."""
        try:
            res = self._client.get("/health")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise GuardForgeError(f"health check failed: {exc}") from exc
        return res.json()
