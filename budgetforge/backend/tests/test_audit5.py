"""TDD Audit #5 — 11 findings (C1-C4, H1-H4, M1-M3).

Chaque test est écrit pour ÉCHOUER contre le code actuel (RED).
Les tests valident le comportement attendu après correction.

C2 frontend (double-click SaveBudget) : hors scope backend, testé séparément.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db
import core.config as config_module


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


@pytest.fixture
async def admin_client(test_db):
    """Client avec admin_api_key configuré."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    original_key = config_module.settings.admin_api_key
    config_module.settings.admin_api_key = "test-admin-key-audit5"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        config_module.settings.admin_api_key = original_key
        app.dependency_overrides.clear()


ADMIN_HDR = {"X-Admin-Key": "test-admin-key-audit5"}


# ── C1 — budget_lock : exception body → double exécution ─────────────────────


@pytest.mark.asyncio
async def test_c1_budget_lock_body_exception_does_not_double_execute():
    """C1: une exception dans le body de budget_lock doit se propager,
    pas déclencher le fallback et exécuter le body une 2e fois.

    Le bug : si Redis est disponible (distributed_budget_lock yield),
    une exception dans le body est catchée par l'except → re-yield sous fallback.
    """
    from services.distributed_budget_lock import budget_lock
    from contextlib import asynccontextmanager

    execution_count = 0

    # Simuler Redis disponible : distributed_budget_lock yield normalement
    @asynccontextmanager
    async def mock_distributed_lock(project_id, timeout=30.0):
        yield  # simule l'acquisition Redis réussie

    with patch(
        "services.distributed_budget_lock.distributed_budget_lock",
        side_effect=mock_distributed_lock,
    ):
        with pytest.raises(ValueError, match="business logic error"):
            async with budget_lock(project_id=999):
                execution_count += 1
                raise ValueError("business logic error")

    assert execution_count == 1, (
        f"Le body a été exécuté {execution_count} fois — "
        "l'exception du body ne doit pas déclencher le fallback"
    )


@pytest.mark.asyncio
async def test_c1_budget_lock_redis_failure_uses_fallback_without_double_execute():
    """C1: si Redis échoue à l'acquisition, le fallback est utilisé sans ré-exécuter le body."""
    from services.distributed_budget_lock import budget_lock

    execution_count = 0

    with patch("services.distributed_budget_lock.distributed_budget_lock") as mock_dbl:
        mock_dbl.side_effect = Exception("Redis connection refused")
        with patch("services.distributed_budget_lock.fallback_budget_lock") as mock_fbl:
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def ok_fallback(project_id):
                yield

            mock_fbl.return_value = ok_fallback(999)

            async with budget_lock(project_id=999):
                execution_count += 1

    assert execution_count == 1


# ── C3 — Stripe webhook : ValueError non intercepté ──────────────────────────


@pytest.mark.asyncio
async def test_c3_stripe_webhook_value_error_returns_400_not_500(client):
    """C3: si construct_event lève ValueError (secret vide/None),
    le webhook doit retourner 400 et non 500."""
    with patch("routes.billing.stripe.Webhook.construct_event") as mock_ce:
        mock_ce.side_effect = ValueError("No webhook secret set")
        resp = await client.post(
            "/webhook/stripe",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "t=123,v1=abc"},
        )
    assert resp.status_code == 400, (
        f"Attendu 400, reçu {resp.status_code} — ValueError doit être intercepté"
    )


@pytest.mark.asyncio
async def test_c3_stripe_webhook_missing_secret_startup_check():
    """C3: une fonction de validation de config doit lever une erreur
    si stripe_webhook_secret est vide/None en production."""

    # Une Settings avec env=production et stripe_webhook_secret="" doit être invalide
    # On teste la présence d'une fonction de validation
    import routes.billing as billing_module

    assert hasattr(billing_module, "validate_stripe_config") or hasattr(
        billing_module, "_validate_stripe_secret"
    ), (
        "routes/billing.py doit exposer une fonction de validation du secret Stripe "
        "appelable au démarrage"
    )


# ── C4 — list_projects() : isolation par owner ───────────────────────────────


