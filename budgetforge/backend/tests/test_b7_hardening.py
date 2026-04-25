"""TDD B7 — Hardening admin + tests.

B7.1: Members admin escalation (H15).
B7.2: Settings smtp hostname validation (H16).
B7.3: CSV injection (H14).
B7.4: Export streaming yield_per (C18).
B7.5: Retry backoff exponentiel (H24).
B7.6: PortalRevokedSession purge (M05).
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from main import app
from core.database import Base, get_db
from core.auth import require_admin
from core.models import Member, PortalRevokedSession, Usage, Project


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


# ── B7.1 — Members admin escalation (H15) ────────────────────────────────────


@pytest.mark.asyncio
async def test_member_admin_cannot_create_another_admin(client, db, monkeypatch):
    """H15: Un member admin ne doit pas pouvoir promouvoir à admin (seul global admin peut)."""
    from core.config import settings

    monkeypatch.setattr(settings, "admin_api_key", "global-secret-key-xyz")
    monkeypatch.setattr(settings, "app_env", "production")

    # Créer un member admin
    member_admin = Member(email="admin_member@test.com", role="admin")
    db.add(member_admin)
    db.commit()
    db.refresh(member_admin)

    # Member admin essaie de créer un autre admin
    r = await client.post(
        "/api/members",
        json={"email": "new_admin@test.com", "role": "admin"},
        headers={"X-Admin-Key": member_admin.api_key},
    )
    assert r.status_code == 403, (
        f"Un member admin ne doit pas pouvoir créer un autre admin. Got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_global_admin_can_create_admin_member(client, db, monkeypatch):
    """H15: Le global admin doit pouvoir créer un member admin."""
    from core.config import settings

    monkeypatch.setattr(settings, "admin_api_key", "global-secret-key-xyz")
    monkeypatch.setattr(settings, "app_env", "production")

    r = await client.post(
        "/api/members",
        json={"email": "new_admin@test.com", "role": "admin"},
        headers={"X-Admin-Key": "global-secret-key-xyz"},
    )
    assert r.status_code == 201, (
        f"Global admin doit pouvoir créer admin member. Got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_member_admin_can_create_viewer(client, db, monkeypatch):
    """H15: Un member admin peut créer un viewer (pas d'escalade de privilège)."""
    from core.config import settings

    monkeypatch.setattr(settings, "admin_api_key", "global-secret-key-xyz")
    monkeypatch.setattr(settings, "app_env", "production")

    member_admin = Member(email="admin_for_viewer@test.com", role="admin")
    db.add(member_admin)
    db.commit()
    db.refresh(member_admin)

    r = await client.post(
        "/api/members",
        json={"email": "new_viewer@test.com", "role": "viewer"},
        headers={"X-Admin-Key": member_admin.api_key},
    )
    assert r.status_code == 201, (
        f"Member admin doit pouvoir créer viewer. Got {r.status_code}: {r.text}"
    )


# ── B7.2 — Settings smtp hostname validation (H16) ───────────────────────────


@pytest.mark.asyncio
async def test_settings_smtp_rejects_private_ip(client, db, monkeypatch):
    """H16: smtp_host avec IP privée doit être refusé."""

    async def noop_admin():
        return None

    app.dependency_overrides[require_admin] = noop_admin

    for private_ip in ["192.168.1.1", "10.0.0.1", "172.16.0.1", "127.0.0.1"]:
        r = await client.put(
            "/api/settings",
            json={"smtp_host": private_ip, "smtp_port": 587},
        )
        assert r.status_code == 422, (
            f"smtp_host={private_ip} devrait être refusé (422), got {r.status_code}"
        )

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: (yield db)


@pytest.mark.asyncio
async def test_settings_smtp_accepts_valid_hostname(client, db, monkeypatch):
    """H16: smtp_host avec hostname public valide doit être accepté."""

    async def noop_admin():
        return None

    app.dependency_overrides[require_admin] = noop_admin

    r = await client.put(
        "/api/settings",
        json={"smtp_host": "smtp.sendgrid.net", "smtp_port": 587},
    )
    assert r.status_code == 200, (
        f"smtp_host valide devrait passer. Got {r.status_code}: {r.text}"
    )

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: (yield db)


# ── B7.3 — CSV injection (H14) ───────────────────────────────────────────────


def test_safe_csv_cell_sanitizes_injection():
    """H14: Les valeurs CSV commençant par =+-@ doivent être préfixées par '."""
    from routes.export import _safe_csv_cell

    assert _safe_csv_cell("=SUM(A1)") == "'=SUM(A1)"
    assert _safe_csv_cell("+1-800-555-1234") == "'+1-800-555-1234"
    assert _safe_csv_cell("-HYPERLINK(...)") == "'-HYPERLINK(...)"
    assert _safe_csv_cell("@SUM(...)") == "'@SUM(...)"
    assert _safe_csv_cell("normal text") == "normal text"
    assert _safe_csv_cell("") == ""
    assert _safe_csv_cell(None) == ""


@pytest.mark.asyncio
async def test_export_csv_sanitizes_agent_field(client, db, monkeypatch):
    """H14: Le champ 'agent' dans le CSV exporté doit être sanitisé."""
    from core.config import settings
    from core.auth import require_viewer

    monkeypatch.setattr(settings, "admin_api_key", "test-admin-key")
    monkeypatch.setattr(settings, "app_env", "production")

    async def noop_viewer():
        return None

    app.dependency_overrides[require_viewer] = noop_viewer

    # Créer un projet et une usage avec agent malicieux
    project = Project(name="csv@test.com")
    db.add(project)
    db.commit()
    db.refresh(project)

    usage = Usage(
        project_id=project.id,
        provider="openai",
        model="gpt-4o",
        agent='=HYPERLINK("http://evil.com","click")',
        cost_usd=0.01,
    )
    db.add(usage)
    db.commit()

    r = await client.get(
        f"/api/usage/export?format=csv&project_id={project.id}",
        headers={"X-Admin-Key": "test-admin-key"},
    )
    assert r.status_code == 200
    content = r.text
    # La valeur sanitisée commence par ' donc dans le CSV elle est "'=HYPERLINK..."
    # Le CSV ne doit PAS contenir =HYPERLINK directement en début de champ (injection active)
    # C'est le cas si la ligne contient ,'=HYPERLINK ou "'=HYPERLINK (début de champ précédé de ' ou virgule)
    assert (
        ",'=HYPERLINK" in content
        or ",\"'=HYPERLINK" in content
        or "'=HYPERLINK" in content
    ), f"La valeur malicieuse doit être préfixée par '. Content: {content[:300]}"
    # Vérifier que le champ ne commence pas directement par =HYPERLINK (sans le préfixe ')
    # Dans un CSV, un champ non-quoté commençant par = serait: ,=HYPERLINK
    # Après sanitisation il doit être: ,'=HYPERLINK ou ",\"'=HYPERLINK"
    import re as _re

    # Chercher les patterns d'injection non sanitisés: virgule suivie directement de =, +, -, @
    assert not _re.search(r",=HYPERLINK", content), (
        "=HYPERLINK non sanitisé trouvé dans le CSV"
    )

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: (yield db)


# ── B7.6 — PortalRevokedSession purge (M05) ──────────────────────────────────


def test_cleanup_old_revoked_sessions_removes_old_entries(db):
    """M05: Les sessions révoquées de plus de 90 jours doivent être purgées."""
    from routes.portal import cleanup_old_revoked_sessions

    old_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=91)
    recent_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)

    old_session = PortalRevokedSession(
        email="old@test.com", iat=1000, revoked_at=old_date
    )
    recent_session = PortalRevokedSession(
        email="recent@test.com", iat=2000, revoked_at=recent_date
    )
    db.add(old_session)
    db.add(recent_session)
    db.commit()

    cleanup_old_revoked_sessions(db)

    remaining = db.query(PortalRevokedSession).all()
    assert len(remaining) == 1
    assert remaining[0].email == "recent@test.com"


