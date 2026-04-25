"""TDD Audit #7 — H2 (budget défaut) + M3 (DoS domaine email).

H2: À la création d'un projet (signup free ou checkout pro/agency),
    budget_usd doit être initialisé à Decimal("1.00") (non-None).

M3: _check_domain_rate_limit doit compter par email exact (3/jour)
    au lieu de par domaine (10/jour), pour éviter le DoS @victim.com.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from core.database import Base, get_db
from core.models import Project, SignupAttempt
from main import app


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    # reset in-memory IP rate limit state
    from routes.signup import _ip_signups

    _ip_signups.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── H2 — budget_usd initialisé à 1.00 au signup free ────────────────────────


class TestH2BudgetDefault:
    def test_signup_free_sets_budget_1_usd(self, client, db):
        """H2: signup free → budget_usd == 1.00 (non-None)."""
        with patch("routes.signup.send_onboarding_email"):
            resp = client.post("/api/signup/free", json={"email": "h2free@example.com"})
        assert resp.status_code == 200
        project = db.query(Project).filter_by(name="h2free@example.com").first()
        assert project is not None
        assert project.budget_usd is not None, (
            "budget_usd ne doit pas être None après signup"
        )
        assert float(project.budget_usd) == pytest.approx(1.00)

    def test_signup_free_budget_allows_proxy_usage(self, client, db):
        """H2: un projet créé via signup free peut passer le check_budget_model sans 402."""
        with patch("routes.signup.send_onboarding_email"):
            client.post("/api/signup/free", json={"email": "h2proxy@example.com"})
        project = db.query(Project).filter_by(name="h2proxy@example.com").first()
        assert project is not None
        assert project.budget_usd is not None


class TestH2BillingWebhook:
    @pytest.mark.asyncio
    async def test_checkout_completed_pro_sets_budget_1_usd(self, db):
        """H2: webhook checkout pro → nouveau projet avec budget_usd == 1.00."""
        from routes.billing import _handle_checkout_completed

        session_obj = {
            "payment_status": "paid",
            "customer_details": {"email": "h2pro@example.com"},
            "metadata": {"plan": "pro"},
            "customer": "cus_test",
            "subscription": "sub_test_h2pro",
        }
        with patch("routes.billing.send_onboarding_email"):
            await _handle_checkout_completed(session_obj, db)

        project = db.query(Project).filter_by(name="h2pro@example.com").first()
        assert project is not None
        assert project.budget_usd is not None, (
            "budget_usd ne doit pas être None après checkout pro"
        )
        assert float(project.budget_usd) == pytest.approx(1.00)

    @pytest.mark.asyncio
    async def test_checkout_completed_agency_sets_budget_1_usd(self, db):
        """H2: webhook checkout agency → nouveau projet avec budget_usd == 1.00."""
        from routes.billing import _handle_checkout_completed

        session_obj = {
            "payment_status": "paid",
            "customer_details": {"email": "h2agency@example.com"},
            "metadata": {"plan": "agency"},
            "customer": "cus_test_agency",
            "subscription": "sub_test_h2agency",
        }
        with patch("routes.billing.send_onboarding_email"):
            await _handle_checkout_completed(session_obj, db)

        project = db.query(Project).filter_by(name="h2agency@example.com").first()
        assert project is not None
        assert project.budget_usd is not None, (
            "budget_usd ne doit pas être None après checkout agency"
        )
        assert float(project.budget_usd) == pytest.approx(1.00)

    @pytest.mark.asyncio
    async def test_checkout_new_project_always_has_budget(self, db):
        """H2: nouveau projet créé via checkout → budget_usd == 1.00 (non-None)."""
        from routes.billing import _handle_checkout_completed

        session_obj = {
            "payment_status": "paid",
            "customer_details": {"email": "h2newproj@example.com"},
            "metadata": {"plan": "pro"},
            "customer": "cus_newproj",
            "subscription": "sub_newproj_unique",
        }
        with patch("routes.billing.send_onboarding_email"):
            await _handle_checkout_completed(session_obj, db)

        project = db.query(Project).filter_by(name="h2newproj@example.com").first()
        assert project is not None
        assert project.budget_usd is not None, (
            "budget_usd ne doit pas être None après checkout"
        )
        assert float(project.budget_usd) == pytest.approx(1.00)

    @pytest.mark.asyncio
    async def test_checkout_free_plan_new_project_has_budget(self, db):
        """H2: checkout plan=free → nouveau projet avec budget_usd == 1.00."""
        from routes.billing import _handle_checkout_completed

        session_obj = {
            "payment_status": "paid",
            "customer_details": {"email": "h2freeplan@example.com"},
            "metadata": {"plan": "free"},
            "customer": "cus_freeplan",
            "subscription": "sub_freeplan_unique",
        }
        with patch("routes.billing.send_onboarding_email"):
            await _handle_checkout_completed(session_obj, db)

        project = db.query(Project).filter_by(name="h2freeplan@example.com").first()
        assert project is not None
        assert project.budget_usd is not None
        assert float(project.budget_usd) == pytest.approx(1.00)


# ── M3 — rate limit par email exact (3/jour) ─────────────────────────────────


class TestM3EmailRateLimit:
    def test_check_email_rate_limit_blocks_after_3(self, db):
        """M3: même email → bloqué après 3 SignupAttempts enregistrés dans la même journée."""
        from routes.signup import _check_email_rate_limit, _record_signup_attempt

        email = "victim@example.com"
        # 3 tentatives enregistrées
        _record_signup_attempt("1.1.1.1", email, db)
        _record_signup_attempt("1.1.1.2", email, db)
        _record_signup_attempt("1.1.1.3", email, db)
        # Après 3 enregistrements, la 4ème vérification doit retourner False
        assert _check_email_rate_limit(email, db) is False

    def test_different_emails_same_domain_not_blocked(self, db):
        """M3: 10 emails différents @victim.com ne bloquent pas un 11ème."""
        from routes.signup import _check_email_rate_limit
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Simuler 10 tentatives de 10 adresses différentes du même domaine
        for i in range(10):
            db.add(
                SignupAttempt(
                    ip=f"1.2.3.{i}",
                    email_domain="victim.com",
                    email=f"user{i}@victim.com",
                    created_at=now - timedelta(minutes=i),
                )
            )
        db.commit()

        # Un nouvel utilisateur @victim.com ne doit PAS être bloqué
        result = _check_email_rate_limit("newuser@victim.com", db)
        assert result is True, (
            "Un email différent du même domaine ne doit pas être bloqué"
        )

    def test_same_email_3_attempts_then_blocked(self, db):
        """M3: 3 tentatives enregistrées pour le même email → la 4ème est bloquée."""
        from routes.signup import _check_email_rate_limit
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        email = "spammer@victim.com"
        # Insérer 3 tentatives passées
        for i in range(3):
            db.add(
                SignupAttempt(
                    ip=f"5.5.5.{i}",
                    email_domain="victim.com",
                    email=email,
                    created_at=now - timedelta(minutes=i + 1),
                )
            )
        db.commit()

        # La prochaine tentative avec cet email doit être bloquée
        assert _check_email_rate_limit(email, db) is False

    def test_signup_free_blocks_after_3_same_email(self, client, db):
        """M3: 4 signups avec le même email → le 4ème retourne 429."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        email = "repeat@example.com"
        # Pré-remplir 3 tentatives
        for i in range(3):
            db.add(
                SignupAttempt(
                    ip="9.9.9.9",
                    email_domain="example.com",
                    email=email,
                    created_at=now - timedelta(minutes=i + 1),
                )
            )
        db.commit()

        with patch("routes.signup.send_onboarding_email"):
            resp = client.post("/api/signup/free", json={"email": email})
        assert resp.status_code == 429

    def test_domain_rate_limit_not_triggered_by_different_emails(self, client, db):
        """M3: 10 utilisateurs différents @victim.com ne bloquent pas victim11@victim.com."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Simuler 10 signups de domaine victim.com (emails différents)
        for i in range(10):
            db.add(
                SignupAttempt(
                    ip=f"2.2.2.{i}",
                    email_domain="victim.com",
                    email=f"legit{i}@victim.com",
                    created_at=now - timedelta(minutes=i + 1),
                )
            )
        db.commit()

        with patch("routes.signup.send_onboarding_email"):
            resp = client.post(
                "/api/signup/free", json={"email": "victim11@victim.com"}
            )
        # Doit passer (200), pas être bloqué par le domaine
        assert resp.status_code == 200, (
            f"victim11@victim.com ne doit pas être bloqué par les signups d'autres emails. "
            f"Obtenu: {resp.status_code}"
        )
