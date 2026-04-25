# HANDOFF — BudgetForge audit #6 (session 25 avril 2026)

## État : AUDIT #6 COMPLET ✅ — 4/4 findings résolus + 9 tests TDD verts

**URL prod** : https://llmbudget.maxiaworld.app  
**Dernier commit** : `584e84b` (audit6 — M1 M2 M3 L1)

## ACTION PROCHAINE SESSION

1. **Deploy prod** : tar+scp vers VPS port 8011 (backup timestampé OBLIGATOIRE avant)
2. `APP_ENV=production` et `STRIPE_WEBHOOK_SECRET` et `TURNSTILE_SECRET_KEY` configurés en prod
3. Tests pré-existants cassés (hors scope, ne pas toucher) :
   - `test_audit_a1_a5::TestA3ExceptTooLarge::test_network_error_propagates_not_swallowed`
   - `test_audit_b1_b6::TestB1::test_all_proxy_endpoints_have_rate_limit`
   - `test_audit_b1_b6::TestB5::test_set_budget_without_max_cost_returns_warning`
   - `test_audit3_phase_f::TestF2::test_stripe_webhook_duplicate_returns_ok` (fixture db_session manquante)
   - `test_autodowngrade::test_downgrade_applied_when_budget_80pct`
   - `test_budget_guard::TestAlertThreshold::test_zero_budget_threshold_check`
   - `test_webhook` × 4 (TestWebhookAlert)
   - `test_plan_enforcement` × 4
   - `test_per_call_cap_output` × 3
   - `test_pricing_configuration` × 3, `test_proxy::TestMistralProxy` × 2
   - `test_rate_limiting_global` × 4, `test_p1_security::test_production_both_set_starts_ok`

## Commits audit #6

| Commit | Contenu |
|---|---|
| `584e84b` | audit6 — M1 Turnstile, M2 TLS, M3 playground dead code, L1 409 name |

## Findings résolus

| ID | Sévérité | Fix |
|----|----------|-----|
| M1 | MEDIUM | `billing.py` — Turnstile sur `POST /api/checkout/free` (fail-closed prod) |
| M2 | MEDIUM | `alert_service.py` — `verify=False→True`, URL originale (TLS hostname valide) |
| M3 | MEDIUM | Suppression `playground/page.tsx` + `Playground.tsx` + CSS (`NEXT_PUBLIC` key) |
| L1 | LOW | `portal.py` 409 — retire le nom du projet du message d'erreur |

## Contamination test découverte et corrigée

`test_audit2_phase_d.py::test_sqlite_connection_has_wal_journal_mode` fait `importlib.reload(cfg_mod)` — après, `routes.billing.settings` et `routes.signup.settings` gardent une référence à l'ANCIEN objet settings. Les tests audit6 qui patchent `settings` doivent cibler `routes.billing.settings` / `routes.signup.settings` directement (pas `core.config.settings`).

## Tests mis à jour (H3 comportement changé)

- `test_audit5.py` H3 : `called_url == pinned_url` → `called_url == original_url`
- `test_encore_fix6_ssrf_pinning.py` : même changement + ajout test `verify=True`
- `test_audit6.py` : 9 tests TDD couvrent M1/M2/L1
