# Investigation prod — 25 avril 2026, 09:11-11:24 UTC

## Sauvegardes effectuées (avant tout)

### VPS
- **Backup full** : `/opt/budgetforge.bak-audit4-pre-fix-20260425-091126` (rsync complet)
- **Backup DB live** : `/opt/budgetforge/backend/budgetforge.db.audit4-pre-fix-20260425-091154` (sqlite3 .backup, 126 KB)
- Backups antérieurs préservés : `/opt/budgetforge.bak-20260424-110710` + 6× `.db.bak*`

### Local
- **Tag git** : `pre-audit4-fix-clean-head` → commit `6f1a8ef` (dernier commit propre)
- **Branche WIP** : `wip-snapshot-2026-04-25-pre-audit4` → commit `0efbd7a` (preserve les ~30k lignes non commitées du 24 avril)
- Working copy : actuellement sur la branche WIP, aucune perte possible

## Découvertes infrastructure critiques

### 1. Prod = code WIP non commité (MD5 match confirmé)

```
Local working copy    →    Prod /opt/budgetforge
proxy.py              0446d254...  (identique)
aws_bedrock_client.py 87399a57...  (identique)
distributed_budget_lock.py acbf84a2... (identique)
dashboard/proxy.ts    5ce70c44...  (identique)
```

**Conclusion** : `deploy.sh` a fait `rsync working-copy → prod` sans passage par git. La prod tourne avec le code que j'ai audité. Tous les findings sont actifs.

### 2. Workers = 1 (single)

```
ExecStart=/opt/budgetforge/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8011 --workers 1
```

**Implications** :
- Bugs C08 (Redlock pattern cassé) et H03 (memory lock per-process) MOINS critiques en pratique — un seul worker
- **Mais** : 1 requête lente bloque toutes les autres. Trade-off scaling.

### 3. requirements.txt prod ≠ local

Prod a `redis, PyYAML, boto3, botocore` installés MANUELLEMENT. Le `requirements.txt` prod ne les liste pas. Le requirements.txt local les contient. Donc au prochain deploy.sh, le requirements.txt local sera rsyncé en prod et `pip install -r` fonctionnera. **Pas de bug à venir.**

### 4. Variables d'environnement OK en prod

```
backend/.env :
  ADMIN_API_KEY <SET>
  PORTAL_SECRET <SET>
  STRIPE_WEBHOOK_SECRET <SET>
  TURNSTILE_SECRET_KEY <SET>
  APP_ENV <SET>

dashboard/.env.local :
  NEXT_PUBLIC_API_BASE_URL <SET>
  DASHBOARD_PASSWORD <SET>
  SESSION_SECRET <SET>
  NEXT_PUBLIC_TURNSTILE_SITE_KEY <SET>
```

**Mitigation partielle** : C11/C12 (SESSION_SECRET fallback) latents mais pas exploitables en prod actuellement.

## Tests live — confirmation findings audit

### C01 — Rate limit cassé (CONFIRMÉ EXPLOITABLE)

**Test 1 : /proxy/openai avec clé bf-* fixée, 35 reqs**
```
1:401 2:401 ... 30:401 31:429 32:429 33:429 34:429 35:429
```
Rate limit fonctionne ✅

**Test 2 : /proxy/anthropic avec clé bf-* fixée, 35 reqs**
```
1:401 2:401 ... 35:401  (AUCUN 429)
```
Rate limit ABSENT ❌

**Bug exploitable réel** : un attaquant avec clé bf-* volée peut faire 1M+ req/min sur 9 providers (anthropic, google, deepseek, mistral, openrouter, ollama×2, together, azure, bedrock).

### C13 — /clients sans auth (CONFIRMÉ — impact MITIGÉ)

```
GET /clients → 200 (page rendue sans auth dashboard middleware)
GET /api/admin/stats (sans X-Admin-Key) → 401
GET /api/projects (sans X-Admin-Key) → 401
```

