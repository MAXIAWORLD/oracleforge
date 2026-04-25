# HANDOFF — BudgetForge
**Date** : 2026-04-25 (session audit #7 — H2 budget défaut + M3 DoS email)
**Branche** : wip-snapshot-2026-04-25-pre-audit4 (les fixes sont non-commités)

## État actuel
Prod en ligne. **Audit #3 (QA Senior) — Phase F + H déployées backend. Phase G + H1 frontend + I1 frontend en code seulement (build en attente).**

## Audit #3 — bilan par phase

### Phase F (blockers sécu) — DÉPLOYÉE BACKEND ✅
| ID | Fix | Fichier |
|---|---|---|
| F1 | Timing attack admin key → `hmac.compare_digest` | `core/auth.py` |
| F2 | Stripe webhook idempotence → catch `IntegrityError` | `routes/billing.py` |
| F3 | Pré-billing overshoot → cap implicite = budget restant | `services/proxy_dispatcher.py` |
| F4 | DNS rebinding webhook → revalidation avant POST | `services/alert_service.py` |

### Phase G (UX frontend) — CODE SEULEMENT 🟡
| ID | Fix | Fichier |
|---|---|---|
| G1 | Double-clic Delete Project → `deletingId` state + disabled | `app/projects/page.tsx` |
| G2 | Backend offline → banner Retry, `fetchError` state | `app/dashboard/page.tsx` |
| G3 | Admin key missing → banner prominent | `app/settings/page.tsx` |
| G4 | Mobile chart <375px → padding adaptatif, YAxis compact | `app/dashboard/page.tsx` |

### Phase H (anti-abus + hardening) — DÉPLOYÉE BACKEND ✅ (H1 frontend en attente)
| ID | Fix | Fichier |
|---|---|---|
| H1 | Turnstile anti-bot (pass-through si pas de clé) | `core/config.py` + `routes/signup.py` + `main.py` + `components/free-signup-form.tsx` |
| H2 | Action block/downgrade immédiate (inclut est_cost) | `services/proxy_dispatcher.py` |
| H3 | Portal session cookie : valider `iat` | `routes/portal.py` |
| H4 | Rate limit par API key (fallback IP) | `core/limiter.py` |

### Phase I (polish) — CODE SEULEMENT 🟡
| ID | Fix | Fichier |
|---|---|---|
| I1 | Auto-reconcile après Stripe success (4 states) | `app/success/page.tsx` |
| I2 | HANDOFF + mémoire | Ce fichier + `memory/project_budgetforge_*` |

## Reste à faire

### 1. Turnstile (H1) — action Alexis
- Créer site https://dash.cloudflare.com → Turnstile → Add site → `llmbudget.maxiaworld.app`
- Récupérer Site Key + Secret Key
- Sur VPS :
  ```
  echo 'TURNSTILE_SECRET_KEY=xxx' >> /opt/budgetforge/backend/.env
  echo 'NEXT_PUBLIC_TURNSTILE_SITE_KEY=yyy' >> /opt/budgetforge/dashboard/.env.local
  sudo systemctl restart budgetforge-backend budgetforge-dashboard
  ```
- Actuellement : warning loggé en prod, signups fonctionnent sans captcha

### 2. Build + rsync dashboard (G + H1 + I1 frontend)
Fichiers modifiés dashboard :
- `app/projects/page.tsx`
- `app/dashboard/page.tsx`
- `app/settings/page.tsx`
- `app/success/page.tsx`
- `components/free-signup-form.tsx`

Commands :
```
cd budgetforge/dashboard && npm run build
rsync -avz --delete .next/ ubuntu@maxiaworld.app:/opt/budgetforge/dashboard/.next/
ssh ubuntu@maxiaworld.app "sudo systemctl restart budgetforge-dashboard"
```

### 3. QA browser (Bloc 7 original)
- Landing + FAQ + Stripe logo
- `/demo` + projets cliquables
- Stripe checkout test card `4242 4242 4242 4242`
- Portal magic link
- Mobile responsive <375px

## Décisions prises cette session

1. **Reduce uvicorn workers 2→1** pour corriger C5 (race budget lock multi-process sans Redis)
2. **Turnstile > Email verification** pour H1 (zero friction, industry standard)
3. **Turnstile fail-open** si pas de clé configurée (pour permettre déploiement progressif)
4. **Cap implicite = budget restant** pour F3 (plus restrictif que juste warning)

## Backups DB prod (24 avril 2026)
- `budgetforge.db.backup-20260424-164616` (pré-A1→B6)
- `budgetforge.db.backup-20260424-172540` (pré-F)
- `budgetforge.db.backup-20260424-*` (pré-H)

## Audit #7 — H2 + M3 (25 avril 2026) ✅

### H2 (BLOQUEUR) — budget_usd = 1.00 à la création
| Fichier | Changement |
|---|---|
| `core/models.py` | `SignupAttempt` : +colonne `email` (nullable, indexée) |
| `routes/signup.py` | `Project(..., budget_usd=1.00)` au signup free |
| `routes/billing.py` | `Project(..., budget_usd=1.00)` dans `_handle_checkout_completed` |

### M3 — Rate limit par email exact (3/jour) au lieu de domaine (10/jour)
| Fichier | Changement |
|---|---|
| `core/models.py` | +colonne `email` sur `SignupAttempt` |
| `routes/signup.py` | `_check_domain_rate_limit` → `_check_email_rate_limit` (filtre sur `email`, max=3) |
| `routes/signup.py` | `_record_signup_attempt` : +`email=email` dans le `SignupAttempt` |
| `tests/test_audit_b1_b6.py` | `test_same_domain_rate_limit_blocks_after_10` → `test_same_email_rate_limit_blocks_after_3` |

### Tests
- **11 nouveaux tests** : `tests/test_audit7_h2_m3.py` — **11/11 VERTS**
- Anciens concernés : 44 tests — **44/44 VERTS**
- 7 pre-existants en échec (`test_b4_budget`) : non causés par ces changements (confirmé)

### Note branche
Les fichiers modifiés sont non-commités sur `wip-snapshot-2026-04-25-pre-audit4`. À commiter avant deploy.

## Prochaine action session suivante

1. Commiter les fixes audit #7 :
   ```
   git add backend/core/models.py backend/routes/signup.py backend/routes/billing.py backend/tests/test_audit7_h2_m3.py backend/tests/test_audit_b1_b6.py
   git commit -m "fix(audit7): H2 budget_usd=1.00 défaut + M3 rate limit par email (11 tests TDD)"
   ```
2. Alembic migration pour colonne `email` sur `signup_attempts` (prod) :
   ```
   alembic revision --autogenerate -m "add email column to signup_attempts"
   alembic upgrade head
   ```
3. Récupérer clés Turnstile de Alexis → configurer `.env` VPS
4. `npm run build` dashboard + rsync VPS
