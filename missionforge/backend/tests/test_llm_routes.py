"""TDD tests for routes/llm.py — HTTP endpoints with TestClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    # Simulate lifespan: set app.state that routes depend on
    app.state.http_client = httpx.AsyncClient(timeout=5.0)
    app.state.chroma_client = None
    return TestClient(app)


class TestListModels:
    """GET /api/llm/models returns available tiers."""

    def test_returns_models_list(self, client: TestClient) -> None:
        resp = client.get("/api/llm/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 1
        # Auto should always be present
        model_ids = [m["id"] for m in data["models"]]
        assert "auto" in model_ids


class TestChatCompletion:
    """POST /api/llm/chat — OpenAI-compatible chat."""

    def test_missing_messages_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/llm/chat", json={})
        assert resp.status_code == 422

    def test_empty_messages_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/llm/chat",
            json={"messages": []},
        )
        assert resp.status_code == 400

    @patch("routes.llm.get_llm_router")
    def test_successful_chat(self, mock_get_router: MagicMock, client: TestClient) -> None:
        mock_router = MagicMock()
        mock_router.call = AsyncMock(return_value="Hello! I can help.")
        mock_router.classify_complexity = MagicMock(return_value="local")
        mock_get_router.return_value = mock_router

        resp = client.post(
            "/api/llm/chat",
            json={
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello! I can help."
        assert "usage" in data
        assert "tier" in data

    @patch("routes.llm.get_llm_router")
    def test_all_providers_down_returns_503(self, mock_get_router: MagicMock, client: TestClient) -> None:
        mock_router = MagicMock()
        mock_router.call = AsyncMock(return_value="")
        mock_get_router.return_value = mock_router

        resp = client.post(
            "/api/llm/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 503


class TestTextCompletion:
    """POST /api/llm/completions — text completion."""

    def test_missing_prompt_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/llm/completions", json={})
        assert resp.status_code == 422

    @patch("routes.llm.get_llm_router")
    def test_successful_completion(self, mock_get_router: MagicMock, client: TestClient) -> None:
        mock_router = MagicMock()
        mock_router.call = AsyncMock(return_value="completed text")
        mock_router.classify_complexity = MagicMock(return_value="local")
        mock_get_router.return_value = mock_router

        resp = client.post(
            "/api/llm/completions",
            json={"prompt": "Once upon a time"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "text_completion"
        assert data["choices"][0]["text"] == "completed text"


class TestUsage:
    """GET /api/llm/usage — today's usage stats."""

    def test_returns_usage_stats(self, client: TestClient) -> None:
        resp = client.get("/api/llm/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "total_calls" in data
        assert "total_cost_usd" in data
