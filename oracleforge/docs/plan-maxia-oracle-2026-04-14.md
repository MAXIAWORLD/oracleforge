# MAXIA Oracle — Plan d'extraction et de mise en production

**Date** : 14 avril 2026
**Auteur** : Session Claude post-pivot stratégique (recherche marché 2026 + audit MAXIA V12)
**Statut** : VALIDÉ ALEXIS — prêt à exécuter en prochaine session
**Remplace** : `plan-2026-04-13.md` (plan OracleForge from-scratch — abandonné)

> **CE DOCUMENT EST LA SOURCE DE VÉRITÉ.** La prochaine session Claude DOIT le lire intégralement avant toute action sur `oracleforge/`. Le plan précédent (`plan-2026-04-13.md`) est obsolète et ne doit plus être suivi.

---

## 1. Pourquoi ce pivot

### 1.1 Ce qui a changé entre le 13 et le 14 avril 2026

Le plan original prévoyait de **construire OracleForge from scratch** sur 6 semaines, niché sur "stablecoin depeg detection", distribué via RapidAPI.

Trois éléments ont invalidé ce plan :

1. **Webacy occupe déjà la niche stablecoin depeg** depuis janvier 2026, avec une offre supérieure (multi-source DeFiLlama/CoinGecko/DEXScreener/Bitquery/0x, FX normalization EUR/JPY/GBP/BRL/ZAR/COP, gold XAU, dashboards production-grade, détection sUSD live janvier 2026, USDe à $0.65 octobre 2025). Voir [Webacy CTO blog janvier 2026](https://world.webacy.com/from-the-ctos-desk-january-2026-webacys-stablecoin-depeg-risk-monitor/).

2. **RapidAPI est mort en 2026** : Nokia a racheté la plateforme en novembre 2024 et l'a recyclée en outil B2B telecom. Le marketplace consumer est en déclin majeur. Le canal de distribution prévu n'existe plus.

3. **MAXIA V12 contient déjà 80% de ce qu'OracleForge devait construire**, mais en mieux. Audit dans `C:/Users/Mini pc/Desktop/MAXIA V12/` :
   - Oracle multi-source 5 sources avec **HFT streaming Pyth SSE <1s** (vs 30-170ms pour OracleForge mockup)
   - **x402 V2 micropaiements déployé Solana + Base mainnet**
   - **MCP server avec 46 tools** (manifest `/mcp/manifest`)
   - **SDK Python `pip install maxia` déjà sur PyPI**
   - **SDK TypeScript** dans `maxia-ts-sdk/`
   - **8 plugins frameworks agent** : `langchain-maxia`, `crewai-tools-maxia`, `autogen-maxia`, `composio-maxia`, `google-adk-maxia`, `llama-index-maxia`, `eliza-plugin-maxia`, `vercel-skill-maxia`
   - **AIP Protocol v0.3.0** signed intent envelopes ed25519
   - **Chainlink cross-verify** before swap (pattern de sécurité déjà implémenté)

Construire from scratch ce qui existe déjà = gâchis de 4-5 semaines.

### 1.2 Contrainte critique — pas de produit régulé

Alexis a explicitement refusé tout produit soumis à une réglementation financière (MSB, VASP, MiCA, EMI, securities). Voir mémoire `feedback_no_regulated_business.md`.

C'est probablement aussi une des raisons pour lesquelles MAXIA V12 est en pause : elle contient escrow custodial Solana+Base, marketplace AI-to-AI intermédiaire, tokenized stocks (xStocks/Ondo/Dinari), fiat onramp — tous régulés.

**MAXIA Oracle doit être construit pour rester strictement HORS du scope régulé** :

| ❌ Interdit | ✅ Autorisé |
|---|---|
| Custody / escrow / tenir des fonds clients | Vendre des données pures (oracle, prix, info publique agrégée) |
| Marketplace intermédiaire entre buyers et sellers | Pay-per-call où l'agent paye **notre** wallet pour **notre** service |
| Tokenized securities (xStocks, Ondo, Dinari) | SDK, MCP server, plugins frameworks (outils dev) |
| Fiat on/off-ramp | SaaS classique avec abonnement Stripe |
| "Investment advice" / signaux trading / predictions | Disclaimer "data feed only, not investment advice" |
| KYC obligatoire utilisateurs | Free tier sans inscription |
| Présenter le produit comme "trading tool" | Présenter le produit comme "data feed for AI agents" |

**Note importante** : Alexis n'a pas d'avocat de référence. Une consultation 1h (~150€ avec un avocat fintech français) reste recommandée AVANT mise en marché publique. En attendant : disclaimers fermes, vente directe documentée, pas d'intermédiation, pas de conseil.

---

## 2. État vérifié de MAXIA V12 (audit 14 avril 2026)

### 2.1 État global

- **Localisation** : `C:/Users/Mini pc/Desktop/MAXIA V12/`
- **Statut prod** : **HORS LIGNE** (confirmé Alexis 14 avril 2026). Backend était sur VPS port 8000, plus actif.
- **Code** : 130+ modules Python, 713 routes API, 46 MCP tools, 285 tests pytest (pas de CI active), pas de linter
- **Audit interne** : `MAXIA V12/AUDIT_COMPLET_V12.md` (27 mars 2026) — score santé 58/100, **6 vulnérabilités CRITIQUES, 14 hautes, 26 moyennes**
- **Plan d'action interne** : `MAXIA V12/PLAN_ACTION_V12.md`
- **SDK Python** : publié sur PyPI sous `maxia` (https://pypi.org/project/maxia/)
- **Smart contracts** : Solana mainnet (`8ADNmAPDxuRvJPBp8dL9rq5jpcGtqAEx4JyZd1rXwBUY`) + Base mainnet (`0xBd31bB973183F8476d0C4cF57a92e648b130510C`) — **NE PAS TOUCHER**, scope régulé

### 2.2 Vulnérabilités critiques de MAXIA V12 à vérifier sur les modules extraits

| Code | Description | Concerne MAXIA Oracle ? |
|---|---|---|
| C1 | HMAC hardcodé `maxia-credit-2026` dans `agent_credit_score.py:21` | Probablement non (credit score ≠ oracle) — à vérifier |
| C2 | Endpoint GPU public sans auth `/api/public/gpu/rent` | Non (pas de GPU dans Oracle) |
| C3 | Admin key dans URL query parameter `main.py:1443` | À vérifier sur les routes oracle si elles ont un mode admin |
| C4 | `ESCROW_PRIVKEY_B58` en `.env` sans KMS | Non (pas d'escrow dans Oracle) |
| C5 | Secrets sans validation startup | **OUI** — appliquer validation stricte sur les secrets MAXIA Oracle |
| C6 | JWT_SECRET aléatoire = sessions perdues au restart | **OUI** — appliquer JWT_SECRET persistant |

Les **14 vulnérabilités hautes** seront auditées sur chaque module extrait (cf. Phase 2 ci-dessous).

### 2.3 Modules réutilisables pour MAXIA Oracle (verts)

**Stack oracle** (cœur du produit) :

| Fichier MAXIA V12 | Rôle | Notes |
|---|---|---|
| `backend/trading/pyth_oracle.py` | Pyth Hermes SSE persistent stream + HTTP | 11 equity + 7 crypto feeds, latence <1s, dual-tier staleness |
| `backend/trading/chainlink_oracle.py` | Chainlink on-chain Base mainnet | eth_call AggregatorV3, ETH/BTC/USDC |
| `backend/trading/price_oracle.py` | CoinGecko + Yahoo + Helius | Cache 5s normal / 1s HFT, circuit breaker, age spread |

**Fonctionnalités déjà implémentées dans ces modules** :
- Cache 5s normal / 1s HFT
- Circuit breaker per-source (CLOSED → OPEN → HALF_OPEN)
- Confidence enforcement : Pyth >2% = trade BLOCKED
- Cross-verify Chainlink before swap
- Auto-refresh fallback prices every 30min
- Monitoring P50/P95/P99 latency
- Specs endpoint

**Distribution agent** :

| Fichier MAXIA V12 | Rôle | Notes |
|---|---|---|
| `backend/marketplace/mcp_server.py` | MCP server avec 46 tools | À filtrer aux ~10 outils oracle uniquement |
| `backend/integrations/x402_middleware.py` | x402 V2 micropaiements | À adapter en mode "vente directe" pour rester non régulé |
| `backend/integrations/l402_middleware.py` | Lightning micropayments | Optionnel, même règle que x402 |
| `backend/core/intent.py` | AIP Protocol v0.3.0 | Signed intent envelopes ed25519, anti-replay nonce |

**Identité agent** :

| Fichier MAXIA V12 | Rôle |
|---|---|
| `backend/core/agent_permissions.py` | DID (W3C) + UAID (HCS-14) + ed25519 keypair, 18 OAuth scopes |
| `backend/core/auth.py` | JWT auth, `require_auth`, `require_agent_sig_auth` (ed25519 DID) |

**SDK + plugins déjà publiés** :

| Repo / package | État |
|---|---|
| `maxia-sdk/` (PyPI `maxia`) | Publié, 30 méthodes core dont `m.prices()`, `m.price(symbol)`, `m.price_monitoring()` |
| `maxia-ts-sdk/` | Existe, à vérifier publication npm |
| `langchain-maxia` | Plugin LangChain, 10 tools |
| `crewai-tools-maxia` | Plugin CrewAI, 10 tools |
| `autogen-maxia` | Plugin Microsoft AutoGen |
| `composio-maxia` | Plugin Composio |
| `google-adk-maxia` | Plugin Google Agent Development Kit |
| `llama-index-maxia` + `llama-index-tools-maxia` | Plugin LlamaIndex |
| `eliza-plugin-maxia` (TS/JS) | Plugin ElizaOS (framework agent crypto/web3 a16z) |
| `vercel-skill-maxia` | Plugin Vercel AI SDK |

### 2.4 Modules à NE PAS extraire (rouges — régulés)

| Fichier MAXIA V12 | Raison |
|---|---|
| `backend/blockchain/escrow_client.py` + `base_escrow_client.py` | Custody = MSB / VASP probable |
| `backend/marketplace/public_api.py` (parties marketplace) | Marketplace intermédiaire = MSB |
| `backend/marketplace/marketplace_features.py` | Idem |
| `backend/trading/tokenized_stocks.py` | Securities (SEC, MiCA) |
| `backend/trading/crypto_swap.py` + `evm_swap.py` | Swap-as-a-service avec commission = MSB selon implémentation |
| `backend/features/streaming_payments.py` | Pay-per-second intermédiaire = MSB |
| `backend/billing/prepaid_credits.py` | Tenir des soldes USDC clients = custodial |
| `backend/integrations/fiat_onramp.py` | Fiat on/off-ramp = EMI obligatoire |
| `backend/trading/dca_bot.py`, `grid_bot.py`, `token_sniper.py`, `trading_features.py` | Trading bots = investment service |
| `backend/trading/yield_aggregator.py`, `solana_defi.py` | DeFi aggregation présenté comme conseil = CIF en France |

---

## 3. Plan d'extraction — 9 phases, checkpoints à chaque phase

**Principe directeur** : extraction propre sans casser MAXIA V12 (qui est hors ligne mais conservée pour archive). Tout ce qui est extrait est COPIÉ, jamais MOVE. À chaque fin de phase, validation Alexis avant la suivante.

### Phase 0 — Préparation et nettoyage `oracleforge/` (1 jour)

**Objectif** : reset propre du dossier `oracleforge/` qui contient encore le code from-scratch du plan original.

| Tâche | Détail |
|---|---|
| Backup du code OracleForge actuel | Tag git `oracleforge-v0-archive` + tarball local |
| Décider quoi garder vs supprimer | Tests existants peuvent être gardés comme référence. Le reste sera remplacé |
| Nettoyer la structure | Préparer arborescence cible (cf. §4) |
| Documenter le pivot dans le README | "MAXIA Oracle — extracted from MAXIA V12" |

**🛑 Checkpoint 0** : Alexis valide que le code OracleForge from-scratch peut être archivé.

---

### Phase 1 — Extraction modules oracle (2 jours)

**Objectif** : copier les 3 modules oracle de MAXIA V12 vers `oracleforge/backend/services/oracle/`.

| Jour | Action |
|---|---|
| 1 | Copier `pyth_oracle.py`, `chainlink_oracle.py`, `price_oracle.py` depuis `MAXIA V12/backend/trading/` |
| 1 | Identifier toutes les dépendances (imports vers d'autres modules MAXIA V12) — list exhaustive |
| 1 | Copier les dépendances strictement nécessaires (http_client, error_utils, config oracle, models Pydantic prix) — **ne JAMAIS importer escrow, marketplace, securities** |
| 2 | Adapter les imports pour qu'ils pointent sur la nouvelle structure |
| 2 | Tester chaque module en isolation : `python -c "from services.oracle import pyth_oracle; ..."` |
| 2 | Test live sur un symbole majeur : BTC, ETH, SOL — vérifier que les 5 sources retournent un prix |

**🛑 Checkpoint 1** :
- ❓ Les 3 modules importent sans erreur ?
- ❓ Aucune dépendance vers les modules régulés (escrow, marketplace, stocks) ?
- ❓ Test live BTC/ETH/SOL passe sur les 5 sources ?

---

### Phase 2 — Audit sécurité sur les modules extraits (2 jours)

**Objectif** : vérifier que les vulnérabilités de l'audit MAXIA V12 (`AUDIT_COMPLET_V12.md`) ne sont pas héritées.

| Vulnérabilité MAXIA V12 | Action sur MAXIA Oracle |
|---|---|
| C1 (HMAC hardcodé) | Vérifier que les modules oracle n'ont pas de secret hardcodé |
| C5 (secrets sans validation startup) | **Appliquer** validation stricte au startup (raise si secret manquant) |
| C6 (JWT secret non persistant) | **Appliquer** JWT secret persistant en .env |
| H7 (rate limiting in-memory non persistent) | Implémenter rate limiting Redis ou DB-backed |
| H9 (pas de security headers) | Ajouter middleware CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| H11 (Swagger public) | `docs_url=None, redoc_url=None, openapi_url=None` en prod |
| H12 (`str(e)` exposé) | Implémenter `safe_error()` utility, jamais retourner `str(e)` au client |
| M1 (CSP meta tag) | N/A (pas de frontend en V1) |

**Délivrable** : `oracleforge/docs/security_audit_extraction.md` documentant chaque vulnérabilité MAXIA V12 et sa résolution dans MAXIA Oracle.

**🛑 Checkpoint 2** :
- ❓ Aucun secret hardcodé ?
- ❓ Validation startup en place pour tous les secrets critiques ?
- ❓ `safe_error()` utilisé partout ?
- ❓ Security headers configurés ?

---

### Phase 3 — API minimaliste FastAPI (2 jours)

**Objectif** : exposer les modules oracle via 5 endpoints propres + auth simple.

**Endpoints** :

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Statut backend + dépendances |
| GET | `/api/sources` | Liste des 5 sources et leur état (CB closed/open) |
| GET | `/api/price/{symbol}` | Prix multi-source + confidence score |
| POST | `/api/prices/batch` | Batch jusqu'à 50 symboles |
| GET | `/api/cache/stats` | Métriques cache + circuit breaker |
| GET | `/mcp/manifest` | MCP server manifest (Phase 5) |

**Auth** :
- Header `X-API-Key` simple
- Free tier : 100 req/jour (DB-backed counter, pas in-memory)
- Pas de KYC, pas d'inscription email, juste `POST /api/register` qui retourne une clé

**Disclaimer obligatoire** dans **chaque** réponse :
```json
{
  "data": { ... },
  "disclaimer": "Data feed only. Not investment advice. No custody. No KYC."
}
```

**🛑 Checkpoint 3** :
- ❓ Les 6 endpoints répondent correctement ?
- ❓ Auth API key fonctionne ?
- ❓ Disclaimer présent dans toutes les réponses ?
- ❓ Free tier 100/jour respecté ?

---

### Phase 4 — x402 middleware en mode vente directe (2 jours)

**Objectif** : extraire `x402_middleware.py` de MAXIA V12 et l'adapter pour rester strictement non régulé.

**Différence critique vs MAXIA V12** :
- ❌ MAXIA V12 utilisait x402 dans un contexte de marketplace AI-to-AI (intermédiation = MSB)
- ✅ MAXIA Oracle utilise x402 pour **vente directe** : l'agent paye 0.001 USDC sur **notre** wallet, on retourne **notre** donnée. **Aucune intermédiation, aucun escrow, aucune custody.**

**Documentation contractuelle (CGV) à rédiger en Phase 4** :
- Définir clairement "vente directe de données"
- Pas de remboursement (data feed)
- Pas de custody
- Pas de KYC
- Disclaimer "data only, no advice"

**🛑 Checkpoint 4** :
- ❓ Un agent peut payer 0.001 USDC en x402 et recevoir une donnée prix ?
- ❓ Les CGV sont rédigées et claires ?
- ❓ Aucun flux de fonds passe par MAXIA Oracle vers un tiers (vente directe pure) ?

---

### Phase 5 — MCP server filtré (1 jour)

**Objectif** : extraire `mcp_server.py` de MAXIA V12 et le filtrer aux ~10 outils oracle uniquement.

**Outils MCP à exposer** :
1. `get_price(symbol)`
2. `get_prices_batch(symbols)`
3. `get_sources_status()`
4. `get_cache_stats()`
5. `get_price_history(symbol, period)` (si data disponible)
6. `get_confidence(symbol)` (retourne le score multi-source)
7. `subscribe_price_stream(symbol)` (Pyth SSE wrap)
8. `list_supported_symbols()`
9. `get_chainlink_onchain(symbol)` (force on-chain Base)
10. `health_check()`

**Ne PAS exposer** : tous les outils marketplace, swap, escrow, stocks, GPU, DeFi yields, etc.

**Test** : connecter Claude Desktop ou Cursor au MCP server local et vérifier que les 10 outils apparaissent.

**🛑 Checkpoint 5** :
- ❓ MCP manifest accessible à `/mcp/manifest` ?
- ❓ Les 10 tools sont exposés et fonctionnent dans Claude Desktop ?
- ❓ Aucun tool régulé n'est exposé par accident ?

---

### Phase 6 — SDK + plugins frameworks (2 jours)

**Objectif** : créer un SDK MAXIA Oracle dérivé du SDK MAXIA existant, et adapter les plugins frameworks.

**Option A** : sous-package `maxia[oracle]` (extra) qui ne wrap que les méthodes oracle
**Option B** : nouveau package `maxia-oracle` totalement séparé sur PyPI

**Recommandation** : **Option B** (totalement séparé) pour isoler MAXIA Oracle de MAXIA V12 (qui contient des features régulées). Évite la confusion réglementaire.

**Nouveau package** : `maxia-oracle` sur PyPI
- Méthodes : `prices()`, `price(symbol)`, `prices_batch(symbols)`, `sources()`, `cache_stats()`, `register()`, `subscribe_stream(symbol)`
- Disclaimer dans la docstring de chaque méthode
- README clair "data feed for AI agents, no advice"

**Plugins frameworks adaptés** :
- `langchain-maxia-oracle` (sous-set des 10 tools de `langchain-maxia`)
- `crewai-tools-maxia-oracle`
- `autogen-maxia-oracle`
- `eliza-plugin-maxia-oracle` (npm)

**🛑 Checkpoint 6** :
- ❓ `pip install maxia-oracle` fonctionne ?
- ❓ Les plugins frameworks tournent dans LangChain, CrewAI, AutoGen, ElizaOS ?
- ❓ Les disclaimers sont présents partout ?

---

### Phase 7 — Deploy VPS (1 jour)

**Objectif** : déployer MAXIA Oracle sur le VPS OVH.

**Infra** :
- VPS : `ubuntu@maxiaworld.app` (146.59.237.43)
- **Port backend** : `8003` (réservé OracleForge dans CLAUDE.md)
- **Pas de dashboard en V1** (focus API, pas de frontend)
- systemd unit dédiée
- nginx vhost
- cert Let's Encrypt via webroot
- Domaine : **`oracle.maxiaworld.app`** (validé Alexis)

**Action Alexis (5 min)** :
- Ajouter record DNS OVH : `oracle.maxiaworld.app` → `146.59.237.43`

**🛑 Checkpoint 7** :
- ❓ `https://oracle.maxiaworld.app/health` répond OK ?
- ❓ Les 5 sources fonctionnent depuis le VPS (IPs prod différentes du local) ?
- ❓ systemd démarre proprement au reboot ?

---

### Phase 8 — Landing page minimaliste (1 jour)

**Objectif** : single page HTML/CSS qui présente MAXIA Oracle.

**Contenu** :
- Pitch en 1 phrase : "Multi-source price oracle for AI agents. Pay-per-call in stablecoin. No custody, no advice, just data."
- Liste des 5 endpoints avec exemple curl
- Lien `pip install maxia-oracle`
- Lien MCP manifest
- Liens plugins frameworks
- Pricing : Free 100 req/jour + x402 0.001 USDC/req
- **Disclaimers fermes** en footer : "Data feed only. Not investment advice. No KYC. No custody. Direct sale."
- Contact ceo@maxiaworld.app

**Pas de** : signup form complexe, dashboard, graphes, analytics user. Tout est via API.

**🛑 Checkpoint 8** :
- ❓ Landing page accessible à `oracle.maxiaworld.app` ?
- ❓ Disclaimer visible et clair ?
- ❓ 5 exemples curl fonctionnels ?

---

### Phase 9 — Distribution (3 jours)

**Objectif** : faire connaître MAXIA Oracle sans faire de promesses régulées.

**Canaux** :

| Canal | Action |
|---|---|
| **MCP marketplaces** | Soumettre à `mcpmarket.com`, `MCP-Hive`, `Glama` |
| **PyPI** | `pip install maxia-oracle` listé avec keywords AI agents, oracle, price feed, MCP, x402 |
| **npm** | Plugins ElizaOS et Vercel AI SDK |
| **GitHub** | Repo public OracleForge avec README pédagogique |
| **Twitter/X** | 3 threads : "extracted from MAXIA V12", "first oracle native MCP+x402", "free tier no KYC" |
| **Show HN** | "Show HN: MAXIA Oracle — multi-source price feed for AI agents, pay-per-call in USDC" |
| **Reddit** | r/MachineLearning, r/algotrading (sans présenter comme trading tool — comme data feed neutre) |
| **Discord** | Serveurs dev crypto+AI (ElizaOS, LangChain, CrewAI) |

**À NE PAS faire** :
- ❌ Présenter comme "trading bot" ou "investment tool"
- ❌ Promettre des rendements
- ❌ Garantir une fiabilité absolue (toujours dire "best-effort multi-source")
- ❌ Lister sur RapidAPI (mort en 2026)

**🛑 Checkpoint 9** :
- ❓ Au moins 3 marketplaces MCP listent MAXIA Oracle ?
- ❓ Premier user signup organique en moins de 7 jours ?
- ❓ Aucune mention "investment" dans le marketing ?

---

## 4. Arborescence cible `oracleforge/`

```
oracleforge/
├── backend/
│   ├── main.py                         # FastAPI app (~150 lignes)
│   ├── core/
│   │   ├── config.py                   # Validation startup secrets
│   │   ├── auth.py                     # API keys + ed25519 (extrait MAXIA)
│   │   ├── security.py                 # Security headers, safe_error
│   │   ├── http_client.py              # Extrait MAXIA
│   │   └── error_utils.py              # safe_error utility
│   ├── services/
│   │   └── oracle/
│   │       ├── pyth_oracle.py          # COPIÉ depuis MAXIA V12
│   │       ├── chainlink_oracle.py     # COPIÉ depuis MAXIA V12
│   │       ├── price_oracle.py         # COPIÉ depuis MAXIA V12
│   │       └── multi_source.py         # Wrapper unifié (existe-il déjà ?)
│   ├── api/
│   │   ├── routes_price.py             # /api/price, /api/prices/batch
│   │   ├── routes_sources.py           # /api/sources, /api/cache/stats
│   │   ├── routes_health.py            # /health
│   │   └── routes_register.py          # /api/register (free tier signup)
│   ├── mcp/
│   │   └── server.py                   # Extrait MAXIA, filtré 10 tools
│   ├── x402/
│   │   └── middleware.py               # Extrait MAXIA, mode vente directe
│   ├── tests/
│   │   ├── test_oracle_unit.py         # Tests existants à garder
│   │   ├── test_oracle_live.py         # NOUVEAU : tests live (manuel, pas CI)
│   │   ├── test_api.py                 # NOUVEAU : tests endpoints
│   │   └── test_security.py            # NOUVEAU : tests vulnérabilités
│   ├── requirements.txt
│   └── .env.example
├── deploy/
│   ├── systemd/
│   │   └── maxia-oracle.service
│   ├── nginx/
│   │   └── maxia-oracle.conf
│   └── deploy.sh                       # Idempotent, hérité du pattern GuardForge
├── landing/
│   ├── index.html                      # Single page
│   ├── style.css
│   └── examples/                       # curl, Python, JS, Go, PHP
├── sdk/
│   ├── python/                         # NOUVEAU package maxia-oracle (PyPI)
│   │   ├── pyproject.toml
│   │   └── src/maxia_oracle/
│   └── typescript/                     # NOUVEAU package @maxia/oracle (npm)
│       ├── package.json
│       └── src/
├── plugins/
│   ├── langchain-maxia-oracle/
│   ├── crewai-tools-maxia-oracle/
│   ├── autogen-maxia-oracle/
│   └── eliza-plugin-maxia-oracle/
├── docs/
│   ├── plan-maxia-oracle-2026-04-14.md # CE DOCUMENT
│   ├── security_audit_extraction.md    # Phase 2 délivrable
│   ├── source_audit.md                 # Phase 1 délivrable (audit live)
│   ├── API.md                          # OpenAPI human-readable
│   ├── CGV.md                          # Conditions générales vente directe
│   └── DISCLAIMER.md                   # "Data only, no advice"
└── README.md                           # "MAXIA Oracle — extracted from MAXIA V12"
```

---

## 5. Estimations totales — réalistes

| Phase | Durée |
|---|---|
| Phase 0 — Préparation | 1 jour |
| Phase 1 — Extraction modules | 2 jours |
| Phase 2 — Audit sécurité | 2 jours |
| Phase 3 — API FastAPI | 2 jours |
| Phase 4 — x402 vente directe | 2 jours |
| Phase 5 — MCP server filtré | 1 jour |
| Phase 6 — SDK + plugins | 2 jours |
| Phase 7 — Deploy VPS | 1 jour |
| Phase 8 — Landing page | 1 jour |
| Phase 9 — Distribution | 3 jours |
| **Total** | **17 jours actifs (~3-4 semaines)** |

**Compte sur 3-4 semaines, pas 6.** Gain massif vs plan original grâce à la réutilisation MAXIA V12.

---

## 6. Risques qui peuvent tuer ce plan

1. **Dépendances cachées dans les modules oracle MAXIA V12** : les modules `pyth_oracle.py`, `chainlink_oracle.py`, `price_oracle.py` peuvent importer 10-20 autres modules MAXIA V12 (config, models, db, etc.). L'extraction propre peut prendre 3-5 jours au lieu de 2. **Mitigation** : mapping complet des dépendances en début Phase 1, décision d'extraction granulaire.

2. **Vulnérabilités MAXIA V12 plus profondes que prévu** : si les modules oracle dépendent de `auth.py` qui contient C5/C6, il faut tout corriger. **Mitigation** : Phase 2 dédiée, ne pas couper les coins.

3. **x402 protocole pas mature** : le pattern "vente directe non régulée" en x402 n'est pas documenté formellement. Risque légal si interprétation extensive. **Mitigation** : disclaimers fermes, CGV claires, consultation avocat 1h recommandée.

4. **Aucune demande pour un oracle dédié AI agents** : on parie sur la convergence agents+crypto, mais elle peut prendre 6-12 mois à se matérialiser. **Mitigation** : Phase 9 distribution intensive, mesurer l'engagement réel en 14 jours, pivot rapide si signal nul.

5. **MAXIA V12 modules cassés** : MAXIA V12 a 6 vulnérabilités critiques + audit 58/100. Les modules oracle peuvent cacher des bugs non détectés (les tests MAXIA sont mockés). **Mitigation** : tests live obligatoires en Phase 1, ne pas faire confiance aux tests mockés.

6. **Concurrence cachée** : un autre projet peut faire pareil sans qu'on le sache (recherche web limitée). **Mitigation** : recherche concurrents complète en Phase 0 (avant de lancer).

---

## 7. Ce que Claude peut faire seul vs ce qu'Alexis doit faire

**Claude (autonome)** :
- Phase 0-6 entièrement (extraction, audit, code, tests, SDK, plugins)
- Phase 7 deploy (sauf record DNS)
- Phase 8 landing page
- Phase 9 marketing material rédigé

**Alexis (~2h actives sur 3-4 semaines)** :
- Ajouter record DNS `oracle.maxiaworld.app` chez OVH (5 min)
- Valider chaque checkpoint (9× 10 min)
- Décider si consultation avocat (~150€) avant Phase 9
- Poster sur Show HN, Twitter, Reddit (Phase 9, ~30 min/post)
- Décider en cas de pivot après Checkpoint 9

---

## 8. Notes pour la prochaine session Claude

**Lecture obligatoire AVANT toute action** :
1. Ce document (`oracleforge/docs/plan-maxia-oracle-2026-04-14.md`)
2. Mémoire `feedback_no_regulated_business.md` — **règle critique non négociable**
3. Mémoire `project_maxia_v12_audit.md` — inventaire MAXIA V12
4. Mémoire `feedback_never_lie.md` — auditer avant d'affirmer
5. CLAUDE.md du projet (`MAXIA Lab/CLAUDE.md`)
6. `MAXIA V12/AUDIT_COMPLET_V12.md` — vulnérabilités à vérifier sur l'extraction

**Règles d'or** :
- ❌ NE PAS extraire de MAXIA V12 les modules régulés (escrow, marketplace, stocks, swap, fiat onramp, prepaid credits)
- ❌ NE PAS présenter MAXIA Oracle comme un trading tool ou investment service
- ❌ NE PAS faire de marketing avant que les disclaimers et CGV soient en place
- ❌ NE PAS faire confiance aux tests mockés MAXIA V12 — toujours valider en live
- ✅ Toujours COPIER depuis MAXIA V12, jamais MOVE (MAXIA V12 doit rester intact comme archive)
- ✅ Toujours documenter chaque vulnérabilité MAXIA V12 vérifiée sur l'extraction
- ✅ Toujours appliquer disclaimer "data only, no advice" partout (responses API, SDK docstrings, README, landing)
- ✅ Toujours valider à chaque checkpoint avec Alexis avant de continuer
- ✅ Demander avis Alexis avant toute décision réglementaire ambiguë

**État au démarrage prochaine session** :
- ✅ Plan validé Alexis (5 points du plan original + nouveau pivot)
- ✅ MAXIA V12 hors ligne (donc on peut extraire sans casser la prod)
- ✅ Branding choisi : **"MAXIA Oracle"** (capitalise sur MAXIA)
- ✅ Domaine : `oracle.maxiaworld.app`
- ✅ Juridiction : France
- ✅ Pas d'avocat (consultation 150€ recommandée mais pas bloquante)
- ✅ Focus : **UN SEUL produit** (MAXIA Oracle), pas de Forge en parallèle
- 🟡 GuardForge reste OFFLINE (ne pas réveiller)
- 🟡 Autres briques MAXIA V12 réutilisables : archivées en mémoire `project_maxia_v12_reusable_bricks.md` pour future référence (pas de travail dessus maintenant)

**Première action prochaine session** : Phase 0 — backup oracleforge actuel + cartographier dépendances des 3 modules oracle dans MAXIA V12.

---

## 9. Rappel de scope — UN SEUL produit

Alexis a explicitement demandé : **focus 100% sur MAXIA Oracle**. Pas de :
- ❌ Pas de OracleForge from-scratch (abandonné)
- ❌ Pas d'observabilité agents IA (pas le bon moment)
- ❌ Pas de MCP gateway crypto (segment trop pris)
- ❌ Pas de stablecoin depeg dédié (Webacy occupe la niche)
- ❌ Pas de réveil GuardForge
- ❌ Pas de travail sur les autres Forges en parallèle (MissionForge, OutreachForge, AuthForge, LLMForge, ForgeSuite — tout pause)

**MAXIA Oracle, et rien d'autre, jusqu'au Checkpoint 9.**
