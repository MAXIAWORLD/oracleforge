"""TDD — Audit 24/04/2026 : corrections B1→B6 (findings hauts).

Écrits en ROUGE avant toute implémentation.
"""

import pathlib
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock, AsyncMock

from main import app
from core.database import Base, get_db
from core.models import Project, SignupAttempt

# ── Fixtures partagées ────────────────────────────────────────────────────────


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


# ── B1 — Rate limiting symétrique sur tous les endpoints proxy ────────────────


class TestB1RateLimitingSymmetric:
    def test_all_proxy_endpoints_have_rate_limit(self):
        """Tous les endpoints proxy (sauf health) doivent avoir @limiter.limit."""
        proxy_file = pathlib.Path(__file__).parent.parent / "routes" / "proxy.py"
        content = proxy_file.read_text()

        endpoints = [
            "/proxy/anthropic/v1/messages",
            "/proxy/google/v1/chat/completions",
            "/proxy/deepseek/v1/chat/completions",
            "/proxy/openrouter/v1/chat/completions",
            "/proxy/mistral/v1/chat/completions",
            "/proxy/ollama/api/chat",
            "/proxy/ollama/v1/chat/completions",
            "/proxy/together/v1/chat/completions",
            "/proxy/azure-openai/v1/chat/completions",
            "/proxy/aws-bedrock/v1/chat/completions",
        ]

        lines = content.splitlines()
        for endpoint in endpoints:
            # Trouver la ligne avec @router.post(endpoint)
            for i, line in enumerate(lines):
                if f'"{endpoint}"' in line or f"'{endpoint}'" in line:
                    # Vérifier qu'une des 3 lignes précédentes a @limiter.limit
                    context = "\n".join(lines[max(0, i - 3) : i + 1])
                    assert "@limiter.limit" in context, (
                        f"Endpoint {endpoint} manque @limiter.limit"
                    )
                    break
            else:
                pytest.fail(f"Endpoint {endpoint} introuvable dans proxy.py")

    def test_all_proxy_handlers_have_request_param(self):
        """Tous les handlers proxy avec @limiter.limit doivent accepter request: Request."""
        proxy_file = pathlib.Path(__file__).parent.parent / "routes" / "proxy.py"
        content = proxy_file.read_text()

        endpoints = [
            "proxy_anthropic",
            "proxy_google",
            "proxy_deepseek",
            "proxy_openrouter",
            "proxy_mistral",
            "proxy_ollama_chat",
            "proxy_ollama_openai",
            "proxy_together",
            "proxy_azure_openai",
            "proxy_aws_bedrock",
        ]

        for fn_name in endpoints:
            # La signature de la fonction doit contenir request: Request
            import re

            pattern = rf"async def {fn_name}\([^)]*request: Request"
            assert re.search(pattern, content, re.DOTALL), (
                f"Handler {fn_name} manque 'request: Request' dans sa signature"
            )


# ── B2 — Cookie portal avec iat (révocable) ───────────────────────────────────


class TestB2PortalCookieIat:
    def test_new_sign_session_includes_iat(self):
        """_sign_session doit inclure un timestamp (iat) dans le cookie."""
        from routes.portal import _sign_session

        cookie = _sign_session("user@example.com")
        # Nouveau format: "{email}|{iat}|{sig}"
        parts = cookie.split("|")
        assert len(parts) == 3, f"Format attendu 'email|iat|sig', obtenu: {cookie!r}"
        email, iat_str, sig = parts
        assert email == "user@example.com"
        assert iat_str.isdigit(), f"iat doit être un entier, obtenu: {iat_str!r}"

    def test_new_verify_session_accepts_valid_cookie(self):
        """_verify_session doit accepter un cookie au nouveau format."""
        from routes.portal import _sign_session, _verify_session

        cookie = _sign_session("user@example.com")
        result = _verify_session(cookie)
        assert result == "user@example.com"

    def test_old_format_cookie_rejected(self):
        """Un cookie à l'ancien format (sans iat) doit être rejeté."""
        import hmac
        import hashlib
        from routes.portal import _portal_secret, _verify_session

        # Ancien format: "{email}.{sig}"
        email = "user@example.com"
        sig = hmac.new(_portal_secret(), email.encode(), hashlib.sha256).hexdigest()
        old_cookie = f"{email}.{sig}"
        result = _verify_session(old_cookie)
        assert result is None, "Ancien format cookie doit être rejeté"

    def test_tampered_cookie_rejected(self):
        """Un cookie avec signature incorrecte doit être rejeté."""
        from routes.portal import _sign_session, _verify_session

        cookie = _sign_session("user@example.com")
        parts = cookie.split("|")
        tampered = f"{parts[0]}|{parts[1]}|invalidsig"
        assert _verify_session(tampered) is None


