"""Phase 5 MCP server tests — discovery, handler round-trips, rate limit, auth.

Coverage targets (Phase 5 Step 7):
    - The 8 V1 tools are defined and match the dispatch table
    - Each tool has a well-formed JSON schema (type object, required list,
      strict additionalProperties)
    - The `build_server()` call_tool handler dispatches correctly and
      propagates tool-level errors as `isError=True`
    - Unknown tool names and argument-arity mismatches surface as
      `isError=True` instead of raising
    - `build_server(rate_limit_key_hash=...)` ticks the Phase 3 daily
      quota on each `tools/call` and refuses with `isError=True` once the
      quota is cramped
    - Stdio path (`build_server()` with no arg) never touches the quota
    - HTTP SSE endpoint `GET /mcp/sse` requires a valid `X-API-Key`

The full SSE streaming round-trip (initialize + tools/list + tools/call via
long-lived stream) is verified manually against a live uvicorn instance in
Step 6 smoke tests. Starlette TestClient + long-lived SSE has enough edge
cases that reproducing it in pytest would trade test reliability for
coverage we already have.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from mcp import types as mt


# ── Session-scoped FastAPI app with a fresh sqlite DB ────────────────────────


@pytest.fixture(scope="session")
def session_app(tmp_path_factory: pytest.TempPathFactory):
    """Import main.py once with a fresh DB path, mirror Phase 3/4 fixtures."""
    db_dir: Path = tmp_path_factory.mktemp("maxia_oracle_mcp_db")
    os.environ["DB_PATH"] = str(db_dir / "test.sqlite")
    import main  # noqa: PLC0415

    from core.db import init_db  # noqa: PLC0415

    init_db()
    return main.app


@pytest.fixture
def client(session_app) -> Iterator[TestClient]:
    """Truncate mutable tables between tests and hand a TestClient over."""
    from core.db import get_db  # noqa: PLC0415

    db = get_db()
    db.execute("DELETE FROM api_keys")
    db.execute("DELETE FROM rate_limit")
    db.execute("DELETE FROM register_limit")

    with TestClient(session_app) as c:
        yield c


@pytest.fixture
def api_key(client: TestClient) -> str:
    response = client.post("/api/register")
    assert response.status_code == 201, response.text
    return response.json()["data"]["api_key"]


# ── Helpers ─────────────────────────────────────────────────────────────────

_EXPECTED_TOOL_NAMES = {
    "get_price",
    "get_prices_batch",
    "get_sources_status",
    "get_cache_stats",
    "get_confidence",
    "list_supported_symbols",
    "get_chainlink_onchain",
    "get_redstone_price",
    "get_pyth_solana_onchain",
    "get_twap_onchain",
    "get_price_context",
    "get_asset_metadata",
    "health_check",
}


async def _call_handler(
    server: Any, name: str, arguments: dict[str, Any]
) -> mt.CallToolResult:
    """Invoke the server's registered call_tool handler and return the inner result."""
    handler = server.request_handlers[mt.CallToolRequest]
    req = mt.CallToolRequest(
        method="tools/call",
        params=mt.CallToolRequestParams(name=name, arguments=arguments),
    )
    result = await handler(req)
    return result.root


# ── Discovery ───────────────────────────────────────────────────────────────


def test_tool_definitions_has_expected_tools(session_app) -> None:
    """V1.0 shipped 8. V1.3 added get_redstone_price (9). V1.4 added
    get_pyth_solana_onchain (10). V1.5 adds get_twap_onchain (11).
    See docs/v1.5_uniswap_twap.md.
    """
    from mcp_server.server import _TOOL_DEFINITIONS  # noqa: PLC0415

    assert len(_TOOL_DEFINITIONS) == 13
    assert {t.name for t in _TOOL_DEFINITIONS} == _EXPECTED_TOOL_NAMES


def test_tool_definitions_match_dispatch_table(session_app) -> None:
    from mcp_server.server import _TOOL_DEFINITIONS, _TOOL_DISPATCH  # noqa: PLC0415

    defined = {t.name for t in _TOOL_DEFINITIONS}
    dispatched = set(_TOOL_DISPATCH.keys())
    assert defined == dispatched
    # Every dispatched entry must be an awaitable
    for name, handler in _TOOL_DISPATCH.items():
        assert asyncio.iscoroutinefunction(handler), f"{name} is not async"


def test_tool_schemas_are_strict_objects(session_app) -> None:
    from mcp_server.server import _TOOL_DEFINITIONS  # noqa: PLC0415

    for tool in _TOOL_DEFINITIONS:
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False, (
            f"{tool.name} schema should be strict"
        )
        assert "properties" in schema
        # Tools that take a symbol must expose a pattern-constrained schema
        if "symbol" in schema["properties"]:
            assert schema["properties"]["symbol"]["pattern"] == "^[A-Z0-9]{1,10}$"
            assert schema.get("required") == ["symbol"]


def test_server_instructions_include_disclaimer(session_app) -> None:
    from mcp_server.server import SERVER_INSTRUCTIONS  # noqa: PLC0415

    assert "Data feed only" in SERVER_INSTRUCTIONS
    assert "Not investment advice" in SERVER_INSTRUCTIONS
    assert "No custody" in SERVER_INSTRUCTIONS
    assert "No KYC" in SERVER_INSTRUCTIONS


