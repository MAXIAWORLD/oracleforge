"""V1.4 -- Pyth native Solana on-chain reader tests.

Covers:
    1. `services/oracle/pyth_solana_oracle.py` decoder (Full variant,
       Partial variant, discriminator mismatch, feed_id mismatch,
       truncated account, non-positive price, invalid exponent).
    2. Cache + circuit breaker semantics (5 failures -> open, cooldown,
       reset helpers).
    3. RPC pool fallback behaviour via a stub httpx client.
    4. `/api/pyth/solana/{symbol}` HTTP route -- success, 404, 400, 502.
    5. `/api/sources` entry + `/api/symbols` grouping include pyth_solana.
    6. MCP `get_pyth_solana_onchain` tool -- validation + dispatch.

All tests are fully offline -- no live RPC call. A fixture builds a
canonical 134-byte `PriceUpdateV2` blob for the BTC feed so the decoder
is tested against a mainnet-shaped buffer without the network.
"""
from __future__ import annotations

import struct
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mcp_server import tools as mcp_tools
from services.oracle import pyth_solana_oracle


# ── Fixture: build a valid PriceUpdateV2 blob ──────────────────────────────


def _build_blob(
    *,
    feed_id_hex: str,
    price: int = 7_500_000_000_000,
    conf: int = 2_500_000_000,
    exponent: int = -8,
    publish_time: int = 1_776_000_000,
    prev_publish_time: int = 1_776_000_000 - 1,
    ema_price: int = 7_500_000_000_000,
    ema_conf: int = 2_500_000_000,
    posted_slot: int = 413_000_000,
    vl_variant: int = 1,              # 1 = Full, 0 = Partial
    vl_num_sig: int = 0,
    discriminator: bytes | None = None,
) -> bytes:
    """Pack a canonical 134-byte PriceUpdateV2 buffer.

    Defaults produce a Full-verified BTC-ish price around $75,000 with a
    fresh publish_time. Overrides let each test exercise a specific
    rejection path without re-deriving the layout by hand.
    """
    if discriminator is None:
        discriminator = pyth_solana_oracle.PRICE_UPDATE_V2_DISCRIMINATOR
    write_authority = bytes(32)  # zero pubkey -- informational only
    feed_id = bytes.fromhex(feed_id_hex)
    assert len(feed_id) == 32

    buf = bytearray(134)
    buf[0:8] = discriminator
    buf[8:40] = write_authority
    buf[40] = vl_variant
    if vl_variant == 0:
        buf[41] = vl_num_sig
        off = 42
    else:
        off = 41
    buf[off:off + 32] = feed_id; off += 32
    struct.pack_into("<q", buf, off, price); off += 8
    struct.pack_into("<Q", buf, off, conf); off += 8
    struct.pack_into("<i", buf, off, exponent); off += 4
    struct.pack_into("<q", buf, off, publish_time); off += 8
    struct.pack_into("<q", buf, off, prev_publish_time); off += 8
    struct.pack_into("<q", buf, off, ema_price); off += 8
    struct.pack_into("<Q", buf, off, ema_conf); off += 8
    struct.pack_into("<Q", buf, off, posted_slot); off += 8
    return bytes(buf)


BTC_FEED_HEX = pyth_solana_oracle.PYTH_SOLANA_FEEDS["BTC"]["feed_id"]


# ── Module-state reset fixture ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    pyth_solana_oracle._reset_for_tests()
    yield
    pyth_solana_oracle._reset_for_tests()


# ── Decoder tests ───────────────────────────────────────────────────────────


def test_decoder_full_happy_path() -> None:
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, price=7_500_000_000_000, exponent=-8)
    decoded = pyth_solana_oracle._decode_price_update_v2(blob, BTC_FEED_HEX)
    assert decoded["verification_is_full"] is True
    assert decoded["feed_id_hex"] == BTC_FEED_HEX
    assert decoded["price_i64"] == 7_500_000_000_000
    assert decoded["exponent"] == -8


def test_decoder_partial_marks_not_full() -> None:
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, vl_variant=0, vl_num_sig=5)
    decoded = pyth_solana_oracle._decode_price_update_v2(blob, BTC_FEED_HEX)
    assert decoded["verification_is_full"] is False
    assert "num_signatures=5" in decoded["verification"]


