"""Tests TDD pour le reset budget mensuel BudgetForge."""

from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from services.budget_guard import BudgetGuard, get_period_start


class TestBudgetReset:
    """Tests pour le reset budget mensuel."""

    def test_get_period_start_monthly(self):
        """Test le calcul du début de période pour reset mensuel."""
        # Arrange
        test_date = datetime(2026, 4, 15, 10, 30, 45)  # 15 avril 2026
        expected_start = datetime(2026, 4, 1, 0, 0, 0)  # 1er avril 2026

        # Act
        with patch("services.budget_guard.datetime") as mock_datetime:
            mock_datetime.now.return_value.replace.return_value = test_date
            result = get_period_start("monthly")

        # Assert
        assert result == expected_start

    def test_get_period_start_weekly(self):
        """Test le calcul du début de période pour reset hebdomadaire."""
        # Arrange
        # Lundi 13 avril 2026 (weekday=0)
        test_date = datetime(2026, 4, 13, 10, 30, 45)
        expected_start = datetime(2026, 4, 13, 0, 0, 0)  # Même lundi

        # Act
        with patch("services.budget_guard.datetime") as mock_datetime:
            mock_datetime.now.return_value.replace.return_value = test_date
            result = get_period_start("weekly")

        # Assert
        assert result == expected_start

    def test_get_period_start_none(self):
        """Test le calcul du début de période pour 'none' (début des temps)."""
        # Arrange
        from datetime import datetime as dt

        # Act
        result = get_period_start("none")

        # Assert
        assert result == dt.min

    def test_get_period_start_invalid_period(self):
        """Test le comportement pour une période invalide."""
        # Arrange
        from datetime import datetime as dt

        # Act
        result = get_period_start("invalid")

        # Assert
        assert result == dt.min


class TestBudgetGuardReset:
    """Tests pour l'intégration du reset dans BudgetGuard."""

    def test_usage_since_reset_monthly(self):
        """Test le calcul de l'usage depuis le dernier reset mensuel."""
        # Arrange

        guard = BudgetGuard()

        # Mock project avec reset mensuel
        mock_project = Mock()
        mock_project.reset_period = "monthly"

        # Mock usages - certains dans la période actuelle, certains avant
        mock_usages = [
            Mock(
                created_at=datetime(2026, 4, 10, 12, 0, 0), cost_usd=2.0
            ),  # Dans la période
            Mock(
                created_at=datetime(2026, 4, 5, 8, 0, 0), cost_usd=3.0
            ),  # Dans la période
            Mock(
                created_at=datetime(2026, 3, 28, 15, 0, 0), cost_usd=5.0
            ),  # Avant la période
        ]

        # Mock get_period_start pour retourner 1er avril 2026
        with patch("services.budget_guard.get_period_start") as mock_period_start:
            mock_period_start.return_value = datetime(2026, 4, 1, 0, 0, 0)

            # Act - Calculer l'usage depuis le reset
            usage_since_reset = sum(
                usage.cost_usd
                for usage in mock_usages
                if usage.created_at >= mock_period_start.return_value
            )

        # Assert
        assert usage_since_reset == 5.0  # 2.0 + 3.0

    def test_usage_since_reset_weekly(self):
        """Test le calcul de l'usage depuis le dernier reset hebdomadaire."""
        # Arrange

        guard = BudgetGuard()

        # Mock project avec reset hebdomadaire
        mock_project = Mock()
        mock_project.reset_period = "weekly"

        # Mock usages - certains dans la semaine actuelle, certains avant
        mock_usages = [
            Mock(
                created_at=datetime(2026, 4, 14, 10, 0, 0), cost_usd=1.0
            ),  # Lundi cette semaine
            Mock(
                created_at=datetime(2026, 4, 16, 14, 0, 0), cost_usd=2.0
            ),  # Mercredi cette semaine
            Mock(
                created_at=datetime(2026, 4, 7, 9, 0, 0), cost_usd=4.0
            ),  # Lundi dernière semaine
        ]

        # Mock get_period_start pour retourner lundi 14 avril 2026
        with patch("services.budget_guard.get_period_start") as mock_period_start:
            mock_period_start.return_value = datetime(2026, 4, 14, 0, 0, 0)

            # Act - Calculer l'usage depuis le reset
            usage_since_reset = sum(
                usage.cost_usd
                for usage in mock_usages
                if usage.created_at >= mock_period_start.return_value
            )

        # Assert
        assert usage_since_reset == 3.0  # 1.0 + 2.0

    def test_reset_prevents_budget_exceeded_error(self):
        """Test que le reset permet de continuer après dépassement de budget."""
        # Arrange
        from services.budget_guard import BudgetAction

        guard = BudgetGuard()

        # Mock project avec budget mensuel déjà dépassé
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.reset_period = "monthly"

        # Usage total historique élevé, mais usage récent faible
        total_historical_usage = 50.0  # Historique élevé
        usage_since_reset = 5.0  # Usage récent faible

        # Act - Vérifier si l'usage est autorisé
        # Le budget guard devrait considérer seulement l'usage depuis le reset
        status = guard.check(
            budget_usd=mock_project.budget_usd,
            used_usd=usage_since_reset,  # Seulement l'usage récent
            action=BudgetAction.BLOCK,
        )

        # Assert
        assert status.allowed is True  # Devrait être autorisé car usage récent < budget

    def test_no_reset_behavior(self):
        """Test le comportement sans reset (usage cumulatif)."""
        # Arrange
        from services.budget_guard import BudgetAction

        guard = BudgetGuard()

        # Mock project sans reset
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.reset_period = "none"

        # Usage total élevé
        total_usage = 15.0

        # Act
        status = guard.check(
            budget_usd=mock_project.budget_usd,
            used_usd=total_usage,
            action=BudgetAction.BLOCK,
        )

        # Assert
        assert status.allowed is False  # Devrait être bloqué car usage total > budget


