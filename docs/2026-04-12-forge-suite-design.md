# Forge Suite — Design Document

**Date** : 12 avril 2026
**Auteur** : Alexis (MAXIA Lab)
**Statut** : Validé en brainstorming
**Session** : Brainstorming no-code, design only

---

## Vision

MAXIA Lab est la marque chapeau d'une suite de 6 outils développeur vendus en SaaS (cloud) et self-hosted (one-time). Chaque outil est extrait et amélioré à partir de la codebase MAXIA V12 (713+ routes, 191 modules, 15 blockchains).

**Objectif** : Revenus récurrents mensuels via des outils standalone, sans exposition réglementaire MiCA/crypto.

**Modèle** : Cloud-first (revenu récurrent, protection contre la revente) + self-hosted premium (one-time, pour devs qui veulent le contrôle).

---

## Branding

| Élément | Nom | Statut |
|---|---|---|
| Marque chapeau | **MAXIA Lab** | Validé — marque existante réutilisée |
| Produit 1 | **MissionForge** | Vérifié disponible (PyPI, npm, GitHub) |
| Produit 2 | **OracleForge** | Vérifié disponible |
| Produit 3 | **GuardForge** | Vérifié disponible (.dev libre) |
| Produit 4 | **OutreachForge** | À vérifier |
| Produit 5 | **AuthForge** | À vérifier |
| Produit 6 | **LLMForge** | À vérifier |

**Identité** : "Forge" = on construit, on façonne, c'est solide et artisanal. Chaque produit porte "Forge" dans son nom. MAXIA Lab est le forgeron.

**Tagline suite** : "Autonomous AI agents with reliable data and built-in privacy"

---

## Les 6 produits

### 1. MissionForge — AI Agent Framework

**Fonction** : Agent autonome avec missions YAML, scheduler, RAG, LLM router multi-provider, dashboard interactif avec chat.

**Extrait de MAXIA** : `agents/scheduler.py`, `ai/llm_router.py`, `ceo_rag.py`, `ceo_vector_memory.py`, `rag_knowledge.py`, dashboard CEO localhost:8888.

**Concurrence** : Dify ($59-159/mois), CrewAI (gratuit mais complexe), n8n ($24-120/mois), LangChain (gratuit mais sur-ingéniéré).

