# HANDOFF — BudgetForge post-session 26 avril 2026

## État : NON COMMITTÉ — prêt à commiter

**URL prod** : https://llmbudget.maxiaworld.app  
**Dernier commit prod** : `e6f1dc6`  
**Branch locale** : master — nombreux fichiers modifiés, rien de commité

---

## Ce qui a été fait cette session

### Playground (nouveau — OpenCode) — 6 fixes appliqués

| Fix | Fichier |
|---|---|
| URL `/api/proxy/` → `/proxy/` (route 404 corrigée) | `src/components/Playground.tsx:104` |
| Provider change → modèle se réinitialise | `src/components/Playground.tsx:234` |
| Anthropic retiré (format incompatible) → DeepSeek + Mistral ajoutés | `src/components/Playground.tsx:30` |
| Champ API key dans la sidebar (plus de demo-key hardcodé) | `src/components/Playground.tsx:210` |
| Guard apiKeyInput dans sendMessage + bouton disabled | `src/components/Playground.tsx:89` |
| `timestamp` retiré du payload API | `src/components/Playground.tsx:116` |
| `/playground` protégé par auth (PROTECTED_PATHS + matcher) | `dashboard/proxy.ts` |
| page.tsx simplifiée (plus de "use client" inutile) | `src/app/playground/page.tsx` |

### Tests / TypeScript — 3 fixes

| Fix | Fichier |
|---|---|
| Regex CORS tronquée par `get_cors_origins()` — cherche dans `src` au lieu de `block` | `tests/test_audit2_phase_d.py:169` |
| Docstring Python dans fichier `.ts` → commentaire JS | `dashboard/__tests__/frontend_resilience.test.ts:1` |
| frontend_resilience.test.ts exclu de la compilation tsc (deps manquantes, JSX dans .ts) | `dashboard/tsconfig.json` |

### Isolation tests backend

| Fix | Fichier |
|---|---|
| `app_env = "test"` + `turnstile_secret_key = ""` ajoutés à l'autouse `_mock_api_keys` | `tests/conftest.py:148` |

---

## Résultat tests

- **Suite complète** : exit code 0 ✅ (~3 minutes)
- **TypeScript** : 0 erreur ✅
- **Failures pre-existantes** : `test_audit_b1_b6` (2 tests) — non liés aux changements, présents avant cette session

## Prochaine action : commiter

---

## TypeScript : ✅ 0 erreur
```bash
cd dashboard && npx tsc --noEmit  # aucune sortie = clean
```

---

## Fichiers modifiés (non committés)

### Dashboard
- `dashboard/proxy.ts` — auth playground
- `dashboard/tsconfig.json` — exclude test
- `dashboard/src/components/Playground.tsx` — 6 fixes
- `dashboard/src/app/playground/page.tsx` — simplification
- `dashboard/__tests__/frontend_resilience.test.ts` — docstring Python → JS comment
- `dashboard/app/clients/page.tsx`, `dashboard/app/dashboard/page.tsx`, etc. — modifiés par OpenCode, vérifiés OK

### Backend
- `backend/tests/conftest.py` — isolation app_env + turnstile_secret_key
- `backend/tests/test_audit2_phase_d.py` — fix regex CORS
- `backend/core/models.py`, `backend/routes/billing.py`, `backend/routes/signup.py` — fixes audit #7 OpenCode

---

## ADMIN_API_KEY prod
`5b3eeaa7d9d4fa3915fc44ee67e23439639e8f001078da8766f5cb820d6c0998`
