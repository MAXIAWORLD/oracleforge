"""Unit tests for services/webhook_dispatcher.

These tests do NOT require a running backend. They exercise the pure
dispatcher logic via direct function calls, and use an in-process test
HTTP server to verify actual POST delivery + signature verification.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from services.webhook_dispatcher import (
    _meets_threshold,
    _sign_payload,
    dispatch_event,
)


# ── Pure function tests ──────────────────────────────────────────


class TestRiskThreshold:
    def test_exact_match_passes(self) -> None:
        assert _meets_threshold("critical", "critical") is True
        assert _meets_threshold("high", "high") is True

    def test_higher_than_minimum_passes(self) -> None:
        assert _meets_threshold("critical", "high") is True
        assert _meets_threshold("critical", "medium") is True
        assert _meets_threshold("high", "medium") is True

    def test_lower_than_minimum_fails(self) -> None:
        assert _meets_threshold("medium", "high") is False
        assert _meets_threshold("low", "critical") is False
        assert _meets_threshold("none", "low") is False

    def test_unknown_level_defaults_low(self) -> None:
        # Unknown actual level → score 0 → below any real threshold
        assert _meets_threshold("unknown", "low") is False


class TestSignature:
    def test_sign_payload_produces_hex_sha256(self) -> None:
        secret = "shared-secret"
        body = b'{"event":"test"}'
        sig = _sign_payload(secret, body)
        assert len(sig) == 64  # sha256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in sig)

    def test_signature_is_deterministic(self) -> None:
        body = b'{"event":"test"}'
        assert _sign_payload("k", body) == _sign_payload("k", body)

    def test_signature_changes_with_secret(self) -> None:
        body = b'{"event":"test"}'
        assert _sign_payload("k1", body) != _sign_payload("k2", body)

    def test_signature_verifiable_with_hmac(self) -> None:
        secret = "my-secret"
        body = b'{"ok":true}'
        sig = _sign_payload(secret, body)
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert sig == expected


# ── End-to-end dispatch tests via in-process HTTP server ─────────


class _CapturingHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures POST bodies + headers into a class attribute."""
    captured: list[dict] = []

    def log_message(self, *args, **kwargs) -> None:
        pass  # silence

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        # Normalize header keys to lowercase for stable lookup
        self.captured.append({
            "path": self.path,
            "body": body,
            "headers": {k.lower(): v for k, v in self.headers.items() if k.lower().startswith("x-")},
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


@pytest.fixture
def http_capture():
    """Spin up an in-process HTTP server on a free port and yield a capture list."""
    _CapturingHandler.captured = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{port}/hook", "captured": _CapturingHandler.captured}
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_dispatch_fires_on_matching_risk(http_capture: dict) -> None:
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": http_capture["url"],
        "secret": "",
        "min_risk_level": "high",
        "enabled": True,
    }]
    results = await dispatch_event(
        webhooks=webhooks,
        event_type="scan.critical_risk",
        risk_level="critical",
        payload={"scan_id": 42},
    )
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert "HTTP 200" in results[0]["message"]
    assert len(http_capture["captured"]) == 1
    body = json.loads(http_capture["captured"][0]["body"])
    assert body["event"] == "scan.critical_risk"
    assert body["risk_level"] == "critical"
    assert body["scan_id"] == 42


@pytest.mark.asyncio
async def test_dispatch_skips_below_threshold(http_capture: dict) -> None:
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": http_capture["url"],
        "secret": "",
        "min_risk_level": "critical",
        "enabled": True,
    }]
    results = await dispatch_event(
        webhooks=webhooks,
        event_type="scan.medium_risk",
        risk_level="medium",  # below critical threshold
        payload={},
    )
    assert results == []
    assert len(http_capture["captured"]) == 0


@pytest.mark.asyncio
async def test_dispatch_skips_disabled(http_capture: dict) -> None:
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": http_capture["url"],
        "secret": "",
        "min_risk_level": "low",
        "enabled": False,  # disabled
    }]
    results = await dispatch_event(
        webhooks=webhooks,
        event_type="scan.critical_risk",
        risk_level="critical",
        payload={},
    )
    assert results == []
    assert len(http_capture["captured"]) == 0


@pytest.mark.asyncio
async def test_dispatch_signs_with_hmac_when_secret_set(http_capture: dict) -> None:
    secret = "super-shared-secret"
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": http_capture["url"],
        "secret": secret,
        "min_risk_level": "critical",
        "enabled": True,
    }]
    await dispatch_event(
        webhooks=webhooks,
        event_type="test",
        risk_level="critical",
        payload={"k": "v"},
    )
    assert len(http_capture["captured"]) == 1
    captured = http_capture["captured"][0]
    sig_header = captured["headers"].get("x-guardforge-signature", "")
    assert sig_header.startswith("sha256=")
    # Verify HMAC matches body
    body_bytes = captured["body"].encode("utf-8")
    expected_hex = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_hex}"


@pytest.mark.asyncio
async def test_dispatch_no_signature_when_no_secret(http_capture: dict) -> None:
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": http_capture["url"],
        "secret": "",
        "min_risk_level": "critical",
        "enabled": True,
    }]
    await dispatch_event(
        webhooks=webhooks,
        event_type="test",
        risk_level="critical",
        payload={},
    )
    captured = http_capture["captured"][0]
    assert "x-guardforge-signature" not in captured["headers"]


@pytest.mark.asyncio
async def test_dispatch_dead_url_returns_failure() -> None:
    webhooks = [{
        "id": 1,
        "name": "test",
        "url": "http://127.0.0.1:1/dead",  # port 1 is unassignable
        "secret": "",
        "min_risk_level": "low",
        "enabled": True,
    }]
    results = await dispatch_event(
        webhooks=webhooks,
        event_type="test",
        risk_level="critical",
        payload={},
    )
    assert len(results) == 1
    assert results[0]["ok"] is False
    assert "error" in results[0]["message"].lower() or "transport" in results[0]["message"].lower()


@pytest.mark.asyncio
async def test_dispatch_multiple_webhooks_parallel(http_capture: dict) -> None:
    # Two webhooks pointing to the same capture URL
    webhooks = [
        {
            "id": 1, "name": "a", "url": http_capture["url"],
            "secret": "", "min_risk_level": "critical", "enabled": True,
        },
        {
            "id": 2, "name": "b", "url": http_capture["url"],
            "secret": "", "min_risk_level": "critical", "enabled": True,
        },
    ]
    results = await dispatch_event(
        webhooks=webhooks,
        event_type="test",
        risk_level="critical",
        payload={},
    )
    assert len(results) == 2
    assert all(r["ok"] for r in results)
    assert len(http_capture["captured"]) == 2


@pytest.mark.asyncio
async def test_dispatch_empty_webhooks_returns_empty() -> None:
    results = await dispatch_event(
        webhooks=[],
        event_type="test",
        risk_level="critical",
        payload={},
    )
    assert results == []
