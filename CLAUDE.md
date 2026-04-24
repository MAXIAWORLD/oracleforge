# CLAUDE.md — MAXIA Lab

**Focus actuel : Forge Suite.** OracleForge est en production. Prochain produit : **BudgetForge** (LLM Budget Guard). Plan Forge Suite : `memory/project_forge_suite_origin.md`.

MAXIA V12 est HORS LIGNE (archive). GuardForge est OFFLINE.

## Préférences user (Alexis) — CRITIQUES

- **Langue** : Alexis parle français, répondre en français
- **PAS de produit régulé** (MSB/VASP/MiCA/securities/custodial/marketplace intermédiaire) — cf. mémoire `feedback_no_regulated_business.md`

## Outils

- **TDD Guard** : framework `pytest` — setup : `/tdd-guard:setup` (à lancer une fois par forge)
- **Trail of Bits** : audit sécurité API + micropaiements x402 — `/trailofbits:audit` avant chaque deploy prod
- **claudekit** : `/checkpoint:create` avant refactor d'une forge entière

## Token discipline

- **Début de session** : `/context-budget`
- **À 60% du contexte** : `/strategic-compact`

## Stack MAXIA Oracle

- **Backend** : Python 3.12 + FastAPI + httpx + SQLite — **extrait de MAXIA V12**
- **Pas de dashboard en V1** (API + landing statique uniquement, focus distribution agent)
- **SDK** : `maxia-oracle` (Python PyPI, nouveau) + `@maxia/oracle` (npm, nouveau)
- **Plugins** : langchain-maxia-oracle, crewai-tools-maxia-oracle, autogen-maxia-oracle, eliza-plugin-maxia-oracle
- **MCP server** : 10 tools oracle-only (extraits des 46 de MAXIA V12)
- **Micropaiements** : x402 V2 en mode **vente directe** (pas d'intermédiation), extrait de MAXIA V12
- **Tests** : tests live obligatoires (les tests mockés MAXIA V12 ne suffisent pas)
- **Deploy** : systemd + venv + nginx

## Ports VPS `ubuntu@maxiaworld.app` (146.59.237.43)

| Port | Service                                      |
| ---- | -------------------------------------------- |
| 8000 | MAXIA V12 backend (HORS LIGNE, archive)      |
| 8003 | **MAXIA Oracle backend** (cible Phase 7)     |
| 8004 | GuardForge backend (OFFLINE)                 |
| 3003 | GuardForge dashboard (OFFLINE)               |
| 3004 | (libre, pas de dashboard MAXIA Oracle en V1) |

Domaine cible : **`oracle.maxiaworld.app`** (record DNS à créer Phase 7)

## Philosophie de travail — règles gstack

### Philosophie de base

Le but n'est jamais d'écrire du code. Le but est de livrer quelque chose qui résout un vrai problème pour un vrai utilisateur. Avant toute ligne de code : qu'est-ce qui casse pour l'utilisateur si on ne fait rien ? Si la réponse est floue, on ne commence pas. Le progrès se mesure en features livrées, pas en lignes de code.

### Protocole de confusion (règle dure)

Si Claude Code n'est pas sûr à 90 %, il demande, il ne devine pas.

- Architecture → demander
- Nom de fichier, chemin, convention → lire le repo
- Choix de librairie → 2-3 options avec trade-offs, l'humain tranche

### Le cycle obligatoire : Plan → Test → Build → Review → QA → Ship → Retro

1. **Office-Hours** (CEO) — reframer la demande, 6 questions forçantes, output = design doc court
2. **Plan** (Eng Manager) — verrouiller archi, flux de données, edge cases, lister les tests à écrire
3. **Test** — écrire les tests, vérifier qu'ils échouent pour les bonnes raisons
4. **Build** — implémenter exactement ce qu'il faut pour faire passer les tests, rien de plus
5. **Review** (Staff Engineer paranoïaque) — diff relu : prod breakage ? secrets commités ? coverage theater ?
6. **QA** — ouvrir le vrai produit, cliquer, tester les flows utilisateur réels, screenshots avant/après
7. **Ship** — PR propre, commit = une seule idée, WIP squashés
8. **Retro** — logger dans `learnings.md` du projet : erreurs CLI, fausses pistes, conventions implicites

### Règles de sécurité dures

Demander confirmation explicite avant : `rm -rf`, `git reset --hard`, `git push --force`, `DROP TABLE`, `DELETE FROM` sans filtre strict, toute instruction qui transfère des fonds ou credentials. Déploiement en prod = mode paranoïa avec double confirmation.

### Règles de communication

- Décrire l'approche en 2-3 phrases avant tout refactor/migration/feature non triviale
- Rapport de fin de session : livré, tests ajoutés, décisions prises, incertitudes, suite
- Pousser en retour si la demande semble fausse ou mal framée

### Apprentissage continu

À la fin de chaque session : logger dans `learnings.md` du projet les erreurs CLI, fausses pistes, quirks découverts, patterns de tests validés. Les sessions suivantes lisent ce fichier au démarrage.

### Meta-règle

Ces règles sont subordonnées au bon sens et à la demande explicite de l'utilisateur. Exception : TDD ne se contourne pas sans justification explicite (ex: "script jetable one-shot").

## Conventions code

- Python : PEP 8, type hints, Pydantic V2
- TypeScript : strict mode, pas de `any`

## Notes pour la prochaine session Claude

- **Lire `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` AVANT toute action sur `oracleforge/`**
- Le plan précédent `plan-2026-04-13.md` est OBSOLÈTE (remplacé)
- Mémoires critiques à charger :
  - `feedback_no_regulated_business.md` — règle produit non négociable
  - `project_maxia_v12_audit.md` — inventaire modules réutilisables
  - `project_maxia_v12_reusable_bricks.md` — inventaire complet vert/rouge
  - `project_maxia_oracle_focus.md` — focus actuel un seul produit
  - `feedback_never_lie.md` — auditer avant d'affirmer
- **Première action prochaine session** : Phase 0 — backup du code `oracleforge/` actuel (tag git `oracleforge-v0-archive`), puis cartographier les dépendances complètes des 3 modules oracle MAXIA V12 (`pyth_oracle.py`, `chainlink_oracle.py`, `price_oracle.py`) AVANT de commencer l'extraction
- MAXIA V12 est HORS LIGNE → extraction safe (copier jamais move, conserver intact comme archive)
- Ne pas réveiller GuardForge, MAXIA V12, ou les autres Forges sans demande explicite
- Skills/agents/rules élagués 13 avril 2026 (voir `~/.claude/*.archive/`). Pour restaurer, voir `docs/harness-prune-2026-04-13.md`
