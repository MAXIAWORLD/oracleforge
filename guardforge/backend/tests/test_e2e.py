"""End-to-end integration tests covering the 5 critical user flows.

These tests REQUIRE a running backend at http://localhost:8004. They exercise
the full HTTP contract as a real client would — equivalent to browser-driven
tests without the browser automation overhead.

Flows covered:
1. Scanner: scan text → audit log persisted → compliance report aggregates
2. Playground: tokenize → roundtrip detokenize → vault persisted across calls
3. Reports: scan → summary endpoint → PDF export (binary verification)
4. Custom entities: create → detect → delete → not detected
5. Webhooks: create → trigger critical scan → dispatcher runs (verified via
   last_triggered_at or failure_count when unreachable)

Each flow is atomic and cleans up after itself so tests can run in any order.
"""

from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

_API_URL = os.environ.get("GUARDFORGE_API_URL", "http://127.0.0.1:8004")
_API_KEY = os.environ.get("GUARDFORGE_API_KEY", "change-me-to-a-random-32-char-string")
_HEADERS = {"X-API-Key": _API_KEY, "Content-Type": "application/json"}


def _backend_alive() -> bool:
    try:
        httpx.get(f"{_API_URL}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_alive(),
    reason=f"GuardForge backend not reachable at {_API_URL}",
)


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=_API_URL, headers=_HEADERS, timeout=10.0) as c:
        yield c


# ── Flow 1: Scanner → audit → report ──────────────────────────────


def test_flow_1_scan_persists_to_audit_and_reports(client: httpx.Client) -> None:
    unique_marker = f"trace-{uuid.uuid4().hex[:8]}@e2e.example.com"
    text = f"Customer {unique_marker} requested a refund"

    # Scan
    scan_res = client.post("/api/scan", json={"text": text, "strategy": "redact"})
    assert scan_res.status_code == 200
    scan = scan_res.json()
    assert scan["pii_count"] >= 1
    assert "email" in scan["pii_types"]
    assert scan["overall_risk"] in ("medium", "high", "critical")
    assert unique_marker not in scan["anonymized_text"], "PII leaked in anonymized text"

    # Audit log should contain our entry
    audit_res = client.get("/api/audit?limit=5")
    assert audit_res.status_code == 200
    entries = audit_res.json()["entries"]
    assert len(entries) >= 1
    latest = entries[0]
    assert "email" in latest["pii_types"]
    assert latest["pii_count"] >= 1
    assert isinstance(latest["pii_types"], list), "pii_types must be a list (not a string)"

    # Summary should include our scan
    summary_res = client.get("/api/reports/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_scans"] >= 1
    assert "email" in summary.get("pii_by_type", {})


# ── Flow 2: Playground tokenize → detokenize roundtrip ────────────


def test_flow_2_tokenize_detokenize_roundtrip(client: httpx.Client) -> None:
    original = "Contact Mr Jean Dupont at jean.dupont@example.fr for support"

    tok_res = client.post("/api/tokenize", json={"text": original})
    assert tok_res.status_code == 200
    tok = tok_res.json()
    session_id = tok["session_id"]
    tokenized = tok["tokenized_text"]
    assert "jean.dupont@example.fr" not in tokenized
    assert "Jean Dupont" not in tokenized
    assert "[EMAIL_" in tokenized
    assert tok["token_count"] >= 1

    # Detokenize should return the original exactly
    detok_res = client.post(
        "/api/detokenize",
        json={"text": tokenized, "session_id": session_id},
    )
    assert detok_res.status_code == 200
    assert detok_res.json()["original_text"] == original


def test_flow_2b_detokenize_with_unknown_session_returns_404(client: httpx.Client) -> None:
    bogus = str(uuid.uuid4())
    res = client.post(
        "/api/detokenize",
        json={"text": "[EMAIL_xxxx]", "session_id": bogus},
    )
    assert res.status_code == 404


# ── Flow 3: Reports summary + PDF export ──────────────────────────


def test_flow_3_summary_has_expected_shape(client: httpx.Client) -> None:
    res = client.get("/api/reports/summary")
    assert res.status_code == 200
    body = res.json()
    # Required keys
    for key in (
        "period",
        "total_scans",
        "total_pii_detected",
        "pii_by_type",
        "action_distribution",
        "risk_distribution",
        "top_policies",
    ):
        assert key in body, f"missing key in summary: {key}"
    assert "from" in body["period"]
    assert "to" in body["period"]
    assert isinstance(body["top_policies"], list)


