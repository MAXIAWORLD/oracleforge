"""MAXIA Oracle — SQLite persistence layer.

Stores API keys and rate-limit counters. SQLite is chosen deliberately over
PostgreSQL / Redis for Phase 3:
    - Single file, zero ops overhead, fits the "distribution-first" focus of
      MAXIA Oracle V1
    - WAL mode + busy_timeout handles Phase 3 concurrency easily
    - Rows are trivially auditable with `sqlite3 db.sqlite "SELECT ..."`

When Phase 7 deploys to VPS, the same file will be used with a mount on
/var/lib/maxia-oracle/. No migration needed.

Schema:
    api_keys        — one row per issued key, holds the SHA256(key+pepper) hash
    rate_limit      — one row per (key_hash, window_start), atomic UPDATE
    register_limit  — one row per (ip, window_start) for /api/register IP gating
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Final

from core.config import DB_PATH

logger = logging.getLogger("maxia_oracle.db")

_BUSY_TIMEOUT_MS: Final[int] = 5000

_SCHEMA_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash    TEXT PRIMARY KEY NOT NULL,
    created_at  INTEGER NOT NULL,
    tier        TEXT NOT NULL DEFAULT 'free',
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rate_limit (
    key_hash     TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key_hash, window_start)
);

CREATE TABLE IF NOT EXISTS register_limit (
    ip           TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ip, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_window
    ON rate_limit (window_start);

CREATE INDEX IF NOT EXISTS idx_register_limit_window
    ON register_limit (window_start);
"""


def _connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection configured for concurrent API use.

    - `isolation_level=None` lets us control transactions explicitly with BEGIN
    - `check_same_thread=False` is required because FastAPI handles each request
      on a worker thread; we use one connection per request, so no cross-thread
      sharing happens anyway
    """
    conn = sqlite3.connect(
        str(db_path),
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    # Performance + concurrency pragmas. WAL allows readers and a single writer
    # to proceed in parallel; busy_timeout retries briefly on write contention.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_shared_connection: sqlite3.Connection | None = None


def init_db() -> sqlite3.Connection:
    """Open the shared DB connection and apply the schema.

    Called from the FastAPI lifespan on startup. Idempotent: safe to call
    multiple times; only opens a new connection if the previous one was
    closed.
    """
    global _shared_connection
    if _shared_connection is not None:
        return _shared_connection

    db_path = Path(DB_PATH).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    conn.executescript(_SCHEMA_SQL)
    logger.info("SQLite initialized at %s", db_path)
    _shared_connection = conn
    return conn


def get_db() -> sqlite3.Connection:
    """Return the shared SQLite connection, initializing it on first access.

    Phase 3 uses one long-lived connection in WAL mode instead of a
    per-request connection pool. SQLite's WAL mode plus the busy_timeout
    handles the concurrency MAXIA Oracle V1 needs (<<1000 req/min) and
    keeps operational complexity to near zero.

    init_db() is still called from the FastAPI lifespan at startup so that
    any configuration error (missing DB_PATH parent, invalid pragma, etc.)
    surfaces before the server begins accepting traffic. This lazy guard is
    purely defensive — it makes get_db() correct under test-harness code
    paths that reload modules and bypass the lifespan.
    """
    global _shared_connection
    if _shared_connection is None:
        init_db()
    if _shared_connection is None:
        raise RuntimeError("init_db() failed to produce a connection")
    return _shared_connection


def close_db() -> None:
    """Close the shared DB connection. Called from the FastAPI lifespan shutdown."""
    global _shared_connection
    if _shared_connection is not None:
        _shared_connection.close()
        _shared_connection = None
        logger.info("SQLite connection closed")


def now_unix() -> int:
    """Return the current Unix timestamp in seconds as int (UTC)."""
    return int(time.time())
