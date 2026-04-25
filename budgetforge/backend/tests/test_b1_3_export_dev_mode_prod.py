"""TDD B1.3 — Export full DB blocked en dev mode prod (audit C17).

Bug audit: routes/export.py:44-52 a:
    is_global_admin = (
        not settings.admin_api_key  # dev mode -> True meme en prod si key vide
        or x_admin_key == settings.admin_api_key
    )

Si app_env=production ET admin_api_key vide (mauvaise config), la
condition `not settings.admin_api_key` devient True -> is_global_admin
True -> tout caller peut dump full DB.

Defense in depth: meme si require_viewer est bypasse (debug, future
refactor), export.py doit refuser un global dump en production sans
admin_api_key configuree.

Le fix attendu: is_global_admin doit etre False en production si
admin_api_key vide, peu importe l'absence de cle dans la requete.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db
from core.auth import require_viewer


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
async def client_no_auth(test_db):
    """Client avec require_viewer override pour tester defense in depth."""

    def override_get_db():
        yield test_db

    async def noop_viewer():
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_viewer] = noop_viewer
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_global_dump_refused_in_production_without_admin_key(
    client_no_auth, monkeypatch
):
    """Production + admin_api_key vide + pas de project_id -> doit refuser
    (defense in depth, meme si require_viewer est bypasse)."""
    from core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "")

    r = await client_no_auth.get("/api/usage/export?format=csv")
    # On attend un refus (400, 503, ou 401 selon la strategie de fix).
    # Pas un 200 avec dump complet de la DB.
    assert r.status_code != 200, (
        f"En prod sans admin_api_key, le dump global ne doit PAS reussir. "
        f"Status code: {r.status_code}"
    )
    assert r.status_code in (400, 401, 503), (
        f"Expected 400/401/503 (refus), got {r.status_code}: {r.text[:200]}"
    )


@pytest.mark.asyncio
async def test_export_global_dump_refused_in_production_with_invalid_key(
    client_no_auth, monkeypatch
):
    """Production avec admin_api_key configuree mais clien envoie une mauvaise
    cle (ou pas de cle) -> refus."""
    from core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "real-admin-key-12345")

    # Sans X-Admin-Key
    r1 = await client_no_auth.get("/api/usage/export?format=csv")
    assert r1.status_code == 400, (
        f"Sans X-Admin-Key en prod, doit demander project_id (400). Got {r1.status_code}"
    )

    # Avec mauvaise X-Admin-Key
    r2 = await client_no_auth.get(
        "/api/usage/export?format=csv",
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert r2.status_code == 400, (
        f"Avec mauvaise X-Admin-Key, doit demander project_id (400). Got {r2.status_code}"
    )


@pytest.mark.asyncio
async def test_export_global_dump_works_in_dev_mode(client_no_auth, monkeypatch):
    """Compat dev: app_env=development + admin_api_key vide -> autorise
    (comportement existant a preserver)."""
    from core.config import settings

    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "admin_api_key", "")

    r = await client_no_auth.get("/api/usage/export?format=csv")
    assert r.status_code == 200, (
        f"En dev mode (app_env != production), le dump global doit marcher. "
        f"Got {r.status_code}: {r.text[:200]}"
    )


@pytest.mark.asyncio
async def test_export_global_dump_works_in_production_with_valid_admin_key(
    client_no_auth, monkeypatch
):
    """Production avec bonne X-Admin-Key -> autorise."""
    from core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "real-admin-key-12345")

    r = await client_no_auth.get(
        "/api/usage/export?format=csv",
        headers={"X-Admin-Key": "real-admin-key-12345"},
    )
    assert r.status_code == 200, (
        f"En prod avec bonne cle, dump global autorise. Got {r.status_code}: {r.text[:200]}"
    )
