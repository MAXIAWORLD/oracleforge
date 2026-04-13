"""In-process route tests using FastAPI TestClient.

These tests import the app directly and call routes via TestClient, which
means pytest-cov can track the routes/*.py modules (unlike the HTTP-based
test_e2e.py which hits an external backend process).

They use a temporary SQLite database for isolation.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


# Configure a test DB BEFORE importing the app
@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    db_dir = tmp_path_factory.mktemp("routes_test_db")
    db_path = db_dir / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-1234567890"
    os.environ["VAULT_ENCRYPTION_KEY"] = ""  # auto-generate
    os.environ["RATE_LIMIT_MAX_REQUESTS"] = "10000"

    # Clear cached settings so new env is picked up
    from core.config import get_settings
    get_settings.cache_clear()

    from main import create_app
    app = create_app()

    with TestClient(app) as c:
        yield c


_HEADERS = {"X-API-Key": "test-secret-key-1234567890"}


# ── Scanner routes ────────────────────────────────────────────────


class TestScannerRoutes:
    def test_scan_email_detection(self, client: TestClient) -> None:
        res = client.post("/api/scan", json={"text": "reach me at foo@bar.com"}, headers=_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert "email" in data["pii_types"]
        assert data["pii_count"] >= 1

    def test_scan_dry_run(self, client: TestClient) -> None:
        res = client.post(
            "/api/scan",
            json={"text": "call +33 6 12 34 56 78", "dry_run": True},
            headers=_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["anonymized_text"] is None

    def test_scan_requires_auth(self, client: TestClient) -> None:
        res = client.post("/api/scan", json={"text": "test"})
        assert res.status_code == 401

    def test_scan_rejects_empty_text(self, client: TestClient) -> None:
        res = client.post("/api/scan", json={"text": ""}, headers=_HEADERS)
        assert res.status_code == 422

    def test_llm_wrap_strips_pii(self, client: TestClient) -> None:
        res = client.post(
            "/api/llm/wrap",
            json={"text": "My card is 4532015112830366"},
            headers=_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert "4532015112830366" not in data["safe_text"]
        assert data["pii_stripped"] >= 1

    def test_tokenize_returns_session_id(self, client: TestClient) -> None:
        res = client.post("/api/tokenize", json={"text": "Mr Alice"}, headers=_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "tokenized_text" in data

    def test_detokenize_roundtrip(self, client: TestClient) -> None:
        tok = client.post(
            "/api/tokenize",
            json={"text": "Contact Mr Bob at bob@example.com"},
            headers=_HEADERS,
        ).json()
        res = client.post(
            "/api/detokenize",
            json={"text": tok["tokenized_text"], "session_id": tok["session_id"]},
            headers=_HEADERS,
        )
        assert res.status_code == 200
        assert "bob@example.com" in res.json()["original_text"]

    def test_detokenize_unknown_session_404(self, client: TestClient) -> None:
        res = client.post(
            "/api/detokenize",
            json={"text": "[EMAIL_aaaa]", "session_id": "00000000-0000-0000-0000-000000000000"},
            headers=_HEADERS,
        )
        assert res.status_code == 404

    def test_policies_returns_16_presets(self, client: TestClient) -> None:
        res = client.get("/api/policies", headers=_HEADERS)
        assert res.status_code == 200
        names = [p["name"] for p in res.json()["policies"]]
        assert "gdpr" in names
        assert "eu_ai_act" in names
        assert "ccpa" in names
        assert len(names) >= 16

    def test_audit_returns_entries(self, client: TestClient) -> None:
        # Generate some scans first
        client.post("/api/scan", json={"text": "email@x.com"}, headers=_HEADERS)
        client.post("/api/scan", json={"text": "another@y.com"}, headers=_HEADERS)
        res = client.get("/api/audit?limit=10", headers=_HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert "entries" in body
        assert len(body["entries"]) >= 2
        assert isinstance(body["entries"][0]["pii_types"], list)


# ── Vault routes (Bearer auth also works via X-API-Key) ──────────


class TestVaultRoutes:
    def test_vault_store_and_get(self, client: TestClient) -> None:
        store_res = client.post(
            "/api/vault/store",
            json={"key": "test_api_key", "value": "sk-secret-123"},
            headers=_HEADERS,
        )
        assert store_res.status_code == 200
        get_res = client.get("/api/vault/get/test_api_key", headers=_HEADERS)
        assert get_res.status_code == 200
        assert get_res.json()["value"] == "sk-secret-123"

    def test_vault_get_missing_returns_404(self, client: TestClient) -> None:
        res = client.get("/api/vault/get/nonexistent_key", headers=_HEADERS)
        assert res.status_code == 404

    def test_vault_delete_then_missing(self, client: TestClient) -> None:
        client.post(
            "/api/vault/store",
            json={"key": "ephemeral", "value": "gone"},
            headers=_HEADERS,
        )
        del_res = client.delete("/api/vault/delete/ephemeral", headers=_HEADERS)
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True
        get_res = client.get("/api/vault/get/ephemeral", headers=_HEADERS)
        assert get_res.status_code == 404

    def test_vault_keys_listed(self, client: TestClient) -> None:
        client.post(
            "/api/vault/store",
            json={"key": "listed_key_a", "value": "x"},
            headers=_HEADERS,
        )
        res = client.get("/api/vault/keys", headers=_HEADERS)
        assert res.status_code == 200
        assert "listed_key_a" in res.json()["keys"]


# ── Entities routes ──────────────────────────────────────────────


class TestEntitiesRoutes:
    def test_create_list_detect_delete(self, client: TestClient) -> None:
        # Create
        res = client.post(
            "/api/entities",
            json={
                "name": "in_process_test_id",
                "pattern": r"IPTEST-\d{4}",
                "risk_level": "low",
                "confidence": 0.95,
                "description": "in-process test",
            },
            headers=_HEADERS,
        )
        assert res.status_code == 201, res.text

        # List
        list_res = client.get("/api/entities", headers=_HEADERS)
        assert list_res.status_code == 200
        names = [e["name"] for e in list_res.json()["entities"]]
        assert "in_process_test_id" in names

        # Scan should detect
        scan_res = client.post(
            "/api/scan",
            json={"text": "Ticket IPTEST-1234 logged"},
            headers=_HEADERS,
        )
        assert "in_process_test_id" in scan_res.json()["pii_types"]

        # Delete
        del_res = client.delete("/api/entities/in_process_test_id", headers=_HEADERS)
        assert del_res.status_code == 200

    def test_invalid_regex_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/entities",
            json={"name": "bad_regex", "pattern": "[unclosed", "risk_level": "low"},
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_invalid_name_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/entities",
            json={"name": "BAD NAME", "pattern": "test", "risk_level": "low"},
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_invalid_risk_level_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/entities",
            json={"name": "bad_risk", "pattern": "test", "risk_level": "extreme"},
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_duplicate_name_returns_409(self, client: TestClient) -> None:
        client.post(
            "/api/entities",
            json={"name": "dup_test", "pattern": "A\\d+", "risk_level": "low"},
            headers=_HEADERS,
        )
        res = client.post(
            "/api/entities",
            json={"name": "dup_test", "pattern": "B\\d+", "risk_level": "low"},
            headers=_HEADERS,
        )
        assert res.status_code == 409
        client.delete("/api/entities/dup_test", headers=_HEADERS)

    def test_reload_endpoint(self, client: TestClient) -> None:
        res = client.post("/api/entities/reload", headers=_HEADERS)
        assert res.status_code == 200
        assert res.json()["reloaded"] is True


# ── Webhooks routes ──────────────────────────────────────────────


class TestWebhooksRoutes:
    def test_create_list_delete(self, client: TestClient) -> None:
        create_res = client.post(
            "/api/webhooks",
            json={
                "name": "in_proc_wh",
                "url": "http://127.0.0.1:1/dead",
                "min_risk_level": "critical",
                "enabled": True,
            },
            headers=_HEADERS,
        )
        assert create_res.status_code == 201
        wh_id = create_res.json()["id"]

        list_res = client.get("/api/webhooks", headers=_HEADERS)
        assert list_res.status_code == 200
        ids = [w["id"] for w in list_res.json()["webhooks"]]
        assert wh_id in ids

        del_res = client.delete(f"/api/webhooks/{wh_id}", headers=_HEADERS)
        assert del_res.status_code == 200

    def test_invalid_url_rejected(self, client: TestClient) -> None:
        res = client.post(
            "/api/webhooks",
            json={"name": "bad", "url": "not-a-url", "min_risk_level": "critical"},
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_invalid_min_risk_rejected(self, client: TestClient) -> None:
        res = client.post(
            "/api/webhooks",
            json={"name": "bad", "url": "https://example.com", "min_risk_level": "invalid"},
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_delete_unknown_returns_404(self, client: TestClient) -> None:
        res = client.delete("/api/webhooks/99999", headers=_HEADERS)
        assert res.status_code == 404

    def test_test_endpoint_on_dead_url(self, client: TestClient) -> None:
        create_res = client.post(
            "/api/webhooks",
            json={
                "name": "test_target",
                "url": "http://127.0.0.1:1/dead",
                "min_risk_level": "critical",
                "enabled": True,
            },
            headers=_HEADERS,
        )
        wh_id = create_res.json()["id"]
        try:
            res = client.post(f"/api/webhooks/{wh_id}/test", headers=_HEADERS)
            assert res.status_code == 200
            results = res.json()["results"]
            assert len(results) == 1
            assert results[0]["ok"] is False  # dead URL
        finally:
            client.delete(f"/api/webhooks/{wh_id}", headers=_HEADERS)


# ── Reports routes ───────────────────────────────────────────────


class TestReportsRoutes:
    def test_summary_shape(self, client: TestClient) -> None:
        res = client.get("/api/reports/summary", headers=_HEADERS)
        assert res.status_code == 200
        body = res.json()
        for key in ("period", "total_scans", "pii_by_type", "action_distribution", "risk_distribution"):
            assert key in body

    def test_summary_with_date_range(self, client: TestClient) -> None:
        res = client.get(
            "/api/reports/summary?from_date=2026-04-01&to_date=2026-04-30",
            headers=_HEADERS,
        )
        assert res.status_code == 200

    def test_summary_invalid_date_format(self, client: TestClient) -> None:
        res = client.get(
            "/api/reports/summary?from_date=not-a-date",
            headers=_HEADERS,
        )
        assert res.status_code == 422

    def test_timeline_day_granularity(self, client: TestClient) -> None:
        res = client.get("/api/reports/timeline?granularity=day", headers=_HEADERS)
        assert res.status_code == 200
        assert res.json()["granularity"] == "day"

    def test_timeline_hour_granularity(self, client: TestClient) -> None:
        res = client.get("/api/reports/timeline?granularity=hour", headers=_HEADERS)
        assert res.status_code == 200

    def test_timeline_invalid_granularity(self, client: TestClient) -> None:
        res = client.get("/api/reports/timeline?granularity=week", headers=_HEADERS)
        assert res.status_code == 422

    def test_pdf_export_returns_valid_pdf(self, client: TestClient) -> None:
        res = client.get("/api/reports/pdf", headers=_HEADERS)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF-")
        assert b"%%EOF" in res.content[-20:]

    def test_pdf_export_with_org_name(self, client: TestClient) -> None:
        res = client.get("/api/reports/pdf?org_name=Acme+Corp", headers=_HEADERS)
        assert res.status_code == 200
        assert res.content.startswith(b"%PDF-")


# ── Health + OpenAPI smoke ──────────────────────────────────────


def test_health_public(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_openapi_enriched(client: TestClient) -> None:
    res = client.get("/openapi.json")
    assert res.status_code == 200
    doc = res.json()
    assert doc["info"]["title"] == "GuardForge"
    assert len(doc["info"].get("description", "")) > 500