# ── B3 — Stripe webhook idempotence ───────────────────────────────────────────


class TestB3StripeWebhookIdempotence:
    def _fake_event(self, event_id: str = "evt_test_001", plan: str = "free") -> dict:
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_001",
                    "customer": "cus_001",
                    "subscription": None,  # free plan: pas de subscription
                    "customer_details": {"email": "newuser@example.com"},
                    "customer_email": None,
                    "metadata": {"plan": plan},
                }
            },
        }

    @pytest.mark.asyncio
    async def test_same_event_twice_creates_only_one_project(self, client, test_db):
        """Même event Stripe envoyé 2 fois → 1 seul projet créé (idempotence)."""
        fake_event = self._fake_event("evt_idempotent_001", "free")

        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            with patch(
                "routes.billing.send_onboarding_email",
                new_callable=AsyncMock,
            ):
                r1 = await client.post(
                    "/webhook/stripe",
                    content=b"fake-payload",
                    headers={"stripe-signature": "t=1,v1=sig"},
                )
                r2 = await client.post(
                    "/webhook/stripe",
                    content=b"fake-payload",
                    headers={"stripe-signature": "t=1,v1=sig"},
                )

        assert r1.status_code == 200
        assert r2.status_code == 200

        count = (
            test_db.query(Project).filter(Project.name == "newuser@example.com").count()
        )
        assert count == 1, f"Attendu 1 projet, trouvé {count} (pas d'idempotence)"

    @pytest.mark.asyncio
    async def test_different_events_both_processed(self, client, test_db):
        """Deux events distincts doivent créer deux projets."""
        for i, email in enumerate(["a@example.com", "b@example.com"]):
            fake_event = {
                "id": f"evt_distinct_{i}",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": f"cs_test_{i}",
                        "customer": f"cus_{i}",
                        "subscription": None,
                        "customer_details": {"email": email},
                        "customer_email": None,
                        "metadata": {"plan": "free"},
                    }
                },
            }
            with patch("stripe.Webhook.construct_event", return_value=fake_event):
                with patch(
                    "routes.billing.send_onboarding_email",
                    new_callable=AsyncMock,
                ):
                    r = await client.post(
                        "/webhook/stripe",
                        content=b"fake-payload",
                        headers={"stripe-signature": "t=1,v1=sig"},
                    )
            assert r.status_code == 200

        count = (
            test_db.query(Project)
            .filter(Project.name.in_(["a@example.com", "b@example.com"]))
            .count()
        )
        assert count == 2


# ── B4 — Endpoint réconciliation Stripe ───────────────────────────────────────


class TestB4StripeReconcile:
    @pytest.mark.asyncio
    async def test_reconcile_creates_project_for_paid_session(self, client, test_db):
        """GET /api/billing/reconcile/{session_id} crée le projet si paiement confirmé."""
        fake_session = MagicMock()
        fake_session.get = lambda k, d=None: {
            "payment_status": "paid",
            "id": "cs_reconcile_001",
            "customer": "cus_rec_001",
            "subscription": None,
            "customer_details": {"email": "reconcile@example.com"},
            "customer_email": None,
            "metadata": {"plan": "pro"},
        }.get(k, d)
        # Also handle dict-style access for _handle_checkout_completed
        fake_session.__getitem__ = lambda self, k: {
            "payment_status": "paid",
            "id": "cs_reconcile_001",
            "customer": "cus_rec_001",
            "subscription": None,
            "customer_details": {"email": "reconcile@example.com"},
            "customer_email": None,
            "metadata": {"plan": "pro"},
        }[k]

        with patch("stripe.checkout.Session.retrieve", return_value=fake_session):
            with patch(
                "routes.billing.send_onboarding_email",
                new_callable=AsyncMock,
            ):
                r = await client.get("/api/billing/reconcile/cs_reconcile_001")

        assert r.status_code == 200
        assert r.json().get("ok") is True

    @pytest.mark.asyncio
    async def test_reconcile_returns_402_for_unpaid_session(self, client):
        """Réconciliation d'une session non payée → 402."""
        fake_session = MagicMock()
        fake_session.get = lambda k, d=None: {
            "payment_status": "unpaid",
        }.get(k, d)

        with patch("stripe.checkout.Session.retrieve", return_value=fake_session):
            r = await client.get("/api/billing/reconcile/cs_unpaid_001")

        assert r.status_code == 402

    @pytest.mark.asyncio
    async def test_reconcile_endpoint_exists(self, client):
        """L'endpoint /api/billing/reconcile/{session_id} doit exister (pas 404/405)."""
        with patch(
            "stripe.checkout.Session.retrieve", side_effect=Exception("stripe error")
        ):
            r = await client.get("/api/billing/reconcile/cs_test")
        # 404 = endpoint n'existe pas, 405 = mauvaise méthode
        assert r.status_code not in (404, 405), (
            f"Endpoint réconciliation absent (status={r.status_code})"
        )