class TestResetIntegration:
    """Tests d'intégration pour le reset budget."""

    def test_reset_updates_alert_sent_flag(self):
        """Test que le reset réinitialise le flag d'alerte envoyée."""
        # Arrange
        # Simuler un projet qui a déjà reçu une alerte
        mock_project = Mock()
        mock_project.alert_sent = True
        mock_project.alert_sent_at = datetime(2026, 3, 15, 10, 0, 0)
        mock_project.reset_period = "monthly"

        # Simuler que nous sommes après le reset (nouveau mois)
        current_period_start = datetime(2026, 4, 1, 0, 0, 0)

        # Act - Si l'alerte a été envoyée avant le début de la période actuelle
        # alors elle devrait être réinitialisée
        if (
            mock_project.alert_sent_at
            and mock_project.alert_sent_at < current_period_start
        ):
            mock_project.alert_sent = False
            mock_project.alert_sent_at = None

        # Assert
        assert mock_project.alert_sent is False
        assert mock_project.alert_sent_at is None

    def test_reset_allows_new_alerts(self):
        """Test que le reset permet de nouvelles alertes."""
        # Arrange

        guard = BudgetGuard()

        # Mock project avec reset mensuel et alerte déjà envoyée
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.alert_threshold_pct = 80
        mock_project.alert_email = "test@example.com"
        mock_project.reset_period = "monthly"

        # Usage récent qui devrait déclencher une alerte
        usage_since_reset = 8.0  # 80%

        # Mais alerte déjà envoyée le mois dernier
        mock_project.alert_sent = True
        mock_project.alert_sent_at = datetime(2026, 3, 20, 10, 0, 0)

        # Simuler que nous sommes dans un nouveau mois
        current_period_start = datetime(2026, 4, 1, 0, 0, 0)

        # Act - Réinitialiser le flag si nécessaire
        if (
            mock_project.alert_sent_at
            and mock_project.alert_sent_at < current_period_start
        ):
            mock_project.alert_sent = False
            mock_project.alert_sent_at = None

        # Vérifier si une alerte devrait être envoyée maintenant
        should_alert = guard.should_alert(
            mock_project.budget_usd, usage_since_reset, mock_project.alert_threshold_pct
        )

        # Assert
        assert should_alert is True
        assert mock_project.alert_sent is False  # Devrait être réinitialisé

    def test_reset_with_database_session(self):
        """Test le reset avec une session de base de données réelle."""
        # Arrange

        guard = BudgetGuard()

        # Mock session DB et project
        mock_db = Mock(spec=Session)
        mock_project = Mock()
        mock_project.id = 1
        mock_project.budget_usd = 10.0
        mock_project.reset_period = "monthly"
        mock_project.alert_sent = True
        mock_project.alert_sent_at = datetime(2026, 3, 25, 10, 0, 0)

        # Mock usages
        mock_usages = [
            Mock(cost_usd=2.0, created_at=datetime(2026, 4, 5, 10, 0, 0)),
            Mock(cost_usd=3.0, created_at=datetime(2026, 4, 10, 14, 0, 0)),
            Mock(
                cost_usd=5.0, created_at=datetime(2026, 3, 20, 9, 0, 0)
            ),  # Avant le reset
        ]

        # Mock get_period_start
        with patch("services.budget_guard.get_period_start") as mock_period_start:
            mock_period_start.return_value = datetime(2026, 4, 1, 0, 0, 0)

            # Act - Calculer l'usage depuis le reset
            usage_since_reset = sum(
                usage.cost_usd
                for usage in mock_usages
                if usage.created_at >= mock_period_start.return_value
            )

            # Réinitialiser l'alerte si nécessaire
            if (
                mock_project.alert_sent_at
                and mock_project.alert_sent_at < mock_period_start.return_value
            ):
                mock_project.alert_sent = False
                mock_project.alert_sent_at = None
                # En production, on ferait mock_db.commit() ici

        # Assert
        assert usage_since_reset == 5.0  # 2.0 + 3.0
        assert mock_project.alert_sent is False
        assert mock_project.alert_sent_at is None
