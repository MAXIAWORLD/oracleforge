# HANDOFF — BudgetForge TDD fix (25 avril 2026)

## État actuel

**BudgetForge live : https://llmbudget.maxiaworld.app**

## Ce qui a été fait cette session

| Tâche | Statut |
|---|---|
| Audit état tests BudgetForge (suite complète) | ✅ |
| Diagnostic test stale `test_audit2_phase_c.py::TestBudgetLockConcurrency` | ✅ |
| Fix test : `budget_usd=0.0001 → 0.0002` (stale depuis H2 fix) | ✅ GREEN |
| Confirmation `test_fix7_token_estimator.py` : 9/9 PASSED | ✅ |
| Suite complète en cours | ⏳ |

## Diagnostic test stale

**Cause** : `check_budget_model` inclut maintenant `est_cost` dans le check (fix H2).
Avec `budget=0.0001` et `compute_cost` patché à `0.00015` :
- `check_budget_model` : `used_usd = 0 + 0.00015 = 0.00015 > 0.0001` → 429 sur le 1er call.

**Fix** : `budget_usd=0.0002` → 1er call passe (`0.00015 < 0.0002`), 2ème bloqué (`0.00015 + 0.00015 = 0.0003 > 0.0002`).

## État distribution OracleForge (session précédente)

| Canal | Statut |
|---|---|
| GitHub `MAXIAWORLD/oracleforge` | ✅ public |
| Glama | ✅ approuvé |
| awesome-mcp-servers PR | ⏳ en attente merge |
| Landing `oracle.maxiaworld.app` | ✅ live |
| PyPI `maxia-oracle` | ✅ |
| npm `@maxia-marketplace/oracle` | ✅ |

## État BudgetForge — Reste à faire

| Priorité | Action | Owner |
|---|---|---|
| 🔴 BLOQUANT | Turnstile Cloudflare C2 : créer site → clés `.env` VPS | **Alexis** |
| 🟠 | Phase G dashboard : build + rsync | Claude |
| 🟡 | Commit fix test stale + commit 6 fixes encore-TDD | Claude |
| 🟡 | Deploy 6 fixes encore-TDD sur VPS | Claude |

## Prochaine action

1. Commit fix test stale
2. Run suite complète → si 0 échec, commit + deploy Phase G dashboard