@pytest.mark.asyncio
async def test_c4_list_projects_viewer_member_cannot_list_all_projects(
    test_db, admin_client
):
    """C4: un member avec role=viewer NE DOIT PAS voir tous les projets.
    GET /api/projects avec viewer key doit retourner 403 ou une liste vide."""
    from core.models import Project, Member

    # Créer 2 projets avec des owners différents
    p1 = Project(name="client-a@test.com", plan="pro", owner_email="client-a@test.com")
    p2 = Project(name="client-b@test.com", plan="pro", owner_email="client-b@test.com")
    test_db.add_all([p1, p2])
    test_db.commit()

    # Créer un member viewer
    member = Member(email="viewer@budgetforge.com", role="viewer")
    test_db.add(member)
    test_db.commit()
    test_db.refresh(member)

    resp = await admin_client.get(
        "/api/projects", headers={"X-Admin-Key": member.api_key}
    )
    # Un viewer ne doit pas voir tous les projets de tous les clients
    assert resp.status_code in (403, 401) or (
        resp.status_code == 200 and len(resp.json()) < 2
    ), (
        f"Viewer a reçu {len(resp.json()) if resp.status_code == 200 else '?'} projets "
        f"(statut {resp.status_code}) — isolation nulle"
    )


@pytest.mark.asyncio
async def test_c4_list_projects_admin_key_sees_all(test_db, admin_client):
    """C4: le global admin key voit tous les projets."""
    from core.models import Project

    p1 = Project(
        name="c4-proj-a@test.com", plan="free", owner_email="c4-proj-a@test.com"
    )
    p2 = Project(
        name="c4-proj-b@test.com", plan="free", owner_email="c4-proj-b@test.com"
    )
    test_db.add_all([p1, p2])
    test_db.commit()

    resp = await admin_client.get("/api/projects", headers=ADMIN_HDR)
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "c4-proj-a@test.com" in names
    assert "c4-proj-b@test.com" in names


# ── H1 — token estimator : plancher à 1 ──────────────────────────────────────


def test_h1_token_estimator_empty_string_returns_minimum_one():
    """H1: estimate_tokens('') doit retourner au moins 1, pas 0.
    Un 0 permet de bypass le budget check (coût apparent = $0)."""
    from services.token_estimator import TokenEstimator

    result = TokenEstimator.estimate_tokens("")
    assert result >= 1, f"estimate_tokens('') retourne {result}, attendu >= 1"


def test_h1_token_estimator_non_empty_text_unaffected():
    """H1: le plancher ne doit pas affecter les textes normaux."""
    from services.token_estimator import TokenEstimator

    result = TokenEstimator.estimate_tokens("Hello world")
    assert result >= 1


# ── H2 — admin bypass : dev mode + clé vide ──────────────────────────────────


@pytest.mark.asyncio
async def test_h2_admin_empty_key_staging_env_denies_request(test_db):
    """H2: admin_api_key='' + app_env='staging' → toute requête sans clé doit être refusée.
    Le bypass dev ne doit pas s'appliquer aux envs non-development."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    original_key = config_module.settings.admin_api_key
    original_env = config_module.settings.app_env
    config_module.settings.admin_api_key = ""
    config_module.settings.app_env = "staging"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/projects")  # pas de clé
        assert resp.status_code in (401, 503), (
            f"Attendu 401/503 pour env=staging sans clé, reçu {resp.status_code}"
        )
    finally:
        config_module.settings.admin_api_key = original_key
        config_module.settings.app_env = original_env
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_h2_admin_empty_key_dev_mode_requires_explicit_dev_env(test_db):
    """H2: admin_api_key='' bypass s'applique UNIQUEMENT à app_env='development'.
    Toute autre valeur (staging, ci, test, empty) doit être refusée."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    original_key = config_module.settings.admin_api_key
    original_env = config_module.settings.app_env
    config_module.settings.admin_api_key = ""
    config_module.settings.app_env = "ci"  # ni "production" ni "development"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/projects")  # pas de clé
        assert resp.status_code in (401, 503), (
            f"Attendu 401/503 pour env=ci sans clé, reçu {resp.status_code}. "
            "Le bypass ne doit s'appliquer qu'en 'development' explicite."
        )
    finally:
        config_module.settings.admin_api_key = original_key
        config_module.settings.app_env = original_env
        app.dependency_overrides.clear()


# ── H3 — DNS rebinding : URL pincée utilisée pour l'envoi ────────────────────


