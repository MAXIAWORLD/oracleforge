"""Exemple d'utilisation du SDK BudgetForge simple."""

import asyncio
from budgetforge_sdk import BudgetForgeLLM, BudgetForgeChat


async def demo_basic():
    """Démo basique du SDK."""
    print("=== Démo SDK BudgetForge ===")

    # LLM simple
    llm = BudgetForgeLLM(
        api_key="votre-cle-api-budgetforge", model="gpt-4", provider="openai"
    )

    response = llm.invoke("Quelle est la capitale de la France?")
    print(f"Réponse LLM: {response}")

    # Chat simple
    chat = BudgetForgeChat(
        api_key="votre-cle-api-budgetforge",
        model="claude-3-sonnet",
        provider="anthropic",
    )

    messages = [
        {"role": "user", "content": "Bonjour!"},
        {"role": "assistant", "content": "Bonjour! Comment puis-je vous aider?"},
        {"role": "user", "content": "Explique-moi l'IA en termes simples"},
    ]

    result = chat.invoke(messages)
    print(f"Réponse Chat: {result['content'][:100]}...")

    print("\n=== Démo Streaming ===")

    # Streaming
    print("Streaming LLM:")
    for chunk in llm.stream("Raconte-moi une courte histoire:"):
        print(chunk, end="", flush=True)
    print()


async def demo_advanced():
    """Démo avancée avec paramètres."""
    print("\n=== Démo Avancée ===")

    llm = BudgetForgeLLM(
        api_key="votre-cle-api-budgetforge",
        model="gpt-4",
        provider="openai",
        temperature=0.5,
        max_tokens=100,
    )

    response = llm.invoke("Écris un poème court sur l'IA", temperature=0.8)
    print(f"Poème IA: {response}")

    # Appel asynchrone
    response_async = await llm.invoke_async("Qu'est-ce que le machine learning?")
    print(f"Réponse async: {response_async[:100]}...")


async def main():
    """Lance toutes les démos."""
    await demo_basic()
    await demo_advanced()


if __name__ == "__main__":
    asyncio.run(main())
