"""MAXIA Oracle — X-API-Key authentication (Phase 3).

API keys are generated server-side, prefixed with "mxo_" so operators can
grep for them in logs/tickets, and delivered exactly once to the user via
POST /api/register. Only the SHA256(key + pepper) hash is persisted.

Why not JWT (Phase 3 decision #3):
    MAXIA Oracle V1 exposes a small number of stateless endpoints. JWT adds
    rotation, refresh, signing, and library surface without benefit. A long
    opaque string in a header is simpler, rotatable (just regenerate), and
    aligns with the pay-per-call x402 model coming in Phase 4.

Why hash + pepper (Phase 3 decision #2):
    If the DB leaks, raw keys would allow immediate impersonation. Hashing
    with SHA256 means the attacker can only check candidate keys one by one
    (still fast for GPUs). Adding a pepper (server-side secret NOT in the DB)
    forces the attacker to also compromise the process memory or config. This
    is the standard "pepper > salt" pattern: the pepper is global and secret,
    salt is per-row and public.

Key format:
    "mxo_" + secrets.token_urlsafe(32)
    token_urlsafe(32) returns ~43 chars of base64url (URL-safe chars A-Z a-z
    0-9 - _), giving ~192 bits of entropy. Total length ~47 chars.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import sqlite3
from typing import Final, Optional

from fastapi import Header, HTTPException, Request, status

from core.config import API_KEY_PEPPER
from core.db import get_db, now_unix

logger = logging.getLogger("maxia_oracle.auth")

_KEY_PREFIX: Final[str] = "mxo_"
_TOKEN_BYTES: Final[int] = 32  # -> ~43 chars of base64url

# Sentinel returned by `require_access` when the request was paid via x402.
# Routes compare the returned key_hash against this sentinel to skip the
# daily rate-limit check (pay-per-call users pay on every request, the
# quota does not apply).
X402_KEY_HASH_SENTINEL: Final[str] = "__x402_paid__"


def generate_key() -> tuple[str, str]:
    """Generate a fresh API key and return (raw_key, key_hash).

    The raw_key is returned ONCE to the user at registration time. Only the
    key_hash is stored — we cannot reconstruct the raw key from the DB.
    """
    raw_key = _KEY_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)
    return raw_key, hash_key(raw_key)


def hash_key(raw_key: str) -> str:
    """Return SHA256(raw_key + pepper) as lowercase hex.

    Uses hashlib.sha256 rather than HMAC because we only need preimage
    resistance, not authentication (the key IS the authenticator).
    """
    digest = hashlib.sha256()
    digest.update(raw_key.encode("utf-8"))
    if API_KEY_PEPPER:
        digest.update(API_KEY_PEPPER.encode("utf-8"))
    return digest.hexdigest()


def verify_hash(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison between hash(raw_key) and stored_hash."""
    return hmac.compare_digest(hash_key(raw_key), stored_hash)


def issue_key(db: sqlite3.Connection, tier: str = "free") -> str:
    """Generate a new key, store its hash, and return the RAW key to the caller.

    The raw key is NEVER written to the DB. The caller MUST hand it back to
    the end-user immediately and must NOT log it.
    """
    raw_key, key_hash = generate_key()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, ?, ?, 1)",
        (key_hash, now_unix(), tier),
    )
    return raw_key


def lookup_key(db: sqlite3.Connection, raw_key: str) -> Optional[sqlite3.Row]:
    """Return the api_keys row matching raw_key if it exists and is active."""
    if not raw_key or not raw_key.startswith(_KEY_PREFIX):
        return None
    key_hash = hash_key(raw_key)
    row = db.execute(
        "SELECT key_hash, created_at, tier, active FROM api_keys "
        "WHERE key_hash = ? AND active = 1",
        (key_hash,),
    ).fetchone()
    return row


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency: validates X-API-Key header and returns the key_hash.

    Returns the hash (not the raw key) so the caller can safely pass it to the
    rate limiter without risk of logging the raw key.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-API-Key header",
            headers={"WWW-Authenticate": 'ApiKey realm="maxia-oracle"'},
        )
    db = get_db()
    row = lookup_key(db, x_api_key)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or inactive API key",
            headers={"WWW-Authenticate": 'ApiKey realm="maxia-oracle"'},
        )
    return row["key_hash"]


async def require_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Phase 4 unified access dependency: accepts either x402 payment or X-API-Key.

    The x402 middleware runs before the route is resolved and, on successful
    payment, sets `request.state.x402_paid = True`. This dependency checks
    that flag first; if set, the request is authorized without an API key
    and the daily rate-limit is skipped (pay-per-call users pay on every
    request).

    Otherwise the request is routed through the existing `require_api_key`
    logic. This preserves the free tier (X-API-Key, 100 req/day) alongside
    the new anonymous pay-per-call path.
    """
    if getattr(request.state, "x402_paid", False):
        return X402_KEY_HASH_SENTINEL
    return await require_api_key(x_api_key=x_api_key)
