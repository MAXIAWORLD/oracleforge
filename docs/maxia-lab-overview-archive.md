# CLAUDE.md — MAXIA Lab

**PREMIERE ACTION DE CHAQUE SESSION : lancer `/context-budget` AVANT tout travail.**
**A 60% du contexte : lancer `/strategic-compact`.**
**ROUTAGE MODELES (OBLIGATOIRE)** : tout appel au tool `Agent` DOIT passer `model:` explicitement. `haiku` pour lookups/grep/reads/fetches/status, `sonnet` pour implementation/refactor/tests/reviews, `opus` rare (archi ambigue uniquement).

## Project Overview

MAXIA Lab est la division outils de MAXIA. Suite de 6 produits developpeur vendus en SaaS (cloud mensuel) + self-hosted (one-time premium) via LemonSqueezy et RapidAPI.

**Design doc complet** : `docs/2026-04-12-forge-suite-design.md`

### Les 6 produits Forge

| Produit | Fonction | Dossier |
|---|---|---|
| **MissionForge** | AI Agent Framework — missions YAML, LLM router, RAG, dashboard + chat | `missionforge/` |
| **OracleForge** | Multi-Source Price Oracle — 5 sources, confidence scoring, circuit breaker | `oracleforge/` |
| **GuardForge** | PII & AI Safety Kit — anonymisation, vault AES-256, compliance, LLM wrapper | `guardforge/` |
| **OutreachForge** | Email Outreach Automation — scoring IA, personnalisation LLM, multi-langue | `outreachforge/` |
| **AuthForge** | Auth complete FastAPI — JWT, OAuth, 2FA, roles, SSO, dashboard users | `authforge/` |
| **LLMForge** | LLM Router Multi-Provider — fallback auto, routing intelligent, observabilite | `llmforge/` |

### Relation avec MAXIA V12

Les produits Forge sont **extraits et ameliores** depuis la codebase MAXIA V12 (`C:\Users\Mini pc\Desktop\MAXIA V12`). Chaque produit est standalone — zero dependance vers MAXIA V12 une fois extrait.

| Produit Forge | Source MAXIA V12 |
|---|---|
| MissionForge | `agents/scheduler.py`, `ai/llm_router.py`, `ceo_rag.py`, `ceo_vector_memory.py`, dashboard CEO |
| OracleForge | `trading/price_oracle.py`, `trading/pyth_oracle.py`, `trading/chainlink_oracle.py` |
| GuardForge | `enterprise/pii_shield.py`, `enterprise/policy_engine.py`, `enterprise/vault.py` |
| OutreachForge | `local_ceo/sales/sales_agent.py`, `local_ceo/sales/email_manager.py`, `local_ceo/sales/lead_tier.py` |
| AuthForge | `core/auth.py`, `core/security.py`, `agents/agent_permissions.py`, `enterprise/enterprise_sso.py` |
| LLMForge | `ai/llm_router.py`, `ai/llm_service.py` |

## Stack technique

### Backend (tous les produits)
- Python 3.12 + FastAPI
- PostgreSQL (prod) / SQLite (dev)
- ChromaDB (RAG — MissionForge uniquement)
- Pydantic V2 pour validation

### Frontend / Dashboards (tous les produits)
- Next.js (App Router)
- Tailwind CSS
- shadcn/ui (composants)
- Recharts (graphiques)
- Lucide Icons
- Style : **friendly, accessible, Notion-like** (fond clair, coins arrondis, pas intimidant)

### Infra
- VPS OVH (cloud instances)
- LemonSqueezy (billing, subscriptions, licence keys)
- RapidAPI (OracleForge API monetisee)
- GitHub org (repos publics = version gratuite limitee)

## Architecture par produit

Chaque produit suit la meme structure :
```
<produit>/
├── backend/
│   ├── main.py           # FastAPI entry point
│   ├── core/             # Config, auth, models
│   ├── services/         # Business logic
│   ├── routes/           # API endpoints
│   └── tests/            # pytest
├── dashboard/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # shadcn/ui components
│   └── lib/              # Utils, API client
├── docs/                 # Documentation utilisateur
├── docker-compose.yml    # Dev environment
├── README.md
└── LICENSE               # Proprietary license
```

## Commands

### Backend dev
```bash
cd <produit>/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Dashboard dev
```bash
cd <produit>/dashboard
npm install
npm run dev    # localhost:3000
```

## Conventions

### Code
- **Python** : PEP 8, type hints obligatoires, Pydantic V2 pour tous les modeles
- **TypeScript** : strict mode, pas de `any`
- **Immutability** : ne pas muter les objets, creer des copies
- **Fichiers** : 200-400 lignes typique, 800 max
- **Fonctions** : <50 lignes
- **Erreurs** : gerer explicitement, jamais silencieusement
- **Tests** : 80%+ coverage, TDD (RED → GREEN → REFACTOR)

### Git
- Conventional commits : `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Un commit par feature logique
- PR avec summary + test plan

### Naming
- Dossiers/fichiers : snake_case
- Classes Python : PascalCase
- Variables/fonctions : snake_case
- Composants React : PascalCase
- CSS classes : kebab-case (Tailwind)

## User Preferences (Alexis)

- **"no code"** = NE PAS modifier de fichiers. Donner uniquement des conseils.
- **Langue** : Alexis parle francais. Repondre en francais.
- **Jamais hardcoder** de valeurs fausses
- **Backend + frontend ENSEMBLE** : jamais l'un sans l'autre
- **Zero fake UI** : jamais de feature UI sans backend fonctionnel

## Modele commercial

- **Cloud-first** : SaaS mensuel = revenu recurrent principal + protection revente
- **Self-hosted** : one-time premium avec licence restrictive + phone-home
- **Open-core** : version gratuite GitHub limitee = acquisition clients
- **3 tiers** par produit : Starter / Pro / Enterprise
- **Bundles** : Forge Suite (6 produits) avec remise ~35%
- **Plateformes** : LemonSqueezy (vente + TVA) + RapidAPI (OracleForge API)

## Repos et templates de reference

Voir `docs/resources.md` pour la liste complete des boilerplates et templates recommandes.

## Skills utiles (auto-trigger)

### A chaque session
- `/context-budget` — debut de session
- `/verify` + `/code-review` + `/python-review` — apres chaque modification backend
- `/tdd` — pour chaque nouvelle feature

### Frontend
- `/frontend-design` — lors de la creation de dashboards

### Lancement produit
- `/launch-strategy` — planifier le go-to-market
- `/pricing-strategy` — valider/ajuster les tiers
- `/marketing-ideas` — strategies croissance
- `/seo-audit` — avant lancement public

### Qualite
- `/quality-gate` — avant de marquer un produit comme pret
- `/test-coverage` — verifier 80%+
- `/security-reviewer` — avant deploy cloud
