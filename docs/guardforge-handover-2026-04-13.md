# GuardForge — Handover pour la prochaine session

**Date de cette session** : 13 avril 2026
**Branche** : `master`
**État global** : **PRODUCTION LIVE** sur https://guardforge.maxiaworld.app — Phases A→D + B/C/D infra + Phase 2/3 deploy + sécurité refactor + bugfixes terminés.

> **Update Session 2 (même jour, après-midi)** — voir section [§10](#10-update-session-2-deploy-vps-complet--securite--bugfixes) à la fin du document. Le reste de ce fichier décrit l'état au début de la Session 2 ; tout est resté valide mais une partie est obsolète (notamment les "prochaines étapes" §5).

---

## 1. Commits de la session (tous sur master)

```
06231dc docs(guardforge): update plan with final status — all 4 phases complete
c399408 feat(guardforge): Phase D — launch materials
066357a feat(guardforge): Phase C — production quality
e58643e feat(guardforge): Phase B — commercial differentiators
f260119 feat(guardforge): Phase A — production-ready foundation
```

**À SAVOIR** : toutes les modifications dashboard (`guardforge/dashboard/`) ne sont **pas** commitées parce que `guardforge/dashboard` est un gitlink orphelin dans le repo parent. Les changements existent sur disque localement (messages/*.json, nouvelles pages `/compliance`, `/entities`, `/webhooks`, etc.) mais ne sont pas suivis par git parent. Si tu reprends, pense à gérer ce dossier séparément (soit l'init en repo standalone, soit le transformer en dossier simple tracké par le parent).

---

## 2. État du code GuardForge

### Backend (`guardforge/backend/`)
- 161 tests pytest passing (unit + integration + in-process + e2e)
- 83% coverage
- Bandit clean (0 issues)
- 19 endpoints API (scanner, tokenize, policies, audit, reports PDF, entities CRUD, webhooks CRUD, vault)
- 16 compliance policies (3 generic + 13 jurisdictions)
- 17 entity types PII (EU/US multilingue)
- Vault SQLite persistent
- Hardening complet (HSTS, CSP, rate limit configurable, payload size limit)

### Python SDK (`guardforge/sdk/python/`)
- Package `guardforge` installable `pip install -e`
- Drop-in `from guardforge import OpenAI` / `Anthropic`
- 12 tests passing

### Dashboard (`guardforge/dashboard/`)
- 10 routes (/, /scanner, /policies, /audit, /vault, /playground, /reports, /compliance, /entities, /webhooks)
- 15 langues i18n complètes
- Hot-reload Next.js 16 Turbopack

### Docs (`guardforge/docs/`)
- `LIMITATIONS.md` — 8 sections exhaustives
- `legal/DPA.md` — GDPR Article 28 template
- `legal/SECURITY_WHITEPAPER.md`
- `legal/SUB_PROCESSORS.md`
- `legal/PRIVACY_POLICY.md`
- `legal/TERMS_OF_SERVICE.md`

### Marketing (`guardforge/marketing/`)
- `index.html` — landing page (~750 lignes, vanilla HTML+CSS)
- `compare.html` — page comparaison concurrents détaillée
- `README_OSS.md` — README pour repo GitHub public
- `LAUNCH_DRAFTS.md` — drafts Show HN / Reddit / Twitter thread
- `vercel.json` — config Vercel avec security headers

---

## 3. Services locaux (ton PC Windows)

**État actuel** :
- Backend port 8004 : **peut-être encore running** (lancé plusieurs fois pendant la session). À killer et relancer proprement si besoin.
- Dashboard port 3003 : **peut-être encore running** (Next.js dev mode).

**Pour relancer proprement depuis zéro** :
```bash
# Tuer ce qui tourne
netstat -ano | grep ":8004.*LISTENING" | awk '{print $5}' | xargs -I{} taskkill //F //PID {}
netstat -ano | grep ":3003.*LISTENING" | awk '{print $5}' | xargs -I{} taskkill //F //PID {}

# Backend
cd "C:/Users/Mini pc/Desktop/MAXIA Lab/guardforge/backend"
./venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8004

# Dashboard (nouvelle fenêtre)
cd "C:/Users/Mini pc/Desktop/MAXIA Lab/guardforge/dashboard"
npm run dev -- --port 3003
```

**Credentials dev local** :
- `SECRET_KEY=change-me-to-a-random-32-char-string` (dans `.env`)
- `VAULT_ENCRYPTION_KEY=MU5aCPvKMx1FfwQFcss7Ly27C5O2CStJ1yAvsgPJXRU=` (dans `.env`)
- `NEXT_PUBLIC_API_KEY=change-me-to-a-random-32-char-string` (dans `dashboard/.env.local`)

---

## 4. VPS — Phase 1 prep faite

**Adresse** : `ubuntu@maxiaworld.app` (IP publique `146.59.237.43`, OVH)
**Accès** : SSH key `~/.ssh/id_ed25519` autorisée
**Port réservé** : 8004 pour GuardForge (MAXIA tourne sur 8000, aucun conflit)

### Ce qui est en place sur le VPS (dans `/opt/guardforge/`)
```
/opt/guardforge/
├── DEPLOY_NOTES.md                    # documentation complète on-server
├── deploy/
│   └── nginx-subdomain.conf           # config nginx vhost (PRÉPARÉE, PAS ACTIVÉE)
└── secrets/                           # chmod 700
    ├── .env.production                # chmod 600, 13 env vars prod
    └── .pg_password                   # chmod 600
```

### Ce qui est créé
- PostgreSQL DB `guardforge` (Postgres 17.7, UTF-8)
- PostgreSQL user `guardforge` avec password aléatoire (stocké sur VPS uniquement)
- Secrets générés :
  - `SECRET_KEY` (64 chars urlsafe)
  - `VAULT_ENCRYPTION_KEY` (Fernet 44 chars base64, **stable, NE JAMAIS régénérer sinon tokenmaps perdus**)
  - Postgres password (43 chars urlsafe)

### Ce qui n'est PAS touché (safety)
- `/opt/maxia/` intact
- `/etc/nginx/sites-enabled/maxia` intact
- systemd service `maxia` toujours UP (vérifié via `systemctl is-active maxia` → `active`)
- MAXIA répond toujours `HTTP 200` sur `https://maxiaworld.app/health`

### Secrets — IMPORTANT
Les secrets sont **uniquement** sur le VPS dans `/opt/guardforge/secrets/`. Ils ne sont ni dans git, ni en local sur ton PC, ni affichés dans cette doc.

**À faire en priorité** : backup ces 2 fichiers hors-ligne (1Password, KeePass, USB chiffré) :
```bash
ssh ubuntu@maxiaworld.app "cat /opt/guardforge/secrets/.env.production"
ssh ubuntu@maxiaworld.app "cat /opt/guardforge/secrets/.pg_password"
```

---

## 5. Prochaines étapes prioritaires (ordre strict)

### ⏳ Étape A — DNS (bloquant, toi seulement, ~5 min + propagation)
Au panneau OVH DNS pour `maxiaworld.app`, ajouter un record :
```
guardforge   A   146.59.237.43   TTL 3600
```
Puis attendre propagation (5-60 min). Vérifier avec :
```bash
dig +short guardforge.maxiaworld.app
# doit renvoyer 146.59.237.43
```

### ⏳ Étape B — Let's Encrypt cert (bloquant, toi via SSH, ~2 min)
Une fois le DNS propagé :
```bash
ssh ubuntu@maxiaworld.app
sudo certbot --nginx -d guardforge.maxiaworld.app
# Répondre aux prompts : email, agree TOS, pas de newsletter, pas de redirect HTTP→HTTPS (certbot le fait)
```

### ⏳ Étape C — Activer nginx vhost (toi via SSH, ~1 min)
```bash
ssh ubuntu@maxiaworld.app
sudo ln -s /opt/guardforge/deploy/nginx-subdomain.conf /etc/nginx/sites-enabled/guardforge
sudo nginx -t   # doit dire "syntax is ok" + "test is successful"
sudo systemctl reload nginx
# Vérifier
curl -sI https://guardforge.maxiaworld.app/  # devrait renvoyer le placeholder text
```

### ⏳ Étape D — Phase 2 : déployer le code backend (moi, prochaine session, ~2h)
Quand A/B/C sont OK, tu dis "go Phase 2" et je fais :
1. Créer `guardforge/backend/Dockerfile` et `docker-compose.prod.yml`
2. Créer `guardforge/deploy/deploy.sh` (git pull + smoke test, comme MAXIA)
3. Créer systemd `guardforge-backend.service`
4. Push le code sur le VPS (via git clone ou scp)
5. Lancer les migrations DB (auto via `Base.metadata.create_all()` au startup)
6. Démarrer le service
7. Smoke test `/health` via HTTPS
8. Tester un `/api/scan` et un `/api/tokenize` end-to-end

### ⏳ Étape E — Phase 3 : déployer dashboard sur Vercel (~30 min)
1. Push marketing/ sur GitHub (nouveau repo public ou privé)
2. Connecter à Vercel
3. Déployer le Next.js dashboard lui-même (pointant vers `https://guardforge.maxiaworld.app/api`)
4. Configurer domain custom `guardforge.io` (si tu achètes) ou sous-domaine Vercel

### ⏳ Étape F — LemonSqueezy + lancement (toi seulement, ~2h)
1. Créer compte LemonSqueezy (gratuit)
2. Créer 4 products (Starter/Pro/Business/Enterprise + 3 Self-hosted)
3. Wire les URLs checkout dans `guardforge/marketing/index.html` (remplacer les `#`)
4. Enregistrer démo Loom 2-3 min
5. Publier marketing (D1/D2/D3/D6 prêts dans `guardforge/marketing/`)
6. Lancer HN / Reddit / Twitter avec les drafts de `LAUNCH_DRAFTS.md`

---

## 6. Bugs connus à NE PAS oublier

| # | Bug | Impact | Fix |
|---|---|---|---|
| 1 | Calendrier date picker `<input type="date">` affiché en langue système Windows, pas celle du dashboard | UX — un user japonais voit un calendrier français si son OS est en français | Fix option simple 15 min : `<html lang={locale}>` dynamique dans `guardforge/dashboard/src/app/layout.tsx`. Option propre : remplacer par `react-day-picker` (~2h). Documenté dans `LIMITATIONS.md` §5 |
| 2 | `guardforge/dashboard` est un gitlink orphelin (pas de `.gitmodules`) | Les changements dashboard ne sont pas commitées au repo parent | À décider : init en repo standalone OU transformer en dossier simple tracké |
| 3 | Backend `.env` contient `VAULT_ENCRYPTION_KEY` en dur dans le fichier local | Risque si `.env` leak (il est dans `.gitignore` donc pas dans git, mais quand même) | Pour le dev c'est OK. En prod VPS, la clé est dans `/opt/guardforge/secrets/.env.production` chmod 600 |

---

## 7. État des budgets tokens

La session a été très longue (Phases A + B + C + D + docs + Phase 1 VPS). Estimation : **~60-70% du contexte max** consommé. Pour la prochaine session :
- Commence par `/context-budget` pour vérifier
- Si déjà saturé, split en plusieurs sessions courtes
- Priorité : Phase 2 deploy code, puis Phase 3 dashboard, puis fix calendrier

---

## 8. Fichiers clés pour reprendre

| Fichier | À quoi ça sert |
|---|---|
| `docs/guardforge-plan.md` | Plan complet décisions pricing + phases |
| `docs/guardforge-handover-2026-04-13.md` | **Ce fichier** |
| `guardforge/README.md` | README pro produit |
| `guardforge/LICENSE` | Licence propriétaire 12 sections |
| `guardforge/docs/LIMITATIONS.md` | Tous les trade-offs documentés |
| `guardforge/marketing/LAUNCH_DRAFTS.md` | Drafts annonces launch day |
| `guardforge/backend/tests/benchmark_results.md` | Métriques perf baseline |
| `guardforge/backend/tests/validation_report.md` | Precision/recall baseline |

---

## 9. Commandes de reprise rapides

```bash
# Vérifier MAXIA toujours OK (sanity check)
curl -sI https://maxiaworld.app/health
ssh ubuntu@maxiaworld.app "systemctl is-active maxia"

# Voir l'état GuardForge VPS
ssh ubuntu@maxiaworld.app "cat /opt/guardforge/DEPLOY_NOTES.md"
ssh ubuntu@maxiaworld.app "ls -la /opt/guardforge/"

# Voir les commits récents
cd "C:/Users/Mini pc/Desktop/MAXIA Lab"
git log --oneline -6

# Vérifier le DNS guardforge
dig +short guardforge.maxiaworld.app
# Si vide → record pas encore ajouté / pas propagé
# Si 146.59.237.43 → prêt pour certbot (Étape B)
```

---

**Fin de session 1.** _(Suite ci-dessous — Session 2 a tout fait jusqu'à launch-ready.)_

---

## 10. Update Session 2 — deploy VPS complet + sécurité + bugfixes

**Date** : 13 avril 2026 (après-midi, suite directe Session 1)
**Branche** : `master`
**Commits ajoutés** : `73e4d27` (Phase 2/3 deploy) + `e5e612c` (dashboard tracking + security proxy + phone fix)

### 10.1 Étapes A/B/C terminées (DNS + cert + nginx)
- DNS `guardforge A 146.59.237.43` ajouté chez OVH par l'utilisateur ✓
- Cert Let's Encrypt obtenu via `certbot certonly --webroot -w /var/www/html` (méthode sans downtime MAXIA — vhost HTTP-only temporaire pour le challenge ACME, supprimé après) ✓
- Vhost final `/opt/guardforge/deploy/nginx-subdomain.conf` symlinké à `/etc/nginx/sites-enabled/guardforge`
- Renouvellement auto vérifié (`certbot renew --dry-run` → success). Le HTTP→HTTPS redirect exempte `/.well-known/acme-challenge/` pour permettre le webroot challenge sur HTTP au renouvellement.

### 10.2 Phase 2 — backend deploy
Au lieu du Docker prévu dans le plan original, j'ai utilisé **systemd + venv natif** (cohérent avec MAXIA, plus simple, moins de couches).

Artefacts créés et committés :
- `guardforge/backend/requirements.txt` — ajout de `asyncpg>=0.29,<1.0` (manquait pour PostgreSQL async)
- `guardforge/deploy/guardforge-backend.service` — systemd unit ubuntu, hardened (NoNewPrivileges, ProtectSystem=full, etc.)
- `guardforge/deploy/deploy.sh` — script idempotent (venv + pip install + restart + smoke test)
- Code transféré via `tar | ssh` (rsync non dispo sur Windows bash)

⚠️ **Piège rencontré** : `ProtectHome=true` dans le systemd unit faisait crasher asyncpg qui stat `~/.postgresql/postgresql.key` au démarrage (PermissionError). **Retiré**. Cette directive est incompatible avec asyncpg.

### 10.3 Vault PostgreSQL fix
Le `services/vault.py` ne supporte que SQLite (sync). Quand la main DB est PostgreSQL, le vault tournait en in-memory only → **les tokens disparaissaient à chaque restart**.

Fix appliqué : nouvelle option `vault_database_url` dans `core/config.py`. Si vide, fallback sur `database_url`. En prod, set à `sqlite+aiosqlite:////opt/guardforge/vault.db` → vault persistent.

Vérifié end-to-end : tokenize → restart service → detokenize avec le même session_id → renvoie le texte original.

### 10.4 Phase 3 — dashboard deploy
- Node 20 LTS installé sur le VPS via NodeSource (`curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -`)
- Dashboard transféré via tar | ssh
- Build avec `output: "standalone"` (déjà dans `next.config.ts`)
- `guardforge/deploy/guardforge-dashboard.service` — systemd unit (NODE_ENV=production, HOSTNAME=127.0.0.1, PORT=3003)
- Standalone runtime à `/opt/guardforge/dashboard/.next/standalone/` avec `static/` et `public/` copiés dedans (requis par Next.js standalone)

### 10.5 Sécurité — server-side API proxy ⭐
**Problème critique trouvé en cours de session** : le dashboard utilisait `NEXT_PUBLIC_API_KEY` qui bundlait le SECRET_KEY backend dans le JS client. **N'importe quel visiteur pouvait lire la clé via DevTools.**

**Fix** :
- Nouveau `dashboard/src/app/api/[...path]/route.ts` — Next.js route handler catch-all qui forward `/api/*` vers le backend en ajoutant `X-API-Key` server-side
- Refactor `dashboard/src/lib/api.ts` — utilise des URLs relatives, plus de header auth côté client
- Env vars renommés `NEXT_PUBLIC_API_KEY` → `GUARDFORGE_API_KEY` (server-only, sans `NEXT_PUBLIC_`)
- Nginx vhost mis à jour : `/api/*` route vers Next.js `:3003` (qui proxie vers backend `:8004`), `/health` reste direct backend
- `dashboard/.env.example` créé documentant les nouvelles vars
- Whitelist `!.env.example` dans `.gitignore`

**Vérifié** : `grep -r GUARDFORGE_API_KEY .next/static` → 0 occurrences. La clé est uniquement dans process.env du serveur Next.js.

### 10.6 SECRET_KEY rotation
Le SECRET_KEY de Session 1 a été involontairement affiché dans une commande SSH. Rotated via Python script qui n'affiche jamais la valeur (juste sha256 prefix `8411c94fec8ca445`). L'ancien key renvoie maintenant 401.

### 10.7 Bug regex phone international
La regex `phone_international` capturait au max 4 groupes → `+33 6 12 34 56 78` détecté comme `+33 6 12 34` (11 chars sur 17). Fix : nouveau quantifier `(?:[\s.-]?\d{2,4}){1,5}` pour 1-5 groupes. Test de non-régression ajouté couvrant FR/US/UK/DE.

**162 tests pytest passent** (était 161, +1 test ajouté).

### 10.8 Bug calendrier date picker
**Déjà fixé** dans `dashboard/src/app/layout.tsx` : `<html lang={locale}>` est déjà en place. Le handover original notait ce bug mais le code était déjà à jour. Rien à faire.

### 10.9 Bug gitlink dashboard orphelin
`guardforge/dashboard` était un gitlink mode 160000 sans `.gitmodules`. Fix : `git rm --cached guardforge/dashboard` + `git add guardforge/dashboard/` → 65+ fichiers maintenant trackés normalement. Le `.gitignore` interne du dashboard exclut déjà `node_modules/`, `.next/`, `.env*` (avec exception `!.env.example`).

### 10.10 Cleanup
- `guardforge/backend/=1.0` — junk file de pip mistype, supprimé
- `/opt/guardforge/deploy/nginx-subdomain.conf.bak` sur le VPS — supprimé

### 10.11 État live final

| URL | État |
|---|---|
| `https://guardforge.maxiaworld.app/` | Dashboard Next.js (37 KB HTML) ✓ |
| `https://guardforge.maxiaworld.app/scanner` etc. | 10 routes dashboard ✓ |
| `https://guardforge.maxiaworld.app/health` | Backend direct, 200 ✓ |
| `https://guardforge.maxiaworld.app/api/scan` | Via Next.js proxy, X-API-Key server-side, fonctionne sans auth client ✓ |
| `https://maxiaworld.app/health` | MAXIA intact, 200 ✓ |

| Service systemd VPS | Port | État |
|---|---|---|
| `maxia` | 8000 | active |
| `guardforge-backend` | 8004 | active |
| `guardforge-dashboard` | 3003 | active |
| `nginx` | 80/443 | active |
| `postgresql` | 5432 | active |

### 10.12 Prochaines étapes — Phase F (toi)
1. Acheter `guardforge.io` (ou autre) si désiré, sinon rester sur `guardforge.maxiaworld.app`
2. Créer compte LemonSqueezy, créer 4 products (Starter/Pro/Business/Enterprise + 3 Self-hosted)
3. Wire les URLs checkout dans `guardforge/marketing/index.html`
4. Enregistrer démo Loom 2-3 min
5. Push vers GitHub (créer un nouveau repo `maxia-lab/guardforge` ou similaire — actuellement aucun remote git)
6. Lancer HN / Reddit / Twitter avec les drafts de `guardforge/marketing/LAUNCH_DRAFTS.md`

### 10.13 Bugs/limites résiduels (non-bloquants)

| # | Item | Sévérité | Note |
|---|---|---|---|
| 1 | Lock file sync VPS | low | Le `npm ci` a échoué initialement sur le VPS, on a dû `npm install`. Localement le lock file est OK. À investiguer si ça reproduit. |
| 2 | Pre-existing nginx warnings `conflicting server name` | low | Causé par `maxia.bak` dans `/etc/nginx/sites-enabled/`. Pas mon code, ne pas y toucher sans confirmer avec MAXIA. |
| 3 | DOCS_ENABLED en prod | medium | À décider : exposer Swagger publiquement ou pas. Actuellement `DOCS_ENABLED=true` dans `.env.production` (héritage du dev). À mettre `false` pour le launch (réduit la surface). |
| 4 | Pas de monitoring/alerting GuardForge | medium | MAXIA a Beszel sur `/monitor/`. Ajouter GuardForge à la même config Beszel après launch. |
| 5 | Pas de backup automatique de la DB GuardForge | medium | À setup avant launch (`pg_dump` quotidien dans `/opt/backups/`). |

### 10.14 Commandes de reprise rapide

```bash
# Vérifier que tout est UP
curl -sI https://guardforge.maxiaworld.app/ | head -1
curl -s https://guardforge.maxiaworld.app/health
ssh ubuntu@maxiaworld.app "sudo systemctl is-active guardforge-backend guardforge-dashboard maxia nginx postgresql"

# Logs
ssh ubuntu@maxiaworld.app "sudo journalctl -u guardforge-backend -n 50 --no-pager"
ssh ubuntu@maxiaworld.app "sudo journalctl -u guardforge-dashboard -n 50 --no-pager"

# Redeploy backend après git pull (sur le VPS)
ssh ubuntu@maxiaworld.app "sudo /opt/guardforge/deploy/deploy.sh"

# Redeploy dashboard après changement
ssh ubuntu@maxiaworld.app "cd /opt/guardforge/dashboard && rm -rf .next && npm run build && cp -r .next/static .next/standalone/.next/static && cp -r public .next/standalone/public && sudo systemctl restart guardforge-dashboard"
```

**Fin de Session 2.** Tout est en prod, sécurisé, testé. Ne reste que la Phase F (commercial/marketing — toi).
