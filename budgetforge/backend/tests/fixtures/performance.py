"""Fixtures pour les tests de performance et de charge."""

import asyncio


# Données pour les tests de charge
LOAD_TEST_CONFIG = {
    "concurrent_users": 10,
    "requests_per_user": 100,
    "think_time_ms": 100,
    "timeout_seconds": 30,
}


# Messages réalistes pour les tests
REALISTIC_MESSAGES = [
    {
        "role": "user",
        "content": "Peux-tu m'expliquer comment fonctionne l'apprentissage automatique ?",
    },
    {
        "role": "user",
        "content": "Quelle est la différence entre un réseau de neurones et un algorithme de régression ?",
    },
    {
        "role": "user",
        "content": "Pouvez-vous me donner un exemple de code Python pour un modèle de classification ?",
    },
    {
        "role": "user",
        "content": "Expliquez-moi les avantages du fine-tuning par rapport au prompt engineering.",
    },
]


# Payloads réalistes pour différents fournisseurs
REALISTIC_PAYLOADS = {
    "openai": {
        "model": "gpt-4o",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
    "anthropic": {
        "model": "claude-3-sonnet-20240229",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
    "openrouter": {
        "model": "openrouter/anthropic/claude-3.5-sonnet",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
    "together": {
        "model": "togethercomputer/LLaMA-2-7B-32K",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
    "azure_openai": {
        "model": "gpt-4o",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
    "aws_bedrock": {
        "model": "anthropic.claude-3-sonnet-20240229",
        "messages": REALISTIC_MESSAGES,
        "max_tokens": 500,
        "temperature": 0.7,
    },
}


async def simulate_concurrent_requests(client, project, payload, num_requests=10):
    """Simule des requêtes concurrentes réalistes."""
    headers = {"Authorization": f"Bearer {project.api_key}"}

    async def make_request():
        response = await client.post(
            "/proxy/openai/v1/chat/completions", json=payload, headers=headers
        )
        return response.status_code

    # Exécuter les requêtes en parallèle
    tasks = [make_request() for _ in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return results


def generate_performance_report(results, start_time, end_time):
    """Génère un rapport de performance basé sur les résultats des tests."""
    total_requests = len(results)
    successful_requests = sum(1 for r in results if r == 200)
    failed_requests = total_requests - successful_requests

    duration = (end_time - start_time).total_seconds()
    requests_per_second = total_requests / duration if duration > 0 else 0

    return {
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "duration_seconds": duration,
        "requests_per_second": requests_per_second,
        "success_rate": (successful_requests / total_requests) * 100
        if total_requests > 0
        else 0,
    }
