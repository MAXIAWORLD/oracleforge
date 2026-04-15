# MAXIA Oracle — Briefing pour la session Phase 6.3-6.8

**Destination** : à donner à Claude au tout début de la prochaine session (copy-paste du bloc ci-dessous, ou simplement `"Continue MAXIA Oracle, lis oracleforge/docs/next-session-prompt-phase6.md avant toute action"`).

**État figé au** : 15 avril 2026 — fin de session après Phase 6.2 (TypeScript SDK committé).

---

## Prompt à coller au début de la prochaine session

```
Continue MAXIA Oracle — Phase 6 plugins frameworks (sous-phases 6.3 à 6.8).

Avant toute action, lis dans l'ordre :
1. oracleforge/docs/next-session-prompt-phase6.md (ce fichier — contexte complet)
2. La mémoire project_maxia_oracle_progress.md (état complet, 91 tests verts,
   commits session précédente, audit V12 SDK)
3. La mémoire project_maxia_oracle_decisions.md (Phase 5 D5 scope adjustment
   + décisions Phase 6 validées)
4. oracleforge/sdk/python/src/maxia_oracle/client.py (les 9 méthodes à
   wrapper dans chaque plugin)
5. oracleforge/backend/mcp_server/server.py (les 8 tool names et JSON
   schemas à réutiliser dans les plugins)

PUIS fais `git log --oneline -8` pour confirmer que tu reprends après
le commit `3a9b502 feat(oracleforge): Phase 6.2 — TypeScript SDK
@maxia/oracle`. Le working tree oracleforge/ doit être propre.

Ne touche pas à : Phase 4 x402 live test (différé, attend wallet Alexis),
Phase 5 MCP server, Phase 6.1 Python SDK, Phase 6.2 TS SDK. Tous
committés et stables. 91 tests verts (57 backend + 17 Python SDK + 17
TS SDK).
```

---

## Contexte critique à conserver

### État git au moment de l'arrêt

Les 6 commits Phase 5 + pre-6 + 6.1 + 6.2 sont **tous sur master**, working tree oracleforge/ propre. Les modifs hors scope (CLAUDE.md, missionforge/, forge-suite/, guardforge/.coverage) restent unstaged comme avant, hors périmètre MAXIA Oracle.

```
3a9b502  Phase 6.2 — TypeScript SDK @maxia/oracle
2413e3f  Phase 6.1 — Python SDK maxia-oracle + stdio MCP bridge
a802998  add /api/symbols + /api/chainlink (prep Phase 6 SDK parity)
9e1ba95  pin Phase 5 dependencies in requirements.txt
2b29440  Phase 5 — MCP server spec-compliant (stdio + HTTP SSE)
a347744  Phase 4 — x402 middleware Base mainnet vente directe
```

### Tests au moment de l'arrêt

- **Backend pytest** : 57/57 verts (16 Phase 3 + 6 extension + 8 Phase 4 DB + 9 Phase 4 x402 + 18 Phase 5 MCP)
- **Python SDK pytest** : 17/17 verts (httpx.MockTransport, 0.11s)
- **TypeScript SDK vitest** : 17/17 verts (fake fetch, 341ms)
- **Total** : 91 tests verts en ~3s, zéro réseau

### Parité atteinte en 6.1 + 6.2

9 méthodes identiques entre : backend REST (Phase 3/4/5 + `/api/symbols` + `/api/chainlink/{symbol}`), MCP server Phase 5 (8 tools + register hors MCP), Python SDK `MaxiaOracleClient`, TypeScript SDK `MaxiaOracleClient`.

| # | Python SDK | TS SDK | REST | MCP tool |
|---|---|---|---|---|
| 1 | `register()` | `register()` | POST /api/register | — |
| 2 | `health()` | `health()` | GET /health | `health_check` |
| 3 | `price(symbol)` | `price(symbol)` | GET /api/price/{symbol} | `get_price` |
| 4 | `prices_batch(symbols)` | `pricesBatch(symbols)` | POST /api/prices/batch | `get_prices_batch` |
| 5 | `sources()` | `sources()` | GET /api/sources | `get_sources_status` |
| 6 | `cache_stats()` | `cacheStats()` | GET /api/cache/stats | `get_cache_stats` |
| 7 | `list_symbols()` | `listSymbols()` | GET /api/symbols | `list_supported_symbols` |
| 8 | `chainlink_onchain(s)` | `chainlinkOnchain(s)` | GET /api/chainlink/{s} | `get_chainlink_onchain` |
| 9 | `confidence(s)` | `confidence(s)` | GET /api/price/{s} extract | `get_confidence` |

