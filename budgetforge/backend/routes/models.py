import asyncio
import time
import httpx
from fastapi import APIRouter, Depends
from core.auth import require_viewer
from core.config import settings

router = APIRouter(prefix="/api", tags=["models"])

# Fallback lists — used when no API key or provider unreachable
ANTHROPIC_FALLBACK = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]
GOOGLE_FALLBACK = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-thinking",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]
DEEPSEEK_FALLBACK = ["deepseek-chat", "deepseek-reasoner"]
OLLAMA_FALLBACK = [
    "llama3",
    "mistral",
    "qwen3",
    "gemma3",
    "phi3",
    "codellama",
    "gemma4:26b",
]
OPENROUTER_FALLBACK = [
    "openrouter/anthropic/claude-3.5-sonnet",
    "openrouter/openai/gpt-4",
    "openrouter/google/gemini-pro",
    "openrouter/meta-llama/llama-3.1-70b-instruct",
    "openrouter/mistralai/mistral-7b-instruct",
]
TOGETHER_FALLBACK = [
    "togethercomputer/LLaMA-2-7B-32K",
    "togethercomputer/LLaMA-2-13B-32K",
    "togethercomputer/LLaMA-2-70B-32K",
    "togethercomputer/LLaMA-3-8B-32K-Instruct",
    "togethercomputer/LLaMA-3-70B-32K-Instruct",
    "togethercomputer/Mistral-7B-Instruct-v0.1",
    "togethercomputer/Mistral-7B-Instruct-v0.2",
    "togethercomputer/Mistral-7B-Instruct-v0.3",
]
AZURE_OPENAI_FALLBACK = [
    "azure/gpt-4o",
    "azure/gpt-4o-mini",
    "azure/gpt-4-turbo",
    "azure/gpt-3.5-turbo",
    "azure/o1",
    "azure/o1-mini",
    "azure/o3-mini",
]

AWS_BEDROCK_FALLBACK = [
    "anthropic.claude-v2",
    "anthropic.claude-v2:1",
    "anthropic.claude-3-haiku",
    "anthropic.claude-3-sonnet",
    "anthropic.claude-3-opus",
    "meta.llama2-13b-chat",
    "meta.llama2-70b-chat",
    "meta.llama3-8b-instruct",
    "meta.llama3-70b-instruct",
]

# OpenAI model name prefixes we care about (filter out embedding/audio/image models)
_OPENAI_CHAT_PREFIXES = ("gpt-", "o1", "o3", "chatgpt-")

# Simple in-memory cache: (timestamp, data)
_cache: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(key: str) -> list[str] | None:
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _store(key: str, value: list[str]) -> list[str]:
    _cache[key] = (time.time(), value)
    return value


async def _fetch_openai_models() -> list[str]:
    cached = _cached("openai")
    if cached:
        return cached
    if not settings.openai_api_key:
        return _store(
            "openai",
            [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
                "o1",
                "o1-mini",
                "o3-mini",
            ],
        )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            if r.status_code == 200:
                all_models = [m["id"] for m in r.json().get("data", [])]
                chat_models = sorted(
                    [
                        m
                        for m in all_models
                        if any(m.startswith(p) for p in _OPENAI_CHAT_PREFIXES)
                    ],
                    reverse=True,
                )
                return (
                    _store("openai", chat_models)
                    if chat_models
                    else _store("openai", ["gpt-4o", "gpt-4o-mini"])
                )
    except Exception:
        pass
    return _store(
        "openai",
        [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "o1",
            "o1-mini",
            "o3-mini",
        ],
    )


async def _fetch_anthropic_models() -> list[str]:
    cached = _cached("anthropic")
    if cached:
        return cached
    if not settings.anthropic_api_key:
        return _store("anthropic", ANTHROPIC_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", []) if m.get("id")]
                return (
                    _store("anthropic", models)
                    if models
                    else _store("anthropic", ANTHROPIC_FALLBACK)
                )
    except Exception:
        pass
    return _store("anthropic", ANTHROPIC_FALLBACK)


async def _fetch_google_models() -> list[str]:
    cached = _cached("google")
    if cached:
        return cached
    if not settings.google_api_key:
        return _store("google", GOOGLE_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": settings.google_api_key},
            )
            if r.status_code == 200:
                models = [
                    m["name"].removeprefix("models/")
                    for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                    and m.get("name", "").startswith("models/")
                ]
                return (
                    _store("google", models)
                    if models
                    else _store("google", GOOGLE_FALLBACK)
                )
    except Exception:
        pass
    return _store("google", GOOGLE_FALLBACK)


async def _fetch_deepseek_models() -> list[str]:
    cached = _cached("deepseek")
    if cached:
        return cached
    if not settings.deepseek_api_key:
        return _store("deepseek", DEEPSEEK_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            )
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", []) if m.get("id")]
                return (
                    _store("deepseek", models)
                    if models
                    else _store("deepseek", DEEPSEEK_FALLBACK)
                )
    except Exception:
        pass
    return _store("deepseek", DEEPSEEK_FALLBACK)


async def _fetch_ollama_models() -> list[str]:
    cached = _cached("ollama")
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code == 200:
                live = [m["name"] for m in r.json().get("models", []) if m.get("name")]
                return (
                    _store("ollama", live)
                    if live
                    else _store("ollama", OLLAMA_FALLBACK)
                )
    except Exception:
        pass
    return _store("ollama", OLLAMA_FALLBACK)


async def _fetch_openrouter_models() -> list[str]:
    cached = _cached("openrouter")
    if cached:
        return cached
    if not settings.openrouter_api_key:
        return _store("openrouter", OPENROUTER_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://budgetforge.io",
                    "X-Title": "BudgetForge",
                },
            )
            if r.status_code == 200:
                models_data = r.json().get("data", [])
                # Filtrer les modèles pertinents (chat/completion)
                chat_models = []
                for model_data in models_data:
                    model_id = model_data.get("id")
                    if (
                        model_id
                        and model_data.get("architecture", {}).get("modality") == "text"
                    ):
                        chat_models.append(model_id)
                return (
                    _store("openrouter", chat_models)
                    if chat_models
                    else _store("openrouter", OPENROUTER_FALLBACK)
                )
    except Exception:
        pass
    return _store("openrouter", OPENROUTER_FALLBACK)


