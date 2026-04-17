"""Tests for V1.8 — Historical Prices."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest


# ── DB helpers ────────────────────────────────────────────────────────────────


class TestDBPriceSnapshots:
    """Unit tests for the price_snapshots table and helpers."""

    def test_insert_and_query_raw(self, session_app):
        from core.db import get_db, insert_price_snapshots, query_price_history

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        now = int(time.time())
        rows = [
            ("BTC", 74000.0, 3),
            ("BTC", 74100.0, 4),
            ("ETH", 2300.0, 3),
        ]
        count = insert_price_snapshots(db, rows)
        assert count == 3

        history = query_price_history(db, "BTC", now - 3600, 300)
        assert len(history) >= 1
        assert history[0]["price"] > 0
        assert "timestamp" in history[0]
        assert "samples" in history[0]

    def test_insert_empty_returns_zero(self, session_app):
        from core.db import get_db, insert_price_snapshots

        db = get_db()
        assert insert_price_snapshots(db, []) == 0

    def test_query_no_data_returns_empty(self, session_app):
        from core.db import get_db, query_price_history

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        history = query_price_history(db, "ZZZZZ", 0, 300)
        assert history == []

    def test_oldest_snapshot_ts(self, session_app):
        from core.db import get_db, insert_price_snapshots, oldest_snapshot_ts

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        assert oldest_snapshot_ts(db, "SOL") is None

        insert_price_snapshots(db, [("SOL", 88.5, 2)])
        ts = oldest_snapshot_ts(db, "SOL")
        assert ts is not None
        assert ts <= int(time.time())

    def test_purge_old_snapshots(self, session_app):
        from core.db import get_db, purge_old_snapshots

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        old_ts = int(time.time()) - 40 * 86400
        db.execute(
            "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
            "VALUES (?, ?, ?, ?)",
            ("BTC", 70000.0, 2, old_ts),
        )
        db.execute(
            "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
            "VALUES (?, ?, ?, ?)",
            ("BTC", 74000.0, 3, int(time.time())),
        )

        deleted = purge_old_snapshots(db, 30)
        assert deleted == 1

        remaining = db.execute(
            "SELECT COUNT(*) FROM price_snapshots"
        ).fetchone()[0]
        assert remaining == 1

    def test_downsampling_1h_bucket(self, session_app):
        from core.db import get_db, query_price_history

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        base_ts = (int(time.time()) // 3600) * 3600
        for i in range(12):
            db.execute(
                "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
                "VALUES (?, ?, ?, ?)",
                ("BTC", 74000.0 + i * 10, 3, base_ts + i * 300),
            )

        history = query_price_history(db, "BTC", base_ts - 1, 3600)
        assert len(history) == 1
        assert history[0]["samples"] == 12
        assert history[0]["price"] > 74000


# ── History service ──────────────────────────────────────────────────────────


class TestHistoryService:
    """Tests for services.oracle.history get_history()."""

    def test_get_history_default_interval(self, session_app):
        from core.db import get_db, insert_price_snapshots
        from services.oracle.history import get_history

        db = get_db()
        db.execute("DELETE FROM price_snapshots")
        insert_price_snapshots(db, [("BTC", 74500.0, 3)])

        result = get_history("BTC", range_key="24h")
        assert result is not None
        assert result["range"] == "24h"
        assert result["interval"] == "5m"
        assert result["symbol"] == "BTC"
        assert isinstance(result["datapoints"], list)
        assert result["count"] >= 0

    def test_get_history_7d_default_1h(self, session_app):
        from services.oracle.history import get_history

        result = get_history("BTC", range_key="7d")
        assert result is not None
        assert result["interval"] == "1h"

    def test_get_history_30d_default_1d(self, session_app):
        from services.oracle.history import get_history

        result = get_history("BTC", range_key="30d")
        assert result is not None
        assert result["interval"] == "1d"

    def test_get_history_explicit_interval(self, session_app):
        from services.oracle.history import get_history

        result = get_history("ETH", range_key="7d", interval_key="5m")
        assert result is not None
        assert result["interval"] == "5m"

    def test_get_history_invalid_range_returns_none(self, session_app):
        from services.oracle.history import get_history

        assert get_history("BTC", range_key="99d") is None

    def test_get_history_invalid_interval_returns_none(self, session_app):
        from services.oracle.history import get_history

        assert get_history("BTC", range_key="24h", interval_key="2h") is None


# ── Sampler ──────────────────────────────────────────────────────────────────


class TestSampler:
    """Tests for the background sampler."""

    @pytest.mark.asyncio
    async def test_sample_once_inserts_rows(self, session_app):
        from core.db import get_db
        from services.oracle.history import _sample_once

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        mock_results = {
            "BTC": {"price": 74500.0, "source": "pyth_crypto", "symbol": "BTC"},
            "ETH": {"price": 2350.0, "source": "pyth_crypto", "symbol": "ETH"},
        }

        with patch(
            "services.oracle.price_cascade.get_batch_prices",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            count, _results = await _sample_once()

        assert count == 2
        rows = db.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        assert rows == 2

    @pytest.mark.asyncio
    async def test_sample_once_skips_zero_price(self, session_app):
        from core.db import get_db
        from services.oracle.history import _sample_once

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        mock_results = {
            "BTC": {"price": 74500.0, "source": "pyth_crypto"},
            "BAD": {"price": 0, "source": "none"},
        }

        with patch(
            "services.oracle.price_cascade.get_batch_prices",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            count, _results = await _sample_once()

        assert count == 1

    @pytest.mark.asyncio
    async def test_sample_once_handles_error_gracefully(self, session_app):
        from services.oracle.history import _sample_once

        with patch(
            "services.oracle.price_cascade.get_batch_prices",
            new_callable=AsyncMock,
            return_value={},
        ):
            count, _results = await _sample_once()

        assert count == 0


# ── REST route ───────────────────────────────────────────────────────────────


class TestHistoryRoute:
    """Tests for GET /api/price/{symbol}/history."""

    def _seed_data(self, symbol: str = "BTC", n: int = 10):
        from core.db import get_db

        db = get_db()
        now = int(time.time())
        for i in range(n):
            db.execute(
                "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
                "VALUES (?, ?, ?, ?)",
                (symbol, 74000.0 + i * 50, 3, now - (n - i) * 300),
            )

    def test_history_200_with_data(self, client, api_key):
        from core.db import get_db

        db = get_db()
        db.execute("DELETE FROM price_snapshots")
        self._seed_data("BTC", 10)

        resp = client.get(
            "/api/price/BTC/history",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "disclaimer" in body
        data = body["data"]
        assert data["symbol"] == "BTC"
        assert data["range"] == "24h"
        assert data["interval"] == "5m"
        assert data["count"] > 0
        assert len(data["datapoints"]) == data["count"]
        dp = data["datapoints"][0]
        assert "timestamp" in dp
        assert "price" in dp

    def test_history_200_empty_no_data(self, client, api_key):
        from core.db import get_db

        db = get_db()
        db.execute("DELETE FROM price_snapshots")

        resp = client.get(
            "/api/price/ZZZZZ/history",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 0
        assert data["datapoints"] == []

    def test_history_custom_range_and_interval(self, client, api_key):
        resp = client.get(
            "/api/price/BTC/history?range=7d&interval=1h",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["range"] == "7d"
        assert data["interval"] == "1h"

    def test_history_invalid_range_400(self, client, api_key):
        resp = client.get(
            "/api/price/BTC/history?range=99d",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_history_invalid_interval_400(self, client, api_key):
        resp = client.get(
            "/api/price/BTC/history?range=24h&interval=2h",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_history_invalid_symbol_400(self, client, api_key):
        resp = client.get(
            "/api/price/bad-sym/history",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_history_no_auth_401(self, client):
        resp = client.get("/api/price/BTC/history")
        assert resp.status_code in (401, 402)

    def test_history_lowercase_symbol_uppercased(self, client, api_key):
        resp = client.get(
            "/api/price/btc/history",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["symbol"] == "BTC"


# ── MCP tool ─────────────────────────────────────────────────────────────────


class TestMCPHistoryTool:
    """Tests for the MCP get_price_history tool."""

    @pytest.mark.asyncio
    async def test_mcp_get_price_history_valid(self, session_app):
        from core.db import get_db
        from mcp_server.tools import get_price_history

        db = get_db()
        db.execute("DELETE FROM price_snapshots")
        now = int(time.time())
        db.execute(
            "INSERT INTO price_snapshots (symbol, price, source_count, sampled_at) "
            "VALUES (?, ?, ?, ?)",
            ("ETH", 2350.0, 3, now - 600),
        )

        result = await get_price_history("ETH")
        assert "data" in result
        assert result["data"]["symbol"] == "ETH"
        assert result["data"]["count"] >= 0

    @pytest.mark.asyncio
    async def test_mcp_get_price_history_invalid_symbol(self, session_app):
        from mcp_server.tools import get_price_history

        result = await get_price_history("bad!")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mcp_get_price_history_invalid_range(self, session_app):
        from mcp_server.tools import get_price_history

        result = await get_price_history("BTC", range="99d")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mcp_get_price_history_invalid_interval(self, session_app):
        from mcp_server.tools import get_price_history

        result = await get_price_history("BTC", interval="2h")
        assert "error" in result


# ── MCP server tool count ────────────────────────────────────────────────────


class TestMCPToolCount:
    """V1.9 bumps the MCP tool count to 17 (14 prior + 3 alert tools)."""

    def test_tool_count(self, session_app):
        from mcp_server.server import _TOOL_DEFINITIONS

        assert len(_TOOL_DEFINITIONS) == 17

    def test_dispatch_count(self, session_app):
        from mcp_server.server import _TOOL_DISPATCH

        assert len(_TOOL_DISPATCH) == 17

    def test_get_price_history_in_definitions(self, session_app):
        from mcp_server.server import _TOOL_DEFINITIONS

        names = {t.name for t in _TOOL_DEFINITIONS}
        assert "get_price_history" in names

    def test_get_price_history_in_dispatch(self, session_app):
        from mcp_server.server import _TOOL_DISPATCH

        assert "get_price_history" in _TOOL_DISPATCH
