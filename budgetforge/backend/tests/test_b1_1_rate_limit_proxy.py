"""TDD B1.1 — Rate limiting sur tous les endpoints /proxy/*.

Bug C01 audit 2026-04-25 : `@limiter.limit` placé AU-DESSUS de `@router.post`
sur 9 endpoints sur 10. FastAPI enregistre la fonction non-wrappée → rate
limiting NUL. Seul `proxy_openai` est protégé.

Test live confirmé : 35 reqs /proxy/anthropic même clé fixe = 0× 429.

Ces tests doivent PASSER une fois les décorateurs réordonnés sur les 9
endpoints (anthropic, google, deepseek, mistral, openrouter, together,
azure-openai, aws-bedrock, ollama×2).
"""

import pytest
from httpx import AsyncClient, ASGITransport

from main import app, limiter
from core.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine_test)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(autouse=True)
def reset_limiter():
    """Re-enable limiter (conftest disables it globally) and reset counters."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def override_db(db):
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


# Endpoints proxy — tous limités à 30/minute selon le code de routes/proxy.py
# Avec une clé fixée (key:bf-...), le 31e call doit retourner 429.
PROXY_ENDPOINTS_30PM = [
    ("/proxy/openai/v1/chat/completions", "openai"),
    ("/proxy/anthropic/v1/messages", "anthropic"),
    ("/proxy/google/v1/chat/completions", "google"),
    ("/proxy/deepseek/v1/chat/completions", "deepseek"),
    ("/proxy/mistral/v1/chat/completions", "mistral"),
    ("/proxy/openrouter/v1/chat/completions", "openrouter"),
    ("/proxy/together/v1/chat/completions", "together"),
    ("/proxy/azure-openai/v1/chat/completions", "azure-openai"),
    ("/proxy/aws-bedrock/v1/chat/completions", "aws-bedrock"),
]

# Endpoints Ollama — limités à 60/minute (plus généreux car local)
PROXY_ENDPOINTS_60PM = [
    ("/proxy/ollama/api/chat", "ollama-native"),
    ("/proxy/ollama/v1/chat/completions", "ollama-openai-compat"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,name", PROXY_ENDPOINTS_30PM)
async def test_proxy_endpoint_rate_limited_at_30_per_minute(path, name):
    """Chaque endpoint /proxy/* (hors ollama) doit retourner 429 après 30 reqs/min
    avec la même clé bf-* (rate-limit par-clé via _key_by_api_or_ip)."""
    fixed_key = f"bf-test-rate-{name}-fixed-12345"
    headers = {
        "Authorization": f"Bearer {fixed_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "x"}]}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = []
        for _ in range(35):
            r = await client.post(path, json=payload, headers=headers)
            responses.append(r.status_code)

    rate_limited = sum(1 for s in responses if s == 429)
    assert rate_limited > 0, (
        f"{path} ({name}) — 35 requêtes même clé, AUCUN 429. "
        f"Status codes vus : {set(responses)}. "
        f"Rate limit cassé (audit C01)."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path,name", PROXY_ENDPOINTS_60PM)
async def test_proxy_ollama_endpoint_rate_limited_at_60_per_minute(path, name):
    """Endpoints Ollama : 65 reqs même clé doivent déclencher au moins un 429."""
    fixed_key = f"bf-test-rate-{name}-fixed-12345"
    headers = {
        "Authorization": f"Bearer {fixed_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": "llama3", "messages": [{"role": "user", "content": "x"}]}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = []
        for _ in range(65):
            r = await client.post(path, json=payload, headers=headers)
            responses.append(r.status_code)

    rate_limited = sum(1 for s in responses if s == 429)
    assert rate_limited > 0, (
        f"{path} ({name}) — 65 requêtes même clé, AUCUN 429. "
        f"Status codes vus : {set(responses)}. "
        f"Rate limit cassé (audit C01)."
    )
