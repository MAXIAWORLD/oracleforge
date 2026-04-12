# MAXIA Lab

Suite de 6 outils developpeur — "Forge Suite"

## Produits

| Produit | Dossier | Description |
|---|---|---|
| MissionForge | `missionforge/` | AI Agent Framework — missions YAML, LLM router, RAG, dashboard |
| OracleForge | `oracleforge/` | Multi-Source Price Oracle — 5 sources, confidence scoring |
| GuardForge | `guardforge/` | PII & AI Safety Kit — anonymisation, vault, compliance |
| OutreachForge | `outreachforge/` | Email Outreach Automation — scoring IA, multi-langue |
| AuthForge | `authforge/` | Auth complete FastAPI — JWT, OAuth, 2FA, SSO |
| LLMForge | `llmforge/` | LLM Router Multi-Provider — fallback auto, observabilite |

## Design

Voir `docs/2026-04-12-forge-suite-design.md` pour le design complet.

## Stack

- Backend : Python 3.12 + FastAPI
- Dashboard : Next.js + Tailwind + shadcn/ui
- DB : PostgreSQL (prod) / SQLite (dev)
- Vente : LemonSqueezy + RapidAPI

## Calendrier

- Semaines 1 : Fondations
- Semaines 2-5 : MissionForge
- Semaines 6-8 : OracleForge + LLMForge
- Semaines 9-11 : GuardForge + AuthForge
- Semaines 12-14 : OutreachForge + Bundles