---

## Scope sous-phases restantes — 6.3 à 6.8 (~5 h)

| # | Livrable | Temps | Dép |
|---|---|---|---|
| 6.3 | `oracleforge/plugins/langchain-maxia-oracle/` — 8 tools LangChain wrappers | ~1 h 30 | — |
| 6.4 | `oracleforge/plugins/crewai-tools-maxia-oracle/` — 8 tools CrewAI | ~1 h | 6.3 |
| 6.5 | `oracleforge/plugins/autogen-maxia-oracle/` — 8 tools AutoGen | ~1 h | 6.3 |
| 6.6 | `oracleforge/plugins/llama-index-tools-maxia-oracle/` — 8 tools LlamaIndex | ~1 h | 6.3 |
| 6.7 | Tests pytest + README par plugin | ~1 h | 6.3-6.6 |
| 6.8 | Commit groupé + audit doc `docs/phase6_sdk_plugins.md` + update mémoires | ~30 min | 6.7 |

**Commencer par 6.3** qui sert de template pour les 3 autres. Une fois le pattern établi avec LangChain, 6.4-6.6 sont presque du copier-coller.

**Tous les plugins ont la même architecture** :
- Dep runtime unique : `maxia-oracle>=0.1.0,<1` (installable via `pip install -e oracleforge/sdk/python` en dev)
- 8 fichiers tool, un par méthode oracle du SDK (drop `register()` — pas un tool agent)
- Pydantic Input schemas pour chaque tool (même pattern que V12 `MaxiaXxxInput(BaseModel)`)
- `_run()` sync qui instancie un `MaxiaOracleClient` au besoin et appelle la méthode
- Chaque tool a le disclaimer dans sa description

---

## Pattern à utiliser (template 6.3 LangChain)

### Structure de fichiers

```
oracleforge/plugins/langchain-maxia-oracle/
├── pyproject.toml
├── README.md
├── src/
│   └── langchain_maxia_oracle/
│       ├── __init__.py
│       ├── client.py          # shared MaxiaOracleClient singleton
│       └── tools.py           # 8 BaseTool classes
└── tests/
    └── test_tools.py
```

### Référence V12 (à NE PAS copier tel quel — y chercher la structure)

- `C:/Users/Mini pc/Desktop/MAXIA V12/langchain-maxia/src/langchain_maxia/tools.py` (382 lignes, 10 tools V12 dont seulement 2-3 sont oracle-pertinents)
- `C:/Users/Mini pc/Desktop/MAXIA V12/langchain-maxia/pyproject.toml` — minimal, copier le style
- `C:/Users/Mini pc/Desktop/MAXIA V12/langchain-maxia/README.md` — layout général

### Tools LangChain à écrire (8 classes)

1. `MaxiaOracleGetPriceTool` → `client.price(symbol)`
2. `MaxiaOracleGetPricesBatchTool` → `client.prices_batch(symbols)`
3. `MaxiaOracleGetSourcesStatusTool` → `client.sources()`
4. `MaxiaOracleGetCacheStatsTool` → `client.cache_stats()`
5. `MaxiaOracleGetConfidenceTool` → `client.confidence(symbol)`
6. `MaxiaOracleListSupportedSymbolsTool` → `client.list_symbols()`
7. `MaxiaOracleGetChainlinkOnchainTool` → `client.chainlink_onchain(symbol)`
8. `MaxiaOracleHealthCheckTool` → `client.health()`

Chaque tool hérite de `langchain_core.tools.BaseTool`, définit `name`, `description` (incluant le disclaimer), `args_schema` (pydantic), et `_run` (sync) + `_arun` (async optionnel).

### Tests pytest minimal par plugin

- 1 test `test_all_tools_exported` — vérifie la liste des 8 classes
- 1 test `test_tool_names` — chaque tool a un nom unique
- 1 test `test_tool_descriptions_contain_disclaimer` — disclaimer présent
- 3-4 tests `test_<tool>_calls_client` avec `MaxiaOracleClient` mocké (unittest.mock) pour valider le dispatch

Pas besoin de tests end-to-end live pour chaque plugin — le SDK Python sous-jacent est déjà couvert par ses propres 17 tests.

### README par plugin

