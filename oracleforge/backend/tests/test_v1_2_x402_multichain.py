"""V1.2 — x402 multi-chain EVM tests (Base + Arbitrum + Optimism + Polygon).

Covers three layers:
    1. Config — X402_CHAIN_CONFIG carries canonical USDC contracts, chain
       IDs, treasury resolution cascade (per-chain override → generic →
       X402_TREASURY_ADDRESS_BASE V1.0 compat).
    2. Verifier — build_x402_challenge, build_all_accepts, x402_verify_payment
       dispatch per chain, treasury-missing path omits a chain from accepts.
    3. Middleware — X-Payment-Network parsing (default base, unknown =>
       base), 402 response shape with 4 accepts, tx persisted with chain,
       replay protection still works, base_verifier shim still dispatches.

All tests run offline — they monkeypatch the generic verifier to avoid
any outbound RPC. The smoke test with a real tx on Arbitrum/Optimism/
Polygon is deferred (same policy as Phase 4 Step 10 for Base).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient


# ── Fixtures (session scoped with configured 4-chain treasury) ──────────────


@pytest.fixture(scope="session")
def multichain_app(tmp_path_factory: pytest.TempPathFactory):
    """Fresh session-scoped app with every chain's treasury configured.

    Sets the per-chain env vars BEFORE importing `main` so the 402
    accepts list contains one entry per chain.
    """
    db_dir: Path = tmp_path_factory.mktemp("maxia_oracle_v12_db")
    os.environ["DB_PATH"] = str(db_dir / "v12.sqlite")
    os.environ["X402_TREASURY_ADDRESS"] = (
        "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41"
    )
    os.environ["X402_TREASURY_ADDRESS_ARBITRUM"] = (
        "0x1111111111111111111111111111111111111111"
    )
    os.environ["X402_TREASURY_ADDRESS_OPTIMISM"] = (
        "0x2222222222222222222222222222222222222222"
    )
    os.environ["X402_TREASURY_ADDRESS_POLYGON"] = (
        "0x3333333333333333333333333333333333333333"
    )
    # Force module reload so core.config picks up the new env vars in the
    # same process that previously imported it under a different setup.
    import importlib

    import core.config as _config  # noqa: PLC0415

    importlib.reload(_config)
    import x402.multichain_verifier as _mcv  # noqa: PLC0415

    importlib.reload(_mcv)
    import x402.base_verifier as _bv  # noqa: PLC0415

    importlib.reload(_bv)
    import x402.middleware as _mw  # noqa: PLC0415

    importlib.reload(_mw)
    import main  # noqa: PLC0415

    importlib.reload(main)
    from core.db import init_db  # noqa: PLC0415

    init_db()
    return main.app


@pytest.fixture
def mc_client(multichain_app) -> Iterator[TestClient]:
    from core.db import get_db  # noqa: PLC0415

    db = get_db()
    db.execute("DELETE FROM api_keys")
    db.execute("DELETE FROM rate_limit")
    db.execute("DELETE FROM register_limit")
    db.execute("DELETE FROM x402_txs")

    with TestClient(multichain_app) as c:
        yield c


@pytest.fixture
def mc_stub_verifier(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub `x402_verify_payment` so we can assert the chain dispatch."""
    state: dict[str, Any] = {
        "valid": True,
        "tx_hash": None,
        "last_chain": None,
        "call_count": 0,
    }

    async def _stub(
        chain: str, payment_header: str, expected_amount_usdc: float
    ) -> dict[str, Any]:
        state["call_count"] += 1
        state["last_chain"] = chain
        if not state["valid"]:
            return {"valid": False, "error": "stub rejected"}
        tx = state["tx_hash"] or (
            payment_header
            if payment_header.startswith("0x") and len(payment_header) == 66
            else "0x" + "cd" * 32
        )
        return {
            "valid": True,
            "txHash": tx,
            "network": f"{chain}-mainnet",
            "verifiedVia": "stub",
            "chainId": 0,
        }

    monkeypatch.setattr("x402.middleware.x402_verify_payment", _stub)
    return state


# ── 1. Config layer ─────────────────────────────────────────────────────────


def test_supported_chains_is_four_chains() -> None:
    from core.config import X402_SUPPORTED_CHAINS

    assert X402_SUPPORTED_CHAINS == ("base", "arbitrum", "optimism", "polygon")


