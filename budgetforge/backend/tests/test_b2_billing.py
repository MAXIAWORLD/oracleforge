"""TDD B2 — Stripe + paiement fiable (C14, C15, C16, C21, H25).

B2.1: Upgrade flow doit upsert le projet existant, pas créer un doublon.
B2.2: Subscription deleted doit révoquer la clé API + reset budget.
B2.3: Webhook HTTPS Slack/Office ne doit pas échouer à cause du pinning IP.
B2.4: Reconcile doit utiliser price_id env var, pas string match fragile.
"""

import pytest
import secrets
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Project


@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=engine)


# ── B2.1 — Upgrade flow (C14, C15) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_checkout_upgrades_existing_free_project(db):
    """C14: si projet free existe avec cet email, il doit être upgradé, pas dupliqué."""
    from routes.billing import _handle_checkout_completed

    # Créer un projet free existant
    free_project = Project(name="user@example.com", plan="free")
    db.add(free_project)
    db.commit()
    original_api_key = free_project.api_key
    original_id = free_project.id

    session_data = {
        "id": "cs_test_123",
        "customer": "cus_test_123",
        "subscription": "sub_pro_456",
        "customer_details": {"email": "user@example.com"},
        "metadata": {"plan": "pro"},
    }

    with patch("routes.billing.send_onboarding_email"):
        await _handle_checkout_completed(session_data, db)

    # Vérifier upsert (pas de nouveau projet)
    projects = db.query(Project).filter(Project.name == "user@example.com").all()
    assert len(projects) == 1, f"Attendu 1 projet, got {len(projects)}"
    assert projects[0].id == original_id
    assert projects[0].plan == "pro"
    assert projects[0].stripe_customer_id == "cus_test_123"
    assert projects[0].stripe_subscription_id == "sub_pro_456"
    # La clé API reste la même (pas de rotation à l'upgrade)
    assert projects[0].api_key == original_api_key


@pytest.mark.asyncio
async def test_checkout_creates_new_project_if_no_existing(db):
    """C15: si aucun projet free, créer un nouveau projet."""
    from routes.billing import _handle_checkout_completed

    session_data = {
        "id": "cs_new_456",
        "customer": "cus_new_789",
        "subscription": "sub_new_000",
        "customer_details": {"email": "newuser@example.com"},
        "metadata": {"plan": "pro"},
    }

    with patch("routes.billing.send_onboarding_email"):
        await _handle_checkout_completed(session_data, db)

    projects = db.query(Project).filter(Project.name == "newuser@example.com").all()
    assert len(projects) == 1
    assert projects[0].plan == "pro"
    assert projects[0].stripe_customer_id == "cus_new_789"


@pytest.mark.asyncio
async def test_checkout_idempotent_existing_subscription(db):
    """Idempotence: si subscription_id déjà connu, mise à jour du plan sans doublon."""
    from routes.billing import _handle_checkout_completed

    existing = Project(
        name="sub@example.com",
        plan="free",
        stripe_subscription_id="sub_existing_123",
    )
    db.add(existing)
    db.commit()

    session_data = {
        "id": "cs_dup_789",
        "customer": "cus_dup_789",
        "subscription": "sub_existing_123",
        "customer_details": {"email": "sub@example.com"},
        "metadata": {"plan": "agency"},
    }

    with patch("routes.billing.send_onboarding_email"):
        await _handle_checkout_completed(session_data, db)

    projects = db.query(Project).all()
    assert len(projects) == 1
    assert projects[0].plan == "agency"


# ── B2.2 — Subscription deleted (C21) ────────────────────────────────────────


def test_subscription_deleted_revokes_api_key(db):
    """C21: downgrade doit générer une nouvelle clé API (l'ancienne est révoquée)."""
    from routes.billing import _handle_subscription_deleted

    original_key = f"bf-{secrets.token_urlsafe(32)}"
    project = Project(
        name="canceller@example.com",
        plan="pro",
        budget_usd=500.0,
        stripe_subscription_id="sub_cancel_abc",
        api_key=original_key,
    )
    db.add(project)
    db.commit()

    sub_data = {"id": "sub_cancel_abc"}

    with patch("routes.billing.send_downgrade_email"):
        _handle_subscription_deleted(sub_data, db)

    db.refresh(project)
    assert project.plan == "free"
    assert project.api_key != original_key, "La clé API doit être rotée au downgrade"
    assert project.api_key.startswith("bf-"), "Nouvelle clé doit commencer par bf-"
    assert project.previous_api_key == original_key, "Ancienne clé doit être préservée"
    assert project.budget_usd is None, "Budget doit être reset à None au downgrade"