# ── B5 — Warning overshoot budget ────────────────────────────────────────────


class TestB5BudgetOvershootWarning:
    @pytest.mark.asyncio
    async def test_set_budget_without_max_cost_returns_warning(self, client):
        """set_budget sans max_cost_per_call_usd doit retourner un warning."""
        proj = (await client.post("/api/projects", json={"name": "no-max-cost"})).json()
        resp = await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={
                "budget_usd": 10.0,
                "alert_threshold_pct": 80,
                "action": "block",
                # max_cost_per_call_usd intentionnellement absent
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("warning"), (
            "Un warning doit être présent si max_cost_per_call_usd est absent"
        )
        assert (
            "max_cost" in data["warning"].lower()
            or "per_call" in data["warning"].lower()
            or "overshoot" in data["warning"].lower()
            or "cap" in data["warning"].lower()
        )

    @pytest.mark.asyncio
    async def test_set_budget_with_max_cost_no_warning(self, client):
        """set_budget avec max_cost_per_call_usd ne doit pas retourner de warning overshoot."""
        proj = (
            await client.post("/api/projects", json={"name": "with-max-cost"})
        ).json()
        resp = await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={
                "budget_usd": 10.0,
                "alert_threshold_pct": 80,
                "action": "block",
                "max_cost_per_call_usd": 1.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Soit pas de warning, soit le warning existant (budget_usd=0) ne s'applique pas ici
        warning = data.get("warning")
        if warning:
            # Le seul warning autorisé est celui de budget=0 (pas overshoot)
            assert "max_cost" not in warning.lower()


# ── B6 — Rate limit signup par domaine email ─────────────────────────────────


class TestB6SignupDomainRateLimit:
    @pytest.mark.asyncio
    async def test_same_domain_rate_limit_blocks_after_10(self, client, test_db):
        """11 signups depuis le même domaine email → le 11ème est bloqué (429)."""
        domain = "test-domain-ratelimit.com"

        # 10 signups acceptés
        for i in range(10):
            # Insérer directement dans SignupAttempt pour simuler les tentatives passées
            pass

        # Insérer 10 tentatives passées pour ce domaine dans la DB
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(10):
            attempt = SignupAttempt(
                ip=f"1.2.3.{i}",
                email_domain=domain,
                created_at=now - timedelta(minutes=i),
            )
            test_db.add(attempt)
        test_db.commit()

        # Le 11ème signup de ce domaine doit être bloqué
        with patch("routes.signup.send_onboarding_email"):
            resp = await client.post(
                "/api/signup/free",
                json={"email": f"user11@{domain}"},
            )

        assert resp.status_code == 429, (
            f"Le 11ème signup du même domaine devrait être bloqué, obtenu {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_different_domains_not_blocked(self, client, test_db):
        """Signups depuis des domaines différents ne se bloquent pas mutuellement."""
        with patch("routes.signup.send_onboarding_email"):
            for i in range(3):
                resp = await client.post(
                    "/api/signup/free",
                    json={"email": f"user@domain{i}.com"},
                )
                assert resp.status_code == 200, (
                    f"domain{i}.com devrait être accepté, obtenu {resp.status_code}"
                )
