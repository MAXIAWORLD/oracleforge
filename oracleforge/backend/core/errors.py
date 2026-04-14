"""MAXIA Oracle — safe error formatting.

Hardening applied for V12 audit vulnerability H12 ("`str(e)` returned to clients
in 40+ files"): in MAXIA V12, many endpoints interpolated raw exception strings
into responses, leaking file paths, SQL table names, internal IPs and library
versions to the attacker. This module provides a single utility used across
the extracted oracle modules to prevent that.

Design rules:
    1. The client-safe message is short, generic, and never includes the
       exception's `str()` representation.
    2. The full exception (type, message, traceback) is still logged to the
       server-side logger so operators can debug.
    3. Each call site passes a `context` string that is safe to return to
       clients (constant, not interpolated with untrusted data).

Usage:
    from core.errors import safe_error

    try:
        ...
    except Exception as exc:
        return {"error": safe_error("Pyth Hermes fetch failed", exc, logger)}
"""
from __future__ import annotations

import logging
from typing import Final


DEFAULT_CLIENT_MESSAGE: Final[str] = "internal error"


def safe_error(
    context: str,
    exc: BaseException,
    logger: logging.Logger | None = None,
    *,
    level: int = logging.ERROR,
) -> str:
    """Return a client-safe error string while logging the full exception server-side.

    Args:
        context: A short, constant, client-safe description of what failed.
                 MUST NOT be built from untrusted data. Examples:
                 "Pyth Hermes fetch failed", "Chainlink eth_call failed".
        exc: The exception caught at the call site.
        logger: Optional logger to use for the server-side log line. If None,
                the exception is logged to the root logger.
        level: Logging level for the server-side log line (default ERROR).

    Returns:
        A string safe to embed in a client response. Contains only the
        `context` and the exception type name — NEVER the exception message,
        stack trace, or any value that could leak server-side state.
    """
    log = logger or logging.getLogger()
    # exc_info=True captures the full traceback in the server log only.
    log.log(level, "%s: %s", context, type(exc).__name__, exc_info=True)
    return f"{context} ({type(exc).__name__})"
