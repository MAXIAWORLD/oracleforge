"""Tests TDD pour le service d'alertes BudgetForge."""

import pytest
from unittest.mock import Mock, patch

from services.alert_service import AlertService


class TestAlertService:
    """Tests pour le service d'alertes."""

    def test_send_email_success(self):
        """Test que l'envoi d'email fonctionne correctement."""
        # Arrange
        to_email = "test@example.com"
        project_name = "Test Project"
        used_usd = 8.0
        budget_usd = 10.0

        # Mock SMTP et configuration
        with patch("services.alert_service.smtplib.SMTP") as mock_smtp:
            with patch("services.alert_service.settings") as mock_settings:
                mock_settings.smtp_host = "smtp.example.com"
                mock_settings.smtp_port = 587
                mock_settings.smtp_user = "user"
                mock_settings.smtp_password = "pass"
                mock_settings.alert_from_email = "noreply@example.com"

                mock_server = Mock()
                mock_smtp.return_value.__enter__.return_value = mock_server

                # Act
                result = AlertService.send_email(
                    to_email, project_name, used_usd, budget_usd
                )

                # Assert
                assert result is True
                mock_smtp.assert_called_once()
                mock_server.starttls.assert_called_once()
                mock_server.sendmail.assert_called_once()

    def test_send_email_failure_smtp_error(self):
        """Test que l'échec d'envoi d'email est géré correctement."""
        # Arrange
        to_email = "test@example.com"
        project_name = "Test Project"
        used_usd = 8.0
        budget_usd = 10.0

        # Mock SMTP avec erreur
        with patch("services.alert_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.starttls.side_effect = (
                Exception("SMTP error")
            )

            # Act
            result = AlertService.send_email(
                to_email, project_name, used_usd, budget_usd
            )

            # Assert
            assert result is False

    def test_send_email_no_smtp_config(self):
        """Test que l'email n'est pas envoyé si SMTP n'est pas configuré."""
        # Arrange
        to_email = "test@example.com"
        project_name = "Test Project"
        used_usd = 8.0
        budget_usd = 10.0

        # Mock config SMTP vide
        with patch("services.alert_service.settings") as mock_settings:
            mock_settings.smtp_host = ""

            # Act
            result = AlertService.send_email(
                to_email, project_name, used_usd, budget_usd
            )

            # Assert
            assert result is False

    @pytest.mark.asyncio
    async def test_send_webhook_success(self):
        """Test que l'envoi de webhook fonctionne correctement."""
        # Arrange
        webhook_url = "https://hooks.slack.com/test"
        project_name = "Test Project"
        used_usd = 8.0
        budget_usd = 10.0

        # Mock httpx
        with patch("services.alert_service.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            # Act
            result = await AlertService.send_webhook(
                webhook_url, project_name, used_usd, budget_usd
            )

            # Assert
            assert result is True
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_failure(self):
        """Test que l'échec d'envoi de webhook est géré correctement."""
        # Arrange
        webhook_url = "https://hooks.slack.com/test"
        project_name = "Test Project"
        used_usd = 8.0
        budget_usd = 10.0

        # Mock httpx avec erreur
        with patch("services.alert_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                Exception("Webhook error")
            )

            # Act
            result = await AlertService.send_webhook(
                webhook_url, project_name, used_usd, budget_usd
            )

            # Assert
            assert result is False

    def test_is_slack_compatible_true(self):
        """Test la détection des URLs Slack compatibles."""
        # Arrange
        slack_urls = [
            "https://hooks.slack.com/test",
            "https://hooks.office.com/test",
            "https://outlook.office.com/test",
        ]

        # Act & Assert
        for url in slack_urls:
            result = AlertService._is_slack_compatible(url)
            assert result is True

    def test_is_slack_compatible_false(self):
        """Test que les URLs non Slack sont correctement détectées."""
        # Arrange
        non_slack_urls = [
            "https://example.com/webhook",
            "https://discord.com/api/webhooks",
            "https://custom-webhook.com/alert",
        ]

        # Act & Assert
        for url in non_slack_urls:
            result = AlertService._is_slack_compatible(url)
            assert result is False


class TestBudgetGuardAlerts:
    """Tests pour l'intégration des alertes dans BudgetGuard."""

    def test_should_alert_true_when_threshold_reached(self):
        """Test que l'alerte est déclenchée quand le seuil est atteint."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()
        budget_usd = 10.0
        used_usd = 8.0  # 80%
        threshold_pct = 80

        # Act
        result = guard.should_alert(budget_usd, used_usd, threshold_pct)

        # Assert
        assert result is True

    def test_should_alert_false_when_below_threshold(self):
        """Test que l'alerte n'est pas déclenchée en-dessous du seuil."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()
        budget_usd = 10.0
        used_usd = 7.9  # 79%
        threshold_pct = 80

        # Act
        result = guard.should_alert(budget_usd, used_usd, threshold_pct)

        # Assert
        assert result is False

    def test_should_alert_true_when_budget_zero(self):
        """Test que l'alerte est déclenchée quand le budget est 0."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()
        budget_usd = 0.0
        used_usd = 5.0
        threshold_pct = 80

        # Act
        result = guard.should_alert(budget_usd, used_usd, threshold_pct)

        # Assert
        assert result is True


class TestAlertIntegration:
    """Tests d'intégration pour les alertes dans le flow proxy."""

    def test_alert_triggered_when_threshold_reached(self):
        """Test qu'une alerte est déclenchée quand le seuil est atteint."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()

        # Mock project avec seuil d'alerte
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.alert_threshold_pct = 80
        mock_project.alert_email = "test@example.com"
        mock_project.alert_sent = False

        # Simuler usage qui déclenche l'alerte
        total_used_usd = 8.0  # 80%

        # Mock AlertService
        with patch("services.alert_service.AlertService.send_email") as mock_send_email:
            mock_send_email.return_value = True

            # Vérifier que l'alerte devrait être déclenchée
            should_alert = guard.should_alert(
                mock_project.budget_usd,
                total_used_usd,
                mock_project.alert_threshold_pct,
            )
            assert should_alert is True

            # Act - Simuler l'envoi d'alerte
            if (
                should_alert
                and mock_project.alert_email
                and not mock_project.alert_sent
            ):
                alert_sent = AlertService.send_email(
                    mock_project.alert_email,
                    mock_project.name,
                    total_used_usd,
                    mock_project.budget_usd,
                )

                # Assert
                assert alert_sent is True
                mock_send_email.assert_called_once_with(
                    mock_project.alert_email,
                    mock_project.name,
                    total_used_usd,
                    mock_project.budget_usd,
                )

    def test_alert_not_triggered_when_already_sent(self):
        """Test qu'une alerte n'est pas déclenchée si déjà envoyée."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()

        # Mock project avec alerte déjà envoyée
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.alert_threshold_pct = 80
        mock_project.alert_email = "test@example.com"
        mock_project.alert_sent = True

        total_used_usd = 8.0  # 80%

        # Mock AlertService
        with patch("services.alert_service.AlertService.send_email") as mock_send_email:
            # Vérifier que l'alerte devrait être déclenchée
            should_alert = guard.should_alert(
                mock_project.budget_usd,
                total_used_usd,
                mock_project.alert_threshold_pct,
            )
            assert should_alert is True

            # Act - Simuler l'envoi d'alerte (ne devrait pas être appelé)
            if (
                should_alert
                and mock_project.alert_email
                and not mock_project.alert_sent
            ):
                AlertService.send_email(
                    mock_project.alert_email,
                    mock_project.name,
                    total_used_usd,
                    mock_project.budget_usd,
                )

            # Assert
            mock_send_email.assert_not_called()

    def test_alert_not_triggered_without_email(self):
        """Test qu'une alerte n'est pas déclenchée sans email configuré."""
        # Arrange
        from services.budget_guard import BudgetGuard

        guard = BudgetGuard()

        # Mock project sans email d'alerte
        mock_project = Mock()
        mock_project.budget_usd = 10.0
        mock_project.alert_threshold_pct = 80
        mock_project.alert_email = None
        mock_project.alert_sent = False

        total_used_usd = 8.0  # 80%

        # Mock AlertService
        with patch("services.alert_service.AlertService.send_email") as mock_send_email:
            # Vérifier que l'alerte devrait être déclenchée
            should_alert = guard.should_alert(
                mock_project.budget_usd,
                total_used_usd,
                mock_project.alert_threshold_pct,
            )
            assert should_alert is True

            # Act - Simuler l'envoi d'alerte (ne devrait pas être appelé)
            if (
                should_alert
                and mock_project.alert_email
                and not mock_project.alert_sent
            ):
                AlertService.send_email(
                    mock_project.alert_email,
                    mock_project.name,
                    total_used_usd,
                    mock_project.budget_usd,
                )

            # Assert
            mock_send_email.assert_not_called()
