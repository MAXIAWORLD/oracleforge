# CLAUDE.md — MAXIA Lab

**Focus actuel : OracleForge.** Plan source de vérité : `oracleforge/docs/plan-2026-04-13.md`.

Les 5 autres produits Forge sont **en pause** (description complète : `docs/maxia-lab-overview-archive.md`). GuardForge est OFFLINE (https://guardforge.maxiaworld.app → 503), code conservé sur le VPS, voir `docs/guardforge-handover-2026-04-13.md`.

## Préférences user (Alexis) — CRITIQUES

- **`no code`** = NE PAS modifier de fichiers, donner uniquement des conseils
- **Langue** : Alexis parle français, répondre en français
- **Jamais hardcoder** de valeurs fausses
- **Backend + frontend ENSEMBLE** : jamais l'un sans l'autre
- **Zero fake UI** : jamais de feature UI sans backend fonctionnel
- **Auditer avant d'affirmer** (cf. mémoire `feedback_never_lie.md`)

## Routage modèles (obligatoire)

Tout appel `Agent` DOIT passer `model:` explicitement.
- `haiku` : lookups, grep, reads, fetches, status checks
- `sonnet` : implementation, refactor, tests, reviews
- `opus` : rare, archi ambiguë uniquement

## Token discipline

- **Début de session** : `/context-budget`
- **À 60% du contexte** : `/strategic-compact`

## Stack OracleForge

- **Backend** : Python 3.12 + FastAPI + httpx + SQLite (pas PostgreSQL)
- **Dashboard** : Next.js 16 + TypeScript + Tailwind + shadcn/ui + next-intl 15 langues
- **Tests** : pytest (22 tests passing, mock-only — voir plan Phase 1 pour tests live)
- **Deploy** : systemd + venv + nginx (pattern hérité de GuardForge)

## Ports VPS `ubuntu@maxiaworld.app` (146.59.237.43)

| Port | Service |
|---|---|
| 8000 | MAXIA backend (intact) |
| 8003 | OracleForge backend (futur) |
| 8004 | GuardForge backend (paused) |
| 3003 | GuardForge dashboard (paused) |
| 3004 | OracleForge dashboard (futur) |

## Conventions code

- Python : PEP 8, type hints, Pydantic V2
- TypeScript : strict mode, pas de `any`
- Immutability, fichiers <800 lignes, fonctions <50 lignes
- Erreurs gérées explicitement
- Commits conventionnels (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
- Tests : viser 80%+, TDD quand possible

## Notes pour la prochaine session Claude

- **Lire `oracleforge/docs/plan-2026-04-13.md` AVANT toute action sur `oracleforge/`**
- Ne pas démarrer Phase 1 OracleForge tant qu'Alexis n'a pas validé les 5 points du §7 du plan
- Ne pas réveiller GuardForge sans demande explicite
- Skills/agents/rules ont été élagués le 13 avril 2026 (voir `~/.claude/*.archive/` pour ce qui a été déplacé). Pour restaurer, voir `docs/harness-prune-2026-04-13.md`
