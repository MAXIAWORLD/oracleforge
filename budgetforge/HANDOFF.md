# HANDOFF — BudgetForge
**Date** : 2026-04-24 (session audit #3 — corrections F→I)
**Branche** : master

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

## Prochaine action session suivante

1. Récupérer clés Turnstile de Alexis → configurer `.env` VPS
2. `npm run build` dashboard local + rsync vers VPS
3. Restart `budgetforge-dashboard`
4. QA browser golden path
5. Lancer éventuellement un audit #4 pour valider l'ensemble
