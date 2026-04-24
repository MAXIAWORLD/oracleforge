"""TDD RED — encore fix3 : forward_azure_openai ne doit pas prendre base_url en paramètre positionnel.

Problème actuel :
  dispatch_openai_format() appelle : forward_fn(payload, api_key, timeout_s=...)
  Mais forward_azure_openai(request_body, api_key, base_url, timeout_s) attend base_url
  → TypeError au runtime (pas au démarrage).

Fix requis :
  forward_azure_openai lit settings.azure_openai_base_url en interne.
  Lève HTTPException(400) si non configuré.
  Même signature que les autres forwarders : (request_body, api_key, timeout_s).
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException

from services.proxy_forwarder import ProxyForwarder


class TestAzureForwarderSignature:
    """forward_azure_openai doit accepter (body, api_key, timeout_s) sans base_url positionnel."""

    @pytest.mark.asyncio
    async def test_azure_openai_no_base_url_raises_400(self):
        """Si AZURE_OPENAI_BASE_URL est vide, doit lever HTTPException 400 — pas TypeError."""
        with patch("services.proxy_forwarder.settings") as mock_settings:
            mock_settings.azure_openai_base_url = ""  # non configuré

            with pytest.raises(HTTPException) as exc_info:
                await ProxyForwarder.forward_azure_openai(
                    request_body={"model": "gpt-4o", "messages": []},
                    api_key="test-key",
                    timeout_s=60.0,
                )

        assert exc_info.value.status_code == 400, (
            f"Expected 400, got {exc_info.value.status_code}. "
            "Currently raises TypeError because base_url is a positional arg."
        )

    @pytest.mark.asyncio
    async def test_azure_openai_callable_without_base_url_arg(self):
        """Doit être appelable sans passer base_url comme argument."""
        import inspect

        sig = inspect.signature(ProxyForwarder.forward_azure_openai)
        params = list(sig.parameters.keys())

        assert "base_url" not in params, (
            f"base_url must not be a positional parameter. Current params: {params}. "
            "Callers (dispatch_openai_format) don't pass base_url."
        )

    @pytest.mark.asyncio
    async def test_azure_openai_uses_settings_base_url(self):
        """Doit lire l'URL depuis settings.azure_openai_base_url."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"choices": [], "usage": {}})

        captured_urls = []

        with patch("services.proxy_forwarder.settings") as mock_settings:
            mock_settings.azure_openai_base_url = "https://my-azure.openai.azure.com"

            async def fake_post(url, **kwargs):
                captured_urls.append(url)
                return mock_resp

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = fake_post

            with patch("httpx.AsyncClient", return_value=mock_client):
                await ProxyForwarder.forward_azure_openai(
                    request_body={"model": "gpt-4o", "messages": []},
                    api_key="test-key",
                    timeout_s=60.0,
                )

        assert len(captured_urls) == 1
        assert "my-azure.openai.azure.com" in captured_urls[0], (
            f"URL should use settings.azure_openai_base_url. Got: {captured_urls}"
        )

    @pytest.mark.asyncio
    async def test_azure_openai_none_base_url_raises_400(self):
        """Si AZURE_OPENAI_BASE_URL est None, doit lever HTTPException 400."""
        with patch("services.proxy_forwarder.settings") as mock_settings:
            mock_settings.azure_openai_base_url = None

            with pytest.raises(HTTPException) as exc_info:
                await ProxyForwarder.forward_azure_openai(
                    request_body={"model": "gpt-4o", "messages": []},
                    api_key="test-key",
                )

        assert exc_info.value.status_code == 400


class TestAzureStreamForwarderSignature:
    """forward_azure_openai_stream : même fix, même signature."""

    @pytest.mark.asyncio
    async def test_azure_stream_no_base_url_raises_400(self):
        """Si base_url manquant, le stream doit lever 400 — pas TypeError."""
        with patch("services.proxy_forwarder.settings") as mock_settings:
            mock_settings.azure_openai_base_url = ""

            with pytest.raises(HTTPException) as exc_info:
                # Doit lever avant d'entrer dans le stream
                async for _ in ProxyForwarder.forward_azure_openai_stream(
                    request_body={"model": "gpt-4o", "messages": []},
                    api_key="test-key",
                    timeout_s=60.0,
                ):
                    pass

        assert exc_info.value.status_code == 400

    def test_azure_stream_callable_without_base_url_arg(self):
        """Le stream ne doit pas avoir base_url comme paramètre positionnel."""
        import inspect

        sig = inspect.signature(ProxyForwarder.forward_azure_openai_stream)
        params = list(sig.parameters.keys())

        assert "base_url" not in params, (
            f"base_url must not be a positional parameter. Current params: {params}."
        )
