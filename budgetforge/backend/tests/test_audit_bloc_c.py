"""Tests TDD Bloc C — X6 C1, H19 C2, H20 C3, H22 C4, M08/M09 C5.

Tous les tests de cette suite doivent être ROUGES avant implémentation.
"""

import asyncio
import inspect
from datetime import datetime, date
from unittest.mock import patch, AsyncMock, MagicMock


# ── C1 (X6) — Admin key → cookie httpOnly ─────────────────────────────────────


class TestX6AdminLoginCookie:
    """POST /api/admin/login + DELETE /api/admin/session → cookie httpOnly."""

    def test_login_endpoint_exists(self, client):
        """POST /api/admin/login doit exister (pas 404/405)."""
        resp = client.post("/api/admin/login", json={"key": ""})
        assert resp.status_code != 404, "Endpoint /api/admin/login non trouvé"

    def test_valid_key_sets_httponly_cookie(self, client, monkeypatch):
        """Clé admin correcte → cookie bf_admin_key HttpOnly."""
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "super-secret-admin")

        resp = client.post("/api/admin/login", json={"key": "super-secret-admin"})
        assert resp.status_code == 200, f"Attendu 200, got {resp.status_code}"
        sc = resp.headers.get("set-cookie", "")
        assert "bf_admin_key" in sc, f"Cookie bf_admin_key absent. Set-Cookie: '{sc}'"
        assert "httponly" in sc.lower(), f"Flag HttpOnly absent. Set-Cookie: '{sc}'"

    def test_invalid_key_returns_401_no_cookie(self, client, monkeypatch):
        """Clé incorrecte → 401, aucun cookie posé."""
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "correct-key")

        resp = client.post("/api/admin/login", json={"key": "wrong-key"})
        assert resp.status_code == 401
        assert "bf_admin_key" not in resp.headers.get("set-cookie", "")

    def test_logout_endpoint_clears_cookie(self, client):
        """DELETE /api/admin/session → efface bf_admin_key (Max-Age=0)."""
        resp = client.delete("/api/admin/session")
        assert resp.status_code in (200, 204), (
            f"DELETE /api/admin/session attendu 200/204, got {resp.status_code}"
        )
        sc = resp.headers.get("set-cookie", "")
        assert "bf_admin_key" in sc, (
            f"bf_admin_key absent du Set-Cookie sur logout. Header: '{sc}'"
        )
        assert "max-age=0" in sc.lower(), (
            f"Max-Age=0 absent → cookie non effacé. Set-Cookie: '{sc}'"
        )

    def test_require_admin_accepts_httponly_cookie(self, client, monkeypatch):
        """require_admin doit accepter bf_admin_key depuis le cookie sans X-Admin-Key header."""
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "cookie-key-123")

        # Pas de header X-Admin-Key, seulement le cookie
        resp = client.get(
            "/api/projects",
            cookies={"bf_admin_key": "cookie-key-123"},
        )
        assert resp.status_code in (200, 204), (
            f"require_admin doit accepter le cookie httpOnly, got {resp.status_code}"
        )


# ── C2 (H19) — Worker finalize sur déconnexion client ─────────────────────────


