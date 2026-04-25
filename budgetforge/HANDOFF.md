# HANDOFF — BudgetForge post-audit-fixes (session 25 avril 2026 — soir)

## État : DÉPLOYÉ EN PROD ✅ — tous findings résolus

**URL prod** : https://llmbudget.maxiaworld.app  
**Dernier commit** : `244f04f` (fix dashboard clients page + next.config)  
**Services** : budgetforge-backend (8011) + budgetforge-dashboard (3011) — actifs

## Ce qui a été fait cette session (fin de journée)

### Corrections ❌ FAIL → ✅
| # | Finding | Résolution |
|---|---|---|
| 1 | `.env` en 644 | `chmod 600` → `-rw-------` ✅ |
| 2 | Doublon nginx `budgetforge.bak-audit4-*` | `rm` sites-enabled ✅ |
| 3 | `APP_URL=http://localhost:8011` | Corrigé → `https://llmbudget.maxiaworld.app` + restart backend ✅ |
| 4 | Headers sécurité absents | Ajoutés dans nginx (X-Frame, HSTS, CSP, Referrer, Permissions) ✅ |
| 5 | Aucun CSP | Inclus dans #4 ✅ |

### Corrections ⚠️ WARN → ✅
| # | Finding | Résolution |
|---|---|---|
| 6 | 7 fichiers DB backup en 644 | `chmod 640 /opt/budgetforge/backend/budgetforge.db*` ✅ |
| 7 | `appDir` deprecated next.config.js | Supprimé locally + poweredByHeader: false (commit 244f04f) |
| 8 | `X-Powered-By: Next.js` leaké | `proxy_hide_header X-Powered-By` nginx ✅ — confirmé absent en prod |

### Code local
- `clients/page.tsx` : envoi `X-Admin-Key` via `getStoredAdminKey()` — commité
- `next.config.js` : `appDir` supprimé, `poweredByHeader: false` ajouté
- `next.config.ts` : `poweredByHeader: false` ajouté

## ADMIN_API_KEY prod

`5b3eeaa7d9d4fa3915fc44ee67e23439639e8f001078da8766f5cb820d6c0998`

→ À entrer dans Settings du dashboard.

## Headers sécurité actifs en prod (vérifiés curl)

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: [CSP complète Cloudflare Turnstile compatible]
X-Powered-By: [supprimé]
```

## Note prochaine session

Les next.config changes (poweredByHeader, appDir) sont en local. Un `redeploy dashboard` les appliquera en prod. Pas critique (X-Powered-By déjà géré nginx).

**Aucun finding ouvert.** BudgetForge est propre.
