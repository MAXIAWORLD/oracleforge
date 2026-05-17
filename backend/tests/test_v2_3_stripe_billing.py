"""V2.3 — Stripe billing tests (TDD RED→GREEN).

Covers:
    1. core.billing_tiers — tier → quota mapping, sanitization
    2. core.rate_limit — per-key tier-based daily quota lookup
    3. services.billing.stripe_service — webhook signature verification,
       idempotency, tier upgrade on checkout.session.completed, tier
       downgrade on customer.subscription.deleted
    4. api.routes_stripe — POST /api/stripe/checkout, POST /api/stripe/webhook

The Stripe HTTP API is never called from these tests. Where checkout
session creation is exercised (test_checkout_creates_session), the
underlying httpx call is monkey-patched to return a fake session id. All
webhook tests sign their own payloads with the test secret so we exercise
the real signature-verification code path.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient


# ── 1. core.billing_tiers ──────────────────────────────────────────────────


def test_billing_tiers_quota_lookup() -> None:
    from core.billing_tiers import (
        DEV_TIER,
        FREE_TIER,
        PRO_TIER,
        is_paid_tier,
        quota_for_tier,
    )

    assert quota_for_tier(FREE_TIER) == 100
    assert quota_for_tier(DEV_TIER) == 10_000
    assert quota_for_tier(PRO_TIER) == 100_000

    assert quota_for_tier(None) == 100
    assert quota_for_tier("garbage") == 100
    assert quota_for_tier("") == 100

    assert is_paid_tier(DEV_TIER) is True
    assert is_paid_tier(PRO_TIER) is True
    assert is_paid_tier(FREE_TIER) is False
    assert is_paid_tier(None) is False


# ── 2. rate_limit per-tier quota ───────────────────────────────────────────


def test_check_daily_uses_tier_quota_for_dev_key(client: TestClient) -> None:
    """A dev-tier key gets 10 000 / day, not 100."""
    from core.auth import hash_key
    from core.db import get_db, now_unix
    from core.rate_limit import check_daily

    raw_key = "mxo_test_dev_tier_quota"
    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, ?, 'dev', 1)",
        (hash_key(raw_key), now_unix()),
    )

    decision = check_daily(db, hash_key(raw_key))
    assert decision.limit == 10_000, "dev tier should resolve to 10 000 req/day"
    assert decision.allowed is True


def test_check_daily_uses_tier_quota_for_pro_key(client: TestClient) -> None:
    from core.auth import hash_key
    from core.db import get_db, now_unix
    from core.rate_limit import check_daily

    raw_key = "mxo_test_pro_tier_quota"
    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, ?, 'pro', 1)",
        (hash_key(raw_key), now_unix()),
    )

    decision = check_daily(db, hash_key(raw_key))
    assert decision.limit == 100_000


def test_check_daily_falls_back_to_free_for_unknown_tier(client: TestClient) -> None:
    """A garbage tier value never grants more than free."""
    from core.auth import hash_key
    from core.db import get_db, now_unix
    from core.rate_limit import check_daily

    raw_key = "mxo_test_garbage_tier"
    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, ?, 'garbage', 1)",
        (hash_key(raw_key), now_unix()),
    )

    decision = check_daily(db, hash_key(raw_key))
    assert decision.limit == 100


# ── 3. services.billing.stripe_service ─────────────────────────────────────


_TEST_WEBHOOK_SECRET = "whsec_test_secret_for_signing_payloads_in_tests"


def _stripe_signature(payload: bytes, secret: str, ts: int | None = None) -> str:
    """Produce a valid Stripe-Signature header for `payload`.

    Stripe uses HMAC-SHA256(secret, f"{ts}.{payload}") and emits the header as
    `t=<ts>,v1=<hex>` (multiple v1 values allowed during rotation).
    """
    if ts is None:
        ts = int(time.time())
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_verify_signature_accepts_valid() -> None:
    from services.billing import stripe_service

    payload = b'{"id":"evt_test","type":"ping"}'
    header = _stripe_signature(payload, _TEST_WEBHOOK_SECRET)

    assert (
        stripe_service.verify_signature(payload, header, _TEST_WEBHOOK_SECRET) is True
    )


def test_verify_signature_rejects_bad_secret() -> None:
    from services.billing import stripe_service

    payload = b'{"id":"evt_test","type":"ping"}'
    header = _stripe_signature(payload, "wrong_secret_used_to_sign_payload")

    assert (
        stripe_service.verify_signature(payload, header, _TEST_WEBHOOK_SECRET) is False
    )


def test_verify_signature_rejects_tampered_payload() -> None:
    from services.billing import stripe_service

    payload = b'{"id":"evt_test","type":"ping"}'
    header = _stripe_signature(payload, _TEST_WEBHOOK_SECRET)
    tampered = b'{"id":"evt_test","type":"hijacked"}'

    assert (
        stripe_service.verify_signature(tampered, header, _TEST_WEBHOOK_SECRET) is False
    )


def test_verify_signature_rejects_old_timestamp() -> None:
    """Replays older than the tolerance window must be rejected (default 5 min)."""
    from services.billing import stripe_service

    payload = b'{"id":"evt_test"}'
    too_old = int(time.time()) - 3600  # 1h ago
    header = _stripe_signature(payload, _TEST_WEBHOOK_SECRET, ts=too_old)

    assert (
        stripe_service.verify_signature(payload, header, _TEST_WEBHOOK_SECRET) is False
    )


def test_verify_signature_rejects_malformed_header() -> None:
    from services.billing import stripe_service

    assert stripe_service.verify_signature(b"{}", "", _TEST_WEBHOOK_SECRET) is False
    assert (
        stripe_service.verify_signature(
            b"{}", "not-a-stripe-header", _TEST_WEBHOOK_SECRET
        )
        is False
    )
    assert (
        stripe_service.verify_signature(b"{}", "t=abc,v1=def", _TEST_WEBHOOK_SECRET)
        is False
    )


# ── 4. Webhook handler — tier upgrade / downgrade / idempotency ────────────


def _post_webhook(
    client: TestClient,
    event: dict,
    secret: str = _TEST_WEBHOOK_SECRET,
) -> None:
    payload = json.dumps(event).encode()
    header = _stripe_signature(payload, secret)
    return client.post(
        "/api/stripe/webhook",
        content=payload,
        headers={
            "Stripe-Signature": header,
            "Content-Type": "application/json",
        },
    )


@pytest.fixture
def stripe_env(monkeypatch: pytest.MonkeyPatch):
    """Inject Stripe test credentials into the running config."""
    from core import config

    monkeypatch.setattr(
        config, "STRIPE_WEBHOOK_SECRET", _TEST_WEBHOOK_SECRET, raising=False
    )
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy", raising=False)
    monkeypatch.setattr(config, "STRIPE_PRICE_DEV_USD", "price_test_dev", raising=False)
    monkeypatch.setattr(
        config, "STRIPE_PRICE_DEV_EUR", "price_test_dev_eur", raising=False
    )
    monkeypatch.setattr(config, "STRIPE_PRICE_PRO_USD", "price_test_pro", raising=False)
    monkeypatch.setattr(
        config, "STRIPE_PRICE_PRO_EUR", "price_test_pro_eur", raising=False
    )
    monkeypatch.setattr(
        config, "LANDING_BASE_URL", "https://oracle.maxiaworld.app", raising=False
    )


def _seed_key(tier: str = "free") -> str:
    """Insert a fresh api_keys row, return the raw key."""
    from core.auth import generate_key
    from core.db import get_db, now_unix

    raw_key, key_hash = generate_key()
    db = get_db()
    db.execute(
        "INSERT INTO api_keys (key_hash, created_at, tier, active) VALUES (?, ?, ?, 1)",
        (key_hash, now_unix(), tier),
    )
    return raw_key


def test_webhook_rejects_invalid_signature(client: TestClient, stripe_env) -> None:
    payload = json.dumps({"id": "evt_1", "type": "checkout.session.completed"}).encode()
    response = client.post(
        "/api/stripe/webhook",
        content=payload,
        headers={
            "Stripe-Signature": "t=1234567890,v1=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400


def test_webhook_upgrades_key_to_dev_on_checkout_completed(
    client: TestClient, stripe_env
) -> None:
    from core.auth import hash_key
    from core.db import get_db

    raw_key = _seed_key("free")
    key_hash = hash_key(raw_key)

    event = {
        "id": "evt_dev_upgrade",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "customer": "cus_test_1",
                "subscription": "sub_test_1",
                "metadata": {"key_hash": key_hash, "tier": "dev"},
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200, response.text

    row = (
        get_db()
        .execute(
            "SELECT tier, stripe_customer_id, stripe_subscription_id "
            "FROM api_keys WHERE key_hash = ?",
            (key_hash,),
        )
        .fetchone()
    )
    assert row["tier"] == "dev"
    assert row["stripe_customer_id"] == "cus_test_1"
    assert row["stripe_subscription_id"] == "sub_test_1"


def test_webhook_upgrades_key_to_pro(client: TestClient, stripe_env) -> None:
    from core.auth import hash_key
    from core.db import get_db

    raw_key = _seed_key("free")
    key_hash = hash_key(raw_key)

    event = {
        "id": "evt_pro_upgrade",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_2",
                "customer": "cus_test_2",
                "subscription": "sub_test_2",
                "metadata": {"key_hash": key_hash, "tier": "pro"},
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200

    row = (
        get_db()
        .execute("SELECT tier FROM api_keys WHERE key_hash = ?", (key_hash,))
        .fetchone()
    )
    assert row["tier"] == "pro"


def test_webhook_is_idempotent_on_replay(client: TestClient, stripe_env) -> None:
    """Re-delivering the same event must not flip the tier twice or 4xx."""
    from core.auth import hash_key
    from core.db import get_db

    raw_key = _seed_key("free")
    key_hash = hash_key(raw_key)

    event = {
        "id": "evt_replay_test",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_replay",
                "customer": "cus_replay",
                "subscription": "sub_replay",
                "metadata": {"key_hash": key_hash, "tier": "dev"},
            }
        },
    }
    r1 = _post_webhook(client, event)
    r2 = _post_webhook(client, event)
    assert r1.status_code == 200
    assert r2.status_code == 200, "replay must return 200 (already processed)"

    rows = (
        get_db()
        .execute(
            "SELECT COUNT(*) FROM stripe_events WHERE event_id = ?",
            ("evt_replay_test",),
        )
        .fetchone()
    )
    assert rows[0] == 1


def test_webhook_downgrades_on_subscription_deleted(
    client: TestClient, stripe_env
) -> None:
    from core.auth import hash_key
    from core.db import get_db

    raw_key = _seed_key("dev")
    key_hash = hash_key(raw_key)
    db = get_db()
    db.execute(
        "UPDATE api_keys SET stripe_customer_id = ?, stripe_subscription_id = ? "
        "WHERE key_hash = ?",
        ("cus_active", "sub_active", key_hash),
    )

    event = {
        "id": "evt_cancel",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_active",
                "customer": "cus_active",
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200

    row = db.execute(
        "SELECT tier FROM api_keys WHERE key_hash = ?", (key_hash,)
    ).fetchone()
    assert row["tier"] == "free", "cancelled subscription must downgrade to free"


def test_webhook_ignores_unknown_event_type(client: TestClient, stripe_env) -> None:
    event = {"id": "evt_unknown", "type": "ping.pong", "data": {"object": {}}}
    response = _post_webhook(client, event)
    assert response.status_code == 200


def test_webhook_rejects_event_for_unknown_key_hash(
    client: TestClient, stripe_env
) -> None:
    event = {
        "id": "evt_no_key",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_orphan",
                "customer": "cus_orphan",
                "subscription": "sub_orphan",
                "metadata": {"key_hash": "non_existent_hash", "tier": "dev"},
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200, "log + ack — never 4xx Stripe on missing key"


def test_webhook_rejects_invalid_tier_in_metadata(
    client: TestClient, stripe_env
) -> None:
    """A metadata.tier outside {dev, pro} must NOT upgrade the row."""
    from core.auth import hash_key
    from core.db import get_db

    raw_key = _seed_key("free")
    key_hash = hash_key(raw_key)

    event = {
        "id": "evt_bad_tier",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_bad",
                "customer": "cus_bad",
                "subscription": "sub_bad",
                "metadata": {"key_hash": key_hash, "tier": "godmode"},
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200

    row = (
        get_db()
        .execute("SELECT tier FROM api_keys WHERE key_hash = ?", (key_hash,))
        .fetchone()
    )
    assert row["tier"] == "free", "invalid tier must not escalate quota"


# ── 5. Checkout endpoint ───────────────────────────────────────────────────


def test_checkout_requires_api_key(client: TestClient, stripe_env) -> None:
    response = client.post("/api/stripe/checkout", json={"tier": "dev"})
    assert response.status_code == 401


def test_checkout_rejects_invalid_tier(
    client: TestClient, api_key: str, stripe_env
) -> None:
    response = client.post(
        "/api/stripe/checkout",
        json={"tier": "godmode"},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 400


def test_checkout_creates_session(
    client: TestClient,
    api_key: str,
    stripe_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: stripe_service.create_checkout_session is called and URL returned."""
    from services.billing import stripe_service

    captured: dict = {}

    async def fake_create(
        *,
        price_id: str,
        key_hash: str,
        tier: str,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> dict:
        captured["price_id"] = price_id
        captured["key_hash"] = key_hash
        captured["tier"] = tier
        return {
            "id": "cs_test_fake",
            "url": "https://checkout.stripe.com/c/pay/cs_test_fake",
        }

    monkeypatch.setattr(stripe_service, "create_checkout_session", fake_create)

    response = client.post(
        "/api/stripe/checkout",
        json={"tier": "dev"},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["url"].startswith("https://checkout.stripe.com/")
    assert captured["tier"] == "dev"
    assert captured["price_id"] == "price_test_dev"
    assert captured["key_hash"], "checkout must carry the key_hash in metadata"
