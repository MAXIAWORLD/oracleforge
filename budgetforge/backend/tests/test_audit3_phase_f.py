"""Tests audit #3 Phase F — Blockers sécurité.

F1 [CRITIQUE] — Timing attack admin key : utiliser hmac.compare_digest
F2 [CRITIQUE] — Stripe webhook double-réception : catch IntegrityError
F3 [HAUT] — Pré-billing overshoot : cancel si final_cost > budget × 1.2
F4 [HAUT] — DNS rebinding webhook : cacher IP résolue au check
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parent.parent
AUTH_FILE = BACKEND / "core" / "auth.py"
BILLING_FILE = BACKEND / "routes" / "billing.py"


# ──────────────────────────────────────────────────────────────────────────────
# F1 — Timing attack admin_api_key : hmac.compare_digest
# ──────────────────────────────────────────────────────────────────────────────


class TestF1TimingAttackAdminKey:
    def test_auth_imports_hmac(self):
        source = AUTH_FILE.read_text(encoding="utf-8")
        assert re.search(r"^import hmac\b", source, re.MULTILINE), (
            "auth.py doit importer hmac pour compare_digest"
        )

    def test_auth_uses_compare_digest(self):
        source = AUTH_FILE.read_text(encoding="utf-8")
        assert "hmac.compare_digest" in source, (
            "auth.py doit utiliser hmac.compare_digest pour la comparaison admin_api_key"
        )

    def test_auth_does_not_use_direct_equality_on_admin_key(self):
        source = AUTH_FILE.read_text(encoding="utf-8")
        # Patterns vulnérables à retirer
        forbidden = re.findall(r"x_admin_key\s*==\s*settings\.admin_api_key", source)
        assert not forbidden, (
            f"Comparaison == vulnérable au timing attack encore présente : {forbidden}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# F2 — Stripe webhook idempotence : catch IntegrityError
# ──────────────────────────────────────────────────────────────────────────────


class TestF2StripeWebhookConcurrentDuplicates:
    def test_billing_catches_integrity_error_on_stripe_event(self):
        source = BILLING_FILE.read_text(encoding="utf-8")
        assert "IntegrityError" in source, (
            "billing.py doit importer et catcher IntegrityError pour le double-webhook"
        )
        # Le pattern doit être dans le contexte du StripeEvent insert
        # Cherche try/except autour de db.add(StripeEvent) ou db.commit
        assert re.search(
            r"db\.add\(StripeEvent",
            source,
        ), "db.add(StripeEvent) doit être présent"
        # Vérifie qu'il y a un except IntegrityError dans le flux webhook
        assert re.search(
            r"except\s+IntegrityError",
            source,
        ), "except IntegrityError requis pour idempotence"

    def test_stripe_webhook_duplicate_returns_ok(self, client, db_session, monkeypatch):
        """Deux webhooks avec même event_id → les 2 retournent 200."""
        import json

        # Bypass signature verification pour le test
        class FakeEvent(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        fake_event = {
            "id": "evt_test_duplicate_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "dup@test.com"},
                    "customer": "cus_test",
                    "subscription": "sub_test_dup",
                    "metadata": {"plan": "pro"},
                }
            },
        }

        def fake_construct_event(payload, sig, secret):
            return fake_event

        import stripe

        monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)

        # Premier webhook
        r1 = client.post(
            "/webhook/stripe",
            content=json.dumps(fake_event).encode(),
            headers={"stripe-signature": "fake"},
        )
        assert r1.status_code == 200

        # Deuxième webhook (même event_id)
        r2 = client.post(
            "/webhook/stripe",
            content=json.dumps(fake_event).encode(),
            headers={"stripe-signature": "fake"},
        )
        # Doit retourner 200 (pas 500) malgré la duplicate UNIQUE constraint
        assert r2.status_code == 200, (
            f"Webhook dupliqué doit retourner 200, pas {r2.status_code}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# F3 — Pré-billing overshoot : cap implicite = remaining budget
# ──────────────────────────────────────────────────────────────────────────────


class TestF3PrebillOvershoot:
    @pytest.mark.asyncio
    async def test_implicit_cap_rejects_call_exceeding_remaining_budget(self):
        """Si budget défini sans max_cost_per_call_usd, un call estimé > budget restant est rejeté."""
        from fastapi import HTTPException

        from core.models import Project
        from services.proxy_dispatcher import check_per_call_cap

        project = Project(
            id=999,
            name="test-cap",
            budget_usd=1.0,
            max_cost_per_call_usd=None,  # pas de cap explicite
        )

        # Payload qui force un coût estimé élevé : modèle cher + beaucoup de tokens
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "x" * 400_000}],
            "max_tokens": 4000,
        }

        with pytest.raises(HTTPException) as exc:
            await check_per_call_cap(project, payload, "gpt-4o")
        assert exc.value.status_code == 400
        assert (
            "cap" in str(exc.value.detail).lower()
            or "budget" in str(exc.value.detail).lower()
        )

    @pytest.mark.asyncio
    async def test_no_cap_if_no_budget_configured(self):
        """Si aucun budget, pas de cap implicite (feature légitime pour usage illimité)."""
        from core.models import Project
        from services.proxy_dispatcher import check_per_call_cap

        project = Project(
            id=998,
            name="unlimited",
            budget_usd=None,
            max_cost_per_call_usd=None,
        )
        payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
        # Ne doit PAS lever
        await check_per_call_cap(project, payload, "gpt-4o")
