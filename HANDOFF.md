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

## Ce qui reste

### Bloc 6 — SDK PyPI (seul bloc ouvert)

Packager et publier sur PyPI :
- `budgetforge/sdk/budgetforge_sdk.py` → package `budgetforge`
- `budgetforge/langchain_budgetforge/` → package `langchain-budgetforge`

Étapes :
1. Créer `budgetforge/sdk/pyproject.toml` (hatchling ou setuptools)
2. `python -m build` → wheel + sdist
3. `twine upload dist/*` (compte PyPI requis — token dans `.env` ou env var `TWINE_PASSWORD`)
4. Même chose pour `langchain_budgetforge/`
5. Mettre à jour README + docs avec `pip install budgetforge`

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
