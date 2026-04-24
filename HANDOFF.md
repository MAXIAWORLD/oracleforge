# HANDOFF — BudgetForge (24 avril 2026 — fin de session finition)

## État actuel

**BudgetForge vendable.** Prod live, tous les blocs sauf SDK PyPI terminés.

## Ce qui a été fait cette session

| Tâche | Statut |
|---|---|
| Fix A : test_alerts budget ($0.0001→$0.001, gpt-4o pricing) | ✅ |
| Fix B : token estimator conservative mode (`prebill` utilise ×2, min 512) | ✅ |
| Test cassé `test_audit2_phase_b` (stripe_webhook_secret manquant dans patch) | ✅ |
| Déploiement Fix A+B sur VPS (SCP + restart) | ✅ |
| Backup daily SQLite (`budgetforge-backup.timer`, 03h00 UTC, rétention 7j) | ✅ |
| QA golden path 28/28 ✓ en prod (`qa_golden_path.py` pointé sur prod) | ✅ |

## Commits de cette session

```
bedf731  fix(qa): point golden path at prod + fix strict-mode locators
1b977e4  fix(tests): add missing stripe_webhook_secret patch in test_startup_no_warning
3c98244  fix(budgetforge-backend): critique A+B — test_alerts budget + token estimator conservative
```

## Bloc 6 — SDK PyPI ✅ DONE

Packages publiés sur PyPI (version 0.1.1) :
- **`budgetforge`** → https://pypi.org/project/budgetforge/0.1.1/
- **`langchain-budgetforge`** → https://pypi.org/project/langchain-budgetforge/0.1.1/

Deliverables :
- Setup.py + métadonnées (author, classifiers, long_description)
- TDD integration tests (`test_sdk_integration.py`) — skipped sans `BF_TEST_API_KEY`
- Both packages ready for `pip install budgetforge`

## Ce qui reste

### Bloc 7 — QA golden path (seul bloc ouvert)

Vérification complète de la chaîne utilisateur (signup → intégration → upgrade) :
- Free signup → email reçu → clé reçu ✓
- Curl avec clé → usage visible dans portal ✓
- Alert : `alert_threshold_pct=1`, appel → email d'alerte reçu ✓
- Upgrade Pro → Stripe test → email → plan upgradé ✓
- Portal magic link → projets → usages ✓
- Admin `/clients` → stats cohérentes ✓
- Demo `/demo` → données + projets cliquables ✓
- Mobile responsive ✓
- Deploy final : rsync avec backup → service redémarre ✓

### Turnstile (action Alexis)

- Créer site sur https://dash.cloudflare.com → Turnstile
- Ajouter `TURNSTILE_SITE_KEY` dans dashboard `.env.local` (VPS)
- Ajouter `TURNSTILE_SECRET_KEY` dans backend `.env` (VPS)
- Sans ça : signups bloqués en mode fail-closed (pas de régression fonctionnelle, juste pas de nouveaux signups via landing)

## Infrastructure prod

| Item | État |
|---|---|
| Backend (port 8011) | ✅ actif |
| Dashboard (port 3011) | ✅ actif |
| SSL Let's Encrypt | ✅ expire 2026-07-20 |
| Backup daily SQLite | ✅ 03h00 UTC |
| ENV vars prod | ✅ sauf TURNSTILE |
| QA golden path | ✅ 28/28 |

## Prochaine action

Démarrer Bloc 6 — SDK PyPI. Vérifier si Alexis a un compte PyPI avant de commencer.