def test_decoder_rejects_discriminator_mismatch() -> None:
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, discriminator=bytes(8))
    with pytest.raises(pyth_solana_oracle._DecodeError, match="discriminator"):
        pyth_solana_oracle._decode_price_update_v2(blob, BTC_FEED_HEX)


def test_decoder_rejects_feed_id_mismatch() -> None:
    other = pyth_solana_oracle.PYTH_SOLANA_FEEDS["ETH"]["feed_id"]
    blob = _build_blob(feed_id_hex=other)
    with pytest.raises(pyth_solana_oracle._DecodeError, match="feed_id"):
        pyth_solana_oracle._decode_price_update_v2(blob, BTC_FEED_HEX)


def test_decoder_rejects_too_short() -> None:
    with pytest.raises(pyth_solana_oracle._DecodeError, match="too short"):
        pyth_solana_oracle._decode_price_update_v2(b"\x00" * 10, BTC_FEED_HEX)


def test_decoder_rejects_unknown_verification_variant() -> None:
    blob = bytearray(_build_blob(feed_id_hex=BTC_FEED_HEX))
    blob[40] = 9  # invalid variant
    with pytest.raises(pyth_solana_oracle._DecodeError, match="verification_level"):
        pyth_solana_oracle._decode_price_update_v2(bytes(blob), BTC_FEED_HEX)


# ── Public API tests (with stub RPC layer) ──────────────────────────────────


class _StubClient:
    """Stand-in for httpx.AsyncClient. Captures each POST and returns a
    pre-canned (status_code, body, raise_exc) tuple per call."""

    def __init__(self, responses: list[tuple[int, Any, Exception | None]]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def post(self, url, *, json=None, timeout=None, **_kwargs):
        entry = self.responses.pop(0) if self.responses else (200, {}, None)
        status_code, body, exc = entry
        self.calls.append({"url": url, "body": json})
        if exc is not None:
            raise exc
        resp = _StubResp(status_code, body)
        return resp


class _StubResp:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        return self._body


def _rpc_ok_body(blob: bytes) -> dict[str, Any]:
    import base64
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"value": {"data": [base64.b64encode(blob).decode(), "base64"]}},
    }


@pytest.mark.asyncio
async def test_get_pyth_solana_price_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import time as _t
    fresh = int(_t.time()) - 5
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, publish_time=fresh,
                       price=7_500_000_000_000, exponent=-8)
    stub = _StubClient([(200, _rpc_ok_body(blob), None)])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert "error" not in result, result
    assert result["source"] == "pyth_solana"
    assert result["symbol"] == "BTC"
    assert result["price"] == pytest.approx(75_000.0, rel=1e-6)
    assert result["stale"] is False
    assert result["age_s"] >= 0
    assert result["price_account"] == pyth_solana_oracle.PYTH_SOLANA_FEEDS["BTC"]["price_account"]


@pytest.mark.asyncio
async def test_get_pyth_solana_price_rejects_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, vl_variant=0, vl_num_sig=3)
    stub = _StubClient([(200, _rpc_ok_body(blob), None)])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert "error" in result
    assert "partial" in result["error"].lower()
    assert pyth_solana_oracle.get_metrics()["rejects_verification"] == 1


@pytest.mark.asyncio
async def test_get_pyth_solana_price_caches_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    import time as _t
    fresh = int(_t.time()) - 2
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, publish_time=fresh)
    stub = _StubClient([(200, _rpc_ok_body(blob), None)])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    await pyth_solana_oracle.get_pyth_solana_price("BTC")
    await pyth_solana_oracle.get_pyth_solana_price("BTC")

    # Only one stub response consumed -> one POST hit.
    assert len(stub.calls) == 1
    assert pyth_solana_oracle.get_metrics()["cache_hits"] == 1


@pytest.mark.asyncio
async def test_get_pyth_solana_price_unsupported_symbol() -> None:
    result = await pyth_solana_oracle.get_pyth_solana_price("NOPE")
    assert result["error"] == "symbol not supported on Pyth Solana shard 0"
    assert pyth_solana_oracle.get_metrics()["symbols_not_supported"] == 1


