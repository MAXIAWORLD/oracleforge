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
    x402_txs        — one row per verified x402 payment, replay-protection
                      (Phase 4): tx_hash is PRIMARY KEY so INSERT OR FAIL
                      detects reuse atomically
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

CREATE TABLE IF NOT EXISTS x402_txs (
    tx_hash      TEXT PRIMARY KEY NOT NULL,
    amount_usdc  REAL NOT NULL,
    path         TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    chain        TEXT NOT NULL DEFAULT 'base'
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_window
    ON rate_limit (window_start);

CREATE INDEX IF NOT EXISTS idx_register_limit_window
    ON register_limit (window_start);

CREATE INDEX IF NOT EXISTS idx_x402_txs_created_at
    ON x402_txs (created_at);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    price       REAL NOT NULL,
    source_count INTEGER NOT NULL DEFAULT 1,
    sampled_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
    ON price_snapshots (symbol, sampled_at);
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


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, ddl_fragment: str
) -> None:
    """Idempotent SQLite `ALTER TABLE ADD COLUMN` guard.

    SQLite has no `ADD COLUMN IF NOT EXISTS` so we introspect the table
    schema via PRAGMA and only execute the ALTER when the column is
    missing. Safe to call on every `init_db()` — a no-op on schemas that
    already include the column.
    """
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl_fragment}")
    logger.info("[db] Added %s.%s via migration", table, column)


def init_db() -> sqlite3.Connection:
    """Open the shared DB connection and apply the schema.

    Called from the FastAPI lifespan on startup. Idempotent: safe to call
    multiple times; only opens a new connection if the previous one was
    closed. Non-destructive migrations (like V1.2's `x402_txs.chain`
    column) are applied here so older DB files upgrade in place.
    """
    global _shared_connection
    if _shared_connection is not None:
        return _shared_connection

    db_path = Path(DB_PATH).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    conn.executescript(_SCHEMA_SQL)

    # V1.2 migration: add `chain` column to pre-existing `x402_txs` tables.
    # The executescript above creates the column for fresh DBs; this guard
    # upgrades DBs that were initialized against the Phase 4 schema.
    _ensure_column(
        conn, "x402_txs", "chain", "chain TEXT NOT NULL DEFAULT 'base'"
    )

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


# ══════════════════════════════════════════════════════════════════════════
# ── x402 replay protection helpers (Phase 4) ──
# ══════════════════════════════════════════════════════════════════════════
#
# The x402 middleware inserts a row per verified payment. A PRIMARY KEY
# collision on tx_hash means the same payment header is being re-used
# (replay attack), and the middleware returns 402 with an explicit message.
#
# tx_hash format is validated by the caller (66 chars, 0x + 64 hex for EVM).
# We do not re-validate here — the DB only enforces uniqueness.

_TX_HASH_MAX_LENGTH: Final[int] = 128  # safety cap against oversized inputs


def x402_tx_already_processed(
    conn: sqlite3.Connection, tx_hash: str
) -> bool:
    """Return True if the given x402 tx_hash has already been recorded.

    Used as a pre-check by the middleware before attempting insertion. The
    authoritative check is the INSERT in x402_record_tx() — this function is
    a defensive fast path that lets the middleware return a specific error
    message without relying on exception control flow.
    """
    if not tx_hash or len(tx_hash) > _TX_HASH_MAX_LENGTH:
        return False
    row = conn.execute(
        "SELECT 1 FROM x402_txs WHERE tx_hash = ? LIMIT 1",
        (tx_hash,),
    ).fetchone()
    return row is not None


def x402_record_tx(
    conn: sqlite3.Connection,
    tx_hash: str,
    amount_usdc: float,
    path: str,
    chain: str = "base",
) -> bool:
    """Record a verified x402 transaction. Return True on insert, False on replay.

    V1.2: `chain` is recorded alongside the hash so the audit trail shows
    which EVM network settled the payment. The primary key stays
    `tx_hash` alone (cf. v1.2 doc, decision D5) because collision across
    chains is cryptographically negligible.

    Uses INSERT OR IGNORE so that concurrent duplicate inserts resolve
    deterministically: the first writer wins, subsequent writers observe a
    0-row change and receive False.
    """
    if not tx_hash or len(tx_hash) > _TX_HASH_MAX_LENGTH:
        raise ValueError("tx_hash must be a non-empty string")
    if amount_usdc <= 0:
        raise ValueError(f"amount_usdc must be strictly positive, got {amount_usdc}")
    if not path:
        raise ValueError("path must be a non-empty string")
    if not chain:
        raise ValueError("chain must be a non-empty string")

    cursor = conn.execute(
        "INSERT OR IGNORE INTO x402_txs (tx_hash, amount_usdc, path, created_at, chain) "
        "VALUES (?, ?, ?, ?, ?)",
        (tx_hash, amount_usdc, path, now_unix(), chain),
    )
    return cursor.rowcount == 1


# ══════════════════════════════════════════════════════════════════════════
# ── V1.8 price history helpers ──
# ══════════════════════════════════════════════════════════════════════════

_MAX_DATAPOINTS: Final[int] = 2000


def insert_price_snapshots(
    conn: sqlite3.Connection,
    rows: list[tuple[str, float, int]],
) -> int:
    """Bulk-insert price snapshots. Each tuple is (symbol, price, source_count).

    Returns the number of rows inserted.
    """
    if not rows:
        return 0
    ts = now_unix()
    conn.executemany(
        "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
        "VALUES (?, ?, ?, ?)",
        [(sym, price, sc, ts) for sym, price, sc in rows],
    )
    return len(rows)


def query_price_history(
    conn: sqlite3.Connection,
    symbol: str,
    since: int,
    bucket_s: int,
) -> list[dict[str, float | int]]:
    """Return downsampled price history as a list of {timestamp, price, samples}.

    Groups raw snapshots into buckets of `bucket_s` seconds and averages.
    """
    rows = conn.execute(
        "SELECT (sampled_at / ?) * ? AS bucket_time, "
        "       ROUND(AVG(price), 6) AS avg_price, "
        "       COUNT(*) AS samples "
        "FROM price_snapshots "
        "WHERE symbol = ? AND sampled_at >= ? "
        "GROUP BY bucket_time "
        "ORDER BY bucket_time "
        "LIMIT ?",
        (bucket_s, bucket_s, symbol, since, _MAX_DATAPOINTS),
    ).fetchall()
    return [
        {"timestamp": row[0], "price": row[1], "samples": row[2]}
        for row in rows
    ]


def oldest_snapshot_ts(conn: sqlite3.Connection, symbol: str) -> int | None:
    """Return the oldest sampled_at for a symbol, or None if no data."""
    row = conn.execute(
        "SELECT MIN(sampled_at) FROM price_snapshots WHERE symbol = ?",
        (symbol,),
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def purge_old_snapshots(conn: sqlite3.Connection, retention_days: int) -> int:
    """Delete snapshots older than `retention_days`. Returns rows deleted."""
    cutoff = now_unix() - retention_days * 86400
    cursor = conn.execute(
        "DELETE FROM price_snapshots WHERE sampled_at < ?", (cutoff,)
    )
    return cursor.rowcount