def test_chain_config_exposes_canonical_usdc_contracts() -> None:
    from core.config import X402_CHAIN_CONFIG

    assert X402_CHAIN_CONFIG["base"]["usdc_contract"] == (
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    )
    assert X402_CHAIN_CONFIG["arbitrum"]["usdc_contract"] == (
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    )
    assert X402_CHAIN_CONFIG["optimism"]["usdc_contract"] == (
        "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"
    )
    assert X402_CHAIN_CONFIG["polygon"]["usdc_contract"] == (
        "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
    )


def test_chain_config_exposes_chain_ids() -> None:
    from core.config import X402_CHAIN_CONFIG

    assert X402_CHAIN_CONFIG["base"]["chain_id"] == 8453
    assert X402_CHAIN_CONFIG["arbitrum"]["chain_id"] == 42161
    assert X402_CHAIN_CONFIG["optimism"]["chain_id"] == 10
    assert X402_CHAIN_CONFIG["polygon"]["chain_id"] == 137


def test_only_base_has_facilitator() -> None:
    from core.config import X402_CHAIN_CONFIG

    assert X402_CHAIN_CONFIG["base"]["facilitator"]
    for chain in ("arbitrum", "optimism", "polygon"):
        assert X402_CHAIN_CONFIG[chain]["facilitator"] is None


# ── 2. Verifier helpers ─────────────────────────────────────────────────────


