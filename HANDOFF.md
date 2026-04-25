# HANDOFF — BudgetForge audit #4 (fin session 25 avril 2026)

## État : B0–B8 + C2 Turnstile DONE ✅ — 12 findings restants

**URL prod** : https://llmbudget.maxiaworld.app  
**Dernier commit** : `9ad359a` (B8 — H11 H12 H21 H23 M12)

## ACTION REQUISE AU DÉMARRAGE PROCHAINE SESSION

Le build Next.js était encore en cours à la fin de session. Exécuter :

```bash
ssh ubuntu@maxiaworld.app
# Vérifier que le build est fini :
pgrep -f 'next build' || echo "build done"
# Redémarrer le dashboard :
sudo systemctl restart budgetforge-dashboard
# Smoke test :
curl -s https://llmbudget.maxiaworld.app/health
```

## Commits audit #4

| Commit | Contenu |
|---|---|
| `491fc77` | B0 — nginx Stripe webhook |
| `c6bf05d` | B1.5 real client IP (deploy prod) |
| `88a8936` | B2–B7 — 44 tests TDD, 22 findings |
| `b30e629` | B1 — 33 tests TDD + source files |
| `51511b4` | HANDOFF mis à jour |
| `9ad359a` | B8 — H11 H12 H21 H23 M12 (19 tests) |

## Tests

- **Total tests verts** : 77 (backend) + suite complète ~200
- **Zéro régression** confirmée

## 12 findings restants (nouvelle session)

### Effort ≤ 2 — À faire en premier (7 items)

| ID | Sévérité | Fichier | Sujet |
|---|---|---|---|
| **H26** | HAUT | `services/dynamic_pricing.py:439-445` | Singleton sans `close()` au shutdown |
| **M01** | MOYEN | `distributed_budget_lock.py:102-103` | `_memory_locks` dict illimité |
| **M02** | MOYEN | `services/token_estimator.py:25-37` | `CODE_PATTERNS` regex unanchored |
| **M03** | MOYEN | `services/alert_service.py:137` | Email mailsplit via `\r\n` dans project_name |
| **M04** | MOYEN | `routes/portal.py:125-146` | Timing enum email portal_request |
| **M10** | MOYEN | `routes/models.py:368-403` | 9 requêtes outbound parallèles par cache miss |
| **M11** | MOYEN | `routes/admin.py:19-22` | `billing_sync` retourne HTTP 200 sur erreur |

### Effort 4 — Complexes (5 items)

| ID | Sévérité | Fichier | Sujet |
|---|---|---|---|
| **H19** | HAUT | `proxy_dispatcher.py` | Worker bloqué si client coupe avant finalize |
| **H20** | HAUT | `get_project_by_api_key` | Timing attack API key lookup |
| **H22** | HAUT | `services/plan_quota.py:50-62` | `check_quota` SQL par appel (perf) |
| **M08** | MOYEN | `routes/history.py:74-87` | History total count lent |
| **M09** | MOYEN | `routes/history.py:65-72` | date_from/to naive UTC |

## Documents de référence

- `budgetforge/docs/audit-qa-senior-2026-04-25.md` — 60 findings complets
- `budgetforge/docs/plan-correction-audit-2026-04-25.md` — plan 7 blocs

## Ce qui est DONE (résumé complet)

- **B0** Stripe webhook nginx
- **B1** Rate limit, /clients protégé, export, CORS, real IP, Turnstile
- **B2** Stripe upsert, subscription deleted, webhook HTTPS, reconcile env vars
- **B3** owner_email migration, multi-projet, POST /api/portal/projects
- **B4** budget=None→402, Redlock token, flock O_NOFOLLOW, streaming finalize, should_alert, token clamp
- **B5** AWS Bedrock Converse API, asyncio.to_thread, usage réel
- **B6** Cookie portal samesite=strict, API key masking, saveBudget warning
- **B7** Members escalation, SMTP IP, CSV injection, export streaming, retry backoff, session purge
- **B8** POST /api/portal/verify, cookie HttpOnly auth, atRisk counting, resend button, plan limits tests
- **C2** Turnstile configuré en prod
