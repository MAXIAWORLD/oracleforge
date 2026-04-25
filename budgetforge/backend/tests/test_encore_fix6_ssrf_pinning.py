"""TDD RED — encore fix6 : SSRF DNS rebinding via IP pinning dans send_webhook.

Problème actuel :
  alert_service.send_webhook() appelle is_safe_webhook_url(url) puis httpx.post(url).
  Entre les deux, le DNS peut être rebindé vers une IP privée (TOCTOU).
  Fix : résoudre le DNS une fois, valider l'IP, pinner l'IP dans la requête HTTP.

Fix requis :
  Utiliser core.url_validator.resolve_safe_host(url) pour obtenir (pinned_url, host_header).
  Appeler client.post(pinned_url, headers={"Host": host_header}).
  Si resolve_safe_host lève ValueError → refus, return False.
"""

import pytest
from unittest.mock import patch, AsyncMock


class TestSendWebhookUsesIPPinning:
    """send_webhook doit utiliser resolve_safe_host, pas is_safe_webhook_url + post(url)."""

    @pytest.mark.asyncio
    async def test_resolve_safe_host_called_not_is_safe_webhook_url(self):
        """resolve_safe_host doit être appelé à la place de is_safe_webhook_url."""
        from services.alert_service import AlertService

        resolve_called = []
        is_safe_called = []

        def fake_resolve(url):
            resolve_called.append(url)
            return ("https://1.2.3.4/hook", "legit.example.com")

        mock_resp = AsyncMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with (
            patch("services.alert_service.resolve_safe_host", side_effect=fake_resolve),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            await AlertService.send_webhook(
                url="https://legit.example.com/hook",
                project_name="test",
                used_usd=10.0,
                budget_usd=100.0,
            )

        assert len(resolve_called) > 0, (
            "resolve_safe_host must be called. "
            "Current code uses is_safe_webhook_url (TOCTOU vulnerability)."
        )

    @pytest.mark.asyncio
    async def test_post_uses_original_url_not_pinned_ip(self):
        """httpx.post doit utiliser l'URL originale (TLS valide le cert via hostname)."""
        from services.alert_service import AlertService

        original_url = "https://legit.example.com/hook"
        pinned_url = "https://1.2.3.4/hook"
        host_header = "legit.example.com"

        posted_urls = []

        async def fake_post(url, **kwargs):
            posted_urls.append(url)
            return AsyncMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with (
            patch(
                "services.alert_service.resolve_safe_host",
                return_value=(pinned_url, host_header),
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            await AlertService.send_webhook(
                url=original_url,
                project_name="test",
                used_usd=10.0,
                budget_usd=100.0,
            )

        assert len(posted_urls) == 1
        assert posted_urls[0] == original_url, (
            f"HTTP POST must use original URL '{original_url}' for TLS cert validation. "
            f"Got: {posted_urls[0]}."
        )

    @pytest.mark.asyncio
    async def test_resolve_safe_host_failure_returns_false(self):
        """Si resolve_safe_host lève ValueError (SSRF blocked), retourner False sans POST."""
        from services.alert_service import AlertService

        post_called = []

        async def fake_post(*a, **kw):
            post_called.append(True)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with (
            patch(
                "services.alert_service.resolve_safe_host",
                side_effect=ValueError("SSRF: IP privée"),
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await AlertService.send_webhook(
                url="http://192.168.1.1/hook",
                project_name="test",
                used_usd=10.0,
                budget_usd=100.0,
            )

        assert result is False, (
            f"send_webhook must return False when SSRF blocked. Got: {result}"
        )
        assert len(post_called) == 0, "POST must not be made when SSRF blocked"

    @pytest.mark.asyncio
    async def test_tls_verify_enabled_not_disabled(self):
        """verify=True doit être passé à AsyncClient (pas verify=False)."""
        from services.alert_service import AlertService

        with (
            patch(
                "services.alert_service.resolve_safe_host",
                return_value=("https://1.2.3.4/hook", "hooks.slack.com"),
            ),
            patch("services.alert_service.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock()
            mock_cls.return_value = mock_client

            await AlertService.send_webhook(
                url="https://hooks.slack.com/T123/B456/xyz",
                project_name="test",
                used_usd=10.0,
                budget_usd=100.0,
            )

        call_kwargs = mock_cls.call_args.kwargs if mock_cls.call_args else {}
        assert call_kwargs.get("verify") is True, (
            f"AsyncClient doit être construit avec verify=True. Got: {call_kwargs.get('verify')}"
        )
