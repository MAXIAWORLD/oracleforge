"""TDD RED → GREEN — Bloc 10 : 5 findings effort=4

H19  proxy_dispatcher  Worker bloqué si client coupe avant finalize
H20  proxy_dispatcher  Timing attack API key lookup
H22  plan_quota        check_quota SQL par appel (no cache)
M08  history           total_cost + count = 2 requêtes séparées
M09  history           date_from/to naive UTC
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import date, datetime


# ─────────────────────────────────────────────
# H19 — Cleanup (finalize/cancel) résiste à la cancellation
# ─────────────────────────────────────────────


class TestH19StreamCleanupOnCancel:
    @pytest.mark.asyncio
    async def test_cancel_usage_called_when_stream_cancelled_before_usage(self):
        """Si le stream est cancelled avant d'avoir reçu usage, cancel_usage doit être appelé."""
        from services.proxy_dispatcher import _openai_format_stream_gen

        mock_db = MagicMock()
        mock_project = MagicMock()
        mock_project.budget_usd = 10.0
        mock_project.reset_period = "monthly"
        mock_project.alert_email = None
        mock_project.webhook_url = None

        async def failing_stream(payload, api_key, timeout_s):
            raise asyncio.CancelledError()
            yield  # make it an async generator

        with (
            patch("services.proxy_dispatcher.cancel_usage") as mock_cancel,
            patch("services.proxy_dispatcher.finalize_usage", new_callable=AsyncMock),
            patch(
                "services.proxy_dispatcher._call_maybe_send_alert",
                new_callable=AsyncMock,
            ),
        ):
            gen = _openai_format_stream_gen(
                {},
                "key",
                failing_stream,
                30.0,
                "openai",
                mock_db,
                42,
                "gpt-4o",
                mock_project,
            )
            try:
                async for _ in gen:
                    pass
            except (asyncio.CancelledError, StopAsyncIteration, Exception):
                pass
            finally:
                await gen.aclose()

            mock_cancel.assert_called_once_with(mock_db, 42)

    @pytest.mark.asyncio
    async def test_finalize_usage_called_when_stream_cancelled_after_usage(self):
        """Si usage reçu avant cancel, finalize_usage doit être appelé malgré la cancel."""
        from services.proxy_dispatcher import _openai_format_stream_gen
        import json

        mock_db = MagicMock()
        mock_project = MagicMock()
        mock_project.budget_usd = 10.0
        mock_project.reset_period = "monthly"
        mock_project.alert_email = None
        mock_project.webhook_url = None

        usage_chunk = json.dumps(
            {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        ).encode()
        sse_chunk = f"data: {usage_chunk.decode()}\n".encode()

        async def stream_with_usage_then_cancel(payload, api_key, timeout_s):
            yield sse_chunk
            raise asyncio.CancelledError()

        with (
            patch("services.proxy_dispatcher.cancel_usage") as mock_cancel,
            patch(
                "services.proxy_dispatcher.finalize_usage", new_callable=AsyncMock
            ) as mock_finalize,
            patch(
                "services.proxy_dispatcher._call_maybe_send_alert",
                new_callable=AsyncMock,
            ),
        ):
            gen = _openai_format_stream_gen(
                {},
                "key",
                stream_with_usage_then_cancel,
                30.0,
                "openai",
                mock_db,
                99,
                "gpt-4o",
                mock_project,
            )
            try:
                async for _ in gen:
                    pass
            except (asyncio.CancelledError, Exception):
                pass
            finally:
                await gen.aclose()

            # finalize doit être appelé (pas cancel) car on a reçu usage
            mock_finalize.assert_called_once()
            mock_cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_protected_with_shield_or_equivalent(self):
        """Le finally block doit utiliser asyncio.shield() ou être protégé contre CancelledError."""
        import inspect
        import services.proxy_dispatcher as pd

        source = inspect.getsource(pd._openai_format_stream_gen)
        assert "asyncio.shield" in source or "shield" in source, (
            "_openai_format_stream_gen doit utiliser asyncio.shield() dans finally "
            "pour protéger finalize/cancel contre la cancellation"
        )


# ─────────────────────────────────────────────
# H20 — Constant-time API key lookup
# ─────────────────────────────────────────────


class TestH20ConstantTimeApiKeyLookup:
    def test_both_queries_always_executed(self):
        """get_project_by_api_key doit toujours exécuter les deux requêtes SQL."""
        from services.proxy_dispatcher import get_project_by_api_key

        mock_db = MagicMock()
        mock_project = MagicMock()

        # Premier query trouve le projet → ancien code retourne immédiatement
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        result = get_project_by_api_key("Bearer validkey123", mock_db)

        # Les deux filtres doivent avoir été appelés (au minimum 2 appels à .filter())
        # On vérifie que query() a été appelé au moins 2 fois
        assert mock_db.query.call_count >= 2, (
            f"Les deux requêtes SQL doivent toujours s'exécuter (got {mock_db.query.call_count} calls)"
        )
        assert result is mock_project

    def test_lookup_executes_second_query_even_when_first_succeeds(self):
        """Même si la clé principale est trouvée, la deuxième requête (grace period) doit s'exécuter."""
        from services.proxy_dispatcher import get_project_by_api_key

        mock_db = MagicMock()
        mock_project = MagicMock()

        query_call_count = [0]
        first_mock = MagicMock()
        first_mock.first.return_value = mock_project

        second_mock = MagicMock()
        second_mock.first.return_value = None

        def query_side_effect(*args, **kwargs):
            query_call_count[0] += 1
            q = MagicMock()
            q.filter.return_value = (
                first_mock if query_call_count[0] == 1 else second_mock
            )
            return q

        mock_db.query.side_effect = query_side_effect
        get_project_by_api_key("Bearer key", mock_db)

        assert query_call_count[0] >= 2, (
            "Les deux requêtes SQL doivent s'exécuter même si la première trouve le projet"
        )


# ─────────────────────────────────────────────
# H22 — check_quota avec cache TTL
# ─────────────────────────────────────────────


class TestH22QuotaCache:
    def test_get_calls_this_month_cached_exists(self):
        """get_calls_this_month_cached doit exister dans plan_quota."""
        import services.plan_quota as pq

        assert hasattr(pq, "get_calls_this_month_cached"), (
            "get_calls_this_month_cached() doit exister pour réduire les requêtes SQL"
        )

    def test_quota_cache_constant_exists(self):
        """_QUOTA_CACHE_TTL doit être défini."""
        import services.plan_quota as pq

        assert hasattr(pq, "_QUOTA_CACHE_TTL"), "_QUOTA_CACHE_TTL doit être défini"
        assert pq._QUOTA_CACHE_TTL > 0

    def test_check_quota_uses_cache_on_repeat_call(self):
        """Deux appels consécutifs à check_quota pour le même projet ne font qu'une requête SQL."""
        import services.plan_quota as pq

        mock_db = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 777
        mock_project.plan = "pro"

        # Vider le cache
        pq._quota_cache.clear()

        db_call_count = [0]

        def fake_count(project_id, db):
            db_call_count[0] += 1
            return 50  # 50 appels ce mois

        with patch("services.plan_quota.get_calls_this_month", side_effect=fake_count):
            pq.check_quota(mock_project, mock_db)
            pq.check_quota(mock_project, mock_db)

        assert db_call_count[0] == 1, (
            f"DB appelée {db_call_count[0]}× — doit être 1 grâce au cache TTL"
        )

    def test_quota_cache_expires(self):
        """Le cache doit expirer après _QUOTA_CACHE_TTL secondes."""
        import services.plan_quota as pq

        mock_db = MagicMock()
        pq._quota_cache.clear()

        db_call_count = [0]

        def fake_count(project_id, db):
            db_call_count[0] += 1
            return 50

        with (
            patch("services.plan_quota.get_calls_this_month", side_effect=fake_count),
            patch("services.plan_quota.time") as mock_time,
        ):
            # Premier appel : t=0
            mock_time.return_value = 0.0
            pq.get_calls_this_month_cached(1, mock_db)
            # Deuxième appel dans le TTL : t=10
            mock_time.return_value = 10.0
            pq.get_calls_this_month_cached(1, mock_db)
            # Troisième appel après expiration : t=TTL+1
            mock_time.return_value = pq._QUOTA_CACHE_TTL + 1.0
            pq.get_calls_this_month_cached(1, mock_db)

        assert db_call_count[0] == 2, (
            f"DB doit être appelée 2× (premier + après expiration), got {db_call_count[0]}"
        )


# ─────────────────────────────────────────────
# M08 — count + sum en une seule requête
# ─────────────────────────────────────────────


class TestM08HistorySingleQuery:
    def test_history_uses_single_combined_query(self):
        """get_history doit obtenir count ET sum en une seule requête SQL."""
        import inspect
        from routes.history import get_history

        source = inspect.getsource(get_history)

        # Vérifier qu'il n'y a qu'un seul bloc query pour count+sum (pas deux séparés)
        # On vérifie l'absence du double-pattern count()+scalar() séparé
        count_calls = source.count("func.count")
        sum_calls = source.count("func.sum")

        # Les deux doivent exister (COUNT + SUM)
        assert count_calls >= 1, "func.count doit être présent"
        assert sum_calls >= 1, "func.sum doit être présent"

        # La combinaison doit être dans un même db.query() — vérifier le pattern
        # Un seul appel `.one()` ou `.first()` pour les deux métriques
        has_combined = ".one()" in source or "func.count(Usage.id), func.sum" in source
        assert has_combined, (
            "count et sum doivent être combinés dans une seule requête via .one() "
            "ou db.query(func.count(...), func.sum(...))"
        )

    def test_history_count_and_sum_combined_mock(self):
        """Vérifier que la route history exécute un seul query pour count+sum."""
        from sqlalchemy.orm import Session
        from unittest.mock import MagicMock, patch

        mock_db = MagicMock(spec=Session)

        # Mock la requête combinée retournant (count, sum)
        combined_mock = MagicMock()
        combined_mock.join.return_value = combined_mock
        combined_mock.filter.return_value = combined_mock
        combined_mock.options.return_value = combined_mock
        combined_mock.order_by.return_value = combined_mock
        combined_mock.offset.return_value = combined_mock
        combined_mock.limit.return_value = combined_mock
        combined_mock.one.return_value = (0, None)  # count=0, sum=None
        combined_mock.all.return_value = []

        mock_db.query.return_value = combined_mock

        with patch("routes.history.require_viewer", return_value=None):
            from routes.history import get_history

            result = get_history(
                page=1,
                page_size=50,
                project_id=None,
                provider=None,
                model=None,
                date_from=None,
                date_to=None,
                db=mock_db,
            )

        # Vérifier qu'une seule requête a été faite (pas deux)
        # Le nombre d'appels à db.query doit être ≤ 2 (une pour count+sum, une pour records)
        assert mock_db.query.call_count <= 2, (
            f"db.query appelé {mock_db.query.call_count}× — "
            "doit être ≤ 2 (1 pour count+sum, 1 pour les records)"
        )


# ─────────────────────────────────────────────
# M09 — date_from/to UTC explicite
# ─────────────────────────────────────────────


class TestM09DateFiltersUTC:
    def test_date_from_produces_midnight_utc(self):
        """date_from doit produire un datetime à minuit UTC (pas local)."""
        from routes.history import _date_to_utc_start

        d = date(2025, 6, 15)
        result = _date_to_utc_start(d)
        assert result == datetime(2025, 6, 15, 0, 0, 0), (
            f"date_from doit produire 2025-06-15 00:00:00 UTC, got {result}"
        )

    def test_date_to_produces_end_of_day_utc(self):
        """date_to doit produire un datetime à 23:59:59.999999 UTC (pas local)."""
        from routes.history import _date_to_utc_end

        d = date(2025, 6, 15)
        result = _date_to_utc_end(d)
        assert result == datetime(2025, 6, 15, 23, 59, 59, 999999), (
            f"date_to doit produire 2025-06-15 23:59:59.999999, got {result}"
        )

    def test_date_filters_use_utc_helpers(self):
        """get_history doit utiliser _date_to_utc_start et _date_to_utc_end."""
        import inspect
        from routes import history

        source = inspect.getsource(history)
        assert "_date_to_utc_start" in source and "_date_to_utc_end" in source, (
            "get_history doit utiliser _date_to_utc_start/_date_to_utc_end "
            "pour éviter l'ambiguïté de timezone"
        )
