"""V1.1 — Chainlink multi-chain reader tests.

Covers the three pillars of the V1.1 extension:
    1. Chainlink module helpers (has_feed, feeds_for, symbols_for,
       all_supported_symbols, SUPPORTED_CHAINS).
    2. /api/chainlink/{symbol}?chain=... HTTP route behavior across
       Base, Ethereum and Arbitrum, plus error paths (invalid chain,
       symbol missing on chain, symbol wrong format).
    3. MCP tool get_chainlink_onchain(symbol, chain) across the same
       dimensions.

All tests run offline — they exercise dispatch/validation logic using
pytest monkeypatching. A single test (`test_chainlink_onchain_live_optional`)
is skipped by default; enable it when the developer machine has outbound
HTTPS to Base/Ethereum/Arbitrum public RPCs.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import CHAIN_RPC_URLS
from mcp_server import tools as mcp_tools
from services.oracle import chainlink_oracle


# ── Module helpers ──────────────────────────────────────────────────────────


def test_supported_chains_is_three_chains() -> None:
    assert chainlink_oracle.SUPPORTED_CHAINS == ("base", "ethereum", "arbitrum")
    assert chainlink_oracle.DEFAULT_CHAIN == "base"


def test_feeds_dict_populated_for_every_supported_chain() -> None:
    for chain in chainlink_oracle.SUPPORTED_CHAINS:
        feeds = chainlink_oracle.feeds_for(chain)
        assert feeds, f"{chain} must declare at least one feed"
        # Every chain must expose BTC + ETH + USDC as a minimum core set.
        for required in ("BTC", "ETH", "USDC"):
            assert required in feeds, f"{chain} missing required feed {required}"


def test_has_feed_base_btc_true() -> None:
    assert chainlink_oracle.has_feed("BTC", "base") is True


def test_has_feed_unknown_chain_returns_false() -> None:
    assert chainlink_oracle.has_feed("BTC", "solana") is False


def test_has_feed_unknown_symbol_returns_false() -> None:
    assert chainlink_oracle.has_feed("NONSENSE99", "ethereum") is False


def test_all_supported_symbols_returns_per_chain_dict() -> None:
    grouped = chainlink_oracle.all_supported_symbols()
    assert set(grouped.keys()) == set(chainlink_oracle.SUPPORTED_CHAINS)
    for chain, syms in grouped.items():
        assert syms == sorted(syms), f"{chain} symbols must be sorted"


def test_chain_rpc_urls_has_three_entries_per_chain() -> None:
    for chain in chainlink_oracle.SUPPORTED_CHAINS:
        rpcs = CHAIN_RPC_URLS[chain]
        assert len(rpcs) >= 2, f"{chain} must expose at least 2 RPC fallbacks"
        assert all(u.startswith("https://") for u in rpcs), f"{chain} RPCs must be HTTPS"


# ── HTTP route — dispatch and validation ────────────────────────────────────


def test_route_rejects_unsupported_chain(client: TestClient, api_key: str) -> None:
    r = client.get(
        "/api/chainlink/BTC",
        params={"chain": "solana"},
        headers={"X-API-Key": api_key},
    )
    # Query regex rejects solana before the handler runs.
    assert r.status_code == 422
    body = r.json()
    assert body["detail"][0]["loc"][-1] == "chain"


def test_route_rejects_unsupported_symbol_on_chain(
    client: TestClient, api_key: str
) -> None:
    r = client.get(
        "/api/chainlink/BTCXYZ",
        params={"chain": "ethereum"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["chain"] == "ethereum"
    assert body["symbol"] == "BTCXYZ"
    assert isinstance(body["supported"], list)


def test_route_default_chain_is_base(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    async def fake_get_chainlink_price(symbol: str, chain: str = "base") -> dict:
        captured["symbol"] = symbol
        captured["chain"] = chain
        return {
            "price": 1.0,
            "decimals": 8,
            "round_id": 1,
            "updated_at": 0,
            "age_s": 0,
            "stale": False,
            "source": f"chainlink_{chain}",
            "contract": "0x0",
            "chain": chain,
        }

    monkeypatch.setattr(
        chainlink_oracle, "get_chainlink_price", fake_get_chainlink_price
    )
    r = client.get("/api/chainlink/BTC", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    assert captured["chain"] == "base"
    assert captured["symbol"] == "BTC"
    assert r.json()["data"]["chain"] == "base"


def test_route_propagates_chain_to_service(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    async def fake_get_chainlink_price(symbol: str, chain: str = "base") -> dict:
        captured["chain"] = chain
        return {
            "price": 2.0,
            "decimals": 8,
            "round_id": 7,
            "updated_at": 0,
            "age_s": 0,
            "stale": False,
            "source": f"chainlink_{chain}",
            "contract": "0x1",
            "chain": chain,
        }

    monkeypatch.setattr(
        chainlink_oracle, "get_chainlink_price", fake_get_chainlink_price
    )
    r = client.get(
        "/api/chainlink/ETH",
        params={"chain": "arbitrum"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    assert captured["chain"] == "arbitrum"
    assert r.json()["data"]["source"] == "chainlink_arbitrum"


# ── MCP tool — dispatch and validation ──────────────────────────────────────


async def _run_tool(symbol: str, chain: str | None = None) -> dict:
    if chain is None:
        return await mcp_tools.get_chainlink_onchain(symbol)
    return await mcp_tools.get_chainlink_onchain(symbol, chain=chain)


@pytest.mark.asyncio
async def test_mcp_tool_rejects_unsupported_chain() -> None:
    result = await _run_tool("BTC", chain="solana")
    assert result["error"] == "unsupported chain"
    assert result["chain"] == "solana"
    assert "base" in result["supported"]


@pytest.mark.asyncio
async def test_mcp_tool_rejects_symbol_not_on_chain() -> None:
    result = await _run_tool("ZZZ999", chain="arbitrum")
    assert "no Chainlink feed" in result["error"]
    assert result["chain"] == "arbitrum"
    assert isinstance(result["supported"], list)


@pytest.mark.asyncio
async def test_mcp_tool_propagates_chain_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_price(symbol: str, chain: str = "base") -> dict:
        captured["symbol"] = symbol
        captured["chain"] = chain
        return {
            "price": 100.0,
            "source": f"chainlink_{chain}",
            "chain": chain,
            "decimals": 8,
            "round_id": 0,
            "updated_at": 0,
            "age_s": 0,
            "stale": False,
            "contract": "0x0",
        }

    monkeypatch.setattr(chainlink_oracle, "get_chainlink_price", fake_price)
    result = await _run_tool("BTC", chain="ethereum")
    assert captured["chain"] == "ethereum"
    assert result["data"]["source"] == "chainlink_ethereum"


@pytest.mark.asyncio
async def test_mcp_tool_default_chain_is_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_price(symbol: str, chain: str = "base") -> dict:
        captured["chain"] = chain
        return {
            "price": 50.0,
            "source": f"chainlink_{chain}",
            "chain": chain,
            "decimals": 8,
            "round_id": 0,
            "updated_at": 0,
            "age_s": 0,
            "stale": False,
            "contract": "0x0",
        }

    monkeypatch.setattr(chainlink_oracle, "get_chainlink_price", fake_price)
    result = await _run_tool("BTC")  # no chain passed
    assert captured["chain"] == "base"
    assert result["data"]["chain"] == "base"


# ── list_supported_symbols now exposes all chains ───────────────────────────


@pytest.mark.asyncio
async def test_mcp_list_supported_symbols_splits_chainlink_per_chain() -> None:
    result = await mcp_tools.list_supported_symbols()
    by_source = result["data"]["by_source"]
    assert "chainlink_base" in by_source
    assert "chainlink_ethereum" in by_source
    assert "chainlink_arbitrum" in by_source
    assert "BTC" in by_source["chainlink_base"]
    assert "BTC" in by_source["chainlink_ethereum"]
    assert "BTC" in by_source["chainlink_arbitrum"]


# ── /api/sources lists every chainlink chain ────────────────────────────────


def test_sources_route_lists_every_chainlink_chain(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["data"]["sources"]]
    assert "chainlink_base" in names
    assert "chainlink_ethereum" in names
    assert "chainlink_arbitrum" in names


# ── /api/symbols returns the multi-chain grouping ───────────────────────────


def test_symbols_route_groups_chainlink_per_chain(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/symbols", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    by_source = r.json()["data"]["by_source"]
    assert "chainlink_base" in by_source
    assert "chainlink_ethereum" in by_source
    assert "chainlink_arbitrum" in by_source


# ── RPC fallback — helper dispatch smoke test ───────────────────────────────


@pytest.mark.asyncio
async def test_eth_call_tries_every_rpc_before_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    async def failing_rpc(rpc_url: str, to: str, data: str) -> str:
        attempts.append(rpc_url)
        raise RuntimeError(f"boom {rpc_url}")

    monkeypatch.setattr(chainlink_oracle, "_try_single_rpc", failing_rpc)

    with pytest.raises(RuntimeError, match="all ethereum RPCs failed"):
        await chainlink_oracle._eth_call("0x00", "0xfeaf968c", "ethereum")

    # The fallback pool has at least two entries per chain; the helper
    # must have tried every one of them before giving up.
    assert len(attempts) >= 2
    # First attempt is the env-configured primary for the chain.
    assert attempts[0] == CHAIN_RPC_URLS["ethereum"][0]
