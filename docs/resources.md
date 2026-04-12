# Ressources & Templates — MAXIA Lab

Repos, boilerplates et librairies identifies lors du brainstorming (12 avril 2026).
A cloner/forker selon les besoins de chaque produit.

---

## FastAPI Boilerplates

| Repo | Stars | Utilite |
|---|---|---|
| [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate) | ~600+ | Async, Pydantic V2, SQLAlchemy 2.0, PostgreSQL, JWT, RBAC. Base solide. |
| [Official FastAPI project template](https://fastapi.tiangolo.com/project-generation/) | — | Template officiel minimaliste FastAPI + PostgreSQL + SQLAlchemy + JWT |
| [fast-saas.com](https://www.fast-saas.com/) | Premium ~$99 | SaaS complet avec Stripe, multi-tenant, email, CI/CD. Payant mais gain de temps. |

**Recommandation** : Partir de benavlabs/FastAPI-boilerplate pour la structure, adapter pour chaque produit.

---

## Next.js + shadcn/ui Dashboard Templates

| Repo | Stars | Utilite |
|---|---|---|
| [Kiranism/next-shadcn-dashboard-starter](https://github.com/Kiranism/next-shadcn-dashboard-starter) | **5800+** | Le meilleur. Production-ready, charts, tables, forms, feature-based folders. |
| [satnaing/shadcn-admin](https://github.com/satnaing/shadcn-admin) | — | Admin dashboard accessible, responsive. Alternative legere. |
| [Vercel Next.js + shadcn template](https://vercel.com/templates/next.js/next-js-and-shadcn-ui-admin-dashboard) | — | Template officiel Vercel, zero config. |

**Recommandation** : Forker Kiranism/next-shadcn-dashboard-starter comme base pour les 6 dashboards. Style Notion-like friendly deja en place.

---

## Full-Stack Monorepo (FastAPI + Next.js)

| Repo | Utilite |
|---|---|
| [vintasoftware/nextjs-fastapi-template](https://github.com/vintasoftware/nextjs-fastapi-template) | **TOP PICK.** Type-safe API→frontend via OpenAPI. Monorepo apps/api + apps/web. Auth integree. |
| [CibiAananth/fullstack-next-fastapi](https://github.com/CibiAananth/fullstack-next-fastapi) | Heavy-duty : Redis, Celery, RabbitMQ. Bon pour jobs background (email outreach). |
| [Vercel full-stack FastAPI template](https://vercel.com/templates/other/full-stack-fastapi-template-with-next-js) | Next.js 16 + FastAPI + shadcn/ui. 1-click deploy. |

**Recommandation** : Evaluer vintasoftware pour la type-safety. Si trop lourd, partir de 2 repos separes (FastAPI + Next.js dashboard).

---

## LemonSqueezy Integration

| Ressource | Utilite |
|---|---|
| [LemonSqueezy REST API docs](https://docs.lemonsqueezy.com/api) | API officielle — subscriptions, licence keys, webhooks, usage records |
| [wdonofrio/lemonsqueezy-py-api](https://github.com/wdonofrio/lemonsqueezy-py-api) | SDK Python non-officiel. Wrapper REST. |

**Recommandation** : Utiliser l'API REST directe via `httpx` (leger). LemonSqueezy gere deja les licence keys nativement — pas besoin d'un systeme separe au debut.

---

## Systeme de licence (phone-home)

| Outil | Type | Utilite |
|---|---|---|
| [keygen-sh/keygen-api](https://github.com/keygen-sh/keygen-api) | Self-hosted (Fair Source) | License keys + validation offline + device activation. Complet. |
| [Cryptolens Python SDK](https://github.com/Cryptolens/cryptolens-python) | SaaS + lib | Validation RSA leger. |
| LemonSqueezy built-in | SaaS | Licence keys natives dans LemonSqueezy. Suffisant pour V1. |

**Recommandation** : Commencer avec LemonSqueezy licence keys (zero infra supplementaire). Migrer vers Keygen CE si besoin de features avancees (offline, device binding).

---

## Composants UI additionnels

| Lib | Utilite |
|---|---|
| [shadcn/ui](https://ui.shadcn.com/) | Base — 50+ composants. Deja inclus. |
| [Sonner](https://sonner.emilkowal.ski/) | Toasts elegants |
| [TanStack React Table](https://tanstack.com/table/) | Tables de donnees avancees (tri, filtre, pagination) |
| [Recharts](https://recharts.org/) | Graphiques React |
| [react-hook-form](https://react-hook-form.com/) | Forms performants |
| [Zod](https://zod.dev/) | Validation schemas TypeScript |

**Recommandation** : shadcn/ui + Sonner + TanStack Table + Recharts. Pas plus — eviter le bloat.

---

## Skills Claude Code recommandes

### Backend (chaque session)
- `/fastapi-expert` — patterns FastAPI, performance, middleware
- `/python-patterns` — idiomes Python, organisation code
- `/python-review` — review PEP 8, type hints, securite
- `/database-optimizer` — requetes PostgreSQL, schemas
- `/api-design` — design REST endpoints pour RapidAPI

### Frontend (dashboards)
- `/frontend-design` — UI production-grade, shadcn/ui patterns
- `/frontend-patterns` — React/Next.js, state management

### Testing
- `/tdd` — TDD obligatoire, 80%+ coverage
- `/e2e` — Playwright pour parcours critiques
- `/webapp-testing` — tester les dashboards dans le navigateur

### Lancement
- `/launch-strategy` — go-to-market, timing, sequencing
- `/pricing-strategy` — tiers, psychologie prix, LemonSqueezy
- `/marketing-ideas` — tactiques croissance dev tools
- `/copywriting` — pages de vente LemonSqueezy
- `/seo-audit` — visibilite pre-lancement
- `/lead-magnets` — version gratuite comme aimant
- `/free-tool-strategy` — monetiser open-core
- `/signup-flow-cro` — optimiser inscription cloud
- `/onboarding-cro` — premiere experience utilisateur
- `/paywall-upgrade-cro` — conversion gratuit → payant
- `/email-sequence` — onboarding email, nurture, upsell bundle
- `/churn-prevention` — retention, save offers

### Qualite
- `/verify` — syntax, imports, secrets
- `/code-review` — qualite, patterns, bugs
- `/quality-gate` — avant release produit
- `/security-reviewer` — avant deploy cloud
- `/test-coverage` — verifier 80%+
