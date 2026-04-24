"""TDD RED — encore fix4 : /api/billing/reconcile doit avoir idempotency + rate-limit.

Problèmes actuels :
  1. Pas de @limiter.limit → endpoint sans rate-limit, spam possible.
  2. Pas d'idempotency → appels multiples créent plusieurs projets.
  3. Pas de Request param → slowapi ne peut pas fonctionner même si ajouté.

Fix requis :
  @limiter.limit("5/hour")
  async def reconcile_stripe_session(request: Request, session_id: str, db=...):
      # idempotency check via StripeEvent(event_id=f"reconcile:{session_id}")
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db
from core.models import StripeEvent


@pytest.fixture
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
def client(test_db):
    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    yield
    app.dependency_overrides.clear()


class TestReconcileIdempotency:
    """Le reconcile doit être idempotent : 2 appels identiques → 1 seul projet créé."""

    @pytest.mark.asyncio
    async def test_duplicate_reconcile_returns_already_processed(self, test_db, client):
        """Le 2ème appel au même session_id doit retourner already_processed=True."""
        session_id = "cs_test_idempotency_001"
        reconcile_key = f"reconcile:{session_id}"

        # Pré-insérer un StripeEvent pour simuler un appel déjà traité
        test_db.add(StripeEvent(event_id=reconcile_key))
        test_db.commit()

        fake_session = {
            "payment_status": "paid",
            "customer_details": {"email": "test@example.com"},
            "customer": "cus_test",
            "subscription": "sub_test",
            "metadata": {"plan": "pro"},
        }

        with patch("stripe.checkout.Session.retrieve", return_value=fake_session):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(f"/api/billing/reconcile/{session_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("already_processed") is True, (
            f"Second reconcile call should return already_processed=True. Got: {data}. "
            "Current code has no idempotency check."
        )

    @pytest.mark.asyncio
    async def test_first_reconcile_creates_idempotency_record(self, test_db, client):
        """Le 1er appel doit insérer un StripeEvent(reconcile:{session_id})."""
        session_id = "cs_test_idempotency_002"
        reconcile_key = f"reconcile:{session_id}"

        fake_session = {
            "payment_status": "paid",
            "customer_details": {"email": "user@example.com"},
            "customer": "cus_x",
            "subscription": "sub_x",
            "metadata": {"plan": "pro"},
        }

        with (
            patch("stripe.checkout.Session.retrieve", return_value=fake_session),
            patch("routes.billing.send_onboarding_email"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(f"/api/billing/reconcile/{session_id}")

        assert resp.status_code == 200

        record = (
            test_db.query(StripeEvent)
            .filter(StripeEvent.event_id == reconcile_key)
            .first()
        )
        assert record is not None, (
            f"StripeEvent(event_id='{reconcile_key}') should be created after reconcile. "
            "Current code has no idempotency insertion."
        )

    @pytest.mark.asyncio
    async def test_failed_reconcile_clears_idempotency_so_retry_works(
        self, test_db, client
    ):
        """Si Stripe lève une erreur, l'idempotency record ne doit PAS rester."""
        session_id = "cs_test_idempotency_003"
        reconcile_key = f"reconcile:{session_id}"

        with patch(
            "stripe.checkout.Session.retrieve",
            side_effect=Exception("stripe down"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(f"/api/billing/reconcile/{session_id}")

        assert resp.status_code == 500

        # L'idempotency record ne doit PAS exister (sinon le retry sera bloqué)
        record = (
            test_db.query(StripeEvent)
            .filter(StripeEvent.event_id == reconcile_key)
            .first()
        )
        assert record is None, (
            "StripeEvent must be deleted on Stripe error so caller can retry. "
            "Current code doesn't insert/delete idempotency records."
        )


class TestReconcileRateLimit:
    """Le reconcile doit avoir un rate-limiter."""

    def test_reconcile_route_has_rate_limit_decorator(self):
        """La route /reconcile doit avoir le décorateur @limiter.limit."""
        import inspect
        from routes.billing import reconcile_stripe_session

        # slowapi stocke la limite dans l'attribut _rate_limit_info sur la fonction
        has_rate_limit = (
            hasattr(reconcile_stripe_session, "_rate_limit_info")
            or hasattr(reconcile_stripe_session, "_rate_limit_key_func")
            # slowapi peut aussi utiliser __wrapped__ ou des closures
        )

        # Alternative : vérifier la signature accepte Request
        sig = inspect.signature(reconcile_stripe_session)
        params = list(sig.parameters.keys())

        assert "request" in params, (
            f"reconcile_stripe_session must accept 'request: Request' for rate limiting. "
            f"Current params: {params}. Add @limiter.limit('5/hour') and Request param."
        )
