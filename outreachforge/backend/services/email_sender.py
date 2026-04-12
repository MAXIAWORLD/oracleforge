"""OutreachForge — SMTP Email Sender with ramp-up.

Handles actual email delivery with configurable SMTP.
Supports ramp-up (gradually increase volume to avoid spam flags).
"""

from __future__ import annotations

import logging
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

from core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    success: bool
    message_id: str = ""
    error: str = ""


class EmailSender:
    """SMTP email sender with daily limit and ramp-up."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sent_today: int = 0
        self._date: str = time.strftime("%Y-%m-%d")
        self._day_number: int = 1  # Ramp-up day counter

    @property
    def daily_limit(self) -> int:
        """Calculate today's send limit based on ramp-up."""
        if not self._settings.ramp_up_enabled:
            return self._settings.max_emails_per_day
        limit = self._settings.ramp_up_start + (self._day_number - 1) * self._settings.ramp_up_increment
        return min(limit, self._settings.max_emails_per_day)

    @property
    def remaining_today(self) -> int:
        self._reset_if_new_day()
        return max(0, self.daily_limit - self._sent_today)

    def _reset_if_new_day(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self._date != today:
            self._sent_today = 0
            self._day_number += 1
            self._date = today

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.smtp_host and self._settings.smtp_from_email)

    def send(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str = "",
    ) -> SendResult:
        """Send a single email via SMTP."""
        self._reset_if_new_day()

        if not self.is_configured:
            return SendResult(success=False, error="SMTP not configured")

        if self._sent_today >= self.daily_limit:
            return SendResult(success=False, error=f"Daily limit reached ({self.daily_limit})")

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self._settings.smtp_from_name} <{self._settings.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.send_message(msg)
            self._sent_today += 1
            msg_id = f"of_{int(time.time())}_{self._sent_today}"
            logger.info("[email] sent to %s — %s (%d/%d today)",
                        to_email, subject, self._sent_today, self.daily_limit)
            return SendResult(success=True, message_id=msg_id)
        except Exception as e:
            logger.error("[email] failed to %s: %s", to_email, e)
            return SendResult(success=False, error=str(e))

    def stats(self) -> dict:
        self._reset_if_new_day()
        return {
            "configured": self.is_configured,
            "sent_today": self._sent_today,
            "daily_limit": self.daily_limit,
            "remaining": self.remaining_today,
            "ramp_up_day": self._day_number,
        }
