# HANDOFF — BudgetForge audit #4 (25 avril 2026)

## État : B0–B7 DONE ✅ — Prêt pour deploy prod

**URL prod** : https://llmbudget.maxiaworld.app
**Dernier commit** : `b30e629` (B1 source files)

## Commits audit #4

| Commit | Contenu |
|---|---|
| `491fc77` | B0 — nginx Stripe webhook |
| `c6bf05d` | B1.5 real client IP (deploy prod) |
| `88a8936` | B2–B7 — 44 tests TDD, 22 findings |
| `b30e629` | B1 — 33 tests TDD + source files (omis) |

## Documents de référence

- `budgetforge/docs/audit-qa-senior-2026-04-25.md` — 60 findings + C23 infra
- `budgetforge/docs/plan-correction-audit-2026-04-25.md` — plan 7 blocs
- `budgetforge/docs/investigation-prod-2026-04-25.md` — état prod live confirmé

## Avancement — TOUT DONE

### ✅ B0 — INFRA Stripe webhook
- nginx `location = /webhook/stripe` → port 8011

### ✅ B1 — Stop-the-bleeding sécurité (33 tests)

| Sous-bloc | Audit ID | Résultat |
|---|---|---|
| B1.1 rate limit 9 endpoints | C01 | 30× 401 + 5× 429 ✅ |
| B1.2 `/clients` protected | C13 | 307 → /login ✅ |
| B1.3 export defense in depth | C17 | 401 sans key, dev bloqué prod |
| B1.4 CORS conditional | H13 | prod = origin unique ✅ |
| B1.5 real client IP | H08 | get_real_client_ip + uvicorn proxy-headers |
| B1.6 Turnstile fail-closed | H09 | sans secret → return False |

### ✅ B2 — Stripe + paiement (test_b2_billing.py)

- B2.1 Upgrade upsert lié au projet (C14, C15)
- B2.2 Subscription deleted = downgrade + révoque clé (C21)
- B2.3 Webhook HTTPS sans IP pinning (C16)
- B2.4 Stripe reconcile via env vars (H25)

### ✅ B3 — Schéma DB + multi-projet (test_b3_multiproject.py)

- B3.1 Migration alembic `owner_email` (C19, C20)
- B3.2 Découplage `name` / `owner_email`
- B3.3 `POST /api/portal/projects` multi-tenant
- B3.4 Frontend portal "Add project"
- B3.5 Pricing page actualisée

### ✅ B4 — Logique budget + race (test_b4_budget.py)

- B4.1 `budget_usd is None` → 402 fail-closed
- B4.2 Redlock token-based (C08)
- B4.3 flock O_NOFOLLOW (H02)
- B4.4 Lock englobe finalize
- B4.5 Streaming finalize partiel
- B4.6 `should_alert` cohérence (H06)
- B4.7 Token estimator clamp (H05)

### ✅ B5 — AWS Bedrock (test_b5_bedrock.py)

- B5.1–B5.6 : Converse API, asyncio.to_thread, usage réel, detection model

### ✅ B6 — Frontend + UX

- B6.3 Cookie portal samesite=strict + 14j (H10)
- B6.5 API key masking (M06)
- B6.6 saveBudget warning toast (M07)

**Non implémenté (non-bloquant pour vendable)** :
- B6.1 localStorage → cookie HttpOnly (H12) — complexe, deferred
- B6.2 Magic link POST (H11) — deferred
- B6.4 Portal "resend link" button — deferred

### ✅ B7 — Hardening admin (test_b7_hardening.py)

- B7.1 Members admin escalation (H15)
- B7.2 SMTP IP validation (H16)
- B7.3 CSV injection (H14)
- B7.4 Export streaming yield_per (C18)
- B7.5 Retry backoff exponentiel (H24)
- B7.6 PortalRevokedSession purge + lifespan (M05)

## Prochaine action : DEPLOY PROD

### Séquence deploy

```bash
# 1. Sur le VPS (ubuntu@maxiaworld.app)
cd /opt/budgetforge
cp budgetforge.db budgetforge.db.bak-b2b7-$(date +%Y%m%d-%H%M%S)

# 2. Pull + migration
git pull origin master
cd backend && alembic upgrade head

# 3. Restart backend
sudo systemctl restart budgetforge-backend

# 4. Smoke tests
curl -s https://llmbudget.maxiaworld.app/health
curl -s -H "X-Admin-Key: $ADMIN_KEY" https://llmbudget.maxiaworld.app/api/projects
```

### Alembic migration — `owner_email`

Migration : `budgetforge/backend/alembic/versions/b3_owner_email.py`
Commande : `alembic upgrade head`
Impact : ajoute colonne `owner_email TEXT` sur table `projects` (nullable)

### Tests smoke post-deploy à vérifier

- `/health` → 200 `{"status":"ok"}`
- `GET /api/projects` sans key → 401
- `GET /api/projects` avec admin key → 200
- `POST /api/usage/export` sans key → 401
- `POST /proxy/anthropic/...` → rate limit actif (30/min)

## Reste (C2 Turnstile — action Alexis)

- Créer compte Cloudflare Turnstile → obtenir `TURNSTILE_SECRET_KEY`
- Setter sur VPS : `echo 'TURNSTILE_SECRET_KEY=xxx' >> /opt/budgetforge/.env`
- Restart backend

## Sauvegardes prod (audit #4)

- Full : `/opt/budgetforge.bak-audit4-pre-fix-20260425-091126`
- DB live : `budgetforge.db.audit4-pre-fix-20260425-091154`