def test_build_server_registers_handlers(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    assert server.name == "maxia-oracle"
    assert server.version == "0.1.7"
    assert mt.ListToolsRequest in server.request_handlers
    assert mt.CallToolRequest in server.request_handlers


# ── Handler round-trip on offline tools ─────────────────────────────────────


@pytest.mark.asyncio
async def test_call_health_check_returns_ok(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(server, "health_check", {})
    assert result.isError is False
    payload = json.loads(result.content[0].text)
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "maxia-oracle-mcp"
    assert "disclaimer" in payload


@pytest.mark.asyncio
async def test_call_list_supported_symbols(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(server, "list_supported_symbols", {})
    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["data"]["total_symbols"] > 0
    assert "pyth_crypto" in sc["data"]["by_source"]
    assert "BTC" in sc["data"]["all_symbols"]


@pytest.mark.asyncio
async def test_call_get_cache_stats(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(server, "get_cache_stats", {})
    assert result.isError is False
    payload = json.loads(result.content[0].text)
    assert "data" in payload
    assert "disclaimer" in payload


# ── Error paths ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_tool_returns_is_error(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(server, "nonexistent_tool", {})
    assert result.isError is True
    payload = json.loads(result.content[0].text)
    assert "unknown tool" in payload["error"]


@pytest.mark.asyncio
async def test_schema_validation_rejects_unknown_argument(session_app) -> None:
    """The SDK's built-in jsonschema validation rejects unknown args before
    our handler runs, because every tool schema uses
    `additionalProperties: False`. The SDK wraps the validation error as a
    plain-text `isError=True` result — not JSON — so we assert on the text.
    """
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(
        server, "health_check", {"unexpected_arg": "value"}
    )
    assert result.isError is True
    assert "Input validation error" in result.content[0].text


@pytest.mark.asyncio
async def test_schema_validation_rejects_missing_required(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    # get_price requires `symbol`
    result = await _call_handler(server, "get_price", {})
    assert result.isError is True
    assert "Input validation error" in result.content[0].text


@pytest.mark.asyncio
async def test_schema_validation_rejects_bad_symbol_pattern(session_app) -> None:
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    result = await _call_handler(server, "get_price", {"symbol": "btc_lower"})
    assert result.isError is True
    assert "Input validation error" in result.content[0].text


# ── Rate limit integration ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_ticks_on_tools_call(client: TestClient) -> None:
    """build_server(key_hash=...) must increment the daily counter per call."""
    from core.auth import hash_key  # noqa: PLC0415
    from core.db import get_db  # noqa: PLC0415
    from mcp_server.server import build_server  # noqa: PLC0415

    raw = "mxo_" + "a" * 40
    key_hash = hash_key(raw)

    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, 0, 'free', 1)",
        (key_hash,),
    )
    db.commit()

    server = build_server(rate_limit_key_hash=key_hash)

    for _ in range(3):
        result = await _call_handler(server, "health_check", {})
        assert result.isError is False

    row = db.execute(
        "SELECT count FROM rate_limit WHERE key_hash = ?", (key_hash,)
    ).fetchone()
    assert row is not None
    assert row["count"] == 3


@pytest.mark.asyncio
async def test_rate_limit_refuses_when_quota_exceeded(client: TestClient) -> None:
    from core.auth import hash_key  # noqa: PLC0415
    from core.db import get_db, now_unix  # noqa: PLC0415
    from core.rate_limit import DAILY_LIMIT, DAILY_WINDOW_S  # noqa: PLC0415
    from mcp_server.server import build_server  # noqa: PLC0415

    raw = "mxo_" + "b" * 40
    key_hash = hash_key(raw)

    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, 0, 'free', 1)",
        (key_hash,),
    )
    now = now_unix()
    window_start = (now // DAILY_WINDOW_S) * DAILY_WINDOW_S
    db.execute(
        "INSERT INTO rate_limit (key_hash, window_start, count) VALUES (?, ?, ?)",
        (key_hash, window_start, DAILY_LIMIT),
    )
    db.commit()

    server = build_server(rate_limit_key_hash=key_hash)
    result = await _call_handler(server, "health_check", {})

    assert result.isError is True
    payload = json.loads(result.content[0].text)
    assert payload["error"] == "rate limit exceeded"
    assert payload["limit"] == DAILY_LIMIT
    assert payload["window_s"] == DAILY_WINDOW_S
    assert payload["retry_after_s"] > 0
    assert payload["reset_at"] > now


@pytest.mark.asyncio
async def test_stdio_build_server_has_no_rate_limit(session_app) -> None:
    """Building without rate_limit_key_hash must never touch the DB quota."""
    from mcp_server.server import build_server  # noqa: PLC0415

    server = build_server()
    for _ in range(10):
        result = await _call_handler(server, "health_check", {})
        assert result.isError is False


# ── HTTP SSE auth (non-streaming asserts only) ──────────────────────────────


def test_mcp_sse_requires_api_key(client: TestClient) -> None:
    r = client.get("/mcp/sse")
    assert r.status_code == 401
    body = r.json()
    assert "missing X-API-Key" in body["error"]
    assert "disclaimer" in body
    assert r.headers.get("WWW-Authenticate", "").startswith("ApiKey")


def test_mcp_sse_rejects_invalid_key(client: TestClient) -> None:
    r = client.get("/mcp/sse", headers={"X-API-Key": "mxo_obviously_fake_key"})
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "invalid or inactive API key"


def test_mcp_sse_rejects_key_with_wrong_prefix(client: TestClient) -> None:
    r = client.get("/mcp/sse", headers={"X-API-Key": "sk-wrong-prefix-123"})
    assert r.status_code == 401
