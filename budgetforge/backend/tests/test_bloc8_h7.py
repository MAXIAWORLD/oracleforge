"""
Bloc 8 — H7 : budget_usd=None silencieux (TDD RED→GREEN)

Projet sans budget → illimité sans warning. Fix :
1. _project_list() expose unlimited_budget=True quand budget_usd=None
2. Budget update endpoint avertit si budget_usd laissé à None
"""

import pytest
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


class TestProjectListUnlimitedFlag:
    def test_project_list_flags_unlimited_when_no_budget(self):
        """_project_list retourne unlimited_budget=True si budget_usd=None."""
        from routes.portal import _project_list

        p = Project(name="user@example.com", plan="free", budget_usd=None)
        result = _project_list([p])
        assert result[0]["unlimited_budget"] is True

    def test_project_list_not_unlimited_when_budget_set(self):
        """_project_list retourne unlimited_budget=False si budget_usd est défini."""
        from routes.portal import _project_list

        p = Project(name="user@example.com", plan="pro", budget_usd=10.0)
        result = _project_list([p])
        assert result[0]["unlimited_budget"] is False

    def test_project_list_exposes_budget_usd(self):
        """_project_list expose budget_usd dans la réponse."""
        from routes.portal import _project_list

        p = Project(name="user@example.com", plan="pro", budget_usd=25.0)
        result = _project_list([p])
        assert result[0]["budget_usd"] == 25.0


class TestBudgetUpdateWarning:
    @pytest.fixture
    async def admin_client(self, test_db):
        def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_budget_update_warns_when_budget_zero(self, admin_client, test_db):
        """PUT /{id}/budget avec budget_usd=0 et action=block retourne un warning."""
        project = Project(name="zero-budget@example.com", plan="free", budget_usd=None)
        test_db.add(project)
        test_db.commit()

        response = await admin_client.put(
            f"/api/projects/{project.id}/budget",
            json={"budget_usd": 0.0, "alert_threshold_pct": 80, "action": "block"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("warning") is not None, (
            "Warning attendu pour budget=0 + action=block"
        )

    @pytest.mark.anyio
    async def test_portal_session_exposes_unlimited_budget(self, admin_client, test_db):
        """GET /api/portal/session retourne unlimited_budget=True si projet sans budget."""
        import time
        import hmac
        import hashlib
        from core.config import settings as real_settings

        project = Project(name="no-budget@example.com", plan="free", budget_usd=None)
        test_db.add(project)
        test_db.commit()

        # Forger un cookie portal valide
        email = "no-budget@example.com"
        iat = str(int(time.time()))
        payload = f"{email}|{iat}"
        secret = (real_settings.portal_secret or "portal-dev-secret").encode()
        sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        cookie = f"{email}|{iat}|{sig}"

        response = await admin_client.get(
            "/api/portal/session",
            cookies={"portal_session": cookie},
        )
        assert response.status_code == 200
        projects = response.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["unlimited_budget"] is True
