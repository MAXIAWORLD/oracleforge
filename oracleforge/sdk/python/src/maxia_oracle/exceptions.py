"""MAXIA Oracle SDK — exception hierarchy.

All SDK calls raise a subclass of `MaxiaOracleError` on failure. Callers
can catch the base class to handle any SDK failure, or catch specific
subclasses for typed error handling.

Design choice: the SDK does NOT silently turn errors into empty results.
A failed call raises. This is the opposite of what the backend route
handlers do (they return `{"error": ...}` dicts with HTTP 200), but the
SDK layer is meant to be used inside `try`/`except` blocks, not inside
`if "error" in response` checks.

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

from typing import Any


class MaxiaOracleError(Exception):
    """Base class for all MAXIA Oracle SDK errors."""


class MaxiaOracleAuthError(MaxiaOracleError):
    """The request was rejected for authentication reasons (401).

    Usual causes: missing API key, invalid key, inactive key. Register a
    fresh key with `client.register()` and retry.
    """


class MaxiaOracleRateLimitError(MaxiaOracleError):
    """The caller exceeded the daily quota (429).

    Attributes:
        retry_after_seconds: Seconds until the current window resets.
        limit: Daily call limit applied to the caller's key.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit


class MaxiaOraclePaymentRequiredError(MaxiaOracleError):
    """The endpoint requires an x402 micropayment (402).

    The caller did not provide a valid `X-API-Key` and did not provide a
    valid `X-Payment` header either. The `accepts` attribute carries the
    payment challenge returned by the backend.
    """

    def __init__(self, message: str, *, accepts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.accepts = accepts or []


class MaxiaOracleValidationError(MaxiaOracleError):
    """The request was rejected for shape or symbol validation reasons (400/422).

    Usual causes: malformed symbol (not matching `^[A-Z0-9]{1,10}$`), batch
    size over 50, empty batch, non-list arguments.
    """


class MaxiaOracleUpstreamError(MaxiaOracleError):
    """Every upstream oracle source failed for this symbol (404 with `no live price available`).

    The symbol is recognized but Pyth, Chainlink, the aggregator and any
    other source returned an error. Retry later or switch to a different
    symbol.
    """


class MaxiaOracleTransportError(MaxiaOracleError):
    """Network or HTTP transport failure (connection refused, timeout, 5xx).

    The SDK did not receive a valid JSON response from the backend. Check
    the backend URL and your network.
    """
