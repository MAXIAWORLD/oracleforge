# BudgetForge API Reference

Documentation complète de l'API BudgetForge pour l'intégration dans vos applications.

## Authentification

Toutes les requêtes API doivent inclure votre clé API dans l'en-tête `Authorization` :

```http
Authorization: Bearer votre-cle-api-budgetforge
```

## Endpoints principaux

### Proxy LLM

Route les requêtes vers les différents providers LLM avec contrôle du budget.

**Endpoint** : `POST /api/proxy/{provider}/v1/chat/completions`

**Paramètres** :
- `provider` : Fournisseur cible (`openai`, `anthropic`, `google`)

**Corps de la requête** :
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Votre prompt ici"}
  ],
  "temperature": 0.7,
  "max_tokens": 500,
  "stream": false
}
```

**Réponse** :
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Réponse du modèle"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

### Gestion du budget

**Endpoint** : `GET /api/budget`

Récupère les informations du budget actuel.

**Réponse** :
```json
{
  "current_spend": 15.75,
  "budget_limit": 100.0,
  "budget_remaining": 84.25,
  "budget_percentage": 15.75,
  "alerts_enabled": true,
  "next_reset": "2026-05-01T00:00:00Z"
}
```

**Endpoint** : `PUT /api/budget`

Met à jour les paramètres du budget.

**Corps de la requête** :
```json
{
  "budget_limit": 200.0,
  "alerts_enabled": true,
  "alert_threshold": 0.8
}
```

### Analytics

**Endpoint** : `GET /api/analytics`

Récupère les statistiques d'utilisation.

**Paramètres de requête** :
- `time_range` : Période (`today`, `week`, `month`, `custom`)
- `start_date` : Date de début (format ISO)
- `end_date` : Date de fin (format ISO)

**Réponse** :
```json
{
  "total_requests": 1250,
  "total_cost": 45.67,
  "cost_by_provider": {
    "openai": 32.15,
    "anthropic": 10.42,
    "google": 3.10
  },
  "cost_by_model": {
    "gpt-4": 25.80,
    "gpt-3.5-turbo": 6.35,
    "claude-3-sonnet": 10.42
  },
  "requests_over_time": [
    {"date": "2026-04-20", "requests": 45, "cost": 1.23},
    {"date": "2026-04-21", "requests": 67, "cost": 2.45}
  ]
}
```

## Exemples d'intégration

### Python avec requests

```python
import requests
import json

API_KEY = "votre-cle-api-budgetforge"
BASE_URL = "https://budget.maxiaworld.app"

def call_budgetforge(prompt, model="gpt-4", provider="openai"):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    response = requests.post(
        f"{BASE_URL}/api/proxy/{provider}/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

# Utilisation
result = call_budgetforge("Explique l'IA en termes simples")
print(result)
```

### JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

const API_KEY = 'votre-cle-api-budgetforge';
const BASE_URL = 'https://budget.maxiaworld.app';

async function callBudgetForge(prompt, model = 'gpt-4', provider = 'openai') {
    const response = await fetch(
        `${BASE_URL}/api/proxy/${provider}/v1/chat/completions`,
        {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${API_KEY}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model,
                messages: [{ role: 'user', content: prompt }],
                temperature: 0.7,
                max_tokens: 500
            })
        }
    );

    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
}

// Utilisation
callBudgetForge('Explique l\'IA en termes simples')
    .then(result => console.log(result))
    .catch(error => console.error(error));
```

### Streaming avec Python

```python
import requests
import json

def stream_budgetforge(prompt, model="gpt-4", provider="openai"):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": True
    }
    
    response = requests.post(
        f"{BASE_URL}/api/proxy/{provider}/v1/chat/completions",
        headers=headers,
        json=payload,
        stream=True
    )
    
    for line in response.iter_lines():
        if line.startswith(b'data: ') and line.strip() != b'data: [DONE]':
            try:
                data = json.loads(line[6:])
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    if 'content' in delta:
                        yield delta['content']
            except json.JSONDecodeError:
                continue

# Utilisation
for chunk in stream_budgetforge("Raconte une histoire:"):
    print(chunk, end='', flush=True)
```

### SDK Python simple

```python
from budgetforge_sdk import BudgetForgeLLM

# Initialisation
llm = BudgetForgeLLM(
    api_key="votre-cle-api-budgetforge",
    model="gpt-4",
    provider="openai"
)

# Appel simple
response = llm.invoke("Votre prompt ici")
print(response)

# Streaming
for chunk in llm.stream("Prompt avec streaming:"):
    print(chunk, end="", flush=True)

# Appel asynchrone
import asyncio

async def async_call():
    response = await llm.invoke_async("Prompt asynchrone")
    print(response)

asyncio.run(async_call())
```

## Gestion des erreurs

### Codes d'erreur courants

- **400** : Requête malformée
- **401** : Clé API invalide
- **402** : Budget dépassé
- **429** : Rate limiting
- **500** : Erreur serveur

### Exemple de gestion d'erreurs

```python
try:
    response = call_budgetforge(prompt)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 402:
        print("Budget dépassé !")
    elif e.response.status_code == 429:
        print("Rate limiting atteint")
    else:
        print(f"Erreur HTTP: {e.response.status_code}")
except Exception as e:
    print(f"Erreur: {e}")
```

## Configuration avancée

### Fallback automatique

BudgetForge supporte le fallback automatique vers des providers moins chers. Configurez vos préférences :

```python
# Configuration de fallback
fallback_config = {
    "primary_provider": "openai",
    "fallback_providers": ["anthropic", "google"],
    "fallback_conditions": ["budget_exceeded", "provider_unavailable"]
}
```

### Alertes budget

Activez les notifications pour les seuils de budget :

```python
# Configuration d'alertes
alert_config = {
    "email_alerts": True,
    "webhook_url": "https://votre-webhook.com/notifications",
    "thresholds": [0.5, 0.8, 0.95]  # 50%, 80%, 95% du budget
}
```

## Intégration avec frameworks

### Langchain

```python
from langchain.llms.base import LLM
from budgetforge_sdk import BudgetForgeLLM

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

### FastAPI

```python
from fastapi import FastAPI, HTTPException
from budgetforge_sdk import BudgetForgeLLM

app = FastAPI()
llm = BudgetForgeLLM(api_key="votre-cle")

@app.post("/chat")
async def chat_endpoint(prompt: str):
    try:
        response = await llm.invoke_async(prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Best practices

1. **Gestion des erreurs** : Toujours catcher les exceptions et gérer les erreurs de budget
2. **Monitoring** : Surveillez régulièrement votre utilisation via l'endpoint `/api/analytics`
3. **Optimisation** : Utilisez des modèles moins chers pour les tâches simples
4. **Streaming** : Privilégiez le streaming pour les réponses longues
5. **Cache** : Mettez en cache les réponses similaires pour réduire les coûts

## Support

- **Documentation** : [https://budget.maxiaworld.app/docs](https://budget.maxiaworld.app/docs)
- **Support** : hello@maxiaworld.app
- **Issues** : [GitHub Issues](https://github.com/maxia-lab/budgetforge/issues)