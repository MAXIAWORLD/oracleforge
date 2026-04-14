# MAXIA Oracle

**Multi-source price data feed for AI agents.** Pay-per-call in USDC via x402.
No custody. No KYC. No investment advice. Just data.

> **Status — 14 avril 2026** : Phase 0 terminée (archivage du code OracleForge from-scratch, pivot validé). Phases 1 à 9 à exécuter selon le plan source de vérité.

## Plan source de vérité

**`docs/plan-maxia-oracle-2026-04-14.md`** — à lire intégralement avant toute action sur ce dossier.

Ce produit est extrait des modules oracle de MAXIA V12 (`C:/Users/Mini pc/Desktop/MAXIA V12/`), pas construit from-scratch. Le plan précédent (`docs/archive/plan-2026-04-13-OBSOLETE.md`) est archivé pour traçabilité et ne doit plus être suivi.

## Scope

| ✅ Dans le scope | ❌ Hors scope (régulé) |
|---|---|
| Multi-source price feed (Pyth, Chainlink, CoinGecko, Helius, Yahoo) | Custody, escrow, fonds clients |
| Batch API pour agents IA | Marketplace AI-to-AI intermédiaire |
| MCP server (10 tools oracle-only) | Tokenized securities, fiat onramp |
| Pay-per-call x402 en vente directe | Trading bots, signals, investment advice |
| SDK Python `maxia-oracle` + plugins frameworks | KYC utilisateurs |

## Composants cibles

| Composant | Statut | Destination |
|---|---|---|
| Backend FastAPI | Phase 1-3 | `backend/` (port 8003 dev, `oracle.maxiaworld.app` prod) |
| MCP server | Phase 5 | `backend/mcp/` (10 tools filtrés depuis les 46 de MAXIA V12) |
| x402 middleware | Phase 4 | `backend/x402/` (mode vente directe pure, extrait de MAXIA V12) |
| SDK Python `maxia-oracle` | Phase 6 | `sdk/python/` (nouveau package PyPI) |
| SDK TypeScript `@maxia/oracle` | Phase 6 | `sdk/typescript/` |
| Plugins frameworks | Phase 6 | `plugins/{langchain,crewai,autogen,llama-index}-maxia-oracle/` |
| Landing page statique | Phase 8 | `landing/` |
| Deploy systemd + nginx | Phase 7 | `deploy/` |

**Hors V1** : Eliza plugin, Vercel AI SDK plugin, dashboard frontend.

## Disclaimers obligatoires

- **Data feed only.** Not investment advice. Not a trading tool.
- **No custody.** Direct sale, no intermediation, no escrow.
- **No KYC.** Free tier without registration.
- **Best-effort multi-source.** No guarantee of uptime or accuracy.

## Archive

Le code OracleForge "from-scratch" (plan 13 avril) est préservé :
- Tag git : `oracleforge-v0-archive`
- Tarball : `C:/Users/Mini pc/Desktop/maxia-lab-backups/oracleforge-v0-2026-04-14.tar.gz`

Pour restaurer un fichier de l'archive : `git checkout oracleforge-v0-archive -- oracleforge/<chemin>`

## License

- **Backend** (`backend/`) : MAXIA Oracle Proprietary — voir `LICENSE`
- **SDK + plugins** (`sdk/`, `plugins/`) : MIT (à la publication, licenses dans chaque subdir)

Contact : contact@maxialab.com