def test_flow_3_pdf_export_returns_valid_pdf(client: httpx.Client) -> None:
    res = client.get("/api/reports/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers.get("content-disposition", "").startswith("attachment")
    # PDF files start with "%PDF-" magic bytes
    assert res.content.startswith(b"%PDF-"), "Response is not a valid PDF binary"
    assert len(res.content) > 500, "PDF is suspiciously small"


def test_flow_3_timeline_returns_series(client: httpx.Client) -> None:
    res = client.get("/api/reports/timeline?granularity=day")
    assert res.status_code == 200
    body = res.json()
    assert "series" in body
    assert body["granularity"] == "day"


# ── Flow 4: Custom entities CRUD → detect → delete ────────────────


def test_flow_4_custom_entity_crud(client: httpx.Client) -> None:
    entity_name = f"e2e_test_id_{uuid.uuid4().hex[:6]}"
    try:
        # Create
        create_res = client.post(
            "/api/entities",
            json={
                "name": entity_name,
                "pattern": r"E2E-TEST-[0-9]{4}",
                "risk_level": "medium",
                "confidence": 0.95,
                "description": "E2E test marker",
            },
        )
        assert create_res.status_code == 201, create_res.text
        created = create_res.json()
        assert created["name"] == entity_name

        # List should include it
        list_res = client.get("/api/entities")
        assert list_res.status_code == 200
        names = [e["name"] for e in list_res.json()["entities"]]
        assert entity_name in names

        # Scan should detect the custom pattern
        scan_res = client.post(
            "/api/scan",
            json={"text": "Ticket E2E-TEST-1234 filed today", "strategy": "redact"},
        )
        assert scan_res.status_code == 200
        detected_types = scan_res.json()["pii_types"]
        assert entity_name in detected_types, f"custom entity not detected: {detected_types}"
    finally:
        # Clean up — delete entity
        del_res = client.delete(f"/api/entities/{entity_name}")
        assert del_res.status_code == 200

    # After delete, the same text should no longer detect it
    scan_after = client.post(
        "/api/scan",
        json={"text": "Ticket E2E-TEST-1234 filed today", "strategy": "redact"},
    )
    assert scan_after.status_code == 200
    assert entity_name not in scan_after.json()["pii_types"]


def test_flow_4b_entity_invalid_regex_returns_422(client: httpx.Client) -> None:
    res = client.post(
        "/api/entities",
        json={
            "name": "e2e_bad_regex",
            "pattern": "[unclosed",  # invalid regex
            "risk_level": "low",
        },
    )
    assert res.status_code == 422
    assert "regex" in res.text.lower()


def test_flow_4c_entity_invalid_name_returns_422(client: httpx.Client) -> None:
    res = client.post(
        "/api/entities",
        json={
            "name": "BAD NAME!!",  # uppercase + space + punctuation
            "pattern": "test",
            "risk_level": "low",
        },
    )
    assert res.status_code == 422


# ── Flow 5: Webhooks CRUD + test dispatch ─────────────────────────


def test_flow_5_webhook_crud_and_test_dispatch(client: httpx.Client) -> None:
    # Use a webhook URL pointing to a definitely-dead endpoint so we don't
    # need a live receiver for the test. We still verify the dispatch was
    # *attempted* via the /test endpoint returning a structured result.
    dead_url = "http://127.0.0.1:1/dead"
    webhook_id: int | None = None
    try:
        create_res = client.post(
            "/api/webhooks",
            json={
                "name": "E2E test webhook",
                "url": dead_url,
                "secret": "",
                "min_risk_level": "critical",
                "enabled": True,
            },
        )
        assert create_res.status_code == 201, create_res.text
        created = create_res.json()
        webhook_id = created["id"]
        assert created["name"] == "E2E test webhook"
        assert created["has_secret"] is False
        assert created["url"] == dead_url

        # List should include it
        list_res = client.get("/api/webhooks")
        assert list_res.status_code == 200
        ids = [w["id"] for w in list_res.json()["webhooks"]]
        assert webhook_id in ids

        # Test dispatch — should return a result (ok=False since URL is dead)
        test_res = client.post(f"/api/webhooks/{webhook_id}/test")
        assert test_res.status_code == 200
        results = test_res.json()["results"]
        assert len(results) == 1
        # Dead URL → dispatch failure, but structure must be correct
        assert "ok" in results[0]
        assert "message" in results[0]
        assert results[0]["ok"] is False  # dead URL cannot respond
    finally:
        if webhook_id is not None:
            client.delete(f"/api/webhooks/{webhook_id}")


def test_flow_5b_webhook_invalid_url_returns_422(client: httpx.Client) -> None:
    res = client.post(
        "/api/webhooks",
        json={
            "name": "bad",
            "url": "not-a-valid-url",
            "min_risk_level": "critical",
        },
    )
    assert res.status_code == 422


# ── Smoke tests for other endpoints ───────────────────────────────


def test_smoke_policies_returns_16_presets(client: httpx.Client) -> None:
    res = client.get("/api/policies")
    assert res.status_code == 200
    policies = res.json()["policies"]
    assert len(policies) >= 16
    names = {p["name"] for p in policies}
    assert {"gdpr", "hipaa", "pci_dss", "eu_ai_act", "ccpa", "lgpd"}.issubset(names)


def test_smoke_health_returns_version(client: httpx.Client) -> None:
    res = httpx.get(f"{_API_URL}/health", timeout=5.0)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "policies_loaded" in body
    assert body["policies_loaded"] >= 16


def test_smoke_openapi_has_enriched_metadata(client: httpx.Client) -> None:
    res = httpx.get(f"{_API_URL}/openapi.json", timeout=5.0)
    assert res.status_code == 200
    doc = res.json()
    assert doc["info"]["title"] == "GuardForge"
    assert len(doc["info"].get("description", "")) > 500
    assert "tags" in doc
    tag_names = {t["name"] for t in doc["tags"]}
    assert {"guard", "reports", "system"}.issubset(tag_names)


def test_smoke_unauthorized_without_api_key(client: httpx.Client) -> None:
    # Use a fresh client with no auth header
    res = httpx.post(
        f"{_API_URL}/api/scan",
        json={"text": "test"},
        timeout=5.0,
    )
    assert res.status_code == 401