**Verdict** : page shell visible (sidebar, h1 "Clients", "Business overview — signups, plans, revenue", liste menu). **Données réelles protégées** par admin_api_key backend → état "Checking…" perpétuel pour visiteur non auth.

**Impact réel** : info disclosure mineure (structure de l'app exposée), pas de fuite de données clients.

### Endpoints admin tous protégés en prod ✅

```
401 /api/usage/export
401 /api/settings
401 /api/members
401 /api/usage/breakdown
401 /api/usage/daily
401 /api/usage/history
401 /api/admin/stats
405 /api/admin/billing/sync (POST attendu)
```

### NOUVEAU FINDING C23 — Stripe webhook 404 en prod

```
POST /webhook/stripe → 404
```

**Cause** : nginx config (`/etc/nginx/sites-enabled/budgetforge`) ne route que `/api/`, `/proxy/`, `/health`, `/api/auth`. Le path `/webhook/stripe` tombe dans le catch-all `location /` → port 3011 (Next.js) → 404.

**Conséquence** : tous les webhooks Stripe envoyés par Stripe → 404 → Stripe retry × N → abandon → **AUCUN upgrade Pro/Agency ne fonctionne en prod**. Customer paie, plan reste Free.

**Vérification croisée** : code `routes/billing.py:71` définit bien `@router.post("/webhook/stripe")` côté FastAPI. Code OK, infra cassée.

**Fix** : ajouter dans nginx config :
```nginx
location = /webhook/stripe {
    proxy_pass         http://127.0.0.1:8011;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
}
```
Puis `nginx -t && sudo systemctl reload nginx`.

## Baseline tests local

Subset critique (test_rate_limit + test_proxy + test_admin_auth) :
- **32 passed / 2 failed** (94%)
- Failures : `test_proxy_mistral_forwards_request`, `test_proxy_mistral_records_usage`

Pytest complet bloqué après 8 min, killé. Probable cause : tests d'intégration faisant httpx réseau → timeout. À investiguer avec marqueurs pytest pour séparer unit/integration.

## Implications sur le plan correction

### Nouveau bloc avant tout : B0 — INFRA Stripe + nginx

**Avant même B1, fixer C23** : Stripe webhook 404 = revenue = 0. Si une vente est tentée maintenant, elle est invisible.

Estimé : 30 minutes (édit nginx + reload + test webhook avec stripe CLI).

### Réajustements

- **C08, H03** : moins critiques avec workers=1, mais à corriger AVANT scale-up à 2+ workers
- **C11/C12** : env set en prod → priorité réduite, mais à durcir au runtime
- **C13** : impact réduit, ajout `/clients` à PROTECTED_PATHS reste rapide

### Liste mise à jour des blockers absolus avant ouverture early adopters

1. **C23** (nouveau) — nginx webhook stripe → fix infra immédiat
2. **C01** — rate limit cassé → fix code
3. **C02-C06** — Bedrock bypass → fix code (réparer décidé)
4. **C14-C15** — Stripe upgrade flow → fix code
5. **C19-C20** — multi-projet → décidé "le plus pro" = implémenter
6. **C07** — budget None = illimité → décidé "402 fail-closed"

## Étape suivante (proposée)

1. **B0 nginx fix** (30 min) — debloque tout flux Stripe
2. **B1 sécurité** (1j) — rate limit + dashboard middleware /clients
3. Suite plan B2→B7 selon `plan-correction-audit-2026-04-25.md`

Avant chaque déploiement :
- Backup auto via deploy.sh (déjà câblé)
- Backup DB explicite supplémentaire
- Test live post-deploy avec curl prouvant le fix

## Notes méthodologiques

- TDD strict requis : test rouge AVANT chaque fix
- Pas de modification multi-finding par commit
- Un commit = un finding fixé + son test
- Vérification live post-déploiement obligatoire (ne pas faire confiance aux unit tests seuls)
