"""TDD Audit #6 — M1 M2 M3 L1.

M1 — Turnstile manquant sur POST /api/checkout/free
M2 — verify=False sur webhooks HTTPS (MITM on-path)
M3 — Code mort playground avec NEXT_PUBLIC_BUDGETFORGE_API_KEY (suppression fichiers)
L1 — 409 portal/projects révèle le nom du projet concurrent
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db


@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── M1 — Turnstile sur /api/checkout/free ────────────────────────────────────


class TestM1CheckoutFreeTurnstile:
    @pytest.mark.asyncio
    async def test_checkout_free_without_token_fails_in_prod(self, client, monkeypatch):
        """M1: POST /api/checkout/free sans token Turnstile en prod → 400."""
        import routes.signup as signup_mod

        # Patch le settings que _verify_turnstile utilise réellement (module signup)
        monkeypatch.setattr(signup_mod.settings, "app_env", "production")
        monkeypatch.setattr(signup_mod.settings, "turnstile_secret_key", "real-secret")

        # Pas de token Turnstile dans le body
        resp = await client.post("/api/checkout/free", json={})
        assert resp.status_code == 400
        assert "captcha" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_checkout_free_with_invalid_token_fails(self, client, monkeypatch):
        """M1: POST /api/checkout/free avec token invalide → 400."""
        from core.config import settings

        monkeypatch.setattr(settings, "turnstile_secret_key", "real-secret")

        with patch(
            "routes.billing._verify_turnstile", new=AsyncMock(return_value=False)
        ):
            resp = await client.post(
                "/api/checkout/free", json={"turnstile_token": "bad-token"}
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_free_with_valid_token_creates_session(
        self, client, monkeypatch
    ):
        """M1: POST /api/checkout/free avec token valide → 200 + checkout_url."""
        import routes.billing as billing_mod

        monkeypatch.setattr(
            billing_mod.settings, "stripe_free_price_id", "price_free_test"
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test-session"

        with patch(
            "routes.billing._verify_turnstile", new=AsyncMock(return_value=True)
        ):
            with patch(
                "routes.billing.stripe.checkout.Session.create",
                return_value=mock_session,
            ):
                resp = await client.post(
                    "/api/checkout/free",
                    json={"turnstile_token": "valid-token"},
                )

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test-session"

    @pytest.mark.asyncio
    async def test_checkout_paid_plan_skips_turnstile(self, client, monkeypatch):
        """M1: POST /api/checkout/pro sans token → Turnstile non vérifié (Stripe gère)."""
        import routes.billing as billing_mod

        monkeypatch.setattr(
            billing_mod.settings, "stripe_pro_price_id", "price_pro_test"
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pro-session"

        turnstile_called = []

        async def track_turnstile(*args, **kwargs):
            turnstile_called.append(True)
            return True

        with patch("routes.billing._verify_turnstile", new=track_turnstile):
            with patch(
                "routes.billing.stripe.checkout.Session.create",
                return_value=mock_session,
            ):
                resp = await client.post("/api/checkout/pro", json={})

        assert resp.status_code == 200
        assert len(turnstile_called) == 0, "Turnstile ne doit pas être vérifié pour pro"

    @pytest.mark.asyncio
    async def test_checkout_free_dev_mode_no_token_passes(self, client, monkeypatch):
        """M1: En dev (pas de secret), checkout/free sans token → pass-through."""
        import routes.billing as billing_mod
        import routes.signup as signup_mod

        monkeypatch.setattr(signup_mod.settings, "app_env", "development")
        monkeypatch.setattr(signup_mod.settings, "turnstile_secret_key", "")
        monkeypatch.setattr(
            billing_mod.settings, "stripe_free_price_id", "price_free_test"
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/dev-session"

        with patch(
            "routes.billing.stripe.checkout.Session.create",
            return_value=mock_session,
        ):
            resp = await client.post("/api/checkout/free", json={})

        assert resp.status_code == 200


# ── M2 — TLS verify=True + SSRF validation ───────────────────────────────────


class TestM2WebhookTLS:
    @pytest.mark.asyncio
    async def test_webhook_uses_tls_verification(self):
        """M2: send_webhook utilise verify=True (pas verify=False) pour HTTPS."""
        from services.alert_service import AlertService

        original_url = "https://hooks.slack.com/services/T00/B00/xxx"

        with patch(
            "services.alert_service.resolve_safe_host",
            return_value=("https://1.2.3.4/services/T00/B00/xxx", "hooks.slack.com"),
        ):
            with patch("services.alert_service.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock()
                mock_client_cls.return_value = mock_client

                await AlertService.send_webhook(
                    url=original_url,
                    project_name="test",
                    used_usd=10.0,
                    budget_usd=100.0,
                )

        # verify=True doit être passé au constructeur AsyncClient
        call_kwargs = (
            mock_client_cls.call_args.kwargs if mock_client_cls.call_args else {}
        )
        call_args = mock_client_cls.call_args
        assert call_args is not None
        # Chercher verify dans kwargs ou args
        all_kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else call_args[1]
        assert all_kwargs.get("verify") is True, (
            f"verify=True attendu, reçu: {all_kwargs.get('verify')}"
        )

    @pytest.mark.asyncio
    async def test_webhook_ssrf_still_blocked(self):
        """M2: resolve_safe_host est toujours appelé — SSRF bloqué même après fix TLS."""
        from services.alert_service import AlertService

        with patch(
            "services.alert_service.resolve_safe_host",
            side_effect=ValueError("Private IP blocked"),
        ):
            result = await AlertService.send_webhook(
                url="https://192.168.1.1/evil",
                project_name="test",
                used_usd=10.0,
                budget_usd=100.0,
            )

        assert result is False, "SSRF doit être bloqué par resolve_safe_host"

    @pytest.mark.asyncio
    async def test_webhook_uses_original_url_not_pinned_ip(self):
        """M2: l'URL originale (hostname) est utilisée pour httpx, pas l'IP pincée."""
        from services.alert_service import AlertService

        original_url = "https://hooks.slack.com/services/T00/B00/xxx"
        pinned_url = "https://1.2.3.4/services/T00/B00/xxx"

        with patch(
            "services.alert_service.resolve_safe_host",
            return_value=(pinned_url, "hooks.slack.com"),
        ):
            with patch("services.alert_service.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock()
                mock_client_cls.return_value = mock_client

                await AlertService.send_webhook(
                    url=original_url,
                    project_name="test",
                    used_usd=10.0,
                    budget_usd=100.0,
                )

        called_url = mock_client.post.call_args[0][0]
        assert called_url == original_url, (
            f"URL originale attendue '{original_url}', reçu '{called_url}'"
        )


# ── L1 — 409 sans fuite du nom ────────────────────────────────────────────────


class TestL1ProjectNameLeak:
    @pytest.mark.asyncio
    async def test_duplicate_project_409_hides_name(self, client, test_db):
        """L1: POST /api/portal/projects avec nom dupliqué → 409 sans le nom dans le message."""
        from core.models import Project
        from routes.portal import _sign_session

        secret_name = "acme-super-secret-project"

        # Créer un projet existant avec ce nom (appartenant à tenant A)
        existing = Project(
            name=secret_name,
            owner_email="tenant-a@example.com",
            plan="pro",
            stripe_customer_id="cus_a",
            stripe_subscription_id="sub_a",
        )
        test_db.add(existing)

        # Créer un projet pour tenant B
        tenant_b = Project(
            name="tenant-b@example.com",
            owner_email="tenant-b@example.com",
            plan="pro",
            stripe_customer_id="cus_b",
            stripe_subscription_id="sub_b",
        )
        test_db.add(tenant_b)
        test_db.commit()

        # Tenant B essaie de créer un projet avec le même nom
        cookie = _sign_session("tenant-b@example.com")
        resp = await client.post(
            "/api/portal/projects",
            json={"name": secret_name},
            cookies={"portal_session": cookie},
        )

        assert resp.status_code == 409
        body = resp.json()
        assert secret_name not in body.get("detail", ""), (
            f"Le nom '{secret_name}' ne doit pas apparaître dans le message 409"
        )
