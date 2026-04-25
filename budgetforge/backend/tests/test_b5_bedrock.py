"""TDD B5 — AWS Bedrock (C02-C06, H18).

B5.1: Import relatif cassé → import absolu.
B5.2: boto3 sync → asyncio.to_thread.
B5.3: API moderne converse (pas invoke_model + prompt format).
B5.4: Usage réel (tokens != 0 hardcodé).
B5.5: Détection model par model_id (pas contenu message).
B5.6: Sentinelle non-configuré → HTTPException 503 (pas ValueError).
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock


# ── B5.1 — Import absolu (C03) ────────────────────────────────────────────────


def test_aws_bedrock_client_import_works():
    """C03: L'import de aws_bedrock_client ne doit pas lever ImportError."""
    try:
        from services.aws_bedrock_client import AWSBedrockClient, aws_bedrock_client
    except ImportError as e:
        pytest.fail(f"ImportError: {e}")


# ── B5.6 — Sentinelle non-configuré (H18) ────────────────────────────────────


@pytest.mark.asyncio
async def test_forward_aws_bedrock_not_configured_raises_503():
    """H18: forward_aws_bedrock doit lever HTTPException 503 (pas ValueError) si non configuré."""
    from fastapi import HTTPException
    from services.proxy_forwarder import ProxyForwarder

    with patch("services.proxy_forwarder.aws_bedrock_client") as mock_client:
        mock_client.is_configured.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await ProxyForwarder.forward_aws_bedrock(
                {"model": "anthropic.claude-v2", "messages": []}
            )

    assert exc_info.value.status_code == 503
    assert "configured" in exc_info.value.detail.lower()


# ── B5.2 — async via to_thread (C05) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_forward_aws_bedrock_uses_asyncio_to_thread():
    """C05: L'appel boto3 synchrone doit être wrappé dans asyncio.to_thread."""
    from services.proxy_forwarder import ProxyForwarder

    thread_call_count = [0]
    original_to_thread = asyncio.to_thread

    async def mock_to_thread(fn, *args, **kwargs):
        thread_call_count[0] += 1
        return await original_to_thread(fn, *args, **kwargs)

    mock_response = {
        "id": "test-id",
        "object": "chat.completion",
        "choices": [
            {
                "message": {"role": "assistant", "content": "hello"},
                "index": 0,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with patch("services.proxy_forwarder.aws_bedrock_client") as mock_client:
        mock_client.is_configured.return_value = True
        mock_client.invoke_model_converse.return_value = mock_response

        with patch("services.proxy_forwarder.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = mock_to_thread
            await ProxyForwarder.forward_aws_bedrock(
                {
                    "model": "anthropic.claude-3",
                    "messages": [{"role": "user", "content": "hello"}],
                }
            )

    # asyncio.to_thread doit être utilisé pour l'appel sync boto3
    assert thread_call_count[0] >= 1 or mock_asyncio.to_thread.called


# ── B5.4 — Usage réel (C02) ──────────────────────────────────────────────────


def test_aws_bedrock_convert_from_converse_returns_real_usage():
    """C02: La réponse convertie doit contenir les vrais tokens (pas 0 hardcodé)."""
    from services.aws_bedrock_client import AWSBedrockClient

    client = AWSBedrockClient.__new__(AWSBedrockClient)

    converse_response = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Hello world"}],
            }
        },
        "usage": {
            "inputTokens": 42,
            "outputTokens": 17,
            "totalTokens": 59,
        },
        "stopReason": "end_turn",
    }

    result = client.convert_from_converse_response(
        converse_response, "anthropic.claude-3"
    )

    assert result["usage"]["prompt_tokens"] == 42, (
        f"Expected 42 prompt_tokens, got {result['usage']['prompt_tokens']}"
    )
    assert result["usage"]["completion_tokens"] == 17, (
        f"Expected 17 completion_tokens, got {result['usage']['completion_tokens']}"
    )
    assert result["usage"]["total_tokens"] == 59


# ── B5.5 — Détection model par model_id (C04) ────────────────────────────────


def test_convert_to_converse_uses_model_id_not_message_content():
    """C04: La conversion doit utiliser model_id, pas le contenu du message."""
    from services.aws_bedrock_client import AWSBedrockClient

    client = AWSBedrockClient.__new__(AWSBedrockClient)

    # Messages qui auraient trompé l'ancien code (pas de "claude" dans content)
    messages = [{"role": "user", "content": "Write me a Python function"}]

    result = client.convert_to_converse_messages(messages)

    # Doit retourner le format converse standard quelle que soit la teneur des messages
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert isinstance(result[0]["content"], list)


# ── B5.3 — API moderne converse (C06) ────────────────────────────────────────


def test_invoke_model_converse_calls_converse_api():
    """C06: invoke_model_converse doit utiliser client.converse(), pas invoke_model()."""
    from services.aws_bedrock_client import AWSBedrockClient

    client = AWSBedrockClient.__new__(AWSBedrockClient)
    mock_boto3 = MagicMock()
    mock_boto3.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "hi"}]}},
        "usage": {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7},
        "stopReason": "end_turn",
    }
    client.client = mock_boto3

    messages = [{"role": "user", "content": "hi"}]

    # Patcher is_configured pour simuler un client configuré
    with patch.object(client, "is_configured", return_value=True):
        client.invoke_model_converse(
            "anthropic.claude-3-sonnet", messages, temperature=0.5, max_tokens=100
        )

    assert mock_boto3.converse.called, "client.converse() doit être appelé"
    assert not mock_boto3.invoke_model.called, (
        "invoke_model() dépréciée ne doit PAS être appelée"
    )
