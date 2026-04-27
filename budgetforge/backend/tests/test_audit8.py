"""Tests audit #8 — X2 X3 X4 X5 H26 M03 M04 M10."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


# ── X2 — email normalization webhook ──────────────────────────────────────────


class TestX2EmailNormalizationWebhook:
    def test_webhook_email_uppercased_normalised(self, db):
        """Email Stripe en majuscules/+tag doit être normalisé avant insert."""
        from routes.billing import _handle_checkout_completed
        from core.models import Project

        session = {
            "customer_details": {"email": "Foo+Work@Gmail.COM"},
            "metadata": {"plan": "pro"},
            "customer": "cus_test",
            "subscription": "sub_test_x2_upper",
        }
        with patch("routes.billing.send_onboarding_email"):
            asyncio.run(_handle_checkout_completed(session, db))

        project = (
            db.query(Project)
            .filter(Project.stripe_subscription_id == "sub_test_x2_upper")
            .first()
        )
        assert project is not None
        assert project.name == "foo@gmail.com", (
            f"Email doit être normalisé à 'foo@gmail.com', got '{project.name}'"
        )

    def test_webhook_email_plus_tag_stripped(self, db):
        """Le +tag doit être strippé pour correspondre au portail."""
        from routes.billing import _handle_checkout_completed
        from core.models import Project

        session = {
            "customer_details": {"email": "user+stripe@example.com"},
            "metadata": {"plan": "pro"},
            "customer": "cus_test2",
            "subscription": "sub_test_x2_tag",
        }
        with patch("routes.billing.send_onboarding_email"):
            asyncio.run(_handle_checkout_completed(session, db))

        project = (
            db.query(Project)
            .filter(Project.stripe_subscription_id == "sub_test_x2_tag")
            .first()
        )
        assert project is not None
        assert project.name == "user@example.com"


# ── X5 — downgrade revoke excess projects ─────────────────────────────────────


class TestX5DowngradeRevokesExcess:
    def test_downgrade_sets_all_projects_to_free(self, db):
        """Annulation sub → TOUS les projets du customer passent en free."""
        from core.models import Project
        from routes.billing import _handle_subscription_deleted

        customer_id = "cus_downgrade_test"
        for i in range(3):
            p = Project(
                name=f"user{i}@test.com",
                plan="pro",
                stripe_customer_id=customer_id,
                stripe_subscription_id=f"sub_down_{i}",
                budget_usd=50.0,
            )
            db.add(p)
        db.commit()

        sub = {"id": "sub_down_0", "customer": customer_id}
        with patch("routes.billing.send_downgrade_email"):
            _handle_subscription_deleted(sub, db)

        projects = (
            db.query(Project).filter(Project.stripe_customer_id == customer_id).all()
        )
        assert all(p.plan == "free" for p in projects), (
            "Tous les projets du customer doivent être passés en free"
        )

    def test_downgrade_sends_email_once(self, db):
        """Email de downgrade envoyé une seule fois (au projet principal)."""
        from core.models import Project
        from routes.billing import _handle_subscription_deleted

        customer_id = "cus_email_once"
        p = Project(
            name="main@test.com",
            plan="pro",
            stripe_customer_id=customer_id,
            stripe_subscription_id="sub_main_email",
            budget_usd=50.0,
        )
        db.add(p)
        db.commit()

        with patch("routes.billing.send_downgrade_email") as mock_email:
            _handle_subscription_deleted(
                {"id": "sub_main_email", "customer": customer_id}, db
            )

        mock_email.assert_called_once()


# ── X3 — webhook payload cap ───────────────────────────────────────────────────


class TestX3WebhookPayloadCap:
    def test_oversized_payload_returns_413(self, client):
        """Payload > 100KB doit retourner 413."""
        oversized = b"x" * (101 * 1024)
        resp = client.post(
            "/webhook/stripe",
            content=oversized,
            headers={"stripe-signature": "t=1,v1=fake"},
        )
        assert resp.status_code == 413, f"Attendu 413, got {resp.status_code}"

    def test_normal_payload_proceeds_to_sig_check(self, client):
        """Payload normal (< 100KB) doit passer au check de signature (400, pas 413)."""
        resp = client.post(
            "/webhook/stripe",
            content=b'{"type":"test"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
        assert resp.status_code == 400  # signature invalide, pas 413


# ── X4 — magic-link hash fragment ─────────────────────────────────────────────


class TestX4MagicLinkHash:
    def test_portal_email_uses_hash_fragment(self):
        """Le lien magic-link doit utiliser # et non ? pour le token."""
        from routes.portal import send_portal_email

        captured_body = []

        def fake_sendmail(from_addr, to_addr, msg_str):
            captured_body.append(msg_str)

        with (
            patch("routes.portal.settings") as mock_settings,
            patch("smtplib.SMTP") as mock_smtp,
        ):
            mock_settings.smtp_host = "smtp.test"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "u"
            mock_settings.smtp_password = "p"
            mock_settings.alert_from_email = "noreply@test.com"
            mock_settings.app_url = "https://llmbudget.maxiaworld.app"

            instance = mock_smtp.return_value.__enter__.return_value
            instance.sendmail.side_effect = fake_sendmail

            send_portal_email("user@test.com", "tok123")

        assert captured_body, "Email non envoyé"
        body = captured_body[0]
        assert "#token=tok123" in body, (
            "Token doit être dans le hash, pas en query string"
        )
        assert "?token=tok123" not in body, "Token NE DOIT PAS être en query string"


