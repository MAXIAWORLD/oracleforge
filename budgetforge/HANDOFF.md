# HANDOFF — BudgetForge post-session 27 avril 2026 (Phase 0 distribution)

## État : CODE FREEZE — focus distribution

**URL prod** : https://llmbudget.maxiaworld.app
**Dernier commit local** : `97b69c5` (audit #8 Bloc C backend)
**Branch locale** : master
**Modifs non committées** : voir liste plus bas

---

## Verdict architecture (formalisé 27 avril)

**Plus d'audit jusqu'à 50 paying users ou bug bloquant rapporté par paying user.**

Référence mémoire : `project_budgetforge_ship_verdict.md`

Sur 8 audits, 95+ findings résolus. Le seul finding non bloquant restant est **M09 (LOW)** — date_from/to en UTC naive. Reporté.

L'effort va à la distribution, pas à la qualité du code.

---

## Ce qui a été ajouté dans cette session

| Item | Fichier(s) | Tests |
|---|---|---|
| **Loops audience sync** (push contact après signup) | `services/loops_sync.py` | 4/4 ✅ TDD |
| Settings `loops_api_key` | `core/config.py` | — |
| Wire signup → Loops fire-and-forget | `routes/signup.py` | — |
| Hero kicker "Beta · 50% lifetime for first 50 users" | `dashboard/app/page.tsx` | — |
| Sous-titre hero refait | `dashboard/app/page.tsx` | — |
| Pricing visible hero | `dashboard/app/page.tsx` | — |
| Email convention `ceo@` → `support@` | `dashboard/app/page.tsx`, `dashboard/app/docs/page.tsx` | — |
| Umami snippet (analytics auto-hébergé) | `dashboard/app/layout.tsx` | — |

Website ID Umami BudgetForge : `befd0e49-8570-4c0d-b420-66f4cebbfe3b`

---

## Sur le VPS

- `LOOPS_API_KEY` ajouté dans `/opt/budgetforge/backend/.env` (jamais committée localement)
- Backups timestampés conservés sur le VPS (`*.bak-loops-*`, `.bak-lot1-*`, `.bak-20260427-*`)
- Service `budgetforge-backend` redémarré, `is-active`
- Service `budgetforge-dashboard` rebuild + redémarré, `is-active`

---

## Coupon Stripe

- ID : `BETA50`
- 50% off, validité Permanente, max 50 redemptions
- Promotion code activé, code = `BETA50`

---

## Prochaines actions

1. **Commit + push** des modifs locales (voir liste ci-dessous)
2. **Phase 1 étape A** : submit BudgetForge sur 10 directories (Smithery, mcp.so, AI Tools List, Glama, etc.)
3. **Phase 1 étape B** : 3 articles SEO ciblés "openai cost limit", "claude api budget", "stop runaway llm bills"
4. **Phase 1 étape C** : submit AppSumo en lifetime deal
5. **Phase 1 étape D** : cold email FR agences IA via Lemlist

---

## Fichiers modifiés (à committer)

```
backend/services/loops_sync.py             (NEW)
backend/tests/test_loops_sync.py           (NEW)
backend/core/config.py                     (modified)
backend/routes/signup.py                   (modified)
dashboard/app/page.tsx                     (modified)
dashboard/app/docs/page.tsx                (modified)
dashboard/app/layout.tsx                   (modified — déjà fait Umami)
```

## Suggestion commit messages

```
feat(loops): sync signup emails to Loops.so audiences (TDD 4/4)
feat(landing): hero copy lot 1 — beta badge + clearer value prop + pricing visible
chore: ceo@ → support@ throughout dashboard
chore(analytics): umami self-hosted tracker (already deployed)
```

---

## ⚠️ Avant la prochaine session

- Vérifier que `support@maxiaworld.app` existe dans OVH Email Pro (sinon créer alias)
- Récupérer la stat Umami live → savoir si la landing convertit (visites / signups)
