"""MAXIA Oracle — DB-backed fixed-window rate limiter (Phase 3).

Addresses V12 audit vulnerability H7 ("rate limiting non-persistent, lost at
restart"). Design choices and trade-offs are explained in the Phase 3
architecture decision #5 (user-facing architecture doc).

Window semantics:
    - window_start = floor(now / WINDOW_SECONDS) * WINDOW_SECONDS
    - Day boundaries are UTC midnight (never local time — a user in France
      and a user in San Francisco must share the same reset)
    - Each (key_hash, window_start) pair has its own row; rows older than
      KEEP_DAYS are purged at startup to keep the table small

Atomicity:
    Two concurrent requests for the same key must not race on the count. We
    use `INSERT OR IGNORE` to create the row if absent, then `UPDATE ...
    SET count = count + 1 WHERE ... RETURNING count` which SQLite runs inside
    a single implicit transaction. The returned count is the post-increment
    value, so the first requester that crosses the limit is the one that
    gets refused — later requesters see count > limit and also get refused.

Register-endpoint gating (IP-based):
    /api/register is gated on the client IP to prevent a bot from spamming
    the endpoint to mint an unlimited number of free-tier keys. The table
    `register_limit` uses the same algorithm with a smaller window (1 min)
    and limit (1 per minute per IP).
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Final

from core.db import now_unix

logger = logging.getLogger("maxia_oracle.rate_limit")

# Daily free tier: 100 req / 24h per api key
DAILY_LIMIT: Final[int] = 100
DAILY_WINDOW_S: Final[int] = 86400

# Register throttle: 1 registration / 60s per IP
REGISTER_LIMIT: Final[int] = 1
REGISTER_WINDOW_S: Final[int] = 60

# How many days of historical counters to keep at startup purge
_KEEP_DAYS: Final[int] = 7


@dataclass(frozen=True)
class RateLimitDecision:
    """Immutable result of a rate-limit check."""

    allowed: bool
    count: int
    limit: int
    window_start: int
    window_s: int

    @property
    def reset_at(self) -> int:
        """Unix timestamp when the current window ends (and counter resets)."""
        return self.window_start + self.window_s

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)

    @property
    def retry_after(self) -> int:
        """Seconds until the next window (for the Retry-After HTTP header)."""
        return max(0, self.reset_at - now_unix())


def _compute_window_start(now: int, window_s: int) -> int:
    return (now // window_s) * window_s


def _check_and_increment(
    db: sqlite3.Connection,
    table: str,
    key_col: str,
    key_value: str,
    limit: int,
    window_s: int,
) -> RateLimitDecision:
    """Atomic check-then-increment against the given counter table.

    Generic helper used by `check_daily` (api_keys rate_limit) and
    `check_register` (register_limit) — both share the fixed-window algorithm
    and only differ by table name, key column, limit and window duration.
    """
    now = now_unix()
    window_start = _compute_window_start(now, window_s)

    # Ensure a row exists for the current window. Idempotent.
    db.execute(
        f"INSERT OR IGNORE INTO {table} ({key_col}, window_start, count) "
        f"VALUES (?, ?, 0)",
        (key_value, window_start),
    )
    # Atomically increment and read back the post-increment value.
    cursor = db.execute(
        f"UPDATE {table} SET count = count + 1 "
        f"WHERE {key_col} = ? AND window_start = ? "
        f"RETURNING count",
        (key_value, window_start),
    )
    row = cursor.fetchone()
    count = row[0] if row is not None else 0

    allowed = count <= limit
    if not allowed:
        logger.info(
            "Rate limit exceeded: %s=%s count=%d limit=%d window=%ds",
            key_col,
            key_value[:16] + "…",  # truncate hash to avoid full-key logs
            count,
            limit,
            window_s,
        )
    return RateLimitDecision(
        allowed=allowed,
        count=count,
        limit=limit,
        window_start=window_start,
        window_s=window_s,
    )


def check_daily(db: sqlite3.Connection, key_hash: str) -> RateLimitDecision:
    """Per-api-key daily quota. Called on every authenticated request."""
    return _check_and_increment(
        db,
        table="rate_limit",
        key_col="key_hash",
        key_value=key_hash,
        limit=DAILY_LIMIT,
        window_s=DAILY_WINDOW_S,
    )


def check_register(db: sqlite3.Connection, client_ip: str) -> RateLimitDecision:
    """Per-IP throttle on /api/register to prevent mass-minting of free keys."""
    return _check_and_increment(
        db,
        table="register_limit",
        key_col="ip",
        key_value=client_ip or "unknown",
        limit=REGISTER_LIMIT,
        window_s=REGISTER_WINDOW_S,
    )


def purge_old_windows(db: sqlite3.Connection) -> int:
    """Delete rate_limit rows older than _KEEP_DAYS. Called at startup.

    Returns the total number of rows deleted (both tables). Safe to run
    against a live database — rows for the current window are protected by
    the WHERE clause.
    """
    now = now_unix()
    rate_cutoff = _compute_window_start(now, DAILY_WINDOW_S) - _KEEP_DAYS * DAILY_WINDOW_S
    register_cutoff = _compute_window_start(now, REGISTER_WINDOW_S) - _KEEP_DAYS * DAILY_WINDOW_S

    cursor1 = db.execute(
        "DELETE FROM rate_limit WHERE window_start < ?",
        (rate_cutoff,),
    )
    cursor2 = db.execute(
        "DELETE FROM register_limit WHERE window_start < ?",
        (register_cutoff,),
    )
    deleted = (cursor1.rowcount or 0) + (cursor2.rowcount or 0)
    if deleted:
        logger.info("Purged %d stale rate-limit rows", deleted)
    return deleted