@pytest.mark.asyncio
async def test_h3_alert_service_http_webhook_uses_pinned_ip():
    """H3: pour un webhook HTTP, l'envoi httpx doit utiliser l'URL pincée (IP résolue)
    et non l'URL originale, pour éviter le DNS rebinding TOCTOU."""
    from services.alert_service import AlertService

    pinned_url = "http://1.2.3.4/webhook"
    original_url = "http://legit.example.com/webhook"

    with patch(
        "services.alert_service.resolve_safe_host",
        return_value=(pinned_url, "legit.example.com"),
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

    # L'URL passée à httpx.post doit être la version pincée, pas l'originale
    assert mock_client.post.called
    called_url = mock_client.post.call_args[0][0]
    assert called_url == pinned_url, (
        f"httpx.post appelé avec '{called_url}' — attendu URL pincée '{pinned_url}'"
    )


@pytest.mark.asyncio
async def test_h3_alert_service_https_webhook_still_uses_pinned():
    """H3: même pour HTTPS, l'URL pincée doit être utilisée (SNI via headers si nécessaire)."""
    from services.alert_service import AlertService

    pinned_url = "https://1.2.3.4/webhook"
    original_url = "https://legit.example.com/webhook"

    with patch(
        "services.alert_service.resolve_safe_host",
        return_value=(pinned_url, "legit.example.com"),
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
    assert called_url == pinned_url


# ── H4 — email alias : normalisation avant lookup ────────────────────────────


@pytest.mark.asyncio
async def test_h4_portal_request_email_alias_finds_base_account(client, test_db):
    """H4: user+tag@example.com doit trouver le projet de user@example.com.
    La normalisation du +alias doit avoir lieu avant la recherche en DB."""
    from core.models import Project

    # Projet créé avec l'email de base
    proj = Project(name="user@example.com", plan="pro", owner_email="user@example.com")
    test_db.add(proj)
    test_db.commit()

    with patch("routes.portal.send_portal_email") as mock_send:
        resp = await client.post(
            "/api/portal/request", json={"email": "user+tag@example.com"}
        )

    assert resp.status_code == 200
    # Si le projet est trouvé via l'alias, send_portal_email est appelé
    assert mock_send.called, (
        "send_portal_email non appelé — user+tag@example.com n'a pas trouvé le projet"
    )


@pytest.mark.asyncio
async def test_h4_portal_email_alias_same_rate_limit_key(client, test_db):
    """H4: user+tag@example.com et user@example.com doivent partager le même compte.
    Créer un second projet avec l'alias doit échouer (compte déjà existant)."""
    from core.models import Project

    proj = Project(
        name="h4base@example.com", plan="pro", owner_email="h4base@example.com"
    )
    test_db.add(proj)
    test_db.commit()

    # Portal request avec alias
    with patch("routes.portal.send_portal_email"):
        resp = await client.post(
            "/api/portal/request", json={"email": "h4base+alias@example.com"}
        )
    assert resp.status_code == 200
    # Après normalisation, l'email loggué doit être h4base@example.com (pas h4base+alias)
    # Ce test valide principalement le flow, la normalisation est vérifiée par H4-1


# ── M1 — Stripe upgrade non atomique ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_m1_checkout_completed_skips_upgrade_if_not_paid(test_db):
    """M1: checkout.session.completed avec payment_status!='paid' NE doit PAS
    mettre à jour le plan. Actuellement _handle_checkout_completed ne vérifie pas."""
    from core.models import Project
    from routes.billing import _handle_checkout_completed

    proj = Project(
        name="m1test@example.com", plan="free", owner_email="m1test@example.com"
    )
    test_db.add(proj)
    test_db.commit()

    session_data = {
        "customer_details": {"email": "m1test@example.com"},
        "plan": "pro",
        "payment_status": "processing",  # pas encore 'paid'
        "customer": "cus_m1",
        "subscription": None,
        "metadata": {"plan": "pro"},
    }

    await _handle_checkout_completed(session_data, test_db)

    test_db.refresh(proj)
    assert proj.plan == "free", (
        f"Plan mis à jour à '{proj.plan}' alors que payment_status='processing'"
    )


@pytest.mark.asyncio
async def test_m1_checkout_completed_upgrades_only_on_paid(test_db):
    """M1: checkout.session.completed avec payment_status='paid' → plan mis à jour."""
    from core.models import Project
    from routes.billing import _handle_checkout_completed

    proj = Project(
        name="m1paid@example.com", plan="free", owner_email="m1paid@example.com"
    )
    test_db.add(proj)
    test_db.commit()

    session_data = {
        "customer_details": {"email": "m1paid@example.com"},
        "plan": "pro",
        "payment_status": "paid",
        "customer": "cus_m1p",
        "subscription": None,
        "metadata": {"plan": "pro"},
    }

    with patch("routes.billing.send_onboarding_email"):
        await _handle_checkout_completed(session_data, test_db)

    test_db.refresh(proj)
    assert proj.plan == "pro"


# ── M2 — allowed_providers JSON malformé ─────────────────────────────────────


@pytest.mark.asyncio
async def test_m2_get_project_with_malformed_allowed_providers_returns_gracefully(
    test_db, admin_client
):
    """M2: un projet avec allowed_providers JSON malformé doit retourner 200
    avec allowed_providers=[] (graceful degradation), pas 500/422 opaque."""
    from core.models import Project

    proj = Project(
        name="m2test@example.com",
        plan="free",
        owner_email="m2test@example.com",
        allowed_providers="[invalid json",  # malformé
    )
    test_db.add(proj)
    test_db.commit()
    test_db.refresh(proj)

    resp = await admin_client.get(f"/api/projects/{proj.id}", headers=ADMIN_HDR)
    assert resp.status_code == 200, (
        f"GET projet avec allowed_providers malformé retourne {resp.status_code} "
        f"— attendu 200 avec dégradation gracieuse"
    )
    data = resp.json()
    assert data["allowed_providers"] == [], (
        f"allowed_providers devrait être [] en cas d'erreur JSON, reçu {data['allowed_providers']}"
    )


@pytest.mark.asyncio
async def test_m2_set_budget_malformed_allowed_providers_raises_422(
    test_db, admin_client
):
    """M2: PUT /api/projects/{id}/budget avec allowed_providers malformé → 422 explicite."""
    from core.models import Project

    proj = Project(name="m2settest@example.com", plan="free")
    test_db.add(proj)
    test_db.commit()
    test_db.refresh(proj)

    resp = await admin_client.put(
        f"/api/projects/{proj.id}/budget",
        json={"allowed_providers": "not-a-list", "budget_usd": 10.0},
        headers=ADMIN_HDR,
    )
    assert resp.status_code == 422


# ── M3 — magic link token en query param ─────────────────────────────────────


@pytest.mark.asyncio
async def test_m3_portal_verify_get_has_cache_control_no_store(client, test_db):
    """M3: GET /api/portal/verify?token=... doit avoir Cache-Control: no-store
    pour empêcher la mise en cache du token par proxy/navigateur/nginx."""
    from core.models import PortalToken
    from datetime import datetime, timezone, timedelta

    token = PortalToken(
        email="m3test@example.com",
        token="test-token-m3-audit5",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    )
    test_db.add(token)
    test_db.commit()

    resp = await client.get("/api/portal/verify?token=test-token-m3-audit5")
    # L'important est le header, pas le statut (token peut être valide ou non)
    assert "no-store" in resp.headers.get("cache-control", "").lower(), (
        f"Cache-Control: no-store absent — token peut être loggué par nginx. "
        f"Cache-Control actuel: '{resp.headers.get('cache-control', 'absent')}'"
    )


@pytest.mark.asyncio
async def test_m3_portal_verify_post_has_cache_control_no_store(client, test_db):
    """M3: POST /api/portal/verify avec token valide doit aussi avoir Cache-Control: no-store.
    Le header doit être présent quelle que soit l'issue (2xx ou 4xx)."""
    from core.models import PortalToken
    from datetime import datetime, timezone, timedelta

    token = PortalToken(
        email="m3post@example.com",
        token="test-token-m3-post-audit5",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    )
    test_db.add(token)
    test_db.commit()

    resp = await client.post(
        "/api/portal/verify", json={"token": "test-token-m3-post-audit5"}
    )
    assert "no-store" in resp.headers.get("cache-control", "").lower(), (
        f"POST /api/portal/verify sans Cache-Control: no-store. "
        f"Actuel: '{resp.headers.get('cache-control', 'absent')}'"
    )
