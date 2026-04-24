"""Fixtures avec données réalistes pour les tests."""

import json
from datetime import datetime, timedelta, timezone


# Données réalistes pour les projets
PROJECTS_REALISTIC = [
    {
        "name": "startup-ai-app",
        "budget_usd": 500.0,
        "alert_threshold_pct": 80,
        "alert_email": "devops@startup.ai",
        "allowed_providers": ["openai", "anthropic", "openrouter"],
        "downgrade_chain": ["gpt-4o", "gpt-3.5-turbo", "ollama/llama3"],
        "proxy_timeout_ms": 30000,
        "proxy_retries": 2,
    },
    {
        "name": "enterprise-research",
        "budget_usd": 5000.0,
        "alert_threshold_pct": 90,
        "alert_email": "research@enterprise.com",
        "webhook_url": "https://example.com/webhook/placeholder",
        "allowed_providers": ["azure_openai", "aws_bedrock"],
        "downgrade_chain": ["gpt-4o", "gpt-3.5-turbo"],
        "max_cost_per_call_usd": 0.10,
    },
    {
        "name": "hobby-project",
        "budget_usd": 50.0,
        "alert_threshold_pct": 50,
        "alert_email": "hobbyist@gmail.com",
        "allowed_providers": ["openrouter", "together"],
        "downgrade_chain": [
            "openrouter/anthropic/claude-3.5-sonnet",
            "togethercomputer/LLaMA-2-7B-32K",
        ],
    },
]


# Modèles réalistes avec prix
MODELS_WITH_REALISTIC_PRICING = {
    "gpt-4o": {"input_per_1m_usd": 5.00, "output_per_1m_usd": 15.00},
    "gpt-4o-mini": {"input_per_1m_usd": 0.15, "output_per_1m_usd": 0.60},
    "gpt-3.5-turbo": {"input_per_1m_usd": 0.50, "output_per_1m_usd": 1.50},
    "claude-3-opus-20240229": {"input_per_1m_usd": 15.00, "output_per_1m_usd": 75.00},
    "claude-3-sonnet-20240229": {"input_per_1m_usd": 3.00, "output_per_1m_usd": 15.00},
    "claude-3-haiku-20240307": {"input_per_1m_usd": 0.25, "output_per_1m_usd": 1.25},
    "openrouter/anthropic/claude-3.5-sonnet": {
        "input_per_1m_usd": 3.00,
        "output_per_1m_usd": 15.00,
    },
    "togethercomputer/LLaMA-2-7B-32K": {
        "input_per_1m_usd": 0.20,
        "output_per_1m_usd": 0.20,
    },
    "anthropic.claude-3-sonnet-20240229": {
        "input_per_1m_usd": 3.00,
        "output_per_1m_usd": 15.00,
    },
    "meta.llama3-70b-instruct-v1": {
        "input_per_1m_usd": 0.65,
        "output_per_1m_usd": 0.65,
    },
}


# Données d'usage réalistes
USAGE_DATA_REALISTIC = [
    {
        "project_id": 1,
        "provider": "openai",
        "model": "gpt-4o",
        "tokens_in": 1500,
        "tokens_out": 800,
        "cost_usd": 0.135,
        "agent": "chatbot-v1",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
    },
    {
        "project_id": 1,
        "provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
        "tokens_in": 2000,
        "tokens_out": 1500,
        "cost_usd": 0.105,
        "agent": "research-agent",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
    },
    {
        "project_id": 2,
        "provider": "azure_openai",
        "model": "gpt-4o",
        "tokens_in": 5000,
        "tokens_out": 3000,
        "cost_usd": 0.45,
        "agent": "enterprise-ai",
        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
    },
]


def create_realistic_project(db, project_data):
    """Crée un projet réaliste dans la base de données."""
    from core.models import Project

    project = Project(
        name=project_data["name"],
        budget_usd=project_data["budget_usd"],
        alert_threshold_pct=project_data["alert_threshold_pct"],
        alert_email=project_data.get("alert_email"),
        webhook_url=project_data.get("webhook_url"),
        allowed_providers=json.dumps(project_data["allowed_providers"]),
        downgrade_chain=json.dumps(project_data.get("downgrade_chain", [])),
        proxy_timeout_ms=project_data.get("proxy_timeout_ms"),
        proxy_retries=project_data.get("proxy_retries"),
        max_cost_per_call_usd=project_data.get("max_cost_per_call_usd"),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_realistic_usage(db, usage_data):
    """Crée un enregistrement d'usage réaliste."""
    from core.models import Usage

    usage = Usage(
        project_id=usage_data["project_id"],
        provider=usage_data["provider"],
        model=usage_data["model"],
        tokens_in=usage_data["tokens_in"],
        tokens_out=usage_data["tokens_out"],
        cost_usd=usage_data["cost_usd"],
        agent=usage_data.get("agent"),
        created_at=usage_data["created_at"],
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage
