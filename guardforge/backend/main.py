"""GuardForge — FastAPI application entry point.

PII & AI Safety Kit: detection, anonymisation, vault, policy engine.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

# Set up basic logging so logger.info() calls from services/routes are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, init_db
from core.models import HealthResponse
from routes.scanner import router as scanner_router
from routes.reports import router as reports_router
from routes.entities import router as entities_router
from routes.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    await init_db(settings.database_url)

    from services.pii_detector import PIIDetector
    from services.vault import Vault
    from services.policy_engine import PolicyEngine

    app.state.pii_detector = PIIDetector(confidence_threshold=settings.pii_confidence_threshold)
    app.state.vault = Vault(
        encryption_key=settings.vault_encryption_key,
        database_url=settings.database_url,
    )
    app.state.policy_engine = PolicyEngine(default_policy=settings.default_policy)
    app.state.audit_log: list[dict] = []  # In-memory audit trail (last 1000 scans)

    # Load custom entity patterns from DB into the live detector
    custom_count = 0
    try:
        import re as _re
        from sqlalchemy import select as _select
        from core.database import get_db as _get_db
        from core.models import CustomEntity as _CustomEntity
        from services.pii_detector import CustomPattern as _CustomPattern

        async for db_session in _get_db():
            rows = (await db_session.execute(
                _select(_CustomEntity).where(_CustomEntity.enabled == 1)
            )).scalars().all()
            patterns = []
            for row in rows:
                try:
                    compiled = _re.compile(row.pattern)
                except _re.error as exc:
                    logger.warning("[startup] skipping invalid custom regex %s: %s", row.name, exc)
                    continue
                patterns.append(_CustomPattern(
                    name=row.name,
                    regex=compiled,
                    risk_level=row.risk_level,
                    confidence=row.confidence,
                ))
            app.state.pii_detector.set_custom_patterns(patterns)
            custom_count = len(patterns)
            break
    except Exception as exc:
        logger.warning("[startup] failed to load custom entities: %s", exc)

    logger.info("[startup] GuardForge ready — vault=%s, policies=%d, custom_entities=%d",
                "on" if app.state.vault.is_available else "off",
                len(app.state.policy_engine.list_policies()),
                custom_count)
    yield
    await close_db()


API_DESCRIPTION = """
**GuardForge — PII & AI Safety Kit**

Detect, redact, and tokenize personally identifiable information before it ever reaches OpenAI, Anthropic, or any other LLM provider.

## Authentication

All endpoints (except `/health` and `/docs`) require an `X-API-Key` header matching the backend `SECRET_KEY` from `.env`.

```
curl -H "X-API-Key: your-secret-key" https://api.guardforge.io/api/scan
```

Vault endpoints additionally accept a `Bearer` token in the `Authorization` header.

## Quick start

1. **Detect PII**: `POST /api/scan` — returns entities, risk levels, anonymized text
2. **Reversible tokenize**: `POST /api/tokenize` → send safe text to LLM → `POST /api/detokenize` to restore
3. **Compliance reports**: `GET /api/reports/summary` for CISO/DPO dashboards

## Compliance support

Built-in policies for GDPR, HIPAA, PCI-DSS, with CCPA, LGPD, EU AI Act and 8 more coming soon.

## Rate limits

60 requests/minute per IP by default. Contact sales for higher tiers.

## Documentation

- Full README: https://github.com/maxia-lab/guardforge
- API examples: see endpoint descriptions below
"""

OPENAPI_TAGS = [
    {
        "name": "guard",
        "description": "Core PII detection, anonymization, tokenization, and vault management.",
    },
    {
        "name": "reports",
        "description": "Compliance reports and audit analytics for CISO/DPO dashboards.",
    },
    {
        "name": "system",
        "description": "Health check and system status.",
    },
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": "MAXIA Lab",
            "url": "https://maxialab.com",
            "email": "contact@maxialab.com",
        },
        license_info={
            "name": "GuardForge Proprietary License",
            "url": "https://github.com/maxia-lab/guardforge/blob/main/LICENSE",
        },
        terms_of_service="https://maxialab.com/terms",
    )
    # Security middleware (auth + rate limit + headers)
    from core.middleware import add_security_middleware
    add_security_middleware(app, settings.secret_key)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(scanner_router)
    app.include_router(reports_router)
    app.include_router(entities_router)
    app.include_router(webhooks_router)

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Health check",
        description=(
            "Public unauthenticated endpoint. Returns service status, version, "
            "loaded policies count, and vault entries count. Use this for "
            "uptime monitoring and load balancer health checks."
        ),
    )
    async def health() -> HealthResponse:
        vault = getattr(app.state, "vault", None)
        pe = getattr(app.state, "policy_engine", None)
        return HealthResponse(
            version=settings.version,
            vault_entries=len(vault.list_keys()) if vault else 0,
            policies_loaded=len(pe.list_policies()) if pe else 0,
        )
    return app


app = create_app()
