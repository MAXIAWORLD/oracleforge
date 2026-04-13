"""GuardForge — PDF compliance report generator using reportlab.

Generates a single-page or multi-page PDF compliance report from a
summary dict (matching the /api/reports/summary response shape).
The report is designed for CISO/DPO presentation: clean, professional,
auditable.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


# Brand colors — match the dashboard neon palette
NEON_CYAN = colors.HexColor("#00bcd4")
NEON_VIOLET = colors.HexColor("#7c3aed")
NEON_PINK = colors.HexColor("#e91e63")
NEON_GREEN = colors.HexColor("#10b981")
NEON_AMBER = colors.HexColor("#f59e0b")
DARK_GREY = colors.HexColor("#334155")
LIGHT_GREY = colors.HexColor("#f1f5f9")
MUTED = colors.HexColor("#64748b")


def _build_styles() -> dict[str, ParagraphStyle]:
    """Return a dict of named paragraph styles."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            name="GFTitle",
            parent=base["Title"],
            fontSize=22,
            leading=26,
            textColor=DARK_GREY,
            spaceAfter=4,
            alignment=0,
        ),
        "subtitle": ParagraphStyle(
            name="GFSubtitle",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=18,
        ),
        "h2": ParagraphStyle(
            name="GFH2",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            textColor=DARK_GREY,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            name="GFBody",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=DARK_GREY,
        ),
        "small": ParagraphStyle(
            name="GFSmall",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
    }


def _stat_card_table(label: str, value: str | int, color: colors.Color) -> Table:
    """Build a 2-row stat card: small label + big value."""
    t = Table(
        [[label], [str(value)]],
        colWidths=[4 * cm],
        rowHeights=[0.6 * cm, 1.0 * cm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("TEXTCOLOR", (0, 1), (-1, 1), color),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _kv_table(rows: list[tuple[str, str]], col_widths: tuple[float, float]) -> Table:
    """Build a generic 2-column key-value table."""
    if not rows:
        rows = [("—", "—")]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK_GREY),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_compliance_report_pdf(
    summary: dict[str, Any],
    org_name: str | None = None,
) -> bytes:
    """Generate a PDF compliance report from a summary dict.

    Args:
        summary: Dict matching /api/reports/summary response shape.
        org_name: Optional organization name shown in the header.

    Returns:
        PDF binary content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="GuardForge Compliance Report",
        author="GuardForge",
        subject="PII Compliance Report",
    )
    styles = _build_styles()
    story: list[Any] = []

    period = summary.get("period", {})
    period_from = period.get("from", "—")
    period_to = period.get("to", "—")
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Header
    story.append(Paragraph("GuardForge Compliance Report", styles["title"]))
    subtitle_text = (
        f"Period: <b>{period_from}</b> to <b>{period_to}</b>"
        f" &nbsp;·&nbsp; Generated: {generated_at}"
    )
    if org_name:
        subtitle_text = f"<b>{org_name}</b><br/>" + subtitle_text
    story.append(Paragraph(subtitle_text, styles["subtitle"]))

    # Stat cards row
    total_scans = summary.get("total_scans", 0)
    total_pii = summary.get("total_pii_detected", 0)
    risk_dist = summary.get("risk_distribution", {})
    critical_count = risk_dist.get("critical", 0)
    high_count = risk_dist.get("high", 0)

    stats_table = Table(
        [[
            _stat_card_table("Total scans", total_scans, NEON_CYAN),
            _stat_card_table("PII detected", total_pii, NEON_VIOLET),
            _stat_card_table("Critical risk", critical_count, NEON_PINK),
            _stat_card_table("High risk", high_count, NEON_AMBER),
        ]],
        colWidths=[4.2 * cm] * 4,
    )
    stats_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 0.6 * cm))

    # PII by type
    story.append(Paragraph("PII detected by type", styles["h2"]))
    pii_by_type = summary.get("pii_by_type", {})
    pii_rows = sorted(pii_by_type.items(), key=lambda x: x[1], reverse=True)
    pii_kv = [(name, str(count)) for name, count in pii_rows] or [("None detected", "0")]
    story.append(_kv_table(pii_kv, col_widths=(12 * cm, 4 * cm)))

    # Action distribution
    story.append(Paragraph("Action distribution", styles["h2"]))
    action_dist = summary.get("action_distribution", {})
    action_rows = sorted(action_dist.items(), key=lambda x: x[1], reverse=True)
    action_kv = [(name, str(count)) for name, count in action_rows] or [("No actions", "0")]
    story.append(_kv_table(action_kv, col_widths=(12 * cm, 4 * cm)))

    # Risk distribution
    story.append(Paragraph("Risk distribution", styles["h2"]))
    risk_order = ["critical", "high", "medium", "low"]
    risk_rows = [(level, str(risk_dist.get(level, 0))) for level in risk_order]
    story.append(_kv_table(risk_rows, col_widths=(12 * cm, 4 * cm)))

    # Top policies
    story.append(Paragraph("Top policies applied", styles["h2"]))
    top_policies = summary.get("top_policies", []) or []
    pol_kv = [(p["name"], str(p["count"])) for p in top_policies] or [("No policies recorded", "0")]
    story.append(_kv_table(pol_kv, col_widths=(12 * cm, 4 * cm)))

    # Footer note
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        "This report is generated automatically from the GuardForge persistent audit log. "
        "Each scan operation logs only metadata (input hash, PII counts, types, action, risk) — "
        "raw text is never stored. This report is suitable for inclusion in GDPR Article 30 "
        "Records of Processing Activities and similar compliance documentation. For the full "
        "audit trail or per-event details, query the /api/audit endpoint.",
        styles["small"],
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "© MAXIA Lab — GuardForge — PII & AI Safety Kit",
        styles["small"],
    ))

    doc.build(story)
    return buf.getvalue()
