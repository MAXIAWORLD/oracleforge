"""TDD tests for services/vault.py."""

import pytest
from services.vault import Vault, VaultUnavailable, _extract_sqlite_path


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


class TestSqlitePathExtraction:
    def test_aiosqlite_url(self) -> None:
        assert _extract_sqlite_path("sqlite+aiosqlite:///./test.db") == "./test.db"

    def test_pysqlite_url(self) -> None:
        assert _extract_sqlite_path("sqlite+pysqlite:///./test.db") == "./test.db"

    def test_plain_sqlite_url(self) -> None:
        assert _extract_sqlite_path("sqlite:///./test.db") == "./test.db"

    def test_postgres_returns_empty(self) -> None:
        assert _extract_sqlite_path("postgresql://user:pass@host/db") == ""

    def test_empty_returns_empty(self) -> None:
        assert _extract_sqlite_path("") == ""


class TestVaultPersistence:
    """Critical regression: vault must survive backend restarts so tokenize sessions
    remain restorable. Previously the vault was in-memory only."""

    def test_store_persists_across_instances(self, tmp_path) -> None:
        db_file = tmp_path / "vault_test.db"
        url = f"sqlite+aiosqlite:///{db_file}"
        # Use a fixed key so both instances can decrypt
        key = Vault.generate_key()

        v1 = Vault(encryption_key=key, database_url=url)
        v1.store_secret("session_42", "secret_payload")
        assert v1.is_persistent is True

        # Simulate restart: discard v1, create v2 with same DB and key
        v2 = Vault(encryption_key=key, database_url=url)
        assert v2.get_secret("session_42") == "secret_payload"

    def test_delete_persists_across_instances(self, tmp_path) -> None:
        db_file = tmp_path / "vault_del.db"
        url = f"sqlite+aiosqlite:///{db_file}"
        key = Vault.generate_key()

        v1 = Vault(encryption_key=key, database_url=url)
        v1.store_secret("ephemeral", "value")
        v1.delete_secret("ephemeral")

        v2 = Vault(encryption_key=key, database_url=url)
        assert v2.get_secret("ephemeral") is None
        assert "ephemeral" not in v2.list_keys()

    def test_multiple_keys_persist(self, tmp_path) -> None:
        db_file = tmp_path / "vault_multi.db"
        url = f"sqlite+aiosqlite:///{db_file}"
        key = Vault.generate_key()

        v1 = Vault(encryption_key=key, database_url=url)
        v1.store_secret("a", "1")
        v1.store_secret("b", "2")
        v1.store_secret("c", "3")

        v2 = Vault(encryption_key=key, database_url=url)
        assert sorted(v2.list_keys()) == ["a", "b", "c"]
        assert v2.get_secret("a") == "1"
        assert v2.get_secret("b") == "2"
        assert v2.get_secret("c") == "3"

    def test_overwrite_persists(self, tmp_path) -> None:
        db_file = tmp_path / "vault_overwrite.db"
        url = f"sqlite+aiosqlite:///{db_file}"
        key = Vault.generate_key()

        v1 = Vault(encryption_key=key, database_url=url)
        v1.store_secret("k", "v1")
        v1.store_secret("k", "v2")

        v2 = Vault(encryption_key=key, database_url=url)
        assert v2.get_secret("k") == "v2"

    def test_in_memory_fallback_for_postgres(self) -> None:
        """Non-SQLite DB should silently fall back to in-memory only."""
        v = Vault(encryption_key=Vault.generate_key(), database_url="postgresql://foo")
        v.store_secret("x", "y")
        assert v.is_persistent is False
        assert v.get_secret("x") == "y"

    def test_no_db_url_acts_as_in_memory(self) -> None:
        """Backward compatibility: no database_url means in-memory only."""
        v = Vault(encryption_key=Vault.generate_key())
        v.store_secret("a", "b")
        assert v.is_persistent is False
        assert v.get_secret("a") == "b"
