"""Phase 4 DB tests — x402 replay-protection table and helpers.

These tests exercise `core.db.x402_record_tx()` and
`core.db.x402_tx_already_processed()` against a throw-away SQLite database.
They intentionally do not spin up FastAPI — the middleware integration tests
live in `test_phase4_x402.py` (Step 7).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def fresh_db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a clean SQLite connection with the MAXIA Oracle schema applied."""
    os.environ["DB_PATH"] = str(tmp_path / "phase4_test.sqlite")

    from core.db import close_db, init_db  # noqa: PLC0415 — env must be set first

    close_db()
    conn = init_db()
    conn.execute("DELETE FROM x402_txs")
    yield conn
    close_db()


VALID_TX_HASH = "0x" + "ab" * 32  # 66 chars — canonical EVM tx hash length


def test_record_tx_inserts_first_time(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    inserted = x402_record_tx(
        fresh_db,
        tx_hash=VALID_TX_HASH,
        amount_usdc=0.001,
        path="/api/price/BTC",
    )
    assert inserted is True


def test_record_tx_replay_returns_false(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    first = x402_record_tx(fresh_db, VALID_TX_HASH, 0.001, "/api/price/BTC")
    second = x402_record_tx(fresh_db, VALID_TX_HASH, 0.001, "/api/price/BTC")
    assert first is True
    assert second is False


def test_already_processed_false_for_unknown_hash(
    fresh_db: sqlite3.Connection,
) -> None:
    from core.db import x402_tx_already_processed  # noqa: PLC0415

    assert x402_tx_already_processed(fresh_db, VALID_TX_HASH) is False


def test_already_processed_true_after_insert(
    fresh_db: sqlite3.Connection,
) -> None:
    from core.db import x402_record_tx, x402_tx_already_processed  # noqa: PLC0415

    x402_record_tx(fresh_db, VALID_TX_HASH, 0.001, "/api/price/BTC")
    assert x402_tx_already_processed(fresh_db, VALID_TX_HASH) is True


def test_record_tx_rejects_empty_hash(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    with pytest.raises(ValueError, match="tx_hash"):
        x402_record_tx(fresh_db, "", 0.001, "/api/price/BTC")


def test_record_tx_rejects_negative_amount(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    with pytest.raises(ValueError, match="amount_usdc"):
        x402_record_tx(fresh_db, VALID_TX_HASH, -0.5, "/api/price/BTC")


def test_record_tx_rejects_empty_path(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    with pytest.raises(ValueError, match="path"):
        x402_record_tx(fresh_db, VALID_TX_HASH, 0.001, "")


def test_round_trip_stores_expected_columns(fresh_db: sqlite3.Connection) -> None:
    from core.db import x402_record_tx  # noqa: PLC0415

    x402_record_tx(fresh_db, VALID_TX_HASH, 0.005, "/api/prices/batch")
    row = fresh_db.execute(
        "SELECT tx_hash, amount_usdc, path, created_at FROM x402_txs WHERE tx_hash = ?",
        (VALID_TX_HASH,),
    ).fetchone()
    assert row is not None
    assert row["tx_hash"] == VALID_TX_HASH
    assert row["amount_usdc"] == 0.005
    assert row["path"] == "/api/prices/batch"
    assert row["created_at"] > 0
