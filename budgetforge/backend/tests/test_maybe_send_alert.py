"""Tests unitaires pour maybe_send_alert."""

import pytest
from unittest.mock import patch
from services.proxy_dispatcher import maybe_send_alert
from core.models import Project


class TestMaybeSendAlert:
    """Tests unitaires pour la fonction maybe_send_alert."""

    @pytest.mark.asyncio
    async def test_alert_sent_when_threshold_crossed(self, db):
        """Teste que l'alerte est envoyée quand le seuil est dépassé."""
        # Créer un projet avec budget très bas et threshold à 1%
        project = Project(
            name="test-project",
            budget_usd=0.0001,
            alert_threshold_pct=1,
            alert_email="test@test.com",
            reset_period="none",
        )
        db.add(project)
        db.commit()

        # Simuler un usage qui dépasse le seuil
        with (
            patch("services.proxy_dispatcher.get_period_used_sql", return_value=0.0002),
            patch("services.proxy_dispatcher.guard.should_alert", return_value=True),
            patch(
                "services.alert_service.AlertService.send_email", return_value=True
            ) as mock_email,
        ):
            await maybe_send_alert(project, db)

            # Vérifier que l'email a été envoyé
            assert mock_email.called

    @pytest.mark.asyncio
    async def test_alert_not_sent_below_threshold(self, db):
        """Teste que l'alerte n'est pas envoyée en dessous du seuil."""
        project = Project(
            name="test-project",
            budget_usd=1.0,
            alert_threshold_pct=80,
            alert_email="test@test.com",
            reset_period="none",
        )
        db.add(project)
        db.commit()

        # Simuler un usage en dessous du seuil
        with (
            patch("services.proxy_dispatcher.get_period_used_sql", return_value=0.5),
            patch("services.proxy_dispatcher.guard.should_alert", return_value=False),
            patch("services.alert_service.AlertService.send_email") as mock_email,
        ):
            await maybe_send_alert(project, db)

            # Vérifier que l'email n'a pas été envoyé
            assert not mock_email.called

    @pytest.mark.asyncio
    async def test_alert_sent_only_once_per_period(self, db):
        """Teste que l'alerte n'est envoyée qu'une fois par période."""
        from datetime import datetime

        project = Project(
            name="test-project",
            budget_usd=0.0001,
            alert_threshold_pct=1,
            alert_email="test@test.com",
            reset_period="monthly",
            alert_sent=True,
            alert_sent_at=datetime.now(),  # Simuler alerte déjà envoyée
        )
        db.add(project)
        db.commit()

        with (
            patch("services.proxy_dispatcher.get_period_used_sql", return_value=0.0002),
            patch("services.proxy_dispatcher.guard.should_alert", return_value=True),
            patch("services.alert_service.AlertService.send_email") as mock_email,
        ):
            await maybe_send_alert(project, db)

            # Vérifier que l'email n'a pas été envoyé (alerte déjà envoyée)
            assert not mock_email.called
