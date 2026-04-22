import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from core.config import settings

logger = logging.getLogger(__name__)

_PLAN_LABELS = {"free": "Free ($0/mo)", "pro": "Pro ($29/mo)", "agency": "Agency ($79/mo)", "ltd": "Lifetime"}

_PLAN_DETAILS = {
    "free":   "1,000 calls/month · 1 project · OpenAI + Anthropic",
    "pro":    "100,000 calls/month · 10 projects · OpenAI · Anthropic · Google · DeepSeek",
    "agency": "500,000 calls/month · Unlimited projects · All providers · Priority support",
    "ltd":    "100,000 calls/month · Lifetime access · All providers",
}

_BODY_TEMPLATE = """\
Welcome to BudgetForge!

Your {plan_label} plan is active.
{plan_details}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR BUDGETFORGE KEY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {api_key}

Keep it safe. This is what identifies your account.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONNECT IN 2 STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — Update your AI tool or app:

  Python / OpenAI SDK:
    client = openai.OpenAI(
        api_key="{api_key}",
        base_url="https://llmbudget.maxiaworld.app/proxy/openai/v1",
        default_headers={{"X-Provider-Key": "YOUR-OPENAI-KEY"}}
    )

  Cursor / n8n / any tool:
    API Key:  {api_key}
    Base URL: https://llmbudget.maxiaworld.app/proxy/openai

  ⚠️  You keep your original OpenAI / Anthropic key.
  BudgetForge never stores it — you pass it as X-Provider-Key.
  BudgetForge only sees it to forward your request.

STEP 2 — Set your spending limit:
  Go to: https://llmbudget.maxiaworld.app/portal
  Enter your email → get a magic link → open your dashboard.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Need help? Reply to this email — we respond within 24h.

— The BudgetForge team
https://llmbudget.maxiaworld.app
"""


def send_onboarding_email(to: str, api_key: str, plan: str) -> bool:
    cfg = {
        "smtp_host":     settings.smtp_host,
        "smtp_port":     settings.smtp_port,
        "smtp_user":     settings.smtp_user,
        "smtp_password": settings.smtp_password,
        "from_email":    settings.alert_from_email,
    }
    if not cfg["smtp_host"]:
        logger.warning("SMTP not configured — skipping onboarding email to %s", to)
        return False

    plan_label = _PLAN_LABELS.get(plan, plan)
    plan_details = _PLAN_DETAILS.get(plan, "")
    body = _BODY_TEMPLATE.format(api_key=api_key, plan_label=plan_label, plan_details=plan_details)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your BudgetForge API key — connect in 2 steps"
    msg["From"] = cfg["from_email"]
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.starttls()
            if cfg["smtp_user"]:
                server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.sendmail(cfg["from_email"], to, msg.as_string())
        logger.info("Onboarding email sent to %s (plan=%s)", to, plan)
        return True
    except Exception as e:
        logger.error("Onboarding email failed for %s: %s", to, e)
        return False