class TestH19FinalizeOnDisconnect:
    """cancel_usage doit être appelé si le client coupe avant réception d'usage."""

    def test_cancel_called_when_client_disconnects_before_usage(self):
        """Déconnexion avant usage data → cancel_usage appelé (pas de budget leak)."""
        from services.proxy_dispatcher import _openai_format_stream_gen

        async def stream_no_usage(*args, **kwargs):
            yield b'data: {"choices": [{"delta": {"content": "hi"}}]}\n\n'
            await asyncio.sleep(9999)  # client coupe avant la fin du stream

        mock_db = MagicMock()
        mock_project = MagicMock(budget_usd=None)
        cancel_calls: list[int] = []

        def mock_cancel(db, uid):
            cancel_calls.append(uid)

        async def run():
            with (
                patch(
                    "services.proxy_dispatcher.cancel_usage",
                    side_effect=mock_cancel,
                ),
                patch(
                    "services.proxy_dispatcher.finalize_usage",
                    new_callable=AsyncMock,
                ),
                patch(
                    "services.proxy_dispatcher._call_maybe_send_alert",
                    new_callable=AsyncMock,
                ),
            ):
                gen = _openai_format_stream_gen(
                    stream_payload={},
                    api_key="test",
                    forward_stream_fn=stream_no_usage,
                    timeout_s=30.0,
                    provider_name="openai",
                    db=mock_db,
                    usage_id=7,
                    final_model="gpt-4o",
                    project=mock_project,
                )
                await gen.__anext__()
                await gen.aclose()  # simule déconnexion client

        asyncio.run(run())

        assert cancel_calls == [7], (
            f"cancel_usage doit être appelé avec uid=7 sur déconnexion client, "
            f"got {cancel_calls}"
        )

    def test_finalize_called_after_usage_received_then_disconnect(self):
        """got_usage=True + déconnexion → finalize_usage appelé (comportement attendu)."""
        from services.proxy_dispatcher import _openai_format_stream_gen

        usage_chunk = (
            b'data: {"usage": {"prompt_tokens": 5, "completion_tokens": 3}}\n\n'
        )

        async def stream_with_usage(*args, **kwargs):
            yield usage_chunk
            await asyncio.sleep(9999)

        mock_db = MagicMock()
        mock_project = MagicMock(budget_usd=None)
        finalize_calls: list[int] = []

        async def mock_finalize(db, uid, ti, to, model):
            finalize_calls.append(uid)

        async def run():
            with (
                patch(
                    "services.proxy_dispatcher.finalize_usage",
                    side_effect=mock_finalize,
                ),
                patch("services.proxy_dispatcher.cancel_usage"),
                patch(
                    "services.proxy_dispatcher._call_maybe_send_alert",
                    new_callable=AsyncMock,
                ),
            ):
                gen = _openai_format_stream_gen(
                    stream_payload={},
                    api_key="test",
                    forward_stream_fn=stream_with_usage,
                    timeout_s=30.0,
                    provider_name="openai",
                    db=mock_db,
                    usage_id=42,
                    final_model="gpt-4o",
                    project=mock_project,
                )
                await gen.__anext__()
                await gen.aclose()

        asyncio.run(run())

        assert finalize_calls == [42], (
            f"finalize_usage doit être appelé quand got_usage=True, got {finalize_calls}"
        )


# ── C3 (H20) — Comparaison constante API key (timing attack) ─────────────────


class TestH20ConstantTimeApiKey:
    """get_project_by_api_key et require_admin doivent utiliser hmac.compare_digest."""

    def test_get_project_by_api_key_uses_hmac_compare_digest(self):
        """proxy_dispatcher.get_project_by_api_key doit appeler hmac.compare_digest."""
        import services.proxy_dispatcher as pd

        source = inspect.getsource(pd.get_project_by_api_key)
        assert "compare_digest" in source, (
            "get_project_by_api_key doit utiliser hmac.compare_digest "
            "pour valider la clé après lookup SQL (H20)"
        )

    def test_require_admin_member_key_uses_hmac_compare_digest(self):
        """require_admin doit appeler compare_digest pour le member key path."""
        import core.auth as auth

        src = inspect.getsource(auth.require_admin)
        count = src.count("compare_digest")
        assert count >= 1, (
            f"require_admin doit appeler compare_digest ≥ 1× "
            f"pour le member key path, actuellement {count}×"
        )

    def test_require_viewer_member_key_uses_hmac_compare_digest(self):
        """require_viewer doit appeler compare_digest pour le member key path."""
        import core.auth as auth

        src = inspect.getsource(auth.require_viewer)
        count = src.count("compare_digest")
        assert count >= 1, (
            f"require_viewer doit appeler compare_digest ≥ 1× "
            f"pour le member key path, actuellement {count}×"
        )


# ── C4 (H22) — Cache quota TTL 30s ────────────────────────────────────────────


class TestH22QuotaCache:
    """get_calls_this_month ne doit pas requêter la DB à chaque appel proxy."""

    def _reset_cache(self):
        from services import plan_quota

        if hasattr(plan_quota, "_quota_cache"):
            plan_quota._quota_cache.clear()

    def test_second_consecutive_call_uses_cache(self):
        """2 appels consécutifs (même project_id) → 1 seule requête SQL."""
        from services.plan_quota import get_calls_this_month

        self._reset_cache()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 15

        count1 = get_calls_this_month(project_id=111, db=mock_db)
        count2 = get_calls_this_month(project_id=111, db=mock_db)

        assert count1 == 15
        assert count2 == 15
        n = mock_db.query.call_count
        assert n == 1, (
            f"DB doit être requêtée 1 fois grâce au cache TTL, appelée {n} fois"
        )

    def test_different_projects_have_independent_cache_entries(self):
        """project_id 1 et 2 ont des entrées cache indépendantes."""
        from services.plan_quota import get_calls_this_month

        self._reset_cache()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [5, 20]

        c1 = get_calls_this_month(project_id=1, db=mock_db)
        c2 = get_calls_this_month(project_id=2, db=mock_db)

        assert c1 == 5
        assert c2 == 20

    def test_cache_expires_after_ttl_and_requeries_db(self):
        """Cache expiré (> TTL) → nouvelle requête DB."""
        from services.plan_quota import get_calls_this_month
        from services import plan_quota

        self._reset_cache()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10

        get_calls_this_month(project_id=222, db=mock_db)

        ttl = getattr(plan_quota, "_QUOTA_CACHE_TTL", 30.0)
        cache = getattr(plan_quota, "_quota_cache", None)
        if cache is not None and 222 in cache:
            count, ts = cache[222]
            cache[222] = (count, ts - ttl - 1)

        get_calls_this_month(project_id=222, db=mock_db)

        n = mock_db.query.call_count
        assert n == 2, f"Cache expiré → 2ème requête DB attendue, got {n} appels"

    def test_quota_cache_ttl_constant_exists(self):
        """_QUOTA_CACHE_TTL doit être défini dans plan_quota (≥ 10s, ≤ 60s)."""
        from services import plan_quota

        assert hasattr(plan_quota, "_QUOTA_CACHE_TTL"), (
            "_QUOTA_CACHE_TTL non défini dans plan_quota"
        )
        assert 10 <= plan_quota._QUOTA_CACHE_TTL <= 60, (
            f"TTL doit être entre 10s et 60s, got {plan_quota._QUOTA_CACHE_TTL}"
        )


