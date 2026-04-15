# MAXIA Oracle — Briefing pour la prochaine session

**Destination** : à donner à Claude au tout début de la prochaine session (copy-paste du bloc ci-dessous, ou simplement `"Continue MAXIA Oracle, lis oracleforge/docs/next-session-prompt.md avant toute action"`).

**État figé au** : 14 avril 2026, soir — fin de session après Phase 5 Steps 1-3.

---

## Prompt à coller au début de la prochaine session

```
Continue MAXIA Oracle — on reprend Phase 5 au Step 4 (wiring server.py).

Avant toute action, lis dans l'ordre :
1. oracleforge/docs/next-session-prompt.md (ce fichier — contexte complet)
2. oracleforge/docs/plan-maxia-oracle-2026-04-14.md §3 Phase 5 (objectif + checkpoint)
3. La mémoire project_maxia_oracle_progress.md (état d'avancement global + Phase 5 Steps 1-3 NON COMMITÉS)
4. La mémoire project_maxia_oracle_decisions.md (les 5 décisions Phase 5 validées par Alexis)
5. oracleforge/backend/mcp_server/tools.py (les 8 tools déjà écrits, à enregistrer Step 4)

PUIS fais `git status` pour confirmer l'état des fichiers non-commit avant d'écrire quoi que ce soit.

Ne touche pas à Phase 4 (tout committé sur master, commit a347744). Le test live Base mainnet Step 10 reste différé jusqu'à ce qu'Alexis ait un wallet test avec ~$0.10.
```

---

## Contexte critique à conserver

### État du working tree : Phase 5 Steps 1-3 NON COMMITÉS

Au moment de l'arrêt, les changements Phase 5 sont dans le working tree mais **pas dans git**. La prochaine session va les retrouver via `git status`. **Ne pas les jeter.**

**Fichiers nouveaux (untracked)** :
- `oracleforge/backend/mcp_server/__init__.py` — package marker + philosophie
- `oracleforge/backend/mcp_server/__main__.py` — skeleton stdio entry point (à finaliser Step 5)
- `oracleforge/backend/mcp_server/server.py` — skeleton `build_server()` vide (à remplir Step 4)
- `oracleforge/backend/mcp_server/tools.py` — **8 tools V1 complets et testés**
- `oracleforge/backend/services/oracle/multi_source.py` — helper extrait de routes_price

**Fichiers modifiés (not staged)** :
- `oracleforge/backend/api/routes_price.py` — refactoré pour utiliser `multi_source.collect_sources` au lieu de la logique inline

### Environnement venv (non-git)

- `mcp 1.27.0` installé via pip dans `oracleforge/backend/venv/`
- `fastapi` upgradé `0.116.2 → 0.135.3` (forcé par starlette 1.0 que mcp a tiré en transitive)
- `starlette 1.0.0` installé (remplace 0.48.0)
- Toutes les dep transitives : `httpx-sse`, `sse-starlette 3.3.4`, `pydantic-settings`, `jsonschema`, etc.

**À faire plus tard (Phase 7 deploy)** : figer ces versions dans un `requirements.txt` propre pour que le VPS ait le même setup.

### Tests à l'arrêt

- 33/33 pytest verts (16 Phase 3 + 8 Phase 4 DB + 9 Phase 4 x402)
- Phase 5 n'a pas encore de tests pytest (prévus Step 7)
- Smoke test manuel Step 3 : `health_check`, `list_supported_symbols`, `get_cache_stats`, toutes les input validations OK
- Le smoke test a touché quelques sources réseau (Pyth, Chainlink) — pas de test full offline en place

---

## Steps déjà effectués (Phase 5 Steps 1-3)

### Step 1 — Install mcp + scaffold package

- `pip install "mcp>=1.0"` → `mcp 1.27.0`
- Upgrade `fastapi` pour compat starlette 1.0
- Créé `oracleforge/backend/mcp_server/` avec 4 fichiers squelettes
- Vérifié imports : `mcp.server.lowlevel.Server`, `mcp.server.stdio.stdio_server`, `mcp.types.Tool`, `mcp.types.TextContent`

### Step 2 — Extract multi_source helper

- Créé `services/oracle/multi_source.py` avec `collect_sources(symbol)` + `compute_divergence(prices)`
- Refactoré `api/routes_price.py` pour importer et utiliser le helper
- Supprimé les fonctions privées `_collect_sources` / `_compute_divergence` des routes
- 33/33 tests Phase 3/4 toujours verts après le refactor

### Step 3 — Écrire les 8 tools MCP

`mcp_server/tools.py` contient **8 fonctions async publiques**, chacune wrappe un oracle service et retourne un dict normalisé :

