"""MAXIA Oracle — transactional email delivery via local SMTP (V2.5).

Used to deliver the rotated raw API key to a paying customer right after
checkout. Postfix is already running on the VPS with DKIM signing
(see project memory `project_scout_email_pipeline.md`), so we can hand
the message to localhost:25 and rely on the mailer for outbound.

Design choices
    - SMTP localhost:25 (no auth, server is loopback only)
    - Plain stdlib `smtplib` + `email.message` — zero new deps
    - HTML body with a tiny inline-styled template baked in this module
      (no Jinja/Loops template required — fully self-contained)
    - Returns a bool, never raises. The caller logs failure and falls
      back to the success-page key delivery if email is undeliverable.

Env
    SMTP_FROM_ADDRESS     — From: address (default "MAXIA Oracle <noreply@oracle.maxiaworld.app>")
    SMTP_HOST             — SMTP server hostname (default "localhost")
    SMTP_PORT             — SMTP server port (default 25)
    SMTP_TIMEOUT_S        — connect/send timeout (default 8)
"""
from __future__ import annotations

import logging
import os
import smtplib
import socket
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Final

logger = logging.getLogger("maxia_oracle.email_transactional")

_DEFAULT_FROM: Final[str] = (
    "MAXIA Oracle <noreply@oracle.maxiaworld.app>"
)
_DEFAULT_HOST: Final[str] = "localhost"
_DEFAULT_PORT: Final[int] = 25
_DEFAULT_TIMEOUT_S: Final[int] = 8


def _smtp_settings() -> tuple[str, int, str, int]:
    host = os.getenv("SMTP_HOST", _DEFAULT_HOST).strip() or _DEFAULT_HOST
    try:
        port = int(os.getenv("SMTP_PORT", str(_DEFAULT_PORT)).strip())
    except ValueError:
        port = _DEFAULT_PORT
    sender = os.getenv("SMTP_FROM_ADDRESS", _DEFAULT_FROM).strip() or _DEFAULT_FROM
    try:
        timeout = int(os.getenv("SMTP_TIMEOUT_S", str(_DEFAULT_TIMEOUT_S)).strip())
    except ValueError:
        timeout = _DEFAULT_TIMEOUT_S
    return host, port, sender, timeout


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _render_welcome_html(
    *,
    tier: str,
    api_key: str,
    daily_limit: int,
    portal_url: str,
    account_url: str,
    recover_url: str,
) -> tuple[str, str]:
    """Return (plain_text, html) bodies for the welcome-paid email."""
    plain = (
        "Welcome to MAXIA Oracle " + tier.upper() + " - your subscription is active.\n\n"
        "Your API key (save it now, it is shown only once):\n"
        "  " + api_key + "\n\n"
        "Daily quota: " + str(daily_limit) + " requests\n\n"
        "Manage subscription: " + portal_url + "\n"
        "My account:          " + account_url + "\n"
        "Lost your key?       " + recover_url + "\n\n"
        "Pass the key as X-API-Key header on every request.\n"
        "MAXIA Oracle is a data feed only. Not investment advice. No custody. No KYC.\n"
    )
    html = (
        '<!DOCTYPE html><html lang="en"><body style="margin:0;padding:24px;background:#060b14;font-family:system-ui,-apple-system,sans-serif;color:#e2e8f0;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" width="560" style="max-width:560px;background:#0d1520;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:36px 32px;">'
        '<tr><td>'
        '<h1 style="font-family:Inter,sans-serif;font-size:24px;color:#ffffff;margin:0 0 12px;">'
        'Welcome to MAXIA Oracle '
        '<span style="background:linear-gradient(90deg,#5eead4,#0099cc);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">'
        + tier.upper() + '</span> 🎉</h1>'
        '<p style="color:#7b8fa6;font-size:15px;line-height:1.6;margin:0 0 24px;">Your subscription is active and your daily quota jumps to <strong style="color:#ffffff;">' + str(daily_limit) + ' requests</strong> immediately.</p>'
        '<p style="color:#e2e8f0;font-size:14px;margin:0 0 8px;">Your API key (save it now — it will <strong>never</strong> be shown again):</p>'
        '<pre style="background:#000000;color:#5eead4;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;padding:14px 18px;border-radius:10px;word-break:break-all;border:1px solid rgba(94,234,212,0.25);margin:0 0 24px;overflow-x:auto;">'
        + api_key + '</pre>'
        '<p style="color:#e2e8f0;font-size:14px;margin:0 0 6px;">Use it on every request:</p>'
        '<pre style="background:#0a0f1a;color:#94a3b8;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;padding:12px 16px;border-radius:10px;margin:0 0 28px;overflow-x:auto;border:1px solid rgba(255,255,255,0.05);">'
        'curl -H "X-API-Key: ' + api_key + '" \\\n'
        '  https://oracle.maxiaworld.app/api/price/BTC</pre>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 28px;">'
        '<tr><td align="center"><a href="' + account_url + '" style="display:inline-block;background:linear-gradient(135deg,#5eead4,#2dd4bf);color:#060b14;padding:12px 28px;border-radius:50px;text-decoration:none;font-weight:700;font-size:14px;">View my account →</a></td></tr></table>'
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;">'
        '<p style="color:#7b8fa6;font-size:13px;line-height:1.7;margin:0;">'
        '<strong style="color:#ffffff;">What\'s next?</strong><br>'
        '· You will receive an invoice by email at each renewal.<br>'
        '· Cancel anytime via the <a href="' + portal_url + '" style="color:#5eead4;text-decoration:none;">Stripe portal</a>.<br>'
        '· Lost your key later? <a href="' + recover_url + '" style="color:#5eead4;text-decoration:none;">Recover it by email</a>.<br>'
        '</p>'
        '<p style="color:rgba(123,143,166,0.6);font-size:11px;line-height:1.6;margin:24px 0 0;">'
        'MAXIA Oracle is a data feed only. Not investment advice. No custody. No KYC.<br>'
        'You are receiving this email because you started a subscription on oracle.maxiaworld.app.</p>'
        '</td></tr></table></body></html>'
    )
    return plain, html


