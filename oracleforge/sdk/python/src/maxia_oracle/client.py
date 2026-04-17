"""MAXIA Oracle SDK — synchronous HTTP client for the REST API.

Usage:

    from maxia_oracle import MaxiaOracleClient

    with MaxiaOracleClient(api_key="mxo_your_key") as client:
        btc = client.price("BTC")
        print(btc["data"]["price"])

If you do not yet have a key, call `register()` on a keyless client first:

    with MaxiaOracleClient() as client:
        registered = client.register()
        key = registered["data"]["api_key"]

Every successful response is the parsed JSON dict as returned by the
backend, including the mandatory `disclaimer` field. Errors are raised as
typed exceptions from `maxia_oracle.exceptions`.

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

import os
from types import TracebackType
from typing import Any, Final

import httpx

from .exceptions import (
    MaxiaOracleAuthError,
    MaxiaOraclePaymentRequiredError,
    MaxiaOracleRateLimitError,
    MaxiaOracleTransportError,
    MaxiaOracleUpstreamError,
    MaxiaOracleValidationError,
)

DEFAULT_BASE_URL: Final[str] = "https://oracle.maxiaworld.app"
DEFAULT_TIMEOUT_S: Final[float] = 15.0
USER_AGENT: Final[str] = "maxia-oracle-python/0.4.0"


class MaxiaOracleClient:
    """Synchronous client for the MAXIA Oracle REST API.

    Implements 9 methods aligned with the 8 MCP tools exposed by the
    MAXIA Oracle server (phase 5) plus `register()`:

        - `register()`              → POST /api/register
        - `health()`                → GET  /health
        - `price(symbol)`           → GET  /api/price/{symbol}
        - `prices_batch(symbols)`   → POST /api/prices/batch
        - `sources()`               → GET  /api/sources
        - `cache_stats()`           → GET  /api/cache/stats
        - `list_symbols()`          → GET  /api/symbols
        - `chainlink_onchain(sym)`  → GET  /api/chainlink/{symbol}
        - `confidence(symbol)`      → GET  /api/price/{symbol} (divergence extract)

    `register()` and `health()` are the only methods that work without a
    key — the rest require a `mxo_`-prefixed key supplied either at
    construction time, via the `MAXIA_ORACLE_API_KEY` environment
    variable, or loaded from a freshly registered session.

    Data feed only. Not investment advice. No custody. No KYC.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("MAXIA_ORACLE_API_KEY")
        self._base_url = (base_url or os.environ.get("MAXIA_ORACLE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=transport,
        )

    # ── Context manager ─────────────────────────────────────────────────────

    def __enter__(self) -> "MaxiaOracleClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # ── Public API ──────────────────────────────────────────────────────────

    def register(self) -> dict[str, Any]:
        """Register a fresh free-tier API key.

        Returns the parsed response dict. The raw key is in
        `response["data"]["api_key"]` — it is returned exactly once, store
        it immediately. The daily quota is in `response["data"]["daily_limit"]`.

        Note: this endpoint is IP-throttled to one registration per minute.
        """
        return self._request("POST", "/api/register", auth=False)

    def health(self) -> dict[str, Any]:
        """Lightweight liveness probe. No authentication required.

        Returns the parsed dict containing `data.status`, `data.env`,
        `data.uptime_s` and the disclaimer.
        """
        return self._request("GET", "/health", auth=False)

    def price(self, symbol: str) -> dict[str, Any]:
        """Return a cross-validated multi-source live price for one asset.

        The response shape mirrors the MCP `get_price` tool: a median price,
        the per-source breakdown, the source count, and the divergence in
        percent across sources.

        Raises:
            MaxiaOracleValidationError: symbol does not match the format.
            MaxiaOracleUpstreamError: every upstream source failed.
            MaxiaOracleAuthError: missing or invalid API key.
            MaxiaOracleRateLimitError: daily quota exhausted.
        """
        symbol = self._validate_symbol(symbol)
        return self._request("GET", f"/api/price/{symbol}")

    def prices_batch(self, symbols: list[str]) -> dict[str, Any]:
        """Return live prices for up to 50 symbols in a single upstream call.

        Uses the Pyth Hermes batch endpoint. Dramatically cheaper than
        N × `price()`. Maximum 50 symbols per call.

        Raises:
            MaxiaOracleValidationError: non-list, empty list, over 50, or
                any symbol fails the format check.
        """
        if not isinstance(symbols, list):
            raise MaxiaOracleValidationError("symbols must be a list of strings")
        if not symbols:
            raise MaxiaOracleValidationError("symbols must contain at least one entry")
        if len(symbols) > 50:
            raise MaxiaOracleValidationError(
                f"batch size exceeds 50 (got {len(symbols)})"
            )
        cleaned = [self._validate_symbol(s) for s in symbols]
        return self._request("POST", "/api/prices/batch", json={"symbols": cleaned})

    def sources(self) -> dict[str, Any]:
        """List every configured upstream oracle source and its current status.

        Returns the parsed dict containing `data.sources` — a list of
        named source objects with their liveness, last-good-read
        timestamp, and base URL.
        """
        return self._request("GET", "/api/sources")

    def cache_stats(self) -> dict[str, Any]:
        """Return the aggregator in-memory cache hit-rate and circuit-breaker state.

        Debug-oriented tool: lets an agent introspect its own latency
        amplification by checking how often reads hit the cache vs how
        often they punch through to the upstream sources.
        """
        return self._request("GET", "/api/cache/stats")

    def list_symbols(self) -> dict[str, Any]:
        """Return the union of supported asset symbols, grouped by upstream source.

        Response shape mirrors the MCP `list_supported_symbols` tool:
        `data.total_symbols`, `data.all_symbols` (flat sorted list), and
        `data.by_source` (pyth_crypto, pyth_equity, chainlink_base,
        price_oracle). No upstream calls — cheap metadata read.
        """
        return self._request("GET", "/api/symbols")

    def chainlink_onchain(
        self, symbol: str, chain: str = "base"
    ) -> dict[str, Any]:
        """Return a single-source price directly from a Chainlink on-chain feed.

        V1.1: accepts `chain` = `"base"` (default), `"ethereum"`, or
        `"arbitrum"`. Forces the on-chain single-source path (bypasses
        Pyth and the aggregator). Useful for audit or for cross-checking
        the median returned by `price()`, or to read the same value a
        smart contract on the requested chain will see.

        Supported symbols per chain are in
        `list_symbols()["data"]["by_source"]["chainlink_<chain>"]`.

        Raises:
            MaxiaOracleValidationError: symbol format invalid, chain not
                in {base, ethereum, arbitrum}, or symbol not supported on
                the requested chain.
        """
        symbol = self._validate_symbol(symbol)
        chain = self._validate_chain(chain)
        return self._request(
            "GET", f"/api/chainlink/{symbol}", params={"chain": chain}
        )

    def redstone(self, symbol: str) -> dict[str, Any]:
        """V1.3 — Single-source RedStone REST price.

        RedStone is the 4th independent upstream in MAXIA Oracle. Coverage
        is dynamic (400+ assets: crypto majors, long-tail, forex,
        equities). Unknown symbols raise
        :class:`MaxiaOracleUpstreamError` (404) rather than being
        pre-rejected on a hardcoded allow-list.

        Raises:
            MaxiaOracleValidationError: symbol format invalid.
            MaxiaOracleUpstreamError: symbol not available on RedStone.
        """
        symbol = self._validate_symbol(symbol)
        return self._request("GET", f"/api/redstone/{symbol}")

    def twap(
        self,
        symbol: str,
        chain: str = "ethereum",
        window_s: int = 1800,
    ) -> dict[str, Any]:
        """V1.5 — Uniswap v3 time-weighted average price (TWAP) on-chain.

        Reads a curated high-liquidity Uniswap v3 pool on ``chain``
        (``"base"`` or ``"ethereum"``) and returns the TWAP computed
        from ``observe(uint32[])`` over ``window_s`` seconds. Default
        window is 30 minutes; range is [60, 86400].

        Coverage: ETH on base + ethereum, BTC on ethereum. Extending
        the list requires a server-side audit -- see
        ``docs/v1.5_uniswap_twap.md``.

        Response (inside ``data``): ``price``, ``avg_tick``, ``window_s``,
        ``tick_cumulatives``, ``chain``, ``pool``, ``fee_bps``,
        ``token0``, ``token1``, ``source``, ``symbol``.

        Raises:
            MaxiaOracleValidationError: symbol format, chain not in
                {"base", "ethereum"}, or window_s out of range.
            MaxiaOracleUpstreamError: pair not configured on that chain
                or upstream unreachable.
        """
        symbol = self._validate_symbol(symbol)
        chain = self._validate_twap_chain(chain)
        self._validate_twap_window(window_s)
        return self._request(
            "GET",
            f"/api/twap/{symbol}",
            params={"chain": chain, "window": window_s},
        )

    def pyth_solana(self, symbol: str) -> dict[str, Any]:
        """V1.4 — Single-source Pyth on-chain read (Solana mainnet).

        Returns the Pyth Price Feed Account value for `symbol` on shard 0
        of the Pyth Push Oracle program. Coverage is a curated list of
        majors (BTC, ETH, SOL, USDT, USDC, WIF, BONK, PYTH, JTO, JUP,
        RAY, EUR, GBP). Anything else raises
        :class:`MaxiaOracleValidationError` (404 surfaced as 400 after
        server-side rejection) or :class:`MaxiaOracleUpstreamError`.

        The reader rejects partial Wormhole verifications, so the caller
        always receives a Full-verified update or an error.

        Response shape (inside `data`): ``price``, ``conf``,
        ``confidence_pct``, ``publish_time``, ``age_s``, ``stale``,
        ``source``, ``symbol``, ``price_account``, ``posted_slot``,
        ``exponent``, ``feed_id``.

        Raises:
            MaxiaOracleValidationError: symbol format invalid.
            MaxiaOracleUpstreamError: symbol unsupported on shard 0 or
                RPC pool exhausted.
        """
        symbol = self._validate_symbol(symbol)
        return self._request("GET", f"/api/pyth/solana/{symbol}")

    def confidence(self, symbol: str) -> dict[str, Any]:
        """Return the multi-source divergence for a symbol, compact.

        Helper built on top of `price()`. Returns the symbol, the source
        count and the divergence in percent — not the individual per-source
        quotes. Use this when all you need is "do the sources agree?",
        not the full price breakdown.
        """
        full = self.price(symbol)
        data = full.get("data", {})
        return {
            "data": {
                "symbol": data.get("symbol", symbol),
                "source_count": data.get("source_count"),
                "divergence_pct": data.get("divergence_pct"),
            },
            "disclaimer": full.get("disclaimer", ""),
        }

    # ── Internals ───────────────────────────────────────────────────────────

    _SYMBOL_MAX_LEN = 10
    _SUPPORTED_CHAINS: Final[frozenset[str]] = frozenset(
        {"base", "ethereum", "arbitrum"}
    )
    _TWAP_SUPPORTED_CHAINS: Final[frozenset[str]] = frozenset(
        {"base", "ethereum"}
    )
    _TWAP_MIN_WINDOW_S: Final[int] = 60
    _TWAP_MAX_WINDOW_S: Final[int] = 86400

    def _validate_chain(self, chain: str) -> str:
        if not isinstance(chain, str):
            raise MaxiaOracleValidationError("chain must be a string")
        cleaned = chain.strip().lower()
        if cleaned not in self._SUPPORTED_CHAINS:
            raise MaxiaOracleValidationError(
                f"chain must be one of {sorted(self._SUPPORTED_CHAINS)}, got {chain!r}"
            )
        return cleaned

    def _validate_twap_chain(self, chain: str) -> str:
        if not isinstance(chain, str):
            raise MaxiaOracleValidationError("chain must be a string")
        cleaned = chain.strip().lower()
        if cleaned not in self._TWAP_SUPPORTED_CHAINS:
            raise MaxiaOracleValidationError(
                f"chain must be one of {sorted(self._TWAP_SUPPORTED_CHAINS)} for twap(), "
                f"got {chain!r}"
            )
        return cleaned

    def _validate_twap_window(self, window_s: int) -> int:
        if not isinstance(window_s, int) or isinstance(window_s, bool):
            raise MaxiaOracleValidationError("window_s must be an integer")
        if window_s < self._TWAP_MIN_WINDOW_S or window_s > self._TWAP_MAX_WINDOW_S:
            raise MaxiaOracleValidationError(
                f"window_s must be within "
                f"[{self._TWAP_MIN_WINDOW_S}, {self._TWAP_MAX_WINDOW_S}], "
                f"got {window_s}"
            )
        return window_s

    def _validate_symbol(self, symbol: str) -> str:
        if not isinstance(symbol, str):
            raise MaxiaOracleValidationError("symbol must be a string")
        cleaned = symbol.strip().upper()
        if not cleaned:
            raise MaxiaOracleValidationError("symbol must not be empty")
        if len(cleaned) > self._SYMBOL_MAX_LEN:
            raise MaxiaOracleValidationError(
                f"symbol must be at most {self._SYMBOL_MAX_LEN} characters"
            )
        if not cleaned.replace("_", "").isalnum():
            raise MaxiaOracleValidationError(
                "symbol must match ^[A-Z0-9]{1,10}$"
            )
        for char in cleaned:
            if not (char.isdigit() or ("A" <= char <= "Z")):
                raise MaxiaOracleValidationError(
                    "symbol must match ^[A-Z0-9]{1,10}$"
                )
        return cleaned

    def _build_headers(self, auth: bool) -> dict[str, str]:
        headers: dict[str, str] = {}
        if auth:
            if not self._api_key:
                raise MaxiaOracleAuthError(
                    "API key required — pass api_key= or set MAXIA_ORACLE_API_KEY"
                )
            headers["X-API-Key"] = self._api_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(2):
            try:
                response = self._client.request(
                    method,
                    path,
                    headers=self._build_headers(auth),
                    json=json,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise MaxiaOracleTransportError(
                    f"transport error on {method} {path}: {exc}"
                ) from exc

            try:
                return self._handle_response(response, method=method, path=path)
            except MaxiaOracleRateLimitError:
                if attempt == 0 and response.status_code == 429:
                    wait = min(response.headers.get("retry-after", 1), 60)
                    import time as _time
                    _time.sleep(float(wait))
                    continue
                raise
        raise MaxiaOracleTransportError(f"exhausted retries on {method} {path}")

    def _handle_response(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
    ) -> dict[str, Any]:
        status = response.status_code

        try:
            body = response.json()
        except ValueError:
            raise MaxiaOracleTransportError(
                f"non-JSON response from {method} {path}: status={status}"
            )

        if status >= 200 and status < 300:
            return body

        # Error branches
        message = body.get("error") if isinstance(body, dict) else None
        message = message or f"HTTP {status}"

        if status == 401:
            raise MaxiaOracleAuthError(message)
        if status == 402:
            raise MaxiaOraclePaymentRequiredError(
                message,
                accepts=body.get("accepts") if isinstance(body, dict) else None,
            )
        if status == 404:
            # Every 404 in the MAXIA Oracle REST surface corresponds to an
            # upstream-level "this symbol is not available here" answer:
            # `no live price available` (/api/price), `symbol has no
            # Chainlink feed on requested chain`, `symbol not found on
            # redstone`, `symbol not supported on Pyth Solana shard 0`.
            raise MaxiaOracleUpstreamError(message)
        if status == 400 or status == 422:
            raise MaxiaOracleValidationError(message)
        if status == 429:
            raise MaxiaOracleRateLimitError(
                message,
                retry_after_seconds=(
                    body.get("retry_after_seconds") if isinstance(body, dict) else None
                ),
                limit=body.get("limit") if isinstance(body, dict) else None,
            )
        raise MaxiaOracleTransportError(
            f"unexpected {status} on {method} {path}: {message}"
        )