async def _fetch_together_models() -> list[str]:
    cached = _cached("together")
    if cached:
        return cached
    if not settings.together_api_key:
        return _store("together", TOGETHER_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.together.xyz/v1/models",
                headers={"Authorization": f"Bearer {settings.together_api_key}"},
            )
            if r.status_code == 200:
                models_data = r.json().get("data", [])
                # Filtrer les modèles de chat/completion
                chat_models = []
                for model_data in models_data:
                    model_id = model_data.get("id")
                    # Together AI expose le type de modèle
                    if model_id and model_data.get("type") == "chat":
                        chat_models.append(model_id)
                return (
                    _store("together", chat_models)
                    if chat_models
                    else _store("together", TOGETHER_FALLBACK)
                )
    except Exception:
        pass
    return _store("together", TOGETHER_FALLBACK)


async def _fetch_azure_openai_models() -> list[str]:
    cached = _cached("azure_openai")
    if cached:
        return cached
    if not settings.azure_openai_api_key or not settings.azure_openai_base_url:
        return _store("azure_openai", AZURE_OPENAI_FALLBACK)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Azure OpenAI utilise le même endpoint que OpenAI mais avec authentification différente
            r = await client.get(
                f"{settings.azure_openai_base_url}/openai/deployments?api-version=2024-02-15-preview",
                headers={"api-key": settings.azure_openai_api_key},
            )
            if r.status_code == 200:
                deployments = r.json().get("data", [])
                # Filtrer les déploiements pertinents (chat models)
                chat_models = []
                for deployment in deployments:
                    model_name = deployment.get("model")
                    if model_name and any(
                        model_name.startswith(p) for p in _OPENAI_CHAT_PREFIXES
                    ):
                        chat_models.append(f"azure/{model_name}")
                return (
                    _store("azure_openai", chat_models)
                    if chat_models
                    else _store("azure_openai", AZURE_OPENAI_FALLBACK)
                )
    except Exception:
        pass
    return _store("azure_openai", AZURE_OPENAI_FALLBACK)


async def _fetch_aws_bedrock_models() -> list[str]:
    """Récupère les modèles AWS Bedrock disponibles."""
    cached = _cached("aws_bedrock")
    if cached:
        return cached

    # AWS Bedrock nécessite des credentials AWS, on utilise le fallback par défaut
    if not settings.aws_bedrock_access_key or not settings.aws_bedrock_secret_key:
        return _store("aws_bedrock", AWS_BEDROCK_FALLBACK)

    try:
        # AWS Bedrock n'a pas d'API publique pour lister les modèles sans credentials
        # On retourne le fallback pour l'instant
        return _store("aws_bedrock", AWS_BEDROCK_FALLBACK)
    except Exception:
        pass

    return _store("aws_bedrock", AWS_BEDROCK_FALLBACK)


@router.get("/models", dependencies=[Depends(require_viewer)])
async def get_models() -> dict:
    (
        openai_models,
        anthropic_models,
        google_models,
        deepseek_models,
        ollama_models,
        openrouter_models,
        together_models,
        azure_openai_models,
        aws_bedrock_models,
    ) = await asyncio.gather(
        _fetch_openai_models(),
        _fetch_anthropic_models(),
        _fetch_google_models(),
        _fetch_deepseek_models(),
        _fetch_ollama_models(),
        _fetch_openrouter_models(),
        _fetch_together_models(),
        _fetch_azure_openai_models(),
        _fetch_aws_bedrock_models(),
    )
    return {
        "providers": {
            "openai": openai_models,
            "anthropic": anthropic_models,
            "google": google_models,
            "deepseek": deepseek_models,
            "ollama": ollama_models,
            "openrouter": openrouter_models,
            "together": together_models,
            "azure_openai": azure_openai_models,
            "aws_bedrock": aws_bedrock_models,
        }
    }
