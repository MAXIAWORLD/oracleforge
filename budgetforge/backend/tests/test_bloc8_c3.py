"""
Bloc 8 — C3 : Stripe periodic reconciliation (TDD RED→GREEN)

Vérifie que reconcile_stripe_subscriptions() :
1. Met à jour le plan si Stripe dit pro mais DB dit free
2. Downgrades si subscription Stripe est cancelled
3. Ne fait rien si déjà cohérent
4. L'endpoint admin POST /api/admin/billing/sync répond 200
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from main import app
from core.database import Base, get_db
from core.models import Project


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


def _make_stripe_subscription(
    sub_id: str, customer_id: str, plan_name: str, status: str = "active"
):
    """Build a minimal Stripe subscription mock."""
    sub = MagicMock()
    sub.id = sub_id
    sub.customer = customer_id
    sub.status = status
    item = MagicMock()
    item.price.nickname = plan_name
    item.price.id = f"price_{plan_name}"
    sub.items.data = [item]
    return sub


class TestStripeReconcileService:
    def test_upgrades_project_plan_when_stripe_has_pro(self, test_db):
        """Si Stripe dit pro et DB dit free → plan mis à jour en pro."""
        from services.stripe_reconcile import reconcile_stripe_subscriptions

        project = Project(
            name="test@example.com",
            plan="free",
            stripe_subscription_id="sub_123",
            stripe_customer_id="cus_abc",
        )
        test_db.add(project)
        test_db.commit()

        stripe_sub = _make_stripe_subscription("sub_123", "cus_abc", "pro")

        with patch("services.stripe_reconcile.stripe") as mock_stripe:
            mock_stripe.api_key = ""
            mock_page = MagicMock()
            mock_page.auto_paging_iter.return_value = iter([stripe_sub])
            mock_stripe.Subscription.list.return_value = mock_page

            result = reconcile_stripe_subscriptions(test_db)

        test_db.refresh(project)
        assert project.plan == "pro"
        assert result["updated"] == 1

    def test_downgrades_project_when_subscription_cancelled(self, test_db):
        """Si subscription Stripe annulée → project passe en free."""
        from services.stripe_reconcile import reconcile_stripe_subscriptions

        project = Project(
            name="paid@example.com",
            plan="pro",
            stripe_subscription_id="sub_456",
            stripe_customer_id="cus_def",
        )
        test_db.add(project)
        test_db.commit()

        stripe_sub = _make_stripe_subscription(
            "sub_456", "cus_def", "pro", status="canceled"
        )

        with patch("services.stripe_reconcile.stripe") as mock_stripe:
            mock_stripe.api_key = ""
            mock_page = MagicMock()
            mock_page.auto_paging_iter.return_value = iter([stripe_sub])
            mock_stripe.Subscription.list.return_value = mock_page

            result = reconcile_stripe_subscriptions(test_db)

        test_db.refresh(project)
        assert project.plan == "free"
        assert result["downgraded"] == 1

    def test_no_change_when_already_coherent(self, test_db):
        """Si DB et Stripe cohérents → aucune modification."""
        from services.stripe_reconcile import reconcile_stripe_subscriptions

        project = Project(
            name="ok@example.com",
            plan="pro",
            stripe_subscription_id="sub_789",
            stripe_customer_id="cus_ghi",
        )
        test_db.add(project)
        test_db.commit()

        stripe_sub = _make_stripe_subscription("sub_789", "cus_ghi", "pro")

        with patch("services.stripe_reconcile.stripe") as mock_stripe:
            mock_stripe.api_key = ""
            mock_page = MagicMock()
            mock_page.auto_paging_iter.return_value = iter([stripe_sub])
            mock_stripe.Subscription.list.return_value = mock_page

            result = reconcile_stripe_subscriptions(test_db)

        assert result["updated"] == 0
        assert result["downgraded"] == 0

    def test_skips_subscription_with_no_matching_project(self, test_db):
        """Subscription Stripe sans project local → ignorée (pas d'erreur)."""
        from services.stripe_reconcile import reconcile_stripe_subscriptions

        stripe_sub = _make_stripe_subscription("sub_unknown", "cus_unknown", "agency")

        with patch("services.stripe_reconcile.stripe") as mock_stripe:
            mock_stripe.api_key = ""
            mock_page = MagicMock()
            mock_page.auto_paging_iter.return_value = iter([stripe_sub])
            mock_stripe.Subscription.list.return_value = mock_page

            result = reconcile_stripe_subscriptions(test_db)

        assert result["updated"] == 0
        assert result["skipped"] >= 1


@pytest.fixture
async def admin_client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestBillingSyncEndpoint:
    @pytest.mark.anyio
    async def test_sync_endpoint_requires_admin(self, admin_client):
        """POST /api/admin/billing/sync sans clé → 401."""
        with patch("core.auth.settings") as mock_settings:
            mock_settings.admin_api_key = "secret"
            mock_settings.app_env = "production"
            response = await admin_client.post("/api/admin/billing/sync")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_sync_endpoint_returns_200_with_valid_key(self, admin_client):
        """POST /api/admin/billing/sync avec clé valide → 200 + stats."""
        with (
            patch("core.auth.settings") as mock_auth_settings,
            patch("routes.admin.settings") as mock_billing_settings,
            patch("routes.admin.reconcile_stripe_subscriptions") as mock_reconcile,
        ):
            mock_auth_settings.admin_api_key = "secret"
            mock_auth_settings.app_env = "production"
            mock_billing_settings.stripe_secret_key = "sk_test"
            mock_reconcile.return_value = {"updated": 0, "downgraded": 0, "skipped": 0}
            response = await admin_client.post(
                "/api/admin/billing/sync",
                headers={"X-Admin-Key": "secret"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "updated" in data
