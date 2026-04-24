"""TDD — Bloc 5: onboarding email correctness + URL from settings."""

import email
from unittest.mock import patch, MagicMock


# ── helpers ───────────────────────────────────────────────────────────────────


def _captured_body(mock_smtp_instance) -> str:
    """Decode and return the plain-text body from the sendmail MIME payload."""
    sendmail_args = mock_smtp_instance.sendmail.call_args
    assert sendmail_args is not None, "sendmail was never called"
    raw = sendmail_args[0][2]
    msg = email.message_from_string(raw)
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            return payload.decode("utf-8")
    return raw


def _make_smtp_mock(mock_smtp_class):
    """Wire up SMTP context manager mock."""
    instance = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=instance)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
    return instance


# ── send_onboarding_email ─────────────────────────────────────────────────────


class TestSendOnboardingEmail:
    @patch("services.onboarding_email.settings")
    def test_returns_false_when_smtp_not_configured(self, mock_settings):
        mock_settings.smtp_host = ""
        from services.onboarding_email import send_onboarding_email

        assert send_onboarding_email("u@x.com", "key-abc", "free") is False

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_returns_true_on_success(self, mock_settings, mock_smtp_class):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "u"
        mock_settings.smtp_password = "p"
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://test.example.com"
        _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_onboarding_email

        assert send_onboarding_email("user@test.com", "key-xyz", "pro") is True

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_body_contains_api_key(self, mock_settings, mock_smtp_class):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "u"
        mock_settings.smtp_password = "p"
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://test.example.com"
        instance = _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_onboarding_email

        send_onboarding_email("u@test.com", "MY-SECRET-KEY", "free")

        body = _captured_body(instance)
        assert "MY-SECRET-KEY" in body

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_body_contains_plan_label(self, mock_settings, mock_smtp_class):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = ""
        mock_settings.smtp_password = ""
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://test.example.com"
        instance = _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_onboarding_email

        send_onboarding_email("u@test.com", "k", "agency")

        body = _captured_body(instance)
        assert "Agency" in body

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_body_url_uses_settings_app_url(self, mock_settings, mock_smtp_class):
        """RED: body must reference settings.app_url, not a hardcoded string."""
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = ""
        mock_settings.smtp_password = ""
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://custom-domain.example.com"
        instance = _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_onboarding_email

        send_onboarding_email("u@test.com", "k", "pro")

        body = _captured_body(instance)
        assert "https://custom-domain.example.com" in body
        assert "llmbudget.maxiaworld.app" not in body

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_returns_false_on_smtp_error(self, mock_settings, mock_smtp_class):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "u"
        mock_settings.smtp_password = "p"
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://test.example.com"
        mock_smtp_class.side_effect = OSError("connection refused")

        from services.onboarding_email import send_onboarding_email

        assert send_onboarding_email("u@test.com", "k", "free") is False


# ── send_downgrade_email ──────────────────────────────────────────────────────


class TestSendDowngradeEmail:
    @patch("services.onboarding_email.settings")
    def test_returns_false_when_smtp_not_configured(self, mock_settings):
        mock_settings.smtp_host = ""
        from services.onboarding_email import send_downgrade_email

        assert send_downgrade_email("u@x.com") is False

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_returns_true_on_success(self, mock_settings, mock_smtp_class):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "u"
        mock_settings.smtp_password = "p"
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://test.example.com"
        _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_downgrade_email

        assert send_downgrade_email("u@test.com") is True

    @patch("services.onboarding_email.smtplib.SMTP")
    @patch("services.onboarding_email.settings")
    def test_downgrade_body_url_uses_settings_app_url(
        self, mock_settings, mock_smtp_class
    ):
        """RED: downgrade body must reference settings.app_url, not hardcoded."""
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = ""
        mock_settings.smtp_password = ""
        mock_settings.alert_from_email = "from@test.com"
        mock_settings.app_url = "https://custom-domain.example.com"
        instance = _make_smtp_mock(mock_smtp_class)

        from services.onboarding_email import send_downgrade_email

        send_downgrade_email("u@test.com")

        body = _captured_body(instance)
        assert "https://custom-domain.example.com" in body
        assert "llmbudget.maxiaworld.app" not in body