**Différenciation** :
- "Agent autonome en 60 secondes" — `missionforge start` et ça tourne
- Missions définies en YAML (aucun concurrent ne fait ça aussi simplement)
- Dashboard web inclus avec chat (CrewAI et LangChain n'ont aucune UI)
- Multi-LLM transparent avec fallback automatique
- Observabilité intégrée (tokens, coût, succès/échec, latence)

**Améliorations prévues** :
- Dashboard Next.js + shadcn/ui style friendly/Notion
- Missions en YAML avec hot-reload
- CLI `missionforge init/start/stop/status`
- Observabilité (P50/P95 latence, coût par mission)
- Multi-LLM avec sélection par coût/latence/qualité

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Starter | $19/mois | 1 agent, 5 missions, chat, dashboard, 1000 calls LLM |
| Pro | $49/mois | Agents illimités, multi-users, mémoire 3 couches, observabilité, API REST, 10K calls |
| Agency | $99/mois | White-label, multi-tenant, licence multi-clients, support prioritaire |
| Self-hosted | $129 one-time | Code source, licence restrictive, clé licence phone-home |

---

### 2. OracleForge — Multi-Source Price Oracle

**Fonction** : Oracle de prix multi-source avec cross-vérification, confidence scoring, circuit breaker, mode HFT.

**Extrait de MAXIA** : `trading/price_oracle.py`, `trading/pyth_oracle.py`, `trading/chainlink_oracle.py`, config sources dans `core/config.py`.

**Concurrence** : CoinGecko ($129-499/mois), CoinMarketCap ($79-299/mois), CryptoCompare ($75-150/mois). Tous mono-source.

**Différenciation** :
- Cross-vérification multi-source avec score de confiance — unique sur le marché
- 5 sources (Pyth SSE, Chainlink on-chain, CoinGecko, Yahoo, Finnhub)
- Stocks + Crypto unifié (rare)
- Circuit breaker par source
- Anomaly detection quand les sources divergent

**Améliorations prévues** :
- Anomaly detection (divergence >X% entre sources)
- Historique de confiance par source
- Webhooks d'alerte (prix + confidence combinés)
- Latence affichée dans chaque réponse
- Dashboard sources avec status temps réel

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Free (RapidAPI) | $0 | 100 calls/jour, 1 source |
| Starter | $9/mois | Accès API, 1 source, basique |
| Pro | $29/mois | 5 sources, confidence scoring, HFT mode, 10K calls/jour |
| Enterprise | $79/mois | 100K calls/jour, webhooks alertes, SLA 99.9% |
| Self-hosted | $149 one-time | Code source complet |

**Double canal** : LemonSqueezy (kit) + RapidAPI (API hébergée).

---

### 3. GuardForge — PII & AI Safety Kit

**Fonction** : Détection PII, anonymisation, chiffrement vault AES-256, policy engine YAML, compliance report, LLM wrapper safe.

**Extrait de MAXIA** : `enterprise/pii_shield.py`, `enterprise/policy_engine.py`, `enterprise/vault.py`, `enterprise/compliance_report.py`, `core/security.py` (content safety).

**Concurrence** : Presidio (gratuit mais complexe), AWS Comprehend ($100-500/mois), Private AI ($1000+/mois), Nightfall ($5000+/an).

**Différenciation** :
- Trou béant dans le marché : rien entre le gratuit basique et le $1000+/mois enterprise
- Self-hosted complet (détect + anonymise + chiffre + compliance) à prix indie
- Policy engine en YAML (presets par industrie)
- LLM wrapper : filtre PII avant envoi au LLM, restaure après

**Améliorations prévues** :
- Détection multi-langue (FR, EN, ES, DE minimum)
- Mode dry-run (scanner avant anonymiser)
- Presets industrie (RGPD, HIPAA, PCI-DSS, FERPA)
- Audit trail exportable pour contrôles CNIL/DPO
- LLM wrapper safe (PII stripped avant envoi, restauré après)

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Starter | $29/mois | PII detect + anonymise, 10K docs/mois |
| Pro | $69/mois | + Policy YAML + Vault + compliance report + LLM wrapper, 100K docs |
| Enterprise | $149/mois | + Multi-langue + audit trail + white-label, 1M docs |
| Self-hosted | $149 one-time | Code source complet |

---

### 4. OutreachForge — Email Outreach Automation

**Fonction** : Automatisation email outreach avec scoring prospects IA, personnalisation LLM, multi-langue, ramp-up progressif.

**Extrait de MAXIA** : `local_ceo/sales/sales_agent.py`, `local_ceo/sales/email_manager.py`, `local_ceo/sales/lead_tier.py`, templates multi-langues.

**Concurrence** : Lemlist ($59-99/mois), Instantly ($37-97/mois), Apollo ($49-119/mois), Woodpecker ($29-59/mois).

**Différenciation** :
- Self-hosted (aucun concurrent ne l'offre)
- Scoring prospects par IA intégré
- Personnalisation LLM de chaque email automatiquement
- Multi-langue 13 langues natif

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Starter | $15/mois | 1 campagne, 100 emails/jour, 5 étapes, anti-bounce, tracking |
| Pro | $39/mois | Illimité, 500/jour, scoring IA, personnalisation LLM, A/B test, multi-langue |
| Enterprise | $69/mois | 2000/jour, multi-sender, warm-up, CRM basique, white-label, compliance |
| Self-hosted | $199 one-time | Code source complet |

---

### 5. AuthForge — Auth complète FastAPI

**Fonction** : Kit auth plug-and-play pour FastAPI — JWT, OAuth, 2FA, rôles, rate limiting, SSO enterprise, dashboard users.

**Extrait de MAXIA** : `core/auth.py`, `core/security.py`, `agents/agent_permissions.py`, `enterprise/enterprise_sso.py`.

**Concurrence** : Clerk ($25-99/mois), Auth0 ($23-240/mois), Supabase Auth ($25/mois couplé), Lucia (gratuit lib only).

**Différenciation** :
- Seul kit auth complet self-hosted avec dashboard pour Python/FastAPI
- Le monde Python est mal servi en auth clé-en-main
- `pip install authforge` → 3 lignes de code

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Starter | $9/mois | JWT, OAuth Google, rate limiting, dashboard, 500 users |
| Pro | $29/mois | Users illimités, multi-OAuth, 2FA, rôles, API keys, sessions |
| Enterprise | $49/mois | SSO OIDC/SAML, multi-tenant, audit trail, IP whitelist, white-label |
| Self-hosted | $149 one-time | Code source complet |

---

### 6. LLMForge — LLM Router Multi-Provider

**Fonction** : Router LLM intelligent — un endpoint, le router choisit le meilleur provider (coût, latence, dispo). Fallback automatique.

**Extrait de MAXIA** : `ai/llm_router.py`, `ai/llm_service.py`.

**Concurrence** : OpenRouter (marge 20%), LiteLLM (gratuit mais sans UI), Portkey ($0-99/mois SaaS), Martian (beta).

**Différenciation** :
- LiteLLM avec un dashboard — c'est le pitch en une phrase
- Self-hosted (vs OpenRouter/Portkey SaaS)
- Config providers en YAML (3 lignes pour ajouter un provider)
- Observabilité intégrée (coût, latence, taux erreur par provider)

**Tiers** :

| Plan | Prix Cloud | Features clés |
|---|---|---|
| Starter | $9/mois | 3 providers, fallback auto, dashboard, 1000 calls/jour |
| Pro | $19/mois | Illimité, 50K/jour, routing intelligent, cache, streaming, observabilité |
| Enterprise | $39/mois | 500K/jour, budget caps, A/B test modèles, audit trail, multi-tenant |
| Self-hosted | $99 one-time | Code source complet |

---

## Pricing consolidé

### Cloud (mensuel)

| Produit | Starter | Pro | Enterprise |
|---|---|---|---|
| MissionForge | $19/mois | $49/mois | $99/mois |
| OracleForge | $9/mois | $29/mois | $79/mois |
| GuardForge | $29/mois | $69/mois | $149/mois |
| OutreachForge | $15/mois | $39/mois | $69/mois |
| AuthForge | $9/mois | $29/mois | $49/mois |
| LLMForge | $9/mois | $19/mois | $39/mois |

### Bundles Cloud

| Bundle | Starter | Pro | Enterprise |
|---|---|---|---|
| Forge Suite (les 6) | $59/mois (~35% off) | $149/mois (~36% off) | $299/mois (~38% off) |

### Self-hosted (one-time)

| Produit | Prix |
|---|---|
| MissionForge | $129 |
| OracleForge | $149 |
| GuardForge | $149 |
| OutreachForge | $199 |
| AuthForge | $149 |
| LLMForge | $99 |
| **Bundle 6 produits** | **$599** (~33% off vs $874) |

---

## Modèle de distribution

### 3 colonnes

| | Cloud (principal) | Self-hosted (premium) |
|---|---|---|
| Cible | 90% des clients | 10% devs/entreprises |
| Paiement | Mensuel | One-time |
| Code source | Non | Oui (licence restrictive) |
| Hébergé par | MAXIA Lab (VPS) | Le client |
| Mises à jour | Automatiques | Manuelles (download) |
| Support | Email/Discord | Docs seulement |
| Protection revente | Impossible (c'est un service) | Licence + clé phone-home |

### Open-core (acquisition)

Version gratuite limitée sur GitHub pour chaque produit :
- Attire du trafic et des étoiles
- Fonctionne vraiment mais avec limites fortes
- Funnel vers le cloud payant

### Plateformes

- **LemonSqueezy** : Vente kits self-hosted + abonnements cloud (gère TVA mondiale)
- **RapidAPI** : OracleForge API (tier gratuit + payants)
- **GitHub** : Repos publics (versions gratuites limitées)

---

## Protection contre la revente

1. **Juridique** : Licence propriétaire — usage personnel/interne uniquement, revente interdite
2. **Technique** : Clé de licence + phone-home mensuel (1 clé = 1 installation)
3. **Stratégique** : Cloud à $19/mois tellement simple et pas cher qu'un revendeur ne peut pas rivaliser

---

## Stack technique

### Backend (tous les produits)
- Python 3.12 + FastAPI
- PostgreSQL (prod) / SQLite (dev)
- ChromaDB (RAG — MissionForge)

### Dashboard (tous les produits)
- Next.js + Tailwind CSS + shadcn/ui
- Recharts (graphiques)
- Style : friendly, accessible, Notion-like (fond clair, coins arrondis, icônes Lucide)
- Responsive mobile

### Infra
- VPS OVH existant (cloud instances)
- LemonSqueezy (billing)
- GitHub (code + CI)

---

## Synergies entre produits

```
MissionForge (l'agent)
    ├── utilise LLMForge (pour ses appels LLM)
    ├── utilise OracleForge (pour les données prix)
    ├── utilise GuardForge (pour protéger les données)
    ├── utilise OutreachForge (pour envoyer des emails)
    └── protégé par AuthForge (pour l'accès dashboard)
```

Les produits se détectent mutuellement quand installés ensemble et se connectent automatiquement.

---

## Calendrier de sortie

| Semaine | Livrable | Milestone |
|---|---|---|
| 1 | Fondations MAXIA Lab | Comptes LemonSqueezy/RapidAPI, GitHub org, structure dossiers, système licence |
| 2-5 | **MissionForge** | Extraction MAXIA, dashboard Next.js, CLI, version gratuite GitHub, page vente, articles Dev.to/Reddit |
| 6-8 | **OracleForge + LLMForge** | Extraction, dashboards, RapidAPI, LemonSqueezy |
| 9-11 | **GuardForge + AuthForge** | Extraction, améliorations (multi-langue, presets industrie), dashboards |
| 12-14 | **OutreachForge + Bundles** | Extraction, Forge Suite landing page, cross-sell automatique |

**Objectif mois 6** : $500-$1500/mois récurrent + $1000-$2000 one-time

---

## Stratégie d'acquisition (résumé)

1. **Repos GitHub publics** (version gratuite) → étoiles → trafic
2. **Articles techniques** Dev.to, Medium, Hashnode
3. **Reddit** r/Python, r/SideProject, r/selfhosted, r/LangChain
4. **RapidAPI** (OracleForge tier gratuit → funnel payant)
5. **Cross-sell** entre produits Forge (email 7 jours après achat)
6. **Démo live publique** (dashboard en lecture seule)

---

## Décisions actées

- Cloud-first, self-hosted = tier premium
- Pas d'exposition MiCA — les outils sont neutres
- MAXIA reste la marque globale, MAXIA Lab = la division outils
- MissionForge sort en premier (le plus unique, le plus visuel)
- LemonSqueezy pour la vente (0 frais fixe, gère TVA)
- Next.js + shadcn/ui pour tous les dashboards (cohérence)
- Style friendly/Notion (pas intimidant)

---

## Produits futurs (Tier B et C — à revisiter plus tard)

Idées brainstormées le 12 avril, non retenues dans la V1 mais disponibles pour extension future.

### Tier B — Bon potentiel, niche spécifique

| Produit | Basé sur (MAXIA) | Description | Concurrence |
|---|---|---|---|
| **ScraperForge** | `web_scraper.py`, `sentiment_analyzer.py` | Web scraping + analyse sentiment intégrée — scrape, nettoie, analyse, stocke | Apify $49/mois, ScrapingBee $49/mois |
| **VaultForge** | `vault.py`, `audit_trail.py` | Coffre-fort de secrets pour apps — AES-256, audit trail, rotation clés, API simple | HashiCorp Vault (complexe), Infisical $15/mois |
| **PricingForge** | `dynamic_pricing.py`, commissions `config.py` | Moteur pricing dynamique — tiers, commissions, règles, A/B test prix. Pour SaaS/marketplaces | Stigg $100+/mois |
| **EscrowForge** | `escrow_client.py`, `base_escrow_client.py`, smart contracts | Escrow as a service — paiement sécurisé tiers de confiance. ⚠️ Attention réglementation si crypto | Niche, peu de concurrence self-hosted |
| **SentinelForge** | `alerts.py`, `health_monitor.py`, `preflight.py`, `chain_resilience.py` | Monitoring & alertes APIs — health checks, circuit breaker, alertes multi-canal, dashboard uptime | BetterStack $29/mois, UptimeRobot $7/mois |
| **BotForge** | `discord_bot.py`, `telegram_bot.py`, `reddit_bot.py` | Framework multi-plateforme bots — un bot déployé sur Discord + Telegram + Reddit. Config unifiée | Peu de concurrence en multi-plateforme |
| **FlowForge** | `scheduler.py`, `swarm.py`, background tasks `main.py` | Orchestrateur workflows Python — jobs planifiés, dépendances, retry, observabilité | Prefect $150+/mois, Airflow (complexe) |

### Tier C — Idées neuves (pas dans MAXIA, à construire)

| Produit | Description | Concurrence |
|---|---|---|
| **FormForge** | Générateur formulaires intelligents — YAML → form → validation → webhook → stockage | Typeform $25/mois, Tally gratuit |
| **DocForge** | Documentation auto à partir du code — scanne, génère, met à jour | Mintlify $150/mois, ReadMe $99/mois |
| **InvoiceForge** | Facturation simple — PDF, suivi paiements, relances auto | Stripe Billing (complexe) |
| **CronForge** | Gestionnaire cron jobs avec UI — créer, monitorer, logs, alertes échec | Mergent $29/mois |

**Note** : Tous les noms ci-dessus sont provisoires et devront être vérifiés (disponibilité PyPI/npm/domaines) avant lancement.

---

## Risques identifiés

| Risque | Mitigation |
|---|---|
| Pas de trafic au lancement | Version gratuite GitHub + articles + Reddit |
| Concurrence open source gratuite | Dashboard + UX + intégration suite = valeur ajoutée |
| Maintenir 6 produits solo | Architecture partagée (même stack, même dashboard template) |
| VPS pas assez puissant pour multi-tenant | Scaler progressivement, commencer avec peu de clients cloud |
| Revente du code self-hosted | Licence restrictive + phone-home + cloud tellement pas cher que la revente n'est pas rentable |
