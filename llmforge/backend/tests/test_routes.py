"""TDD tests for LLMForge routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app
from services.cache import ResponseCache


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.state.http_client = httpx.AsyncClient(timeout=5.0)
    app.state.cache = ResponseCache()
    from services.llm_router import LLMRouter
    from core.config import get_settings
    app.state.llm_router = LLMRouter(
        settings=get_settings(),
        http_client=app.state.http_client,
        cache=app.state.cache,
    )
    return TestClient(app, headers={"X-API-Key": "test-secret-key-32-chars-ok!!"})


class TestHealth:
    def test_health(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "providers_configured" in data
        assert "cache_enabled" in data


class TestModels:
    def test_list_models(self, client) -> None:
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        ids = [m["id"] for m in data["models"]]
        assert "auto" in ids
        assert "local" in ids


class TestChat:
    def test_empty_messages_400(self, client) -> None:
        resp = client.post("/api/chat", json={"messages": []})
        assert resp.status_code == 400

    @patch("routes.router._get_router")
    def test_successful_chat(self, mock_get, client) -> None:
        mock_router = MagicMock()
        mock_router.call = AsyncMock(return_value=("Hello!", "fast", False))
        mock_router.classify_complexity = MagicMock(return_value="fast")
        mock_get.return_value = mock_router

        resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["tier"] == "fast"
        assert data["cached"] is False


class TestCacheEndpoints:
    def test_cache_stats(self, client) -> None:
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_cache_clear(self, client) -> None:
        resp = client.post("/api/cache/clear")
        assert resp.status_code == 200
        assert "cleared" in resp.json()


class TestUsage:
    def test_usage(self, client) -> None:
        resp = client.get("/api/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_calls" in data
        assert "total_cache_hits" in data

    def test_usage_tiers(self, client) -> None:
        resp = client.get("/api/usage/tiers")
        assert resp.status_code == 200
        assert "tiers" in resp.json()