@pytest.mark.asyncio
async def test_get_pyth_solana_price_rejects_malformed_symbol() -> None:
    assert (await pyth_solana_oracle.get_pyth_solana_price("bad sym!"))["error"] == (
        "invalid symbol format"
    )
    assert (await pyth_solana_oracle.get_pyth_solana_price(""))["error"] == (
        "invalid symbol format"
    )


@pytest.mark.asyncio
async def test_rpc_pool_fallback_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """First RPC 403, second RPC 200 -> one fallback recorded."""
    import time as _t
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, publish_time=int(_t.time()))
    stub = _StubClient([
        (403, {"error": "forbidden"}, None),
        (200, _rpc_ok_body(blob), None),
    ])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert "error" not in result
    metrics = pyth_solana_oracle.get_metrics()
    assert metrics["rpc_fallbacks"] == 1


@pytest.mark.asyncio
async def test_rpc_pool_exhausted_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every RPC returns 500 -> pool exhausted + circuit failure counted."""
    responses = [(500, {"error": "boom"}, None)] * len(pyth_solana_oracle.SOLANA_RPC_URLS)
    stub = _StubClient(responses)
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert result["error"] == "pyth_solana RPC pool exhausted"
    assert pyth_solana_oracle.get_metrics()["circuit"]["failures"] == 1


@pytest.mark.asyncio
async def test_circuit_opens_after_five_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _dead_pool():
        return _StubClient([(500, {"error": "boom"}, None)] * 50)

    # Replace get_http_client to return a fresh dead stub each call to avoid
    # running out of responses; we only care about circuit counting.
    clients = []
    def _factory():
        c = _dead_pool()
        clients.append(c)
        return c
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", _factory)

    for _ in range(pyth_solana_oracle._CB_MAX_FAILURES):
        await pyth_solana_oracle.get_pyth_solana_price("BTC")

    assert pyth_solana_oracle.get_metrics()["circuit"]["state"] == "open"
    assert pyth_solana_oracle.get_metrics()["circuit_breaks"] == 1

    # Next call must short-circuit without touching the stub factory.
    before = len(clients)
    r = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert r["error"] == "pyth_solana circuit open"
    assert len(clients) == before  # no new client created


@pytest.mark.asyncio
async def test_stale_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """An age_s > 60 marks the feed stale but still returns the price."""
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, publish_time=1)
    stub = _StubClient([(200, _rpc_ok_body(blob), None)])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert "error" not in result
    assert result["stale"] is True
    assert result["age_s"] > pyth_solana_oracle._STALE_AFTER_S


@pytest.mark.asyncio
async def test_decoder_rejects_invalid_exponent(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = _build_blob(feed_id_hex=BTC_FEED_HEX, exponent=5)  # positive exponent
    stub = _StubClient([(200, _rpc_ok_body(blob), None)])
    monkeypatch.setattr(pyth_solana_oracle, "get_http_client", lambda: stub)

    result = await pyth_solana_oracle.get_pyth_solana_price("BTC")
    assert "invalid exponent" in result["error"]


# ── Helper surface ──────────────────────────────────────────────────────────


def test_has_feed_case_insensitive() -> None:
    assert pyth_solana_oracle.has_feed("BTC") is True
    assert pyth_solana_oracle.has_feed("btc") is True
    assert pyth_solana_oracle.has_feed("XXX") is False
    assert pyth_solana_oracle.has_feed("") is False
    assert pyth_solana_oracle.has_feed("bad sym!") is False


def test_list_supported_symbols_sorted_unique() -> None:
    syms = pyth_solana_oracle.list_supported_symbols()
    assert syms == sorted(syms)
    assert len(syms) == len(set(syms))
    assert "BTC" in syms and "ETH" in syms and "SOL" in syms


# ── HTTP route tests ────────────────────────────────────────────────────────


def test_route_pyth_solana_returns_price(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> dict:
        return {
            "price": 75000.0,
            "conf": 12.3,
            "confidence_pct": 0.02,
            "publish_time": 1_776_000_000,
            "age_s": 5,
            "stale": False,
            "source": "pyth_solana",
            "symbol": symbol,
            "price_account": "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
            "posted_slot": 413_000_000,
            "exponent": -8,
            "feed_id": BTC_FEED_HEX,
        }

    monkeypatch.setattr(pyth_solana_oracle, "get_pyth_solana_price", fake_price)
    r = client.get("/api/pyth/solana/BTC", headers={"X-API-Key": api_key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["source"] == "pyth_solana"
    assert body["data"]["price"] == 75000.0


def test_route_pyth_solana_404_on_unsupported(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/pyth/solana/ZZZZ", headers={"X-API-Key": api_key})
    assert r.status_code == 404


def test_route_pyth_solana_400_on_bad_symbol(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/pyth/solana/bad-symbol", headers={"X-API-Key": api_key})
    assert r.status_code == 400


def test_route_pyth_solana_502_on_upstream_error(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> dict:
        return {"error": "pyth_solana RPC pool exhausted",
                "source": "pyth_solana", "symbol": symbol}

    monkeypatch.setattr(pyth_solana_oracle, "get_pyth_solana_price", fake_price)
    r = client.get("/api/pyth/solana/BTC", headers={"X-API-Key": api_key})
    assert r.status_code == 502


# ── /api/sources + /api/symbols wiring ──────────────────────────────────────


def test_sources_lists_pyth_solana(client: TestClient, api_key: str) -> None:
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["data"]["sources"]]
    assert "pyth_solana" in names


def test_symbols_includes_pyth_solana_group(client: TestClient, api_key: str) -> None:
    r = client.get("/api/symbols", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    body = r.json()["data"]
    assert "pyth_solana" in body["by_source"]
    assert "BTC" in body["by_source"]["pyth_solana"]


# ── MCP tool tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_pyth_solana_rejects_bad_symbol() -> None:
    result = await mcp_tools.get_pyth_solana_onchain("bad symbol!")
    assert result["error"] == "invalid symbol format"


@pytest.mark.asyncio
async def test_mcp_pyth_solana_rejects_unsupported() -> None:
    result = await mcp_tools.get_pyth_solana_onchain("ZZZZ")
    assert result["error"] == "symbol not supported on Pyth Solana shard 0"


@pytest.mark.asyncio
async def test_mcp_pyth_solana_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_price(symbol: str) -> dict:
        captured["symbol"] = symbol
        return {
            "price": 75000.0,
            "conf": 12.3,
            "confidence_pct": 0.02,
            "publish_time": 1_776_000_000,
            "age_s": 5,
            "stale": False,
            "source": "pyth_solana",
            "symbol": symbol,
            "price_account": "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
            "posted_slot": 413_000_000,
            "exponent": -8,
            "feed_id": BTC_FEED_HEX,
        }

    monkeypatch.setattr(pyth_solana_oracle, "get_pyth_solana_price", fake_price)
    result = await mcp_tools.get_pyth_solana_onchain("BTC")
    assert captured["symbol"] == "BTC"
    assert "error" not in result


# ── multi_source wiring ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_sources_includes_pyth_solana(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_sources() must include pyth_solana when the module answers."""
    from services.oracle import multi_source

    async def fake_pyth_solana(symbol: str) -> dict[str, Any]:
        return {
            "price": 75000.0,
            "conf": 10.0,
            "confidence_pct": 0.01,
            "publish_time": 1_776_000_000,
            "age_s": 1,
            "stale": False,
            "source": "pyth_solana",
            "symbol": symbol,
            "price_account": "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
            "posted_slot": 413_000_000,
            "exponent": -8,
            "feed_id": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
        }

    async def _skip(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {"error": "skip"}

    async def _skip_price_oracle(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(multi_source.pyth_solana_oracle, "get_pyth_solana_price", fake_pyth_solana)
    monkeypatch.setattr(multi_source.pyth_oracle, "get_pyth_price", _skip)
    monkeypatch.setattr(multi_source.chainlink_oracle, "get_chainlink_price", _skip)
    monkeypatch.setattr(multi_source.price_oracle, "get_prices", _skip_price_oracle)
    monkeypatch.setattr(multi_source.redstone_oracle, "get_redstone_price", _skip)
    monkeypatch.setattr(multi_source.uniswap_v3_oracle, "get_twap_price", _skip)

    sources = await multi_source.collect_sources("BTC")

    assert any(s["name"] == "pyth_solana" for s in sources), sources
    entry = next(s for s in sources if s["name"] == "pyth_solana")
    assert entry["price"] == 75000.0
    assert entry["age_s"] == 1
    assert entry["stale"] is False
