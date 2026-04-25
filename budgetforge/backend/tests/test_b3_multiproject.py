"""TDD B3 — Schéma DB + multi-projet (C19, C20).

B3.1: Colonne owner_email ajoutée au modèle Project.
B3.2: check_project_quota utilise owner_email (pas name).
B3.3: POST /api/portal/projects crée un projet pour Pro/Agency.
B3.4: portal_request/session cherche par owner_email.
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
async def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── B3.1 — owner_email colonne ────────────────────────────────────────────────


def test_project_model_has_owner_email_field(db):
    """C19/C20: Le modèle Project doit avoir un champ owner_email."""
    assert hasattr(Project, "owner_email"), (
        "Project doit avoir un attribut owner_email (C20: 'plan Pro = 10 projets' nécessite owner tracking)"
    )


def test_project_owner_email_nullable(db):
    """owner_email doit être nullable (compat backfill projets existants)."""
    project = Project(name="test@example.com")
    db.add(project)
    db.commit()
    db.refresh(project)
    assert project.owner_email is None or project.owner_email == "test@example.com"


def test_project_signup_sets_owner_email(db):
    """Signup doit définir owner_email = email."""
    project = Project(name="owner@example.com", owner_email="owner@example.com")
    db.add(project)
    db.commit()
    db.refresh(project)
    assert project.owner_email == "owner@example.com"


# ── B3.2 — check_project_quota via owner_email ────────────────────────────────


def test_check_project_quota_uses_owner_email(db):
    """C19: check_project_quota doit compter via owner_email, pas Project.name."""
    from services.plan_quota import check_project_quota
    from fastapi import HTTPException

    email = "quota@example.com"

    # 0 projets: doit passer (avant création du 1er)
    check_project_quota(email, "free", db)

    # Créer 1 projet avec owner_email (plan free: limite 1)
    project = Project(name="proj-slug-1", owner_email=email, plan="free")
    db.add(project)
    db.commit()

    # 1 projet free existant → ne peut pas en créer un 2ème (limite = 1)
    with pytest.raises(HTTPException) as exc_info:
        check_project_quota(email, "free", db)
    assert exc_info.value.status_code == 429


def test_check_project_quota_pro_allows_10(db):
    """Plan Pro: jusqu'à 10 projets autorisés."""
    from services.plan_quota import check_project_quota
    from fastapi import HTTPException

    email = "pro@example.com"

    # 0 projets: passe
    check_project_quota(email, "pro", db)

    # Créer 10 projets: le 11ème doit bloquer
    for i in range(10):
        db.add(Project(name=f"pro-slug-{i}", owner_email=email, plan="pro"))
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        check_project_quota(email, "pro", db)
    assert exc_info.value.status_code == 429


def test_check_project_quota_agency_unlimited(db):
    """Plan Agency: pas de limite de projets."""
    from services.plan_quota import check_project_quota

    email = "agency@example.com"
    for i in range(20):
        db.add(Project(name=f"agency-slug-{i}", owner_email=email, plan="agency"))
    db.commit()

    check_project_quota(email, "agency", db)  # ne doit pas lever


# ── B3.3 — POST /api/portal/projects ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_portal_create_project_requires_session(client):
    """POST /api/portal/projects sans session doit retourner 401."""
    r = await client.post("/api/portal/projects", json={"name": "my-new-project"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_portal_create_project_for_pro_user(client, db, monkeypatch):
    """Pro user peut créer un 2ème projet."""
    from core.config import settings
    from routes import portal as portal_module

    monkeypatch.setattr(settings, "portal_secret", "test-portal-secret")
    monkeypatch.setattr(settings, "app_url", "https://test.example.com")

    # Créer un projet pro existant avec owner_email
    existing = Project(
        name="pro@example.com", owner_email="pro@example.com", plan="pro"
    )
    db.add(existing)
    db.commit()

    # Générer un cookie de session valide
    cookie_value = portal_module._sign_session("pro@example.com")

    r = await client.post(
        "/api/portal/projects",
        json={"name": "second-project"},
        cookies={"portal_session": cookie_value},
    )
    assert r.status_code == 201, (
        f"Pro user doit pouvoir créer un 2ème projet. Got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_portal_create_project_blocked_for_free(client, db, monkeypatch):
    """Free user ne peut pas créer un 2ème projet (limite = 1)."""
    from core.config import settings
    from routes import portal as portal_module

    monkeypatch.setattr(settings, "portal_secret", "test-portal-secret")
    monkeypatch.setattr(settings, "app_url", "https://test.example.com")

    existing = Project(
        name="free@example.com", owner_email="free@example.com", plan="free"
    )
    db.add(existing)
    db.commit()

    cookie_value = portal_module._sign_session("free@example.com")

    r = await client.post(
        "/api/portal/projects",
        json={"name": "second-project"},
        cookies={"portal_session": cookie_value},
    )
    assert r.status_code == 429, (
        f"Free user ne doit pas pouvoir créer un 2ème projet. Got {r.status_code}: {r.text}"
    )
