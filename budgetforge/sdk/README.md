# BudgetForge SDK Simple

SDK léger et simple pour intégrer BudgetForge dans vos projets Python.

## Installation

Aucune installation nécessaire ! Copiez simplement le fichier `budgetforge_sdk.py` dans votre projet.

```python
from budgetforge_sdk import BudgetForgeLLM, BudgetForgeChat
```

## Utilisation rapide

### LLM simple

```python
from budgetforge_sdk import BudgetForgeLLM

llm = BudgetForgeLLM(
    api_key="votre-cle-api-budgetforge",
    model="gpt-4",
    provider="openai"
)

response = llm.invoke("Bonjour, comment vas-tu?")
print(response)
```

### Chat simple

```python
from budgetforge_sdk import BudgetForgeChat

chat = BudgetForgeChat(
    api_key="votre-cle-api-budgetforge",
    model="claude-3-sonnet",
    provider="anthropic"
)

messages = [
    {"role": "user", "content": "Bonjour!"},
    {"role": "assistant", "content": "Bonjour! Comment puis-je vous aider?"},
    {"role": "user", "content": "Explique-moi l'IA"}
]

result = chat.invoke(messages)
print(result["content"])
```

### Streaming

```python
# Streaming LLM
for chunk in llm.stream("Raconte-moi une histoire:"):
    print(chunk, end="", flush=True)

# Streaming Chat
for generation in chat.stream(messages):
    print(generation["content"], end="", flush=True)
```

## Configuration

### Paramètres du LLM

- `api_key`: Votre clé API BudgetForge
- `model`: Modèle cible ("gpt-4", "claude-3-sonnet", etc.)
- `provider`: Fournisseur ("openai", "anthropic", "google", etc.)
- `api_base_url`: URL de base de l'API (défaut: localhost:8000)
- `max_tokens`: Nombre maximum de tokens par appel
- `temperature`: Température de réponse (0.0-2.0)
- `timeout`: Timeout des requêtes en secondes

### Fonctionnalités BudgetForge

Le SDK bénéficie automatiquement de toutes les fonctionnalités BudgetForge :

- ✅ **Enforcement du budget** - Les appels sont bloqués si le budget est dépassé
- ✅ **Tracking des coûts** - Suivi en temps réel des dépenses par projet
- ✅ **Fallback automatique** - Bascule vers des providers moins chers
- ✅ **Alertes** - Notifications email/webhook pour les seuils de budget
- ✅ **Analytics détaillées** - Breakdown par provider, modèle, agent

## Exemples avancés

### Appel asynchrone

```python
import asyncio

async def main():
    llm = BudgetForgeLLM(api_key="votre-cle")
    response = await llm.invoke_async("Question asynchrone")
    print(response)

asyncio.run(main())
```

### Paramètres personnalisés

```python
llm = BudgetForgeLLM(
    api_key="votre-cle",
    model="gpt-4",
    temperature=0.5,
    max_tokens=500,
    timeout=60
)

# Paramètres par appel
response = llm.invoke(
    "Prompt complexe",
    temperature=0.8,
    max_tokens=1000
)
```

### Multi-providers

```python
# Différents providers pour différents usages
openai_llm = BudgetForgeLLM(api_key="cle", model="gpt-4", provider="openai")
anthropic_llm = BudgetForgeLLM(api_key="cle", model="claude-3-sonnet", provider="anthropic")

# Utiliser le provider approprié pour chaque tâche
complex_task = openai_llm.invoke("Analyse complexe...")
creative_task = anthropic_llm.invoke("Tâche créative...")
```

## Gestion des erreurs

```python
try:
    response = llm.invoke("Votre prompt")
except ValueError as e:
    if "budget exceeded" in str(e).lower():
        print("Budget épuisé!")
    elif "provider unavailable" in str(e).lower():
        print("Provider indisponible")
    else:
        print(f"Erreur: {e}")
```

## Intégration avec d'autres frameworks

### Langchain (manuellement)

```python
from langchain.llms.base import LLM
from typing import Optional, List

class BudgetForgeLangchainWrapper(LLM):
    def __init__(self, api_key: str, model: str = "gpt-4", provider: str = "openai"):
        super().__init__()
        self.budgetforge_llm = BudgetForgeLLM(api_key, model, provider)
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        return self.budgetforge_llm.invoke(prompt)
    
    @property
    def _llm_type(self) -> str:
        return "budgetforge"

# Utilisation
llm = BudgetForgeLangchainWrapper(api_key="votre-cle")
```

## Support

- **Documentation**: [BudgetForge Docs](https://budget.maxiaworld.app/docs)
- **Issues**: [GitHub Issues](https://github.com/maxia-lab/budgetforge/issues)
- **Email**: ceo@maxiaworld.app

## Licence

MIT License