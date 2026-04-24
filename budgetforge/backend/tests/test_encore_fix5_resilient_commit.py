"""TDD RED — encore fix5 : cancel_usage et finalize_usage doivent être résilients.

Problème actuel :
  cancel_usage et finalize_usage appellent db.commit() sans try/except.
  Si le commit échoue (SQLite locked, network error), l'exception bubble up
  et crashe le handler de streaming/proxy avec une 500 non-informative.

Fix requis :
  Wrapper db.commit() dans try/except + db.rollback() + log.
  Ne pas re-raise (dégradation silencieuse acceptable — usage estimé reste).
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError


class TestCancelUsageResilient:
    """cancel_usage doit gérer les erreurs de commit sans crash."""

    def test_cancel_usage_survives_commit_error(self):
        """Si db.commit() échoue, cancel_usage ne doit pas lever d'exception."""
        from services.proxy_dispatcher import cancel_usage

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 1
        mock_db.commit.side_effect = OperationalError("database is locked", None, None)

        # Ne doit pas lever d'exception
        try:
            cancel_usage(mock_db, usage_id=42)
        except Exception as exc:
            pytest.fail(
                f"cancel_usage must not raise on commit error. Got: {exc!r}. "
                "Current code calls db.commit() without try/except."
            )

    def test_cancel_usage_calls_rollback_on_commit_error(self):
        """Sur erreur de commit, cancel_usage doit appeler db.rollback()."""
        from services.proxy_dispatcher import cancel_usage

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 1
        mock_db.commit.side_effect = OperationalError("database is locked", None, None)

        cancel_usage(mock_db, usage_id=42)

        (
            mock_db.rollback.assert_called_once(),
            (
                "db.rollback() must be called after commit failure. "
                "Current code has no rollback."
            ),
        )

    def test_cancel_usage_happy_path_still_works(self):
        """Le path normal (commit réussit) doit toujours fonctionner."""
        from services.proxy_dispatcher import cancel_usage

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 1
        mock_db.commit.return_value = None

        cancel_usage(mock_db, usage_id=99)

        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()


class TestFinalizeUsageResilient:
    """finalize_usage doit gérer les erreurs de commit sans crash."""

    @pytest.mark.asyncio
    async def test_finalize_usage_survives_commit_error(self):
        """Si db.commit() échoue dans finalize_usage, ne doit pas lever d'exception."""
        from services.proxy_dispatcher import finalize_usage

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.update.return_value = 1
        mock_db.commit.side_effect = OperationalError("database is locked", None, None)

        with patch(
            "services.proxy_dispatcher.CostCalculator.compute_cost",
            return_value=0.001,
        ):
            try:
                await finalize_usage(
                    mock_db, usage_id=42, tokens_in=100, tokens_out=50, model="gpt-4o"
                )
            except Exception as exc:
                pytest.fail(
                    f"finalize_usage must not raise on commit error. Got: {exc!r}. "
                    "Current code calls db.commit() without try/except."
                )

    @pytest.mark.asyncio
    async def test_finalize_usage_calls_rollback_on_commit_error(self):
        """Sur erreur de commit, finalize_usage doit appeler db.rollback()."""
        from services.proxy_dispatcher import finalize_usage

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.update.return_value = 1
        mock_db.commit.side_effect = OperationalError("database is locked", None, None)

        with patch(
            "services.proxy_dispatcher.CostCalculator.compute_cost",
            return_value=0.001,
        ):
            await finalize_usage(
                mock_db, usage_id=42, tokens_in=100, tokens_out=50, model="gpt-4o"
            )

        (
            mock_db.rollback.assert_called_once(),
            ("db.rollback() must be called after commit failure in finalize_usage."),
        )
