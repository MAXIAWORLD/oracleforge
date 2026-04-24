# Guide d'intégration rapide BudgetForge

Démarrez avec BudgetForge en 5 minutes.

## Étape 1 : Obtenir une clé API

1. Créez un compte sur [BudgetForge](https://budget.maxiaworld.app)
2. Allez dans "API Keys" et générez une nouvelle clé
3. Copiez votre clé API

## Étape 2 : Installation (Optionnel)

Pour utiliser le SDK Python simple, copiez le fichier `budgetforge_sdk.py` dans votre projet :

```bash
# Téléchargez le SDK simple
wget https://raw.githubusercontent.com/maxia-lab/budgetforge/main/sdk/budgetforge_sdk.py
```

## Étape 3 : Premier appel

### Avec le SDK Python

```python
from budgetforge_sdk import BudgetForgeLLM

# Initialisation
llm = BudgetForgeLLM(
    api_key="votre-cle-api-budgetforge",
    model="gpt-4",
    provider="openai"
)

# Premier appel
response = llm.invoke("Bonjour ! Comment fonctionne BudgetForge ?")
print(response)
```

### Avec requests (sans SDK)

```python
import requests

API_KEY = "votre-cle-api-budgetforge"

response = requests.post(
    "https://budget.maxiaworld.app/api/proxy/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Bonjour !"}]
    }
)

print(response.json()["choices"][0]["message"]["content"])
```

## Étape 4 : Configurer votre budget

```python
import requests

# Vérifier le budget actuel
response = requests.get(
    "https://budget.maxiaworld.app/api/budget",
    headers={"Authorization": f"Bearer {API_KEY}"}
)
budget_info = response.json()
print(f"Budget utilisé: ${budget_info['current_spend']}")

# Configurer un nouveau budget
requests.put(
    "https://budget.maxiaworld.app/api/budget",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "budget_limit": 50.0,
        "alerts_enabled": True,
        "alert_threshold": 0.8
    }
)
```

## Étape 5 : Tester le playground

1. Connectez-vous à votre dashboard BudgetForge
2. Allez dans "Playground"
3. Testez différents prompts et modèles
4. Surveillez les coûts en temps réel

## Exemples pratiques

### Chat conversationnel

```python
from budgetforge_sdk import BudgetForgeChat

chat = BudgetForgeChat(api_key=API_KEY)

messages = [
    {"role": "user", "content": "Bonjour !"},
    {"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"},
    {"role": "user", "content": "Explique-moi comment fonctionne l'IA"}
]

result = chat.invoke(messages)
print(result["content"])
```

### Streaming pour réponses longues

```python
from budgetforge_sdk import BudgetForgeLLM

llm = BudgetForgeLLM(api_key=API_KEY)

print("Réponse streaming:")
for chunk in llm.stream("Raconte-moi une longue histoire sur l'IA:"):
    print(chunk, end="", flush=True)
```

### Multi-providers avec fallback

```python
from budgetforge_sdk import BudgetForgeLLM

providers = ["openai", "anthropic", "google"]

for provider in providers:
    try:
        llm = BudgetForgeLLM(api_key=API_KEY, provider=provider)
        response = llm.invoke("Question importante")
        print(f"{provider}: {response}")
        break  # Premier provider qui fonctionne
    except Exception as e:
        print(f"{provider} échoué: {e}")
        continue
```

## Dépannage

### Erreur commune : Clé API invalide

```python
try:
    response = llm.invoke("Test")
except ValueError as e:
    if "401" in str(e):
        print("Clé API invalide. Vérifiez votre clé.")
```

### Erreur commune : Budget dépassé

```python
try:
    response = llm.invoke("Test")
except ValueError as e:
    if "budget" in str(e).lower():
        print("Budget dépassé. Augmentez votre limite ou attendez le reset.")
```

### Vérifier la connectivité

```python
import requests

try:
    response = requests.get("https://budget.maxiaworld.app/api/health")
    print("API accessible")
except:
    print("API inaccessible")
```

## Prochaines étapes

1. **Explorez le dashboard** : Gérez vos budgets et surveillez l'utilisation
2. **Lisez la documentation complète** : [API Reference](./api-reference.md)
3. **Testez différentes configurations** : Température, tokens max, providers
4. **Intégrez dans votre application** : Utilisez les exemples d'intégration

## Support

- 📚 [Documentation complète](./api-reference.md)
- 💬 [Support technique](mailto:ceo@maxiaworld.app)
- 🐛 [Signaler un bug](https://github.com/maxia-lab/budgetforge/issues)