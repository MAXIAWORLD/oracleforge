# HANDOFF — BudgetForge post-session 27 avril 2026

## État prod : DÉPLOYÉ — commits `3518c82` + `687b847`

**URL prod** : https://llmbudget.maxiaworld.app  
**Health** : `{"status":"ok"}` ✅  
**DB** : restaurée depuis backup (corrompue pendant session, restaurée avant fin)

---

## Ce qui a été fait cette session

### Deploy
- Commit `3518c82` : playground fixes + test isolation + audit #4 B2-B8 backend
- Commit `687b847` : migration Alembic merge dual heads (`b3_owner_email` + `e3_signup_attempts_email`)
- DB SQLite prod corrompue → restaurée depuis `/opt/budgetforge.bak-20260427-093340`
- Migrations re-appliquées : `e3_signup_attempts_email` + `975c3fce2c49_merge_dual_heads`
- Build Next.js OK (21 pages) — services `active`

### Audit #8 (Opus 4.7 — Trail of Bits methodology)
Audit complet réalisé en session. 7 findings :

| # | Sévérité | Titre | État |
|---|---|---|---|
| X1 | CRITICAL | DB SQLite prod corrompue | **RÉSOLU** |
| X2 | HIGH | Webhook Stripe email non normalisé | À corriger (plan A1) |
| X3 | HIGH | `/webhook/stripe` payload illimité | À corriger (plan A3) |
| X4 | HIGH | Magic-link token en query string | À corriger (plan A4) |
| X5 | MEDIUM | Downgrade ne révoque pas les projets excédentaires | À corriger (plan A2) |
| X6 | MEDIUM | Admin key en localStorage | À corriger (plan C1) |
| X8 | LOW | Cookie `bf_session` sans flag Secure | À corriger (plan B1) |

### Plan écrit
`budgetforge/docs/superpowers/plans/2026-04-27-audit8-fixes.md`

3 blocs :
- **BLOC A** (bloquants mise en vente) : A1/A2/A3/A4 — X2/X5/X3/X4
- **BLOC B** (effort ≤ 2) : B1→B8 — X8 + 7 findings audit #4 restants (H26/M01/M02/M03/M04/M10/M11)
- **BLOC C** (session dédiée post-launch) : X6/H19/H20/H22/M08/M09

---

## Pourquoi la DB était corrompue

La DB prod (`budgetforge.db`) s'est corrompue après le premier deploy du jour (tar+ssh). La cause probable est un checkpoint WAL incomplet pendant le restart des services. La DB de backup (`/opt/budgetforge.bak-20260427-093340`) était saine (integrity_check = ok). Données perdues : 0 (la DB ne contenait que 2 projets de test et 0 usages réels).

**Prévention future :** Avant restart, faire `sqlite3 budgetforge.db "PRAGMA wal_checkpoint(TRUNCATE);"` pour vider le WAL proprement.

---

## Pourquoi le deploy est complexe (Alembic dual heads)

La migration `e3_signup_attempts_email` a été créée avec `down_revision = "daaa6555f2ce"` (22 avril) alors que la tête réelle était `b3_owner_email` (25 avril). Résultat : 2 branches parallèles. Fix : migration de merge `975c3fce2c49_merge_dual_heads` créée et committée.

**Ne plus jamais créer de migration sans vérifier `alembic heads` d'abord.**

---

## Prochaine session — actions immédiates

1. **Exécuter le plan `2026-04-27-audit8-fixes.md`** : Bloc A en priorité (A1→A4)
2. Lire le plan : `budgetforge/docs/superpowers/plans/2026-04-27-audit8-fixes.md`
3. Commencer par Task A1 (2 lignes, `billing.py:114`) — le plus rapide et le plus impactant
4. Deploy après Bloc A complet, puis Bloc B, puis deploy final

## Verdict audit #8

**PRÊT AVEC RÉSERVES** — X1 résolu, X2+X5 à corriger avant premier client payant.

---

## Commits de cette session

```
687b847  fix(alembic): merge dual heads b3_owner_email + e3_signup_attempts_email
3518c82  fix(budgetforge): playground fixes, test isolation, audit #4 backend corrections
```

## Backup VPS actuel
`/opt/budgetforge.bak-20260427-093340` — sain, 124K

## ADMIN_API_KEY prod
`5b3eeaa7d9d4fa3915fc44ee67e23439639e8f001078da8766f5cb820d6c0998`