| # | Tool | Wrap | Input validation |
|---|---|---|---|
| 1 | `get_price(symbol)` | `multi_source.collect_sources + compute_divergence` | symbole regex `^[A-Z0-9]{1,10}$` |
| 2 | `get_prices_batch(symbols)` | `pyth_oracle.get_batch_prices` | liste non-vide ≤ 50, dedup, regex |
| 3 | `get_sources_status()` | Ping BTC sur Pyth + Chainlink + price_oracle en // | aucun |
| 4 | `get_cache_stats()` | `price_oracle.get_cache_stats()` | aucun |
| 5 | `get_confidence(symbol)` | `collect_sources` + `_interpret_divergence` | regex |
| 6 | `list_supported_symbols()` | Fusion `CRYPTO_FEEDS + EQUITY_FEEDS + CHAINLINK_FEEDS + TOKEN_MINTS` (79 symbols total) | aucun |
| 7 | `get_chainlink_onchain(symbol)` | `chainlink_oracle.get_chainlink_price` | regex + vérif présence dans CHAINLINK_FEEDS |
| 8 | `health_check()` | Liveness probe léger (pas de ping upstream) | aucun |

**Pattern de retour** :
- Succès : `{"data": ..., "disclaimer": "Data feed only. Not investment advice. No custody. No KYC."}`
- Erreur : `{"error": "...", ...extra, "disclaimer": "..."}`
- **Jamais de raise** — toute exception est capturée et retournée comme error dict

---

## Step 4 — ce qui reste à faire immédiatement

**Scope** : finaliser `oracleforge/backend/mcp_server/server.py` avec les handlers MCP officiels.

Structure attendue dans `server.py` :

```python
from mcp.server.lowlevel import Server
from mcp import types
from mcp_server import tools

server = Server("maxia-oracle")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_price",
            description="...",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string", ...}},
                "required": ["symbol"],
            },
        ),
        # ... 7 autres
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    # dispatch name -> tools.<func>
    # convertir le dict retourné en JSON texte
    # isError=True si "error" dans le dict
    ...
```

**Points délicats à gérer Step 4** :
1. Chaque Tool doit avoir un JSON schema complet (pas juste description) pour que Claude Desktop affiche les paramètres proprement
2. Le dispatch name → fonction peut être un dict `{"get_price": tools.get_price, ...}` ou un getattr
3. La réponse doit être sérialisée en JSON (via `json.dumps`) puis wrappée en `types.TextContent(type="text", text=...)`
4. Si le dict retour contient `"error"`, construire la `CallToolResult` avec `isError=True` pour que Claude Desktop distingue erreurs de succès

**Temps estimé** : 30 min.

---

## Steps 5 à 9 — ordre de priorité pour la prochaine session

| Step | Tâche | Temps | Dépend |
|---|---|---|---|
| 4 | `server.py` wiring 8 tools | 30 min | — |
| 5 | `__main__.py` final test `python -m mcp_server` | 15 min | 4 |
| 6 | `routes_mcp.py` HTTP SSE mount | 45 min | 4 |
| 7 | Tests pytest (8 tools mocks + discovery) | 1 h | 4-5-6 |
| 8 | README + smoke test Claude Desktop local | 30 min | 5 |
| 9 | Audit `docs/phase5_mcp_extraction.md` + commit + mémoires | 30 min | 7-8 |

**Total estimé** : ~3h30 de travail effectif pour finir Phase 5 complètement.

---

## Décisions Phase 5 validées — à NE PAS remettre en question

1. **SDK officiel `mcp>=1.0`** — pas d'extraction du V12 custom (non-compliant avec Claude Desktop)
2. **8 tools V1** — drop `get_price_history` et `subscribe_price_stream`, reportés V1.1
3. **Dual transport** — stdio (local Claude Desktop) + HTTP SSE (`/mcp/sse` remote)
4. **Package maxia-oracle** avec entry point `maxia-oracle-mcp` Phase 6 (pas de package séparé)
5. **Auth via env var `MAXIA_ORACLE_API_KEY`** — l'user colle sa clé dans `claude_desktop_config.json`

Détail complet dans la mémoire `project_maxia_oracle_decisions.md`.

---

## Autres rappels

### Ne pas toucher

- **Phase 4** : tout committé sur master, commit `a347744`, le middleware x402 fonctionne
- **Step 10 Phase 4** : test live Base mainnet différé indéfiniment (attend qu'Alexis ait un wallet test avec `~$0.10`)
- **GuardForge, MissionForge, MAXIA V12** : hors scope, en pause

### Règles produit non négociables

- **Pas de produit régulé** (mémoire `feedback_no_regulated_business.md`) — pas d'escrow, pas de custody, pas de KYC, pas de marketplace intermédiaire
- **Auditer avant d'affirmer** (mémoire `feedback_never_lie.md`) — vérifier avant de dire "ça marche"
- **Alexis parle français**, répondre en français
- **Jamais hardcoder** de valeurs fausses
- **Backend + frontend ensemble** — mais pas de frontend en Phase 5, donc N/A ici

### Routage modèles

- Tout appel Agent doit passer `model:` explicitement (`haiku` pour lookups/reads, `sonnet` pour implementation)
- Au début de session : `/context-budget`
- À 60 % du contexte : `/strategic-compact`