# ── C5 (M08) — Index composite usages(project_id, created_at) ────────────────


class TestM08CompositeIndex:
    """Index (project_id, created_at) doit exister sur la table usages."""

    def test_usage_table_has_composite_index_project_created_at(self):
        """Index composite (project_id, created_at) déclaré dans SQLAlchemy metadata."""
        from sqlalchemy import create_engine
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy.pool import StaticPool
        from core.database import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)

        insp = sa_inspect(engine)
        indexes = insp.get_indexes("usages")
        col_sets = [frozenset(idx["column_names"]) for idx in indexes]

        target = frozenset({"project_id", "created_at"})
        assert target in col_sets, (
            f"Index (project_id, created_at) absent sur usages. "
            f"Index présents : {[list(s) for s in col_sets]}"
        )


# ── C5 (M09) — Dates UTC-aware dans history ───────────────────────────────────


class TestM09UTCAwareDates:
    """date_from/date_to de /api/usage/history : comportement aux bornes UTC."""

    def test_date_from_includes_record_at_midnight_utc(self, db):
        """Record créé exactement à UTC midnight du date_from doit être INCLUS."""
        from core.models import Usage, Project
        from routes.history import get_history

        proj = Project(name="utctest1@test.com")
        db.add(proj)
        db.commit()
        db.refresh(proj)

        db.add(
            Usage(
                project_id=proj.id,
                provider="openai",
                model="gpt-4o",
                tokens_in=10,
                tokens_out=5,
                cost_usd=0.001,
                created_at=datetime(2024, 4, 1, 0, 0, 0),  # UTC midnight
            )
        )
        db.commit()

        result = get_history(
            page=1,
            page_size=50,
            project_id=proj.id,
            provider=None,
            model=None,
            date_from=date(2024, 4, 1),
            date_to=None,
            db=db,
        )
        assert result.total >= 1, "Record à UTC midnight de date_from doit être inclus"

    def test_date_to_includes_record_at_end_of_day(self, db):
        """Record créé à 23:59:59 le date_to doit être INCLUS."""
        from core.models import Usage, Project
        from routes.history import get_history

        proj = Project(name="utctest2@test.com")
        db.add(proj)
        db.commit()
        db.refresh(proj)

        db.add(
            Usage(
                project_id=proj.id,
                provider="openai",
                model="gpt-4o",
                tokens_in=10,
                tokens_out=5,
                cost_usd=0.001,
                created_at=datetime(2024, 4, 30, 23, 59, 59),
            )
        )
        db.commit()

        result = get_history(
            page=1,
            page_size=50,
            project_id=proj.id,
            provider=None,
            model=None,
            date_from=None,
            date_to=date(2024, 4, 30),
            db=db,
        )
        assert result.total >= 1, "Record à 23:59:59 le date_to doit être inclus"

    def test_date_to_excludes_next_day_record(self, db):
        """Record créé le lendemain du date_to doit être EXCLU."""
        from core.models import Usage, Project
        from routes.history import get_history

        proj = Project(name="utctest3@test.com")
        db.add(proj)
        db.commit()
        db.refresh(proj)

        db.add(
            Usage(
                project_id=proj.id,
                provider="openai",
                model="gpt-4o",
                tokens_in=10,
                tokens_out=5,
                cost_usd=0.001,
                created_at=datetime(2024, 5, 1, 0, 0, 0),  # lendemain
            )
        )
        db.commit()

        result = get_history(
            page=1,
            page_size=50,
            project_id=proj.id,
            provider=None,
            model=None,
            date_from=None,
            date_to=date(2024, 4, 30),
            db=db,
        )
        assert result.total == 0, (
            "Record le lendemain du date_to ne doit PAS être inclus"
        )
