"""AuthForge — JWT authentication + password hashing.

Core auth service: register, login, token generation/validation, roles.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt

from core.config import Settings


class AuthService:
    """Stateless JWT auth with bcrypt-style password hashing."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret or settings.secret_key
        self._algo = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.jwt_access_ttl_minutes)
        self._refresh_ttl = timedelta(days=settings.jwt_refresh_ttl_days)

    # ── Password hashing (HMAC-SHA256 + salt) ────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with random salt using PBKDF2."""
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return f"{salt}:{h.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, expected = hashed.split(":")
            h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
            return hmac.compare_digest(h.hex(), expected)
        except (ValueError, AttributeError):
            return False

    # ── JWT tokens ───────────────────────────────────────────────

    def create_access_token(self, user_id: int, email: str, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + self._access_ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def create_refresh_token(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": now,
            "exp": now + self._refresh_ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def verify_token(self, token: str, token_type: str = "access") -> dict | None:
        """Verify and decode a JWT token. Returns payload or None."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algo])
            if payload.get("type") != token_type:
                return None
            return payload
        except jwt.PyJWTError:
            return None

    def create_token_pair(self, user_id: int, email: str, role: str) -> dict:
        """Create access + refresh token pair."""
        return {
            "access_token": self.create_access_token(user_id, email, role),
            "refresh_token": self.create_refresh_token(user_id),
            "token_type": "bearer",
            "expires_in": int(self._access_ttl.total_seconds()),
        }

    # ── API key generation ───────────────────────────────────────

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """Generate an API key. Returns (raw_key, key_hash)."""
        raw = f"af_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        return raw, key_hash

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self._window
        requests = self._requests.get(key, [])
        requests = [t for t in requests if t > cutoff]
        self._requests[key] = requests
        if len(requests) >= self._max:
            return False
        requests.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        cutoff = now - self._window
        requests = [t for t in self._requests.get(key, []) if t > cutoff]
        return max(0, self._max - len(requests))
