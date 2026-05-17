"""Tests for V1.9 — Alerts + Streaming."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════════════
# ── DB alert helpers ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestDBAlertHelpers:

    def test_create_and_get_alert(self, session_app):
        from core.db import create_alert, get_alert, get_db

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(
            db,
            key_hash="testhash",
            symbol="BTC",
            condition="above",
            threshold=80000.0,
            callback_url="https://example.com/hook",
        )
        assert aid > 0

        alert = get_alert(db, aid, "testhash")
        assert alert is not None
        assert alert["symbol"] == "BTC"
        assert alert["condition"] == "above"
        assert alert["threshold"] == 80000.0
        assert alert["active"] is True
        assert alert["triggered_at"] is None

    def test_get_alert_wrong_key_returns_none(self, session_app):
        from core.db import create_alert, get_alert, get_db

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(db, "k1", "ETH", "below", 2000.0, "https://x.com/h")
        assert get_alert(db, aid, "wrong_key") is None

    def test_list_alerts(self, session_app):
        from core.db import create_alert, get_db, list_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        create_alert(db, "k1", "ETH", "below", 2000.0, "https://a.com/h")
        create_alert(db, "k2", "SOL", "above", 100.0, "https://a.com/h")

        k1_alerts = list_alerts(db, "k1")
        assert len(k1_alerts) == 2
        k2_alerts = list_alerts(db, "k2")
        assert len(k2_alerts) == 1

    def test_delete_alert(self, session_app):
        from core.db import create_alert, delete_alert, get_db, list_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        assert delete_alert(db, aid, "k1") is True
        assert list_alerts(db, "k1") == []

    def test_delete_wrong_key_returns_false(self, session_app):
        from core.db import create_alert, delete_alert, get_db

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        assert delete_alert(db, aid, "wrong_key") is False

    def test_count_active_alerts(self, session_app):
        from core.db import count_active_alerts, create_alert, get_db, trigger_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        a1 = create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        create_alert(db, "k1", "ETH", "below", 2000.0, "https://a.com/h")
        assert count_active_alerts(db, "k1") == 2

        trigger_alert(db, a1)
        assert count_active_alerts(db, "k1") == 1

    def test_trigger_alert_deactivates(self, session_app):
        from core.db import create_alert, get_alert, get_db, trigger_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        trigger_alert(db, aid)

        alert = get_alert(db, aid, "k1")
        assert alert is not None
        assert alert["active"] is False
        assert alert["triggered_at"] is not None

    def test_get_all_active_alerts(self, session_app):
        from core.db import create_alert, get_all_active_alerts, get_db, trigger_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        a1 = create_alert(db, "k1", "BTC", "above", 90000.0, "https://a.com/h")
        create_alert(db, "k2", "ETH", "below", 2000.0, "https://b.com/h")
        trigger_alert(db, a1)

        active = get_all_active_alerts(db)
        assert len(active) == 1
        assert active[0]["symbol"] == "ETH"


# ══════════════════════════════════════════════════════════════════════════
# ── Alert evaluation ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestAlertEvaluation:

    def test_evaluate_above_triggered(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("above", 80000.0, 85000.0) is True

    def test_evaluate_above_not_triggered(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("above", 80000.0, 75000.0) is False

    def test_evaluate_below_triggered(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("below", 80000.0, 75000.0) is True

    def test_evaluate_below_not_triggered(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("below", 80000.0, 85000.0) is False

    def test_evaluate_at_threshold_above(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("above", 80000.0, 80000.0) is True

    def test_evaluate_at_threshold_below(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("below", 80000.0, 80000.0) is True

    def test_evaluate_invalid_condition(self, session_app):
        from services.oracle.alerts import evaluate_alert

        assert evaluate_alert("invalid", 80000.0, 85000.0) is False


# ══════════════════════════════════════════════════════════════════════════
# ── SSRF protection ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestCallbackURLValidation:

    def test_valid_https_url(self, session_app):
        from services.oracle.alerts import validate_callback_url

        assert validate_callback_url("https://example.com/webhook") is None

    def test_rejects_http(self, session_app):
        from services.oracle.alerts import validate_callback_url

        err = validate_callback_url("http://example.com/webhook")
        assert err is not None
        assert "HTTPS" in err

    def test_rejects_localhost(self, session_app):
        from services.oracle.alerts import validate_callback_url

        err = validate_callback_url("https://localhost/webhook")
        assert err is not None
        assert "localhost" in err

    def test_rejects_127_0_0_1(self, session_app):
        from services.oracle.alerts import validate_callback_url

        err = validate_callback_url("https://127.0.0.1/webhook")
        assert err is not None
        assert "localhost" in err

    def test_rejects_empty(self, session_app):
        from services.oracle.alerts import validate_callback_url

        assert validate_callback_url("") is not None

    def test_rejects_too_long(self, session_app):
        from services.oracle.alerts import validate_callback_url

        err = validate_callback_url("https://example.com/" + "a" * 2100)
        assert err is not None
        assert "2048" in err


# ══════════════════════════════════════════════════════════════════════════
# ── check_and_fire_alerts integration ──────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestCheckAndFireAlerts:

    @pytest.mark.asyncio
    async def test_fires_matching_alert(self, session_app):
        from core.db import create_alert, get_alert, get_db
        from services.oracle.alerts import check_and_fire_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(
            db, "k1", "BTC", "above", 70000.0,
            "https://example.com/hook",
        )

        with patch(
            "services.oracle.alerts.fire_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_webhook:
            triggered = await check_and_fire_alerts(
                {"BTC": {"price": 75000.0}}
            )

        assert triggered == 1
        mock_webhook.assert_called_once()
        alert = get_alert(db, aid, "k1")
        assert alert["active"] is False

    @pytest.mark.asyncio
    async def test_does_not_fire_unmet_condition(self, session_app):
        from core.db import create_alert, get_alert, get_db
        from services.oracle.alerts import check_and_fire_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        aid = create_alert(
            db, "k1", "BTC", "above", 90000.0,
            "https://example.com/hook",
        )

        with patch(
            "services.oracle.alerts.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook:
            triggered = await check_and_fire_alerts(
                {"BTC": {"price": 75000.0}}
            )

        assert triggered == 0
        mock_webhook.assert_not_called()
        alert = get_alert(db, aid, "k1")
        assert alert["active"] is True

    @pytest.mark.asyncio
    async def test_skips_missing_symbol(self, session_app):
        from core.db import create_alert, get_db
        from services.oracle.alerts import check_and_fire_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        create_alert(
            db, "k1", "ZZZZZ", "above", 1.0,
            "https://example.com/hook",
        )

        triggered = await check_and_fire_alerts(
            {"BTC": {"price": 75000.0}}
        )
        assert triggered == 0

    @pytest.mark.asyncio
    async def test_no_alerts_returns_zero(self, session_app):
        from core.db import get_db
        from services.oracle.alerts import check_and_fire_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        triggered = await check_and_fire_alerts(
            {"BTC": {"price": 75000.0}}
        )
        assert triggered == 0


# ══════════════════════════════════════════════════════════════════════════
# ── Sampler integration ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestSamplerAlertIntegration:

    @pytest.mark.asyncio
    async def test_sample_once_returns_results_for_alerts(self, session_app):
        from services.oracle.history import _sample_once

        mock_results = {
            "BTC": {"price": 74500.0, "source": "pyth_crypto", "symbol": "BTC"},
        }

        with patch(
            "services.oracle.price_cascade.get_batch_prices",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            count, results = await _sample_once()

        assert count == 1
        assert "BTC" in results


# ══════════════════════════════════════════════════════════════════════════
# ── REST routes ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestAlertRoutes:

    def test_create_alert_201(self, client, api_key):
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "BTC",
                "condition": "above",
                "threshold": 90000.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["id"] > 0
        assert data["symbol"] == "BTC"
        assert data["condition"] == "above"
        assert data["active"] is True

    def test_create_alert_invalid_condition_422(self, client, api_key):
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "BTC",
                "condition": "invalid",
                "threshold": 90000.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422

    def test_create_alert_bad_callback_400(self, client, api_key):
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "BTC",
                "condition": "above",
                "threshold": 90000.0,
                "callback_url": "http://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400
        assert "HTTPS" in resp.json()["error"]

    def test_create_alert_threshold_too_large_422(self, client, api_key):
        """Threshold above 1e12 must be rejected — never triggers and signals bad input."""
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "BTC",
                "condition": "above",
                "threshold": 1e13,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422

    def test_create_alert_quota_exceeded(self, client, api_key):
        for i in range(10):
            resp = client.post(
                "/api/alerts",
                json={
                    "symbol": f"SYM{i}",
                    "condition": "above",
                    "threshold": 100.0,
                    "callback_url": "https://example.com/hook",
                },
                headers={"X-API-Key": api_key},
            )
            assert resp.status_code == 201

        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "EXTRA",
                "condition": "above",
                "threshold": 100.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 429

    def test_list_alerts_200(self, client, api_key):
        client.post(
            "/api/alerts",
            json={
                "symbol": "ETH",
                "condition": "below",
                "threshold": 2000.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )

        resp = client.get("/api/alerts", headers={"X-API-Key": api_key})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] >= 1
        assert len(data["alerts"]) == data["count"]

    def test_delete_alert_200(self, client, api_key):
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "SOL",
                "condition": "above",
                "threshold": 200.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        aid = resp.json()["data"]["id"]

        resp = client.delete(
            f"/api/alerts/{aid}",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_delete_nonexistent_alert_404(self, client, api_key):
        resp = client.delete(
            "/api/alerts/999999",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 404

    def test_alert_no_auth_401(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code in (401, 402)

    def test_create_alert_lowercase_symbol_uppercased(self, client, api_key):
        resp = client.post(
            "/api/alerts",
            json={
                "symbol": "btc",
                "condition": "above",
                "threshold": 90000.0,
                "callback_url": "https://example.com/hook",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["symbol"] == "BTC"


# ══════════════════════════════════════════════════════════════════════════
# ── SSE streaming route ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestStreamRoute:

    def test_stream_no_symbols_400(self, client, api_key):
        resp = client.get(
            "/api/prices/stream?symbols=",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_stream_too_many_symbols_400(self, client, api_key):
        syms = ",".join(f"SYM{i}" for i in range(15))
        resp = client.get(
            f"/api/prices/stream?symbols={syms}",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_stream_invalid_symbol_400(self, client, api_key):
        resp = client.get(
            "/api/prices/stream?symbols=bad!sym",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 400

    def test_stream_no_auth_401(self, client):
        resp = client.get("/api/prices/stream?symbols=BTC")
        assert resp.status_code in (401, 402)


# ══════════════════════════════════════════════════════════════════════════
# ── MCP tools ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════


class TestMCPAlertTools:

    @pytest.mark.asyncio
    async def test_create_price_alert(self, session_app):
        from core.db import get_db
        from mcp_server.tools import create_price_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        result = await create_price_alert(
            symbol="BTC",
            condition="above",
            threshold=90000.0,
            callback_url="https://example.com/hook",
        )
        assert "data" in result
        assert result["data"]["id"] > 0
        assert result["data"]["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_create_price_alert_invalid_symbol(self, session_app):
        from mcp_server.tools import create_price_alert

        result = await create_price_alert(
            symbol="bad!", condition="above",
            threshold=90000.0, callback_url="https://x.com/h",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_price_alert_bad_condition(self, session_app):
        from mcp_server.tools import create_price_alert

        result = await create_price_alert(
            symbol="BTC", condition="maybe",
            threshold=90000.0, callback_url="https://x.com/h",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_price_alert_bad_url(self, session_app):
        from mcp_server.tools import create_price_alert

        result = await create_price_alert(
            symbol="BTC", condition="above",
            threshold=90000.0, callback_url="http://x.com/h",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_price_alerts(self, session_app):
        from core.db import get_db
        from mcp_server.tools import create_price_alert, list_price_alerts

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        await create_price_alert(
            symbol="ETH", condition="below",
            threshold=2000.0, callback_url="https://x.com/h",
        )

        result = await list_price_alerts()
        assert "data" in result
        assert result["data"]["count"] >= 1

    @pytest.mark.asyncio
    async def test_delete_price_alert(self, session_app):
        from core.db import get_db
        from mcp_server.tools import create_price_alert, delete_price_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        create_result = await create_price_alert(
            symbol="SOL", condition="above",
            threshold=200.0, callback_url="https://x.com/h",
        )
        aid = create_result["data"]["id"]

        result = await delete_price_alert(aid)
        assert "data" in result
        assert result["data"]["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_alert(self, session_app):
        from core.db import get_db
        from mcp_server.tools import delete_price_alert

        db = get_db()
        db.execute("DELETE FROM price_alerts")

        result = await delete_price_alert(999999)
        assert "error" in result


class TestMCPToolCountV19:

    def test_tool_count_is_17(self, session_app):
        from mcp_server.server import _TOOL_DEFINITIONS
        assert len(_TOOL_DEFINITIONS) == 17

    def test_dispatch_count_is_17(self, session_app):
        from mcp_server.server import _TOOL_DISPATCH
        assert len(_TOOL_DISPATCH) == 17

    def test_alert_tools_in_definitions(self, session_app):
        from mcp_server.server import _TOOL_DEFINITIONS

        names = {t.name for t in _TOOL_DEFINITIONS}
        assert "create_price_alert" in names
        assert "list_price_alerts" in names
        assert "delete_price_alert" in names

    def test_alert_tools_in_dispatch(self, session_app):
        from mcp_server.server import _TOOL_DISPATCH

        assert "create_price_alert" in _TOOL_DISPATCH
        assert "list_price_alerts" in _TOOL_DISPATCH
        assert "delete_price_alert" in _TOOL_DISPATCH
