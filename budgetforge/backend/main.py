import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta, timezone
from fastapi import FastAPI, Depends, Request

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        return response


from sqlalchemy.orm import Session
from core.config import settings
from core.database import get_db
from core.limiter import limiter
from core.models import Usage
from core.auth import require_viewer
from routes.projects import (
    router as projects_router,
    _compute_breakdown,
    UsageBreakdown,
    DailySpend,
)
from routes.proxy import router as proxy_router
from routes.history import router as history_router
from routes.models import router as models_router
from routes.settings import router as settings_router
from routes.export import router as export_router
from routes.members import router as members_router
from routes.demo import router as demo_router
from routes.billing import router as billing_router
from routes.admin import router as admin_router
from routes.portal import router as portal_router
from routes.signup import router as signup_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.app_env == "production":
        missing = [
            name
            for name, val in [
                ("ADMIN_API_KEY", settings.admin_api_key),
                ("PORTAL_SECRET", settings.portal_secret),
                ("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"Variables obligatoires manquantes en production : {', '.join(missing)}"
            )
        if not settings.app_url.startswith("https"):
            logger.warning(
                "APP_URL='%s' doit commencer par https en production.", settings.app_url
            )
        if not settings.turnstile_secret_key:
            logger.warning(
                "TURNSTILE_SECRET_KEY absent en production — signups free seront bloqués "
                "(fail-closed anti-bot). Configurer sur https://dash.cloudflare.com/?to=/:account/turnstile"
            )
    yield


app = FastAPI(
    title="LLM BudgetForge",
    description="""
    **LLM Budget Guard** — Proxy layer with hard limits per project/user/agent
    
    ## Features
    - 🔒 **Budget enforcement** per project with hard limits
    - 🔄 **Multi-provider support** (OpenAI, Anthropic, Google, OpenRouter, etc.)
    - 📊 **Real-time monitoring** with usage analytics
    - 🚨 **Alerts & notifications** when budgets are exceeded
    - ⚡ **Rate limiting** to prevent abuse
    
    ## Quick Start
    1. Create a project via `/api/projects` (POST)
    2. Get your API key from the response
    3. Use the proxy endpoints with your API key
    
    ## Authentication
    Use `Bearer <API_KEY>` in the Authorization header.
    
    **Production URL**: https://llmbudget.maxiaworld.app
    """,
    version="1.0.0",
    contact={
        "name": "MAXIA Lab Support",
        "email": "ceo@maxiaworld.app",
        "url": "https://maxiaworld.app",
    },
    license_info={"name": "Proprietary", "url": "https://maxiaworld.app/terms"},
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


def get_cors_origins(app_env: str) -> list[str]:
    """B1.4 — CORS conditionne sur app_env (audit H13).

    En production: uniquement l'origin prod (pas de localhost).
    En dev/test: localhost autorise pour faciliter le dev.
    Fail-safe: env inconnu = comportement prod (restrictif).
    """
    prod_origin = "https://llmbudget.maxiaworld.app"
    dev_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]
    if app_env in ("development", "dev", "test", "testing"):
        return [*dev_origins, prod_origin]
    return [prod_origin]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(settings.app_env),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Provider-Key",
        "X-Agent-Name",
        "X-Admin-Key",
    ],
    allow_credentials=True,
)

app.include_router(projects_router)
app.include_router(proxy_router)
app.include_router(history_router)
app.include_router(models_router)
app.include_router(settings_router)
app.include_router(export_router)
app.include_router(members_router)
app.include_router(demo_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(portal_router)
app.include_router(signup_router)


@app.get("/health")
@limiter.exempt
def health():
    return {"status": "ok", "service": "llm-budgetforge"}


@app.get("/api/public/test")
@limiter.limit("60/minute")
def public_test_endpoint(request: Request):
    """Public endpoint for rate limiting testing."""
    return {"message": "OK", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(
    "/api/usage/breakdown",
    response_model=UsageBreakdown,
    tags=["usage"],
    dependencies=[Depends(require_viewer)],
)
def global_breakdown(db: Session = Depends(get_db)):
    """Breakdown local vs cloud across ALL projects."""
    all_usages = db.query(Usage).all()
    return _compute_breakdown(all_usages)


@app.get(
    "/api/usage/daily",
    response_model=list[DailySpend],
    tags=["usage"],
    dependencies=[Depends(require_viewer)],
)
def global_daily_usage(db: Session = Depends(get_db)):
    """Last 30 days aggregated spend across ALL projects."""
    today = date.today()
    start = today - timedelta(days=29)
    start_dt = datetime(start.year, start.month, start.day)

    usages = db.query(Usage).filter(Usage.created_at >= start_dt).all()

    daily: dict[str, float] = {}
    for i in range(30):
        daily[(start + timedelta(days=i)).isoformat()] = 0.0
    for u in usages:
        d = u.created_at.date().isoformat()
        if d in daily:
            daily[d] += u.cost_usd

    return [DailySpend(date=d, spend=round(v, 9)) for d, v in sorted(daily.items())]
