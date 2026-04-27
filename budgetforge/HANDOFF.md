# HANDOFF — BudgetForge post-session 27 avril 2026 (session 2)

## État prod : DÉPLOYÉ — audit #8 Blocs A+B complets

**URL prod** : https://llmbudget.maxiaworld.app  
**Health** : `{"status":"ok"}` ✅  
**DB** : saine, migrations à jour (`975c3fce2c49`)  
**Tests** : 31 tests audit8+effort2 verts. 1 échec pré-existant inter-modules (isolation, hors scope).

---

## Ce qui a été fait cette session

### Audit #8 — Blocs A + B (14 findings résolus)

| # | Sévérité | Titre | Commit |
|---|---|---|---|
| X2 | HIGH | Webhook email normalisé (lower + strip +tag) | `7307d27` |
| X5 | MEDIUM | Downgrade révoque TOUS les projets du customer | `61d4020` |
| X3 | HIGH | Webhook payload cap 100KB | `cab9de0` |
| X4 | HIGH | Magic-link token via hash fragment (+ dashboard) | `ce10e9c` |
| X8 | LOW | Cookie bf_session flag Secure en prod | `b724d37` |
| H26 | LOW | DynamicPricingManager.close() + shutdown lifespan | `7a5dfe7` + `123ba76` |
| M01 | LOW | _memory_locks cap FIFO 1000 entrées | `0b630aa` |
| M02 | LOW | CODE_PATTERNS regex compilées | `14c802f` |
| M03 | LOW | CRLF injection rejeté (portal + signup + alert subject) | `3ac742d` + `a3a8486` |
| M04 | LOW | portal_request constant-time (100ms floor) | `2dd8058` |
| M10 | LOW | /api/models stampede protection + cache résultat | `a3a8486` |
| M11 | LOW | billing_sync retourne 503 si Stripe non configuré | `07db5a4` |

### Fix migration Alembic
Chaîne linearisée : `e3` dépend de `e2`, `h6` dépend de `e3` (commit `356b33c`).  
Plus de dual heads — upgrade propre de `daaa6555f2ce` → `975c3fce2c49` en 16 étapes.

---

## Ce qui reste

### BLOC C — Session dédiée (ne pas mélanger avec du support client)

| Task | Finding | Description | Effort |
|---|---|---|---|
| C1 | X6 | Admin key → cookie httpOnly (breaking change dashboard) | 3-4h |
| C2 | H19 | Worker bloqué si client coupe avant finalize (`asyncio.shield`) | 2h |
| C3 | H20 | Timing attack API key lookup (`hmac.compare_digest`) | 1h |
| C4 | H22 | SQL quota par appel proxy (cache TTL 30s) | 2h |
| C5 | M08/M09 | History count lent (index) + dates naïves UTC | 2h |

**C1 est le plus impactant** — commencer par C1 en priorité.

---

## Prochaine session — première action

```
Lis HANDOFF.md et memory/project_budgetforge_audit8_plan.md.
Audit #8 Blocs A+B déployés. Prochain sprint : Bloc C (C1 = X6 admin httpOnly cookie).
```

Plan C1 détaillé dans `budgetforge/docs/superpowers/plans/2026-04-27-audit8-fixes.md` section "Task C1".

---

## Commits de cette session (chronologique)

```
7307d27  fix(billing): normalize Stripe webhook email — X2
61d4020  fix(billing): downgrade revokes all customer projects — X5
cab9de0  fix(billing): cap webhook payload at 100KB — X3
ce10e9c  fix(portal): magic-link token via hash fragment — X4
b724d37  fix(dashboard): Secure flag on bf_session cookie — X8
7a5dfe7  fix(dynamic_pricing): add close() + call in lifespan — H26
0b630aa  fix(lock): cap _memory_locks at 1000 entries — M01
14c802f  fix(estimator): pre-compile CODE_PATTERNS regex — M02
3ac742d  fix(portal,signup): reject emails containing CRLF — M03
2dd8058  fix(portal): constant-time response — M04
07db5a4  fix(admin): billing_sync returns 503 — M11
123ba76  fix(dynamic_pricing): sync close() + shutdown_pricing_manager() — H26
a3a8486  fix(portal,models,alert): CRLF subject + portal helper + stampede — M03/M04/M10
356b33c  fix(alembic): linearize migration chain e3→e2, h6→e3
```

## Backup VPS actuel
`/opt/budgetforge.bak-20260427-*` (créé avant deploy de cette session)

## ADMIN_API_KEY prod
`5b3eeaa7d9d4fa3915fc44ee67e23439639e8f001078da8766f5cb820d6c0998`