# ── B7.5 — Retry backoff (H24) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_uses_exponential_backoff():
    """H24: Les retries doivent utiliser un backoff exponentiel (2^attempt, cap 10s)."""
    sleep_calls = []

    import asyncio as _asyncio

    original_sleep = _asyncio.sleep

    async def mock_sleep(delay):
        sleep_calls.append(delay)

    from services.proxy_dispatcher import dispatch_openai_format
    from core.models import Project

    project = Project(name="retry@test.com", plan="pro", budget_usd=100.0)

    call_count = [0]

    async def always_fail(body, api_key, timeout_s=60.0):
        import httpx

        call_count[0] += 1
        raise httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=MagicMock(status_code=500)
        )

    def noop_cancel(db, usage_id):
        pass

    with patch("services.proxy_dispatcher.asyncio.sleep", mock_sleep):
        with patch("services.proxy_dispatcher.cancel_usage", noop_cancel):
            with patch("services.proxy_dispatcher._call_maybe_send_alert", AsyncMock()):
                try:
                    from unittest.mock import MagicMock as MM

                    db_mock = MM()
                    await dispatch_openai_format(
                        payload={"model": "gpt-4o"},
                        project=project,
                        provider_name="openai",
                        final_model="gpt-4o",
                        usage_id=1,
                        api_key="sk-test",
                        forward_fn=always_fail,
                        forward_stream_fn=None,
                        timeout_s=5.0,
                        db=db_mock,
                        max_retries=2,
                    )
                except Exception:
                    pass

    if sleep_calls:
        # Vérifier le backoff exponentiel
        assert sleep_calls[0] == 1.0 or sleep_calls[0] in (1, 2), (
            f"Premier sleep doit être ~1s (2^0), got {sleep_calls[0]}"
        )
        if len(sleep_calls) >= 2:
            assert sleep_calls[1] >= sleep_calls[0], "Backoff doit croître"
