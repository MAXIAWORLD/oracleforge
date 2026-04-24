"""
Endpoints proxy pour BudgetForge.
Architecture simplifiée avec fonction helper pour éviter la duplication.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.limiter import limiter
from core.models import Project
from services.budget_guard import BudgetGuard, BudgetAction
from services.budget_lock import budget_lock
from services.cost_calculator import CostCalculator, UnknownModelError
from services.plan_quota import check_quota
from services.proxy_forwarder import ProxyForwarder
from services import proxy_dispatcher

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])
guard = BudgetGuard()


# ── Auth ──────────────────────────────────────────────────────────────────────

_GRACE_PERIOD_MINUTES = 5


def _get_project_by_api_key(authorization: Optional[str], db: Session) -> Project:
    """Récupère un projet par sa clé API."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    api_key = authorization.removeprefix("Bearer ").strip()

    project = db.query(Project).filter(Project.api_key == api_key).first()
    if project:
        return project

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=_GRACE_PERIOD_MINUTES
    )
    project = (
        db.query(Project)
        .filter(
            Project.previous_api_key == api_key,
            Project.key_rotated_at >= cutoff,
        )
        .first()
    )
    if project:
        return project

    raise HTTPException(status_code=401, detail="Invalid API key")


async def require_api_key(authorization: Optional[str], db: Session) -> Project:
    """Vérifie l'authentification JWT ou API key."""
    return _get_project_by_api_key(authorization, db)


# ── Validation ─────────────────────────────────────────────────────────────────


def _check_provider(project: Project, provider_name: str):
    """Vérifie que le fournisseur est autorisé pour le projet."""
    if not project.allowed_providers:
        return

    try:
        allowed = json.loads(project.allowed_providers)
    except json.JSONDecodeError:
        logger.warning("Invalid allowed_providers JSON for project %s", project.id)
        return

    if provider_name not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Provider {provider_name} not allowed for this project",
        )


def _resolve_provider_key(
    custom_key: Optional[str], default_key: Optional[str], provider_name: str
) -> str:
    """Résout la clé API à utiliser."""
    if custom_key:
        return custom_key
    if default_key:
        return default_key
    raise HTTPException(
        status_code=400, detail=f"No API key configured for {provider_name}"
    )


def _check_budget(project: Project, db: Session, model: str) -> str:
    """Vérifie le budget et retourne le modèle final."""
    if project.budget_usd is None:
        return model

    # Récupère l'usage de la période
    used = proxy_dispatcher.get_period_used_sql(project.id, project.reset_period, db)

    # Vérifie le budget
    downgrade_chain = None
    if project.downgrade_chain:
        try:
            downgrade_chain = json.loads(project.downgrade_chain)
        except (json.JSONDecodeError, TypeError):
            pass
    budget_status = guard.check(
        budget_usd=project.budget_usd,
        used_usd=used,
        action=BudgetAction(project.action),
        current_model=model,
        downgrade_chain=downgrade_chain,
    )

    if not budget_status.allowed:
        raise HTTPException(status_code=429, detail="Budget exceeded")

    if budget_status.downgrade_to:
        logger.info(
            "Downgrading from %s to %s due to budget", model, budget_status.downgrade_to
        )
        return budget_status.downgrade_to

    return model


async def _check_per_call_cap(project: Project, payload: dict, model: str):
    """Vérifie la limite de coût par appel."""
    if not project.max_cost_per_call_usd:
        return

    # Estimation des tokens
    tokens_in = proxy_dispatcher.estimate_input_tokens(payload)
    tokens_out = proxy_dispatcher.estimate_output_tokens(payload)

    try:
        estimated_cost = await CostCalculator.compute_cost(model, tokens_in, tokens_out)
    except UnknownModelError:
        return  # Si modèle inconnu, on ignore la vérification

    if estimated_cost > project.max_cost_per_call_usd:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estimated call cost ${estimated_cost:.6f} exceeds per-call cap "
                f"${project.max_cost_per_call_usd:.6f}"
            ),
        )


# ── Fonction helper pour éviter la duplication ─────────────────────────────────