def send_welcome_paid(
    *,
    to_email: str,
    tier: str,
    api_key: str,
    daily_limit: int,
    portal_url: str = "",
    account_url: str = "",
    recover_url: str = "",
) -> bool:
    """Send the welcome-paid email with the rotated API key.

    Returns True on a successful SMTP handshake + accepted message.
    Never raises — failures are logged and the caller is expected to
    fall back to the success-page key delivery.
    """
    if not to_email or "@" not in to_email:
        logger.warning("send_welcome_paid: invalid to_email")
        return False
    if not api_key:
        logger.warning("send_welcome_paid: missing api_key")
        return False

    portal_url = portal_url or "https://oracle.maxiaworld.app/account.html"
    account_url = account_url or "https://oracle.maxiaworld.app/account.html"
    recover_url = recover_url or "https://oracle.maxiaworld.app/recover.html"

    plain, html = _render_welcome_html(
        tier=tier,
        api_key=api_key,
        daily_limit=daily_limit,
        portal_url=portal_url,
        account_url=account_url,
        recover_url=recover_url,
    )

    host, port, sender, timeout = _smtp_settings()
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = f"Welcome to MAXIA Oracle {tier.upper()} — your API key"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="oracle.maxiaworld.app")
    msg["MIME-Version"] = "1.0"
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host=host, port=port, timeout=timeout) as smtp:
            smtp.send_message(msg)
        logger.info(
            "Transactional welcome email delivered to %s (tier=%s)",
            _mask_email(to_email),
            tier,
        )
        return True
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        logger.warning(
            "Transactional welcome email FAILED to %s: %s",
            _mask_email(to_email),
            exc,
        )
        return False
    except Exception:
        logger.warning(
            "Transactional welcome email crashed for %s",
            _mask_email(to_email),
            exc_info=True,
        )
        return False
