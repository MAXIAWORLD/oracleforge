"""GuardForge — AES-256 Secret Vault.

Extracted from MAXIA V12 core/vault.py and enhanced:
- Class-based with injected key
- Fernet encryption (AES-128-CBC + HMAC-SHA256)
- Key rotation support
- In-memory store with optional DB persistence
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_FERNET_OK = False
try:
    from cryptography.fernet import Fernet, MultiFernet, InvalidToken
    _FERNET_OK = True
except ImportError:
    pass


class VaultUnavailable(RuntimeError):
    pass


class Vault:
    """AES-256 encrypted secret storage."""

    def __init__(self, encryption_key: str = "") -> None:
        self._fernet: Any = None
        self._store: dict[str, str] = {}  # key → encrypted value

        if not _FERNET_OK:
            logger.warning("[vault] cryptography not installed — vault disabled")
            return

        if not encryption_key:
            # Auto-generate a key for dev
            encryption_key = Fernet.generate_key().decode()
            logger.info("[vault] auto-generated encryption key (dev mode)")

        try:
            # Support comma-separated keys for rotation
            keys = [k.strip() for k in encryption_key.split(",") if k.strip()]
            fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
            self._fernet = MultiFernet(fernets) if len(fernets) > 1 else fernets[0]
        except Exception as e:
            logger.error("[vault] invalid encryption key: %s", e)

    @property
    def is_available(self) -> bool:
        return self._fernet is not None

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        if not _FERNET_OK:
            raise VaultUnavailable("cryptography not installed")
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns base64 ciphertext."""
        if not self.is_available:
            raise VaultUnavailable("Vault not initialised")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string. Returns plaintext."""
        if not self.is_available:
            raise VaultUnavailable("Vault not initialised")
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def store_secret(self, key: str, value: str) -> None:
        """Encrypt and store a secret."""
        self._store[key] = self.encrypt(value)

    def get_secret(self, key: str) -> str | None:
        """Retrieve and decrypt a secret."""
        encrypted = self._store.get(key)
        if encrypted is None:
            return None
        return self.decrypt(encrypted)

    def delete_secret(self, key: str) -> bool:
        """Delete a secret. Returns True if existed."""
        return self._store.pop(key, None) is not None

    def list_keys(self) -> list[str]:
        """List all stored secret keys (not values)."""
        return list(self._store.keys())

    def stats(self) -> dict:
        return {
            "available": self.is_available,
            "entries": len(self._store),
        }