def test_subscription_deleted_resets_budget(db):
    """C21: budget_usd reset à None après annulation abonnement."""
    from routes.billing import _handle_subscription_deleted

    project = Project(
        name="budget@example.com",
        plan="agency",
        budget_usd=10_000.0,
        stripe_subscription_id="sub_budget_xyz",
    )
    db.add(project)
    db.commit()

    with patch("routes.billing.send_downgrade_email"):
        _handle_subscription_deleted({"id": "sub_budget_xyz"}, db)

    db.refresh(project)
    assert project.budget_usd is None


# ── B2.3 — Webhook HTTPS Slack/Office (C16) ──────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_https_slack_does_not_fail_cert_pinning():
    """C16: Le webhook Slack HTTPS ne doit pas échouer à cause du pinning IP.

    Avant le fix: resolve_safe_host retourne une URL IP → httpx vérifie le cert
    contre l'IP → TLS error car le cert est pour hooks.slack.com.

    Après le fix: valider SSRF via resolve_safe_host, mais envoyer à l'URL originale.
    """
    from services.alert_service import AlertService

    slack_url = "https://hooks.slack.com/services/T000/B000/xxxxx"

    # Simuler resolve_safe_host qui valide le hostname (SSRF check)
    # mais retourne URL pincée IP (comportement actuel)
    mocked_pinned_url = "https://34.36.12.99/services/T000/B000/xxxxx"
    mocked_host_header = "hooks.slack.com"

    sent_url = None

    async def mock_post(url, **kwargs):
        nonlocal sent_url
        sent_url = url
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with patch(
        "services.alert_service.resolve_safe_host",
        return_value=(mocked_pinned_url, mocked_host_header),
    ):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_client_cls.return_value = mock_client

            result = await AlertService.send_webhook(
                slack_url, "test-project", 80.0, 100.0
            )

    # L'URL envoyée doit être l'URL originale, pas l'IP pincée
    assert sent_url == slack_url, (
        f"L'URL envoyée doit être l'URL originale '{slack_url}', "
        f"pas l'IP pincée '{mocked_pinned_url}'. Got: '{sent_url}'"
    )
    assert result is True


@pytest.mark.asyncio
async def test_webhook_ssrf_still_blocked():
    """B2.3: La validation SSRF doit toujours fonctionner."""
    from services.alert_service import AlertService

    with patch(
        "services.alert_service.resolve_safe_host",
        side_effect=ValueError("IP 127.0.0.1 dans plage bloquée"),
    ):
        result = await AlertService.send_webhook(
            "http://127.0.0.1/evil", "proj", 10.0, 100.0
        )

    assert result is False


# ── B2.4 — Reconcile price_id (H25) ──────────────────────────────────────────


def test_plan_from_price_id_uses_env_vars():
    """H25: La détection du plan doit utiliser les price_id env vars, pas string match."""
    from services.stripe_reconcile import _plan_from_price_id
    from core.config import settings

    with patch.object(settings, "stripe_pro_price_id", "price_abc123"):
        with patch.object(settings, "stripe_agency_price_id", "price_def456"):
            assert _plan_from_price_id("price_abc123") == "pro"
            assert _plan_from_price_id("price_def456") == "agency"
            assert _plan_from_price_id("price_unknown") == "free"


def test_plan_from_price_id_fallback_nickname():
    """H25: Si price_id ne matche pas, fallback sur nickname (compat)."""
    from services.stripe_reconcile import _plan_from_subscription

    sub = MagicMock()
    item = MagicMock()
    item.price.id = "price_XYZ_unknown"
    item.price.nickname = "Pro Monthly"
    sub.items.data = [item]

    with patch("services.stripe_reconcile.settings") as mock_settings:
        mock_settings.stripe_pro_price_id = "price_prod_pro_123"
        mock_settings.stripe_agency_price_id = "price_prod_agency_456"
        plan = _plan_from_subscription(sub)

    assert plan == "pro"
