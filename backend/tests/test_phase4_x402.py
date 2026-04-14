"""Phase 4 E2E tests — x402 middleware, base_verifier, replay protection.

These tests exercise the middleware path end-to-end against a FastAPI
TestClient with the `x402_verify_payment_base` function monkey-patched to
a deterministic stub. They do NOT perform any real Base-mainnet RPC call —
the live mainnet test is deferred to Phase 4 Step 10.

Coverage:
    - 402 challenge emitted when X-Payment is absent on a priced route
    - 402 when payment verification returns invalid=False
    - 200 when payment verification is valid (free tier bypassed)
    - 402 on replay of the same tx_hash
    - Daily rate limit NOT enforced for x402-paid requests
    - Unprotected paths (/health, /api/register) still work unauthenticated
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def session_app(tmp_path_factory: pytest.TempPathFactory):
    """Fresh session-scoped app with an isolated DB and a configured treasury address.

    Sets X402_TREASURY_ADDRESS_BASE in the environment BEFORE importing
    `main` so the 402 challenge carries a populated `accepts` list.
    """
    db_dir: Path = tmp_path_factory.mktemp("maxia_oracle_phase4_db")
    os.environ["DB_PATH"] = str(db_dir / "phase4.sqlite")
    os.environ["X402_TREASURY_ADDRESS_BASE"] = (
        "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41"
    )

    import main  # noqa: PLC0415 — late import after env setup
    from core.db import init_db  # noqa: PLC0415

    init_db()
    return main.app


@pytest.fixture
def client(session_app) -> Iterator[TestClient]:
    from core.db import get_db  # noqa: PLC0415

    db = get_db()
    db.execute("DELETE FROM api_keys")
    db.execute("DELETE FROM rate_limit")
    db.execute("DELETE FROM register_limit")
    db.execute("DELETE FROM x402_txs")

    with TestClient(session_app) as c:
        yield c


@pytest.fixture
def stub_verifier(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace `x402_verify_payment_base` with a controllable stub.

    The fixture returns a mutable dict that the test body can use to
    configure the stub's response. Default: valid payment, tx_hash
    derived from the payment_header.
    """
    state: dict[str, Any] = {"valid": True, "tx_hash": None, "call_count": 0}

    async def _stub(payment_header: str, expected_amount_usdc: float) -> dict[str, Any]:
        state["call_count"] += 1
        tx_hash = state["tx_hash"] or (
            payment_header
            if payment_header.startswith("0x") and len(payment_header) == 66
            else "0x" + "ab" * 32
        )
        if not state["valid"]:
            return {"valid": False, "error": "stub rejected"}
        return {
            "valid": True,
            "txHash": tx_hash,
            "network": "base-mainnet",
            "verifiedVia": "stub",
        }

    # The middleware imports x402_verify_payment_base directly into its
    # namespace, so we must patch the name at that import site.
    monkeypatch.setattr(
        "x402.middleware.x402_verify_payment_base", _stub
    )
    return state


# ── Unprotected paths: no x402 interference ────────────────────────────────


def test_health_unaffected_by_x402(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert "disclaimer" in r.json()


def test_register_unaffected_by_x402(client: TestClient) -> None:
    r = client.post("/api/register")
    assert r.status_code == 201
    assert r.json()["data"]["api_key"].startswith("mxo_")


# ── 402 challenge discovery ─────────────────────────────────────────────────


def test_challenge_emitted_on_priced_route_without_headers(
    client: TestClient,
) -> None:
    r = client.get("/api/price/BTC")
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 2
    assert len(body["accepts"]) == 1
    entry = body["accepts"][0]
    assert entry["scheme"] == "exact"
    assert entry["network"] == "base-mainnet"
    assert entry["maxAmountRequired"] == "1000"  # 0.001 USDC in 6-dec atomic units
    assert entry["payTo"] == "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41"
    assert entry["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert entry["extra"]["chainId"] == 8453


def test_batch_challenge_pricing(client: TestClient) -> None:
    r = client.post("/api/prices/batch", json={"symbols": ["BTC", "ETH"]})
    assert r.status_code == 402
    entry = r.json()["accepts"][0]
    assert entry["maxAmountRequired"] == "5000"  # 0.005 USDC


# ── Payment verification path ───────────────────────────────────────────────


def test_valid_payment_grants_access(
    client: TestClient, stub_verifier: dict[str, Any]
) -> None:
    stub_verifier["tx_hash"] = "0x" + "11" * 32
    r = client.get("/api/price/BTC", headers={"X-Payment": "0x" + "11" * 32})
    # 200 if an upstream oracle returned data, 404 if every source is
    # offline in the test environment. Either way the middleware let the
    # request through to the route handler.
    assert r.status_code in (200, 404)
    assert stub_verifier["call_count"] == 1


def test_invalid_payment_rejected(
    client: TestClient, stub_verifier: dict[str, Any]
) -> None:
    stub_verifier["valid"] = False
    r = client.get("/api/price/BTC", headers={"X-Payment": "0xdeadbeef"})
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "payment verification failed"


def test_replay_same_tx_hash_rejected(
    client: TestClient, stub_verifier: dict[str, Any]
) -> None:
    stub_verifier["tx_hash"] = "0x" + "22" * 32
    header = "0x" + "22" * 32
    first = client.get("/api/price/BTC", headers={"X-Payment": header})
    second = client.get("/api/price/BTC", headers={"X-Payment": header})
    assert first.status_code in (200, 404)
    assert second.status_code == 402
    assert second.json()["error"] == "payment already used (replay detected)"


def test_x402_paid_bypasses_daily_rate_limit(
    client: TestClient, stub_verifier: dict[str, Any]
) -> None:
    """A paying client never hits the free-tier 100 req/day ceiling.

    We make 5 requests, each with a unique tx hash to avoid replay
    detection. The free-tier rate limiter is not exercised because
    `require_access` returns the x402 sentinel, causing
    `_enforce_rate_limit` to short-circuit to None.
    """
    for i in range(5):
        hex_index = format(i + 0xA0, "02x")
        tx = "0x" + hex_index * 32
        stub_verifier["tx_hash"] = tx
        r = client.get("/api/price/BTC", headers={"X-Payment": tx})
        assert r.status_code in (200, 404)
    assert stub_verifier["call_count"] == 5


# ── X-API-Key coexistence with x402 ────────────────────────────────────────


def test_api_key_still_works_on_priced_route(
    client: TestClient,
) -> None:
    """A client with a valid X-API-Key can still use priced routes free of charge."""
    # Register a fresh key.
    reg = client.post("/api/register")
    assert reg.status_code == 201
    api_key = reg.json()["data"]["api_key"]

    r = client.get("/api/price/BTC", headers={"X-API-Key": api_key})
    # Free tier works — the middleware passes through when an X-API-Key
    # is present even if the route is priced.
    assert r.status_code in (200, 404)
