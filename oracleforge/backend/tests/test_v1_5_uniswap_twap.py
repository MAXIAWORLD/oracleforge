"""V1.5 -- Uniswap v3 TWAP reader tests.

Covers:
    1. ABI encode/decode of observe() calldata + return tuple.
    2. The tick -> human_price math, both orientations (base_is_token0).
    3. Input validation: symbol / chain / window_s bounds.
    4. RPC pool fallback, circuit breaker, cache hit, pool revert.
    5. Route /api/twap/{symbol} -- 200, 400, 404, 502.
    6. /api/sources + /api/symbols include uniswap_v3 entry.
    7. MCP tool get_twap_onchain -- validation + dispatch.

All tests fully offline. A minimal stub of httpx.AsyncClient fulfills
the eth_call surface used by the module.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from mcp_server import tools as mcp_tools
from services.oracle import uniswap_v3_oracle


# ── Fixture: reset module state before every test ──────────────────────────


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    uniswap_v3_oracle._reset_for_tests()
    yield
    uniswap_v3_oracle._reset_for_tests()


# ── ABI encode ──────────────────────────────────────────────────────────────


def test_encode_observe_calldata_layout() -> None:
    data = uniswap_v3_oracle._encode_observe_calldata((1800, 0))
    # selector (4) + offset (32) + length (32) + two entries (32 each) = 132 bytes hex
    assert data.startswith(uniswap_v3_oracle.OBSERVE_SELECTOR)
    assert len(data) == 2 + 4 * 2 + 4 * 64
    # length word = 2
    length_hex = data[2 + 8 + 64: 2 + 8 + 64 * 2]
    assert int(length_hex, 16) == 2
    # first entry = 1800
    entry0 = data[2 + 8 + 64 * 2: 2 + 8 + 64 * 3]
    assert int(entry0, 16) == 1800


def test_encode_observe_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        uniswap_v3_oracle._encode_observe_calldata((2**33,))


# ── ABI decode ──────────────────────────────────────────────────────────────


def _build_observe_response(ticks: list[int], liqs: list[int]) -> str:
    """Assemble a Solidity ABI-encoded `(int56[],uint160[])` return blob."""
    head_len = 64  # two offsets, 32 bytes each
    arr1_off = head_len
    arr1_body_bytes = 32 + len(ticks) * 32
    arr2_off = arr1_off + arr1_body_bytes

    parts: list[bytes] = []
    parts.append(arr1_off.to_bytes(32, "big"))
    parts.append(arr2_off.to_bytes(32, "big"))
    parts.append(len(ticks).to_bytes(32, "big"))
    for t in ticks:
        parts.append(t.to_bytes(32, "big", signed=True))
    parts.append(len(liqs).to_bytes(32, "big"))
    for l in liqs:
        parts.append(l.to_bytes(32, "big", signed=False))
    return "0x" + b"".join(parts).hex()


def test_decode_observe_round_trip() -> None:
    ticks = [123456789, 123456999]
    liqs = [1, 2]
    blob = _build_observe_response(ticks, liqs)
    decoded_ticks, decoded_liqs = uniswap_v3_oracle._decode_observe_result(blob)
    assert decoded_ticks == ticks
    assert decoded_liqs == liqs


def test_decode_observe_negative_ticks() -> None:
    ticks = [-16237306335028, -16237664061038]
    blob = _build_observe_response(ticks, [0, 0])
    decoded_ticks, _ = uniswap_v3_oracle._decode_observe_result(blob)
    assert decoded_ticks == ticks


def test_decode_observe_rejects_short_payload() -> None:
    with pytest.raises(ValueError):
        uniswap_v3_oracle._decode_observe_result("0x" + "00" * 10)


# ── TWAP math ───────────────────────────────────────────────────────────────


def test_twap_price_eth_ethereum_usdc_weth() -> None:
    # Ethereum USDC/WETH pool: USDC is token0 (6 dec), WETH is token1 (18 dec).
    # base_is_token0=False means we price WETH. Reference avg_tick 198735
    # maps to ETH ~ $2341.
    tc = [30974752662779, 30975110386247]
    avg_tick, price = uniswap_v3_oracle._twap_price_from_ticks(
        tc, 1800, decimals0=6, decimals1=18, base_is_token0=False
    )
    assert avg_tick == 198735
    assert 2300 < price < 2400


def test_twap_price_eth_base_weth_usdc() -> None:
    # Base WETH/USDC pool: WETH is token0 (18), USDC is token1 (6).
    # base_is_token0=True. Same ETH ~ $2341 price.
    # Note: Solidity truncates toward zero for signed int division, so the
    # expected tick is -198736, not the Python-floor -198737.
    tc = [-16237306335028, -16237664061038]
    avg_tick, price = uniswap_v3_oracle._twap_price_from_ticks(
        tc, 1800, decimals0=18, decimals1=6, base_is_token0=True
    )
    assert avg_tick == -198736
    assert 2300 < price < 2400


def test_twap_price_btc_ethereum() -> None:
    tc = [9642417811787, 9642536959187]
    avg_tick, price = uniswap_v3_oracle._twap_price_from_ticks(
        tc, 1800, decimals0=8, decimals1=6, base_is_token0=True
    )
    assert avg_tick == 66193
    assert 70000 < price < 80000


def test_twap_price_requires_two_cumulatives() -> None:
    with pytest.raises(ValueError):
        uniswap_v3_oracle._twap_price_from_ticks(
            [1], 1800, decimals0=6, decimals1=18, base_is_token0=False
        )


# ── Input validation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_symbol() -> None:
    r = await uniswap_v3_oracle.get_twap_price("bad-sym!", chain="ethereum")
    assert r["error"] == "invalid symbol format"


@pytest.mark.asyncio
async def test_invalid_chain() -> None:
    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="solana")
    assert "unsupported chain" in r["error"]


@pytest.mark.asyncio
async def test_invalid_window() -> None:
    for bad in (0, -1, 10, 10**9):
        r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum", window_s=bad)
        assert "window_s" in r["error"]


@pytest.mark.asyncio
async def test_unsupported_symbol_chain_combo() -> None:
    r = await uniswap_v3_oracle.get_twap_price("BTC", chain="base")
    assert "no Uniswap v3 pool" in r["error"]


# ── RPC layer stubs ─────────────────────────────────────────────────────────


class _StubClient:
    """Captures each POST; returns a canned response per call."""

    def __init__(self, responses: list[tuple[int, Any]]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def post(self, url, *, json=None, timeout=None, **_kw):
        self.calls.append({"url": url, "body": json})
        entry = self.responses.pop(0) if self.responses else (200, {"result": "0x"})
        code, body = entry
        return _StubResp(code, body)


class _StubResp:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        return self._body


def _rpc_result_body(hex_result: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "result": hex_result}


# ── Public API integration ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_eth_ethereum(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = [30974752662779, 30975110386247]
    blob = _build_observe_response(tc, [0, 0])
    stub = _StubClient([(200, _rpc_result_body(blob))])
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum", window_s=1800)
    assert "error" not in r, r
    assert r["symbol"] == "ETH"
    assert r["chain"] == "ethereum"
    assert r["window_s"] == 1800
    assert r["avg_tick"] == 198735
    assert 2300 < r["price"] < 2400
    assert r["pool"] == "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"


@pytest.mark.asyncio
async def test_cache_returns_same_blob(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = _build_observe_response([30974752662779, 30975110386247], [0, 0])
    stub = _StubClient([(200, _rpc_result_body(blob))])
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    r1 = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")
    r2 = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")

    assert len(stub.calls) == 1
    assert r1 == r2
    assert uniswap_v3_oracle.get_metrics()["cache_hits"] == 1


@pytest.mark.asyncio
async def test_cache_key_includes_window(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = _build_observe_response([30974752662779, 30975110386247], [0, 0])
    stub = _StubClient([
        (200, _rpc_result_body(blob)),
        (200, _rpc_result_body(blob)),
    ])
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum", window_s=1800)
    await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum", window_s=3600)

    # Different window -> separate cache entry -> two RPC calls.
    assert len(stub.calls) == 2


@pytest.mark.asyncio
async def test_rpc_fallback_on_first_error(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = _build_observe_response([30974752662779, 30975110386247], [0, 0])
    stub = _StubClient([
        (500, {"error": "boom"}),
        (200, _rpc_result_body(blob)),
    ])
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")
    assert "error" not in r
    assert uniswap_v3_oracle.get_metrics()["rpc_fallbacks"] == 1


@pytest.mark.asyncio
async def test_pool_revert_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubClient([
        (200, {"jsonrpc": "2.0", "id": 1,
                "error": {"code": -32000, "message": "execution reverted: OLD"}}),
    ])
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")
    assert "pool rejected observe()" in r["error"]
    # A revert must NOT trip the breaker: it is a pool config issue.
    assert uniswap_v3_oracle.get_metrics()["circuit"]["ethereum"]["failures"] == 0
    assert uniswap_v3_oracle.get_metrics()["rpc_reverts"] == 1


@pytest.mark.asyncio
async def test_rpc_pool_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    # All 3 Ethereum RPCs return 500.
    responses = [(500, {"error": "boom"})] * 5
    stub = _StubClient(responses)
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", lambda: stub)

    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")
    assert "RPC pool exhausted" in r["error"]
    assert uniswap_v3_oracle.get_metrics()["circuit"]["ethereum"]["failures"] == 1


@pytest.mark.asyncio
async def test_circuit_opens_after_five_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _factory():
        return _StubClient([(500, {"error": "boom"})] * 50)
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", _factory)

    for _ in range(uniswap_v3_oracle._CB_MAX_FAILURES):
        await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")

    metrics = uniswap_v3_oracle.get_metrics()
    assert metrics["circuit"]["ethereum"]["state"] == "open"
    assert metrics["circuit_breaks"] == 1

    # Next call short-circuits, no RPC hit.
    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")
    assert "circuit open" in r["error"]


@pytest.mark.asyncio
async def test_circuit_is_per_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail on Ethereum, but Base stays healthy.
    def _factory_eth():
        return _StubClient([(500, {"error": "boom"})] * 50)
    monkeypatch.setattr(uniswap_v3_oracle, "get_http_client", _factory_eth)
    for _ in range(uniswap_v3_oracle._CB_MAX_FAILURES):
        await uniswap_v3_oracle.get_twap_price("ETH", chain="ethereum")

    # Now swap the client to a healthy one and hit Base.
    blob = _build_observe_response([-16237306335028, -16237664061038], [0, 0])
    monkeypatch.setattr(
        uniswap_v3_oracle, "get_http_client",
        lambda: _StubClient([(200, _rpc_result_body(blob))]),
    )
    r = await uniswap_v3_oracle.get_twap_price("ETH", chain="base")
    assert "error" not in r
    m = uniswap_v3_oracle.get_metrics()
    assert m["circuit"]["ethereum"]["state"] == "open"
    assert m["circuit"]["base"]["state"] == "closed"


# ── Helpers ─────────────────────────────────────────────────────────────────


def test_has_pool_and_all_supported_symbols() -> None:
    assert uniswap_v3_oracle.has_pool("ETH", "ethereum") is True
    assert uniswap_v3_oracle.has_pool("ETH", "base") is True
    assert uniswap_v3_oracle.has_pool("BTC", "ethereum") is True
    assert uniswap_v3_oracle.has_pool("BTC", "base") is False
    assert uniswap_v3_oracle.has_pool("NOPE", "ethereum") is False
    assert uniswap_v3_oracle.has_pool("eth", "ETHEREUM") is True

    grouping = uniswap_v3_oracle.all_supported_symbols()
    assert "ETH" in grouping["ethereum"]
    assert "BTC" in grouping["ethereum"]
    assert "ETH" in grouping["base"]
    assert "BTC" not in grouping["base"]


# ── HTTP route ──────────────────────────────────────────────────────────────


def test_route_twap_returns_price(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake(symbol: str, chain: str = "ethereum", window_s: int = 1800):
        return {
            "price": 2341.12,
            "avg_tick": 198735,
            "window_s": window_s,
            "tick_cumulatives": [1, 2],
            "chain": chain,
            "pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "fee_bps": 5,
            "token0": "USDC",
            "token1": "WETH",
            "source": "uniswap_v3",
            "symbol": symbol,
        }

    monkeypatch.setattr(uniswap_v3_oracle, "get_twap_price", fake)
    r = client.get("/api/twap/ETH", headers={"X-API-Key": api_key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["source"] == "uniswap_v3"
    assert body["data"]["window_s"] == 1800


def test_route_twap_accepts_custom_window(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def fake(symbol: str, chain: str = "ethereum", window_s: int = 1800):
        captured["window_s"] = window_s
        return {
            "price": 2341.0, "avg_tick": 198735, "window_s": window_s,
            "tick_cumulatives": [1, 2], "chain": chain,
            "pool": "0xpool", "fee_bps": 5, "token0": "USDC", "token1": "WETH",
            "source": "uniswap_v3", "symbol": symbol,
        }

    monkeypatch.setattr(uniswap_v3_oracle, "get_twap_price", fake)
    r = client.get(
        "/api/twap/ETH?window=3600", headers={"X-API-Key": api_key}
    )
    assert r.status_code == 200
    assert captured["window_s"] == 3600


def test_route_twap_400_on_bad_symbol(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/twap/bad-sym", headers={"X-API-Key": api_key})
    assert r.status_code == 400


def test_route_twap_404_on_unsupported(
    client: TestClient, api_key: str
) -> None:
    # BTC on Base is not in UNISWAP_V3_POOLS (only ETH on Base).
    r = client.get("/api/twap/BTC?chain=base", headers={"X-API-Key": api_key})
    assert r.status_code == 404


def test_route_twap_422_on_invalid_chain(
    client: TestClient, api_key: str
) -> None:
    # Arbitrum isn't in the V1.5 pattern (_TWAP_CHAIN_PATTERN).
    r = client.get("/api/twap/ETH?chain=arbitrum", headers={"X-API-Key": api_key})
    assert r.status_code == 422


def test_route_twap_502_on_upstream(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake(symbol: str, chain: str = "ethereum", window_s: int = 1800):
        return {
            "error": "uniswap_v3 ethereum RPC pool exhausted",
            "source": "uniswap_v3", "symbol": symbol, "chain": chain,
        }
    monkeypatch.setattr(uniswap_v3_oracle, "get_twap_price", fake)
    r = client.get("/api/twap/ETH", headers={"X-API-Key": api_key})
    assert r.status_code == 502


# ── /api/sources + /api/symbols wiring ──────────────────────────────────────


def test_sources_lists_uniswap_v3(client: TestClient, api_key: str) -> None:
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["data"]["sources"]]
    assert "uniswap_v3" in names


def test_symbols_includes_uniswap_v3_groups(client: TestClient, api_key: str) -> None:
    r = client.get("/api/symbols", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    body = r.json()["data"]
    assert "uniswap_v3_ethereum" in body["by_source"]
    assert "uniswap_v3_base" in body["by_source"]
    assert "ETH" in body["by_source"]["uniswap_v3_ethereum"]
    assert "BTC" in body["by_source"]["uniswap_v3_ethereum"]
    assert "ETH" in body["by_source"]["uniswap_v3_base"]


# ── MCP tool ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_twap_rejects_bad_symbol() -> None:
    r = await mcp_tools.get_twap_onchain("bad-sym!")
    assert r["error"] == "invalid symbol format"


@pytest.mark.asyncio
async def test_mcp_twap_rejects_unsupported_chain() -> None:
    r = await mcp_tools.get_twap_onchain("ETH", chain="solana")
    assert r["error"] == "unsupported chain"


@pytest.mark.asyncio
async def test_mcp_twap_rejects_window_out_of_range() -> None:
    r = await mcp_tools.get_twap_onchain("ETH", chain="ethereum", window_s=5)
    assert r["error"] == "window_s out of range"


@pytest.mark.asyncio
async def test_mcp_twap_rejects_unsupported_pair() -> None:
    r = await mcp_tools.get_twap_onchain("BTC", chain="base")
    assert "no Uniswap v3 pool" in r["error"]


@pytest.mark.asyncio
async def test_mcp_twap_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake(symbol: str, chain: str = "ethereum", window_s: int = 1800):
        captured.update(symbol=symbol, chain=chain, window_s=window_s)
        return {
            "price": 2341.0, "avg_tick": 198735, "window_s": window_s,
            "tick_cumulatives": [1, 2], "chain": chain,
            "pool": "0xpool", "fee_bps": 5, "token0": "USDC", "token1": "WETH",
            "source": "uniswap_v3", "symbol": symbol,
        }

    monkeypatch.setattr(uniswap_v3_oracle, "get_twap_price", fake)
    r = await mcp_tools.get_twap_onchain("ETH", chain="ethereum", window_s=3600)
    assert captured == {"symbol": "ETH", "chain": "ethereum", "window_s": 3600}
    assert "error" not in r


# ── multi_source wiring ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_sources_includes_uniswap_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_sources() must include uniswap_v3 when the module answers."""
    from services.oracle import multi_source

    async def fake_twap(symbol: str, chain: str = "ethereum", window_s: int = 1800) -> dict[str, Any]:
        return {
            "price": 75100.0,
            "avg_tick": 548_000,
            "window_s": window_s,
            "tick_cumulatives": [100, 200],
            "chain": chain,
            "pool": "0x99ac8cA7087fA4A2A1FB6357269965A2014ABc35",
            "fee_bps": 30,
            "token0": "WBTC",
            "token1": "USDC",
            "source": "uniswap_v3",
            "symbol": symbol,
        }

    async def _skip(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {"error": "skip"}

    async def _skip_price_oracle(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(multi_source.uniswap_v3_oracle, "get_twap_price", fake_twap)
    monkeypatch.setattr(multi_source.pyth_oracle, "get_pyth_price", _skip)
    monkeypatch.setattr(multi_source.chainlink_oracle, "get_chainlink_price", _skip)
    monkeypatch.setattr(multi_source.price_oracle, "get_prices", _skip_price_oracle)
    monkeypatch.setattr(multi_source.redstone_oracle, "get_redstone_price", _skip)
    monkeypatch.setattr(multi_source.pyth_solana_oracle, "get_pyth_solana_price", _skip)

    sources = await multi_source.collect_sources("BTC")

    assert any(s["name"] == "uniswap_v3" for s in sources), sources
    entry = next(s for s in sources if s["name"] == "uniswap_v3")
    assert entry["price"] == 75100.0
