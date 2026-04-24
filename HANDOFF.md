# HANDOFF — BudgetForge (24 avril 2026 — fin de session encore-TDD)

## État actuel

**Backend "encore" : 6/7 fixes livrés TDD.** Prod à jour sauf déploiement (commit git fait, SCP pas encore).

## Ce qui a été fait cette session

### TDD strict — 6 cycles RED→GREEN

| Fix | Fichier(s) | Tests | Statut |
|---|---|---|---|
| #1 Budget lock cross-process | `distributed_budget_lock.py` | 4 | ✅ GREEN |
| #2 Dynamic pricing bypass | `cost_calculator.py` | 6 | ✅ GREEN |
| #3 Azure OpenAI TypeError | `proxy_forwarder.py` | 6 | ✅ GREEN |
| #4 Reconcile idempotency + rate-limit | `billing.py` | 4 | ✅ GREEN |
| #5 Cancel/finalize commit résilient | `proxy_dispatcher.py` | 5 | ✅ GREEN |
| #6 SSRF webhook IP pinning | `url_validator.py` + `alert_service.py` | 4 | ✅ GREEN |

**29 nouveaux tests** dans `tests/test_encore_fix[1-6]_*.py` — tous verts.

### Détail des fixes

- **Fix #1** : `fallback_budget_lock` utilise `fcntl.flock` (Linux, cross-process) au lieu de `asyncio.Lock` (in-process seulement). Windows garde `asyncio.Lock`.
- **Fix #2** : `CostCalculator.get_price` priorité inversée — prix statiques `_PRICES` d'abord, dynamic pricing seulement pour modèles inconnus ET seulement si prix > 0.
- **Fix #3** : `forward_azure_openai` et `forward_azure_openai_stream` : `base_url` retiré des params, lit `settings.azure_openai_base_url` en interne, lève `HTTPException(400)` si non configuré.
- **Fix #4** : `reconcile_stripe_session` : `@limiter.limit("5/hour")` + `Request` param + idempotency via `StripeEvent(event_id=f"reconcile:{session_id}")` + rollback si Stripe error.
- **Fix #5** : `cancel_usage` et `finalize_usage` : `db.commit()` enrobé `try/except + db.rollback()` — plus de 500 sur SQLite lock.
- **Fix #6** : `alert_service.send_webhook` utilise `resolve_safe_host()` (nouveau dans `url_validator.py`) — DNS résolu une fois, IP pincée dans le POST, header `Host` preservé.

## Ce qui reste (encore plan non terminé)

### Token estimator (HAUT) — non fait
Problème : `estimate_output_tokens` = heuristique ×0.75. Client sans `max_tokens` sur un gros prompt → estimate=75 tokens, réel potentiellement 8000. Prebill sous-facture → finalize arrive après overshoot possible.
**Risque** : medium en pratique (2 workers, SQLite WAL, busy_timeout=30s absorbe une partie).
**À faire** : TDD — écrire test `check_per_call_cap must not reject small calls but prebill must use safe upper bound`, puis corriger l'estimateur.

### Test pré-existant cassé
`tests/test_alerts.py::TestAlertTriggered::test_alert_sent_when_threshold_crossed` — FAIL avant cette session. Probablement lié au même problème token estimator (check_per_call_cap rejette le call avant que maybe_send_alert soit atteint).

### Depuis le plan "encore" — non adressés (CRITIQUE, MOYEN)
- **CRITIQUE** : `admin_api_key=""` par défaut + pas de fail-fast si `.env` manquant en prod (déjà géré dans main.py lifespan mais à vérifier)
- **MOYEN** : `Usage.cost_usd` Float au lieu de Decimal
- **MOYEN** : Portal cookie HMAC non révocable
- **MOYEN** : Compteurs rate-limit per-worker × 2 non documenté

## Fichiers modifiés (non commités)

```
budgetforge/backend/services/distributed_budget_lock.py
budgetforge/backend/services/cost_calculator.py
budgetforge/backend/services/proxy_forwarder.py
budgetforge/backend/routes/billing.py
budgetforge/backend/services/proxy_dispatcher.py
budgetforge/backend/core/url_validator.py
budgetforge/backend/services/alert_service.py
budgetforge/backend/tests/test_encore_fix1_budget_lock.py  (nouveau)
budgetforge/backend/tests/test_encore_fix2_dynamic_pricing.py  (nouveau)
budgetforge/backend/tests/test_encore_fix3_azure_dispatch.py  (nouveau)
budgetforge/backend/tests/test_encore_fix4_reconcile.py  (nouveau)
budgetforge/backend/tests/test_encore_fix5_resilient_commit.py  (nouveau)
budgetforge/backend/tests/test_encore_fix6_ssrf_pinning.py  (nouveau)
```

## Prochaine action

1. `git commit` des 6 fixes + 6 fichiers de tests
2. Backup VPS : `ssh ubuntu@maxiaworld.app 'cp /opt/budgetforge/backend/budgetforge.db /opt/budgetforge/backend/budgetforge.db.bak.$(date +%Y%m%d_%H%M%S)'`
3. SCP des 7 fichiers modifiés vers VPS
4. `sudo systemctl restart budgetforge-backend`
5. Curl health + test webhook
6. Adresser token estimator (Fix manquant) — TDD obligatoire

## Infrastructure prod
- VPS : ubuntu@maxiaworld.app (146.59.237.43), port 8011
- Dashboard : port 3011
- SSL : Let's Encrypt, expire 2026-07-20
- Backup cron : 03h00 UTC ✅
- UptimeRobot : /health ✅
