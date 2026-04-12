"""OracleForge — Circuit Breaker for price source reliability.

Extracted from MAXIA V12 price_oracle.py CircuitBreaker class.
States: CLOSED (normal) → OPEN (failures exceeded) → HALF_OPEN (cooldown expired, try one).
"""

from __future__ import annotations

import time
from enum import StrEnum


class State(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-source circuit breaker with TTL-based recovery."""

    def __init__(self, threshold: int = 3, ttl: int = 60) -> None:
        self._threshold = threshold
        self._ttl = ttl
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at: float = 0.0
        self._last_error: str = ""

    @property
    def state(self) -> State:
        if self._state == State.OPEN:
            if time.time() - self._opened_at >= self._ttl:
                self._state = State.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == State.OPEN

    @property
    def last_error(self) -> str:
        return self._last_error

    def record_success(self) -> None:
        self._failures = 0
        self._state = State.CLOSED

    def record_failure(self, error: str = "") -> None:
        self._failures += 1
        self._last_error = error
        if self._failures >= self._threshold:
            self._state = State.OPEN
            self._opened_at = time.time()

    def get_status(self) -> dict:
        return {
            "state": self.state.value,
            "failures": self._failures,
            "threshold": self._threshold,
            "ttl": self._ttl,
            "last_error": self._last_error,
        }