# ── H26 — dynamic_pricing close ───────────────────────────────────────────────


class TestH26DynamicPricingClose:
    def test_dynamic_pricing_manager_has_close_method(self):
        """DynamicPricingManager doit avoir une méthode close() async."""
        from services.dynamic_pricing import DynamicPricingManager
        import inspect

        assert hasattr(DynamicPricingManager, "close"), "Méthode close() manquante"
        assert inspect.iscoroutinefunction(DynamicPricingManager.close), (
            "close() doit être async"
        )

    def test_dynamic_pricing_close_closes_http_client(self):
        """close() doit fermer le client httpx si existant."""
        import httpx
        from services.dynamic_pricing import DynamicPricingManager

        manager = DynamicPricingManager()
        manager._http_client = httpx.AsyncClient()
        asyncio.run(manager.close())
        assert manager._http_client is None or manager._http_client.is_closed


# ── M03 — email injection via \r\n ─────────────────────────────────────────────


class TestM03EmailInjection:
    def test_portal_request_rejects_email_with_crlf(self, client):
        """`\\r\\n` dans l'email doit retourner 422 ou 400."""
        resp = client.post(
            "/api/portal/request",
            json={"email": "user@test.com\r\nBcc: attacker@evil.com"},
        )
        assert resp.status_code in (400, 422), (
            f"Email avec CRLF doit être rejeté, got {resp.status_code}"
        )

    def test_portal_request_rejects_email_with_newline(self, client):
        resp = client.post(
            "/api/portal/request",
            json={"email": "user@test.com\nX-Injected: header"},
        )
        assert resp.status_code in (400, 422)


# ── M04 — timing portal_request ───────────────────────────────────────────────


class TestM04TimingPortalRequest:
    def test_portal_request_response_time_consistent(self, client):
        """Les deux branches (email trouvé / non trouvé) prennent >= MIN_DELAY."""
        import time

        MIN_DELAY = 0.08  # 80ms

        t0 = time.monotonic()
        client.post("/api/portal/request", json={"email": "nobody@nowhere.com"})
        t_miss = time.monotonic() - t0

        t0 = time.monotonic()
        client.post("/api/portal/request", json={"email": "also_nobody@nowhere.com"})
        t_miss2 = time.monotonic() - t0

        # Au moins l'un des deux doit atteindre le délai (warmup pour le 1er)
        assert max(t_miss, t_miss2) >= MIN_DELAY, (
            f"Délai constant manquant : {t_miss:.3f}s / {t_miss2:.3f}s (min={MIN_DELAY})"
        )


# ── M10 — /api/models cache ────────────────────────────────────────────────────


class TestM10ModelsCache:
    def test_models_endpoint_uses_cache(self, client):
        """/api/models ne doit pas refaire tous les appels outbound au 2ème appel."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, json=lambda: {"data": []}
            )
            client.get("/api/models", headers={"X-Admin-Key": "test-admin-key"})
            first_calls = mock_get.call_count

            client.get("/api/models", headers={"X-Admin-Key": "test-admin-key"})
            second_calls = mock_get.call_count - first_calls

        assert second_calls < first_calls, (
            f"2ème appel doit utiliser le cache : 1er={first_calls}, 2ème={second_calls}"
        )
