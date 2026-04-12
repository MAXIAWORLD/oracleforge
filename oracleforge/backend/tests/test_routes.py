"""TDD tests for OracleForge routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app
from services.price_engine import PriceEngine, AggregatedPrice


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.state.http_client = httpx.AsyncClient(timeout=5.0)
    from core.config import get_settings
    app.state.price_engine = PriceEngine(
        settings=get_settings(),
        http_client=app.state.http_client,
    )
    return TestClient(app)


class TestHealth:
    def test_health(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "sources_healthy" in data
        assert "sources_total" in data


class TestSources:
    def test_list_sources(self, client) -> None:
        resp = client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert len(data["sources"]) >= 3


class TestCacheStats:
    def test_cache_stats(self, client) -> None:
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data


class TestBatchPrices:
    def test_empty_symbols_400(self, client) -> None:
        resp = client.post("/api/prices/batch", json={"symbols": []})
        assert resp.status_code == 400

    def test_too_many_symbols_400(self, client) -> None:
        resp = client.post("/api/prices/batch", json={"symbols": ["X"] * 51})
        assert resp.status_code == 400
