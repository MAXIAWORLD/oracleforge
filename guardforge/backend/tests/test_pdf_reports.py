"""Unit tests for services/pdf_reports.

Direct unit tests that don't require a running backend. Verify the PDF
rendering function produces valid binary output with the expected shape.
"""

from __future__ import annotations

from services.pdf_reports import render_compliance_report_pdf


def _sample_summary() -> dict:
    return {
        "period": {"from": "2026-04-01", "to": "2026-04-30"},
        "total_scans": 150,
        "total_pii_detected": 423,
        "pii_by_type": {
            "email": 120,
            "phone_international": 85,
            "credit_card": 12,
            "iban": 8,
            "siret_fr": 30,
        },
        "action_distribution": {
            "block": 45,
            "anonymize": 78,
            "allow": 20,
            "warn": 7,
        },
        "risk_distribution": {
            "critical": 20,
            "high": 55,
            "medium": 60,
            "low": 15,
        },
        "top_policies": [
            {"name": "gdpr", "count": 80},
            {"name": "strict", "count": 50},
            {"name": "hipaa", "count": 20},
        ],
    }


class TestPdfRendering:
    def test_returns_bytes(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary())
        assert isinstance(pdf, bytes)

    def test_starts_with_pdf_magic_bytes(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary())
        assert pdf.startswith(b"%PDF-")

    def test_has_reasonable_size(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary())
        # Should be at least 1KB (with tables, fonts, etc.) but not ridiculous
        assert 1000 < len(pdf) < 200_000

    def test_ends_with_eof_marker(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary())
        # PDF files end with %%EOF (possibly followed by newline)
        assert b"%%EOF" in pdf[-20:]

    def test_empty_summary_still_renders(self) -> None:
        minimal = {
            "period": {"from": "2026-04-01", "to": "2026-04-30"},
            "total_scans": 0,
            "total_pii_detected": 0,
            "pii_by_type": {},
            "action_distribution": {},
            "risk_distribution": {},
            "top_policies": [],
        }
        pdf = render_compliance_report_pdf(minimal)
        assert pdf.startswith(b"%PDF-")

    def test_org_name_accepted(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary(), org_name="Acme Corp")
        assert pdf.startswith(b"%PDF-")

    def test_none_org_name_accepted(self) -> None:
        pdf = render_compliance_report_pdf(_sample_summary(), org_name=None)
        assert pdf.startswith(b"%PDF-")

    def test_large_payload_does_not_crash(self) -> None:
        """Payload with many PII types shouldn't produce a malformed PDF."""
        big = _sample_summary()
        big["pii_by_type"] = {f"type_{i}": i for i in range(30)}
        big["top_policies"] = [{"name": f"policy_{i}", "count": i * 10} for i in range(15)]
        pdf = render_compliance_report_pdf(big)
        assert pdf.startswith(b"%PDF-")
        assert b"%%EOF" in pdf[-20:]

    def test_missing_period_keys_handled_gracefully(self) -> None:
        """If period is malformed, renderer should not crash."""
        summary = _sample_summary()
        summary["period"] = {}
        pdf = render_compliance_report_pdf(summary)
        assert pdf.startswith(b"%PDF-")
