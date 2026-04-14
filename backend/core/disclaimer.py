"""MAXIA Oracle — mandatory response disclaimer (Phase 3).

Every API response MUST carry the disclaimer below. The product scope rule
from CLAUDE.md ("no regulated business") relies on MAXIA Oracle being
presented strictly as a data feed, never as investment advice or custody.
Forgetting the disclaimer on one endpoint undermines the whole position.

Usage:
    from core.disclaimer import wrap_with_disclaimer, wrap_error

    @router.get("/example")
    def example():
        return wrap_with_disclaimer({"symbol": "BTC", "price": 74287.07})

    @router.get("/example_error")
    def example_error():
        return wrap_error("symbol not found", symbol="BOGUS")

Why a helper instead of a middleware:
    A middleware that rewrites every JSONResponse is magic that surprises
    future maintainers. An explicit helper on every route is obvious in code
    review and trivially greppable. See Phase 3 architecture decision #6.
"""
from __future__ import annotations

from typing import Any, Final

DISCLAIMER_TEXT: Final[str] = (
    "Data feed only. Not investment advice. No custody. No KYC."
)


def wrap_with_disclaimer(data: Any) -> dict[str, Any]:
    """Wrap a successful response payload as {"data": ..., "disclaimer": ...}."""
    return {"data": data, "disclaimer": DISCLAIMER_TEXT}


def wrap_error(error: str, **extra: Any) -> dict[str, Any]:
    """Wrap an error response as {"error": ..., <extras>, "disclaimer": ...}.

    Extras are merged at the top level, not nested under `error`, so clients
    can read e.g. `response["retry_after"]` directly.
    """
    payload: dict[str, Any] = {"error": error}
    payload.update(extra)
    payload["disclaimer"] = DISCLAIMER_TEXT
    return payload