def test_build_x402_challenge_returns_none_without_treasury(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a chain has no treasury configured, no accepts entry is built."""
    from x402 import multichain_verifier as mcv

    patched = dict(mcv.X402_CHAIN_CONFIG)
    patched["arbitrum"] = {
        **patched["arbitrum"],
        "treasury": "",
    }
    monkeypatch.setattr(mcv, "X402_CHAIN_CONFIG", patched)

    assert mcv.build_x402_challenge("arbitrum", "/api/price/BTC", 0.001) is None


def test_build_x402_challenge_shape_for_arbitrum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from x402 import multichain_verifier as mcv

    patched = dict(mcv.X402_CHAIN_CONFIG)
    patched["arbitrum"] = {
        **patched["arbitrum"],
        "treasury": "0x1111111111111111111111111111111111111111",
    }
    monkeypatch.setattr(mcv, "X402_CHAIN_CONFIG", patched)

    entry = mcv.build_x402_challenge("arbitrum", "/api/price/BTC", 0.001)
    assert entry is not None
    assert entry["network"] == "arbitrum-mainnet"
    assert entry["payTo"] == "0x1111111111111111111111111111111111111111"
    assert entry["asset"] == "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    assert entry["maxAmountRequired"] == "1000"  # 0.001 * 1_000_000
    assert entry["extra"]["chainId"] == 42161
    assert "facilitator" not in entry["extra"]  # arbitrum has no facilitator


def test_build_all_accepts_yields_entry_per_configured_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from x402 import multichain_verifier as mcv

    # Every chain configured — expect 4 entries.
    patched = {
        chain: {**cfg, "treasury": f"0x{str(i) * 40}"}
        for i, (chain, cfg) in enumerate(mcv.X402_CHAIN_CONFIG.items(), start=1)
    }
    monkeypatch.setattr(mcv, "X402_CHAIN_CONFIG", patched)

    accepts = mcv.build_all_accepts("/api/price/BTC", 0.001)
    assert len(accepts) == 4
    assert {e["network"] for e in accepts} == {
        "base-mainnet",
        "arbitrum-mainnet",
        "optimism-mainnet",
        "polygon-mainnet",
    }


def test_build_all_accepts_drops_chains_without_treasury(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from x402 import multichain_verifier as mcv

    patched = {chain: {**cfg, "treasury": ""} for chain, cfg in mcv.X402_CHAIN_CONFIG.items()}
    patched["base"] = {
        **patched["base"],
        "treasury": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    }
    monkeypatch.setattr(mcv, "X402_CHAIN_CONFIG", patched)

    accepts = mcv.build_all_accepts("/api/price/BTC", 0.001)
    assert len(accepts) == 1
    assert accepts[0]["network"] == "base-mainnet"


@pytest.mark.asyncio
async def test_verifier_rejects_unsupported_chain() -> None:
    from x402 import multichain_verifier as mcv

    result = await mcv.x402_verify_payment("solana", "0x" + "a" * 64, 0.001)
    assert result["valid"] is False
    assert "unsupported chain" in result["error"]


# ── 3. Middleware layer (integrated via TestClient) ─────────────────────────


def test_402_accepts_contains_every_chain_with_treasury(
    mc_client: TestClient,
) -> None:
    r = mc_client.get("/api/price/BTC")
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 2
    networks = [a["network"] for a in body["accepts"]]
    assert "base-mainnet" in networks
    assert "arbitrum-mainnet" in networks
    assert "optimism-mainnet" in networks
    assert "polygon-mainnet" in networks
    assert len(body["accepts"]) == 4


def test_middleware_default_chain_is_base(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    r = mc_client.get(
        "/api/price/BTC", headers={"X-Payment": "0x" + "a" * 64}
    )
    assert r.status_code == 200
    assert mc_stub_verifier["last_chain"] == "base"


def test_middleware_parses_arbitrum_header(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    r = mc_client.get(
        "/api/price/BTC",
        headers={
            "X-Payment": "0x" + "b" * 64,
            "X-Payment-Network": "arbitrum",
        },
    )
    assert r.status_code == 200
    assert mc_stub_verifier["last_chain"] == "arbitrum"


def test_middleware_unknown_network_falls_back_to_base(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    r = mc_client.get(
        "/api/price/BTC",
        headers={
            "X-Payment": "0x" + "c" * 64,
            "X-Payment-Network": "solana",
        },
    )
    assert r.status_code == 200
    assert mc_stub_verifier["last_chain"] == "base"


def test_middleware_records_chain_in_x402_txs(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    r = mc_client.get(
        "/api/price/BTC",
        headers={
            "X-Payment": "0x" + "d" * 64,
            "X-Payment-Network": "polygon",
        },
    )
    assert r.status_code == 200

    from core.db import get_db  # noqa: PLC0415

    row = get_db().execute(
        "SELECT chain FROM x402_txs WHERE tx_hash = ?",
        ("0x" + "d" * 64,),
    ).fetchone()
    assert row is not None
    assert row["chain"] == "polygon"


def test_middleware_replay_protection_still_enforced(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    tx_hash = "0x" + "e" * 64
    # Pin the stub to always return the same txHash so the second call
    # hits the replay check rather than looking like a fresh payment.
    mc_stub_verifier["tx_hash"] = tx_hash
    r1 = mc_client.get(
        "/api/price/BTC",
        headers={"X-Payment": tx_hash, "X-Payment-Network": "optimism"},
    )
    assert r1.status_code == 200

    r2 = mc_client.get(
        "/api/price/BTC",
        headers={"X-Payment": tx_hash, "X-Payment-Network": "optimism"},
    )
    assert r2.status_code == 402
    assert "replay" in r2.json()["error"].lower()


def test_middleware_rejects_when_stub_says_invalid(
    mc_client: TestClient, mc_stub_verifier: dict[str, Any]
) -> None:
    mc_stub_verifier["valid"] = False
    r = mc_client.get(
        "/api/price/BTC",
        headers={"X-Payment": "0x" + "f" * 64, "X-Payment-Network": "arbitrum"},
    )
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "payment verification failed"
    assert body["chain"] == "arbitrum"


# ── 4. Compat shim — base_verifier still dispatches ────────────────────────


@pytest.mark.asyncio
async def test_base_verifier_wraps_multichain_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """x402_verify_payment_base must delegate to the generic dispatcher."""
    from x402 import base_verifier, multichain_verifier

    captured: dict[str, Any] = {}

    async def fake(chain: str, header: str, amount: float) -> dict[str, Any]:
        captured["chain"] = chain
        captured["header"] = header
        captured["amount"] = amount
        return {"valid": True, "verifiedVia": "fake"}

    monkeypatch.setattr(multichain_verifier, "x402_verify_payment", fake)
    # Also patch the bound name used by base_verifier's private alias.
    monkeypatch.setattr(base_verifier, "_verify_payment", fake)

    result = await base_verifier.x402_verify_payment_base("0x" + "a" * 64, 0.001)
    assert captured["chain"] == "base"
    assert captured["amount"] == 0.001
    assert result["valid"] is True
