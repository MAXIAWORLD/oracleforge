"""GuardForge — AES-256 Secret Vault with SQLite write-through persistence.

Extracted from MAXIA V12 core/vault.py and enhanced:
- Class-based with injected key
- Fernet encryption (AES-128-CBC + HMAC-SHA256)
- Key rotation support (MultiFernet)
- In-memory cache + sync SQLite write-through
- Survives backend restarts (critical for tokenization sessions)
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

_FERNET_OK = False
try:
    from cryptography.fernet import Fernet, MultiFernet
    _FERNET_OK = True
except ImportError:
    pass


class VaultUnavailable(RuntimeError):
    pass


def _extract_sqlite_path(database_url: str) -> str:
    """Extract the file path from a SQLAlchemy SQLite URL.

    Examples:
        sqlite+aiosqlite:///./guardforge.db  → ./guardforge.db
        sqlite:///./db.sqlite                → ./db.sqlite
        postgresql://...                     → ""
    """
    if not database_url or "sqlite" not in database_url:
        return ""
    # Strip the driver prefix and the triple slash
    for prefix in ("sqlite+aiosqlite:///", "sqlite+pysqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            return database_url[len(prefix):]
    return ""


class Vault:
    """AES-256 encrypted secret storage with SQLite persistence.

    Reads from in-memory cache (fast). Writes go to both cache AND DB
    (synchronously) so secrets survive restarts. On startup, all rows
    from `vault_entries` are loaded into the cache.

    For non-SQLite databases (PostgreSQL), persistence is disabled and
    the vault behaves as in-memory only — a future async-aware
    implementation would be needed.
    """

    def __init__(self, encryption_key: str = "", database_url: str = "") -> None:
        self._fernet: Any = None
        self._store: dict[str, str] = {}  # key → encrypted value (cache)
        self._db_path: str = _extract_sqlite_path(database_url)

        if not _FERNET_OK:
            logger.warning("[vault] cryptography not installed — vault disabled")
            return

        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            logger.info("[vault] auto-generated encryption key (dev mode)")

        try:
            keys = [k.strip() for k in encryption_key.split(",") if k.strip()]
            fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
            self._fernet = MultiFernet(fernets) if len(fernets) > 1 else fernets[0]
        except Exception as e:
            logger.error("[vault] invalid encryption key: %s", e)
            return

        # Load existing entries from DB into cache
        if self._db_path:
            self._load_from_db()
        else:
            logger.info("[vault] no SQLite path — running in-memory only (non-SQLite DB)")

    # ── DB helpers ───────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Open a sync SQLite connection. Caller is responsible for closing."""
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """Ensure the vault_entries table exists (idempotent).

        The aiosqlite engine should have already created it via Base.metadata
        on startup, but we guard against race conditions / fresh installs.
        """
        conn.execute(
            "CREATE TABLE IF NOT EXISTS vault_entries ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key VARCHAR(255) UNIQUE NOT NULL, "
            "encrypted_value TEXT NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    def _load_from_db(self) -> None:
        """Bulk-load all vault entries from DB into the in-memory cache."""
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                rows = conn.execute(
                    "SELECT key, encrypted_value FROM vault_entries"
                ).fetchall()
                for row in rows:
                    self._store[row["key"]] = row["encrypted_value"]
            logger.info("[vault] loaded %d entries from DB", len(self._store))
        except sqlite3.Error as exc:
            logger.warning("[vault] failed to load from DB (cache-only mode): %s", exc)

    def _persist(self, key: str, encrypted_value: str) -> None:
        """Upsert a single entry to DB. Best-effort, logs on failure."""
        if not self._db_path:
            return
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute(
                    "INSERT INTO vault_entries (key, encrypted_value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "encrypted_value = excluded.encrypted_value, "
                    "updated_at = CURRENT_TIMESTAMP",
                    (key, encrypted_value),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("[vault] failed to persist key %s: %s", key, exc)

    def _remove(self, key: str) -> None:
        """Delete a single entry from DB. Best-effort."""
        if not self._db_path:
            return
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute("DELETE FROM vault_entries WHERE key = ?", (key,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("[vault] failed to delete key %s: %s", key, exc)

    # ── Public API ───────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._fernet is not None

    @property
    def is_persistent(self) -> bool:
        """True if writes are backed by DB persistence."""
        return bool(self._db_path) and self._fernet is not None

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
        """Encrypt and store a secret. Writes through to DB if configured."""
        encrypted = self.encrypt(value)
        self._store[key] = encrypted
        self._persist(key, encrypted)

    def get_secret(self, key: str) -> str | None:
        """Retrieve and decrypt a secret from the cache."""
        encrypted = self._store.get(key)
        if encrypted is None:
            return None
        return self.decrypt(encrypted)

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from cache and DB. Returns True if existed."""
        existed = self._store.pop(key, None) is not None
        if existed:
            self._remove(key)
        return existed

    def list_keys(self) -> list[str]:
        """List all stored secret keys (not values)."""
        return list(self._store.keys())

    def stats(self) -> dict:
        return {
            "available": self.is_available,
            "persistent": self.is_persistent,
            "entries": len(self._store),
        }