async def _proxy_helper(
    request: Request,
    provider_name: str,
    payload: dict,
    authorization: Optional[str],
    x_provider_key: Optional[str],
    x_budgetforge_agent: Optional[str],
    db: Session,
    default_model: str = "gpt-4",
    provider_config_key: str = None,
):
    """Helper pour tous les endpoints proxy."""

    # Authentification
    project = await require_api_key(authorization, db)

    # Validation du fournisseur
    _check_provider(project, provider_name)

    # Résolution de la clé API
    if provider_config_key is None:
        provider_config_key = f"{provider_name.replace('-', '_')}_api_key"

    provider_key = _resolve_provider_key(
        x_provider_key, getattr(settings, provider_config_key, None), provider_name
    )

    # Récupération du modèle
    model = payload.get("model", default_model)

    # Vérification des quotas
    check_quota(project, db)

    # Vérification du budget avec verrou
    async with budget_lock(project.id):
        final_model = _check_budget(project, db, model)
        await _check_per_call_cap(project, payload, final_model)

        # Détermination du provider final (pour Ollama)
        actual_provider = (
            "ollama" if final_model.startswith("ollama/") else provider_name
        )

        # Pré-facturation
        usage_id = await proxy_dispatcher.prebill_usage(
            db, project, actual_provider, final_model, payload, x_budgetforge_agent
        )

    # Configuration du timeout
    timeout_s = project.proxy_timeout_ms / 1000.0 if project.proxy_timeout_ms else 60.0
    max_retries = project.proxy_retries or 0

    # Routage spécial pour Ollama
    if final_model.startswith("ollama/"):
        return await proxy_dispatcher.dispatch_ollama_fallback(
            payload, project, final_model, usage_id, db
        )

    # Détermination des fonctions de forward
    forward_mapping = {
        "openai": (ProxyForwarder.forward_openai, ProxyForwarder.forward_openai_stream),
        "anthropic": (
            ProxyForwarder.forward_anthropic,
            ProxyForwarder.forward_anthropic_stream,
        ),
        "google": (ProxyForwarder.forward_google, ProxyForwarder.forward_google_stream),
        "deepseek": (
            ProxyForwarder.forward_deepseek,
            ProxyForwarder.forward_deepseek_stream,
        ),
        "openrouter": (
            ProxyForwarder.forward_openrouter,
            ProxyForwarder.forward_openrouter_stream,
        ),
        "together": (
            ProxyForwarder.forward_together,
            ProxyForwarder.forward_together_stream,
        ),
        "azure-openai": (
            ProxyForwarder.forward_azure_openai,
            ProxyForwarder.forward_azure_openai_stream,
        ),
        "aws-bedrock": (
            ProxyForwarder.forward_aws_bedrock,
            ProxyForwarder.forward_aws_bedrock_stream,
        ),
    }

    forward_fn, forward_stream_fn = forward_mapping.get(provider_name)
    if not forward_fn:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {provider_name}"
        )

    # Dispatch vers le fournisseur
    return await proxy_dispatcher.dispatch_openai_format(
        payload,
        project,
        provider_name,
        final_model,
        usage_id,
        provider_key,
        forward_fn,
        forward_stream_fn,
        timeout_s,
        db,
        max_retries=max_retries,
    )


# ── Endpoints proxy ───────────────────────────────────────────────────────────


@router.post("/proxy/openai/v1/chat/completions")
@limiter.limit("30/minute", "1000/hour")
async def proxy_openai(
    request: Request,
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour OpenAI."""
    return await _proxy_helper(
        request,
        "openai",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
    )


@router.post("/proxy/anthropic/v1/messages")
async def proxy_anthropic(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Anthropic."""
    return await _proxy_helper(
        None,
        "anthropic",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "claude-3-5-sonnet-20241022",
    )


@router.post("/proxy/google/v1/chat/completions")
async def proxy_google(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Google."""
    return await _proxy_helper(
        None,
        "google",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "gemini-1.5-pro",
    )


@router.post("/proxy/deepseek/v1/chat/completions")
async def proxy_deepseek(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour DeepSeek."""
    return await _proxy_helper(
        None,
        "deepseek",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "deepseek-chat",
    )


@router.post("/proxy/openrouter/v1/chat/completions")
async def proxy_openrouter(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour OpenRouter."""
    return await _proxy_helper(
        None,
        "openrouter",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "openrouter/nousresearch/nous-hermes-2-mixtral-8x7b-dpo",
    )


@router.post("/proxy/ollama/api/chat")
async def proxy_ollama_chat(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Ollama (format chat)."""
    return await _proxy_helper(
        None,
        "ollama",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "llama2",
    )


@router.post("/proxy/ollama/v1/chat/completions")
async def proxy_ollama_openai(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Ollama (format OpenAI)."""
    return await _proxy_helper(
        None,
        "ollama",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "llama2",
    )


@router.post("/proxy/together/v1/chat/completions")
async def proxy_together(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Together."""
    return await _proxy_helper(
        None,
        "together",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "togethercomputer/CodeLlama-34b-Instruct",
    )


@router.post("/proxy/azure-openai/v1/chat/completions")
async def proxy_azure_openai(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour Azure OpenAI."""
    return await _proxy_helper(
        None,
        "azure-openai",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "gpt-4",
    )


@router.post("/proxy/aws-bedrock/v1/chat/completions")
async def proxy_aws_bedrock(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_budgetforge_agent: Optional[str] = Header(None, alias="X-BudgetForge-Agent"),
    db: Session = Depends(get_db),
):
    """Proxy pour AWS Bedrock."""
    return await _proxy_helper(
        None,
        "aws-bedrock",
        payload,
        authorization,
        x_provider_key,
        x_budgetforge_agent,
        db,
        "anthropic.claude-3-sonnet-20240229",
    )
