"""MAXIA Oracle — shared async HTTP client singleton (Phase 4 / Step 5).

Before Step 5, each of the 3 oracle services (`pyth_oracle`, `chainlink_oracle`,
`price_oracle`) and the new `x402/base_verifier` maintained its own
`httpx.AsyncClient` singleton with slightly different limits. That wasted
sockets (4 separate keepalive pools), made shutdown ordering fragile, and
duplicated ~30 lines of identical boilerplate per module.

This module centralizes the shared client. It is imported lazily by each
service so the client is only materialized on the first outbound call.
The FastAPI lifespan calls `close_http_client()` on shutdown, so the pool
is cleanly released.

Design notes:
    - `max_connections=30` covers the worst-case fan-out: 3 oracle sources
      running concurrently for a batch of up to 50 symbols + x402 facilitator
      + base RPC fallback pool.
    - `max_keepalive_connections=15` keeps half the pool hot between calls
      so the cost of TCP + TLS handshake is amortized across the first
      few requests.
    - Default timeout is 15 s read / 5 s connect; callers that need a
      different timeout pass it explicitly in the `request()` call.
"""
from __future__ import annotations

import logging
from typing import Final

import httpx

logger = logging.getLogger("maxia_oracle.http_client")


_DEFAULT_TIMEOUT: Final[httpx.Timeout] = httpx.Timeout(15.0, connect=5.0)
_DEFAULT_LIMITS: Final[httpx.Limits] = httpx.Limits(
    max_connections=30,
    max_keepalive_connections=15,
)


_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client, creating it if necessary.

    The client is created on first call and reused across the lifetime of
    the FastAPI process. Concurrent callers receive the same instance.
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            limits=_DEFAULT_LIMITS,
            follow_redirects=True,
        )
        logger.debug("Created shared AsyncClient")
    return _client


async def close_http_client() -> None:
    """Close the shared async HTTP client — call from FastAPI shutdown lifespan."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Shared AsyncClient closed")
    _client = None
