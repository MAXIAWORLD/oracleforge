"""TDD tests for services/vault.py."""

import pytest
from services.vault import Vault, VaultUnavailable


class TestVault:
    def test_encrypt_decrypt(self) -> None:
        v = Vault()  # auto-generates key
        cipher = v.encrypt("my secret")
        assert cipher != "my secret"
        assert v.decrypt(cipher) == "my secret"

    def test_store_and_get(self) -> None:
        v = Vault()
        v.store_secret("api_key", "sk-12345")
        assert v.get_secret("api_key") == "sk-12345"

    def test_get_missing_returns_none(self) -> None:
        v = Vault()
        assert v.get_secret("nonexistent") is None

    def test_delete_secret(self) -> None:
        v = Vault()
        v.store_secret("temp", "value")
        assert v.delete_secret("temp") is True
        assert v.delete_secret("temp") is False

    def test_list_keys(self) -> None:
        v = Vault()
        v.store_secret("a", "1")
        v.store_secret("b", "2")
        keys = v.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_is_available(self) -> None:
        v = Vault()
        assert v.is_available is True

    def test_generate_key(self) -> None:
        key = Vault.generate_key()
        assert len(key) > 20

    def test_stats(self) -> None:
        v = Vault()
        v.store_secret("x", "y")
        stats = v.stats()
        assert stats["available"] is True
        assert stats["entries"] == 1