- Install : `pip install langchain-maxia-oracle`
- Quick start : `from langchain_maxia_oracle import MAXIA_ORACLE_TOOLS` + exemple dans un agent LangChain
- Les 8 tools listés
- Non-goals (pas d'ordre routing, etc.)

---

## Audit V12 synthèse — référence rapide

- `maxia-sdk/client.py` : 1116 lignes, 46 méthodes, ~8 oracle-pertinentes (prices, stocks, stock_price, trending, fear_greed, sentiment, status, close). 38 régulées (swap, escrow, GPU, DeFi, credits, streams, DCA, identity, signals, marketplace exec).
- `langchain-maxia/tools.py` : 382 lignes, 10 tools V12, 2-3 oracle-pertinents (stock_price, crypto_prices, sentiment borderline).
- Même ratio ~20-30 % attendu pour crewai-tools-maxia, autogen-maxia, llama-index-tools-maxia.
- **Conséquence stratégique** : extraction = **structure** (pyproject, layout, BaseTool class pattern) PAS **surface** (les méthodes/tools sont réécrits).

### Plugins V12 à consulter pour la structure

```
C:/Users/Mini pc/Desktop/MAXIA V12/langchain-maxia/
C:/Users/Mini pc/Desktop/MAXIA V12/crewai-tools-maxia/
C:/Users/Mini pc/Desktop/MAXIA V12/autogen-maxia/
C:/Users/Mini pc/Desktop/MAXIA V12/llama-index-tools-maxia/
```

Chacun a un layout `src/<pkg>/{__init__,client,tools}.py` + `pyproject.toml` + `README.md` + `dist/`.

---

## Décisions Phase 6 — à NE PAS remettre en question

1. **Option B = package séparé** (pas un `maxia[oracle]` extra). Recommandation du plan, validée implicitement.
2. **TS SDK full parity V1** (validé Alexis 15 avril — "être pro") — déjà livré en 6.2.
3. **LlamaIndex inclus V1** (validé Alexis 15 avril — "inclu").
4. **Eliza et Vercel hors V1** (validé Alexis avant Phase 6).
5. **Python SDK = la dep runtime unique des plugins**. Pas de duplication du client HTTP dans chaque plugin. Chaque plugin déclare `maxia-oracle>=0.1.0,<1` et importe `MaxiaOracleClient`.
6. **Nom PyPI confirmé** : `langchain-maxia-oracle`, `crewai-tools-maxia-oracle`, `autogen-maxia-oracle`, `llama-index-tools-maxia-oracle`. Nom import Python : `langchain_maxia_oracle`, etc. (snake_case).
7. **Pas de publication PyPI/npm en Phase 6**. Les packages vivent dans le repo et sont testés via `pip install -e` local. La publication effective c'est Phase 9 Distribution.

---

## Règles produit non négociables

Mémoires critiques à re-consulter si tentation de dévier :

- `feedback_no_regulated_business.md` — **Pas de produit régulé**. Aucun tool d'exécution (swap, buy, sell), aucun tool de custody (wallets, signing), aucun tool de marketplace intermédiaire, aucun tool de KYC, aucun xStock / tokenized security.
- `feedback_never_lie.md` — **Auditer avant d'affirmer**. Chaque commit doit venir avec preuves (pytest vert, smoke test réussi, typecheck OK). Ne jamais dire "ça marche" sans preuve.
- `user_alexis.md` — Alexis parle français, répondre en français.
- Jamais hardcoder de valeurs fausses. Si une source échoue → erreur propre, pas de fake price.

## Routage modèles

- Tout appel `Agent` DOIT passer `model:` explicitement (`haiku` pour lookups/reads/greps, `sonnet` pour implementation, `opus` réservé aux archi ambiguës)
- Début de session : `/context-budget` pour voir où on en est
- À 60 % du contexte : `/strategic-compact` pour préserver la marge

---

## Totaux au moment de l'arrêt

- **Backend** : ~6 500 lignes Python, 33 modules, 57 pytest verts
- **Python SDK** : ~1 900 lignes (client 300 + bridge 280 + errors 100 + tests 280 + README + pyproject), 17 pytest verts
- **TypeScript SDK** : ~900 lignes (client 310 + errors 80 + types 90 + index 40 + tests 290 + README + package.json + tsconfig), 17 vitest verts
- **Grand total** : ~9 300 lignes de code tracked, **91 tests verts**
- **6 commits Phase 5 + pre-6 + 6.1 + 6.2** tous sur master

---

**Temps estimé pour finir Phase 6** : ~5 h de travail effectif. À l'issue de 6.8, Phase 6 sera entièrement terminée et on passera à Phase 7 (Deploy VPS `ubuntu@maxiaworld.app:8003`, domaine `oracle.maxiaworld.app`).
