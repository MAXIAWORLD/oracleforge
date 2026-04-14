# MAXIA Oracle — Security audit on extracted modules (Phases 2 + 3)

**Phase 2 date** : 14 avril 2026 — audit sécurité sur le code extrait
**Phase 3 date** : 14 avril 2026 — résolution des items différés côté API
**Plan** : `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` §3 Phase 2
**Scope** : `oracleforge/backend/` (3 modules oracle + core/ + api/ + main.py)

Ce document est le délivrable Phase 2 (cf. plan §3 "Délivrable :
`oracleforge/docs/security_audit_extraction.md`"), étendu en Phase 3 pour
marquer les items différés comme résolus. Chaque vulnérabilité de
`MAXIA V12/AUDIT_COMPLET_V12.md` est listée, son applicabilité à MAXIA Oracle
est évaluée, et le fix appliqué (ou sa phase cible) est documenté.

Référence source : `MAXIA V12/AUDIT_COMPLET_V12.md` — 6 critiques, 14 hautes,
26 moyennes, 19+ basses, score global 58/100.

---

## 1. Verdict global

**MAXIA Oracle après Phase 3** : **clean sur toutes les vulns V12 applicables**.

| Catégorie | Phase 2 état | Phase 3 état |
|---|---|---|
| Hardcoded secrets dans le code extrait | **0 trouvé** ✅ | inchangé ✅ |
| Weak crypto (MD5/SHA1) | **0 trouvé** ✅ | inchangé ✅ |
| `str(e)` retourné au client (**H12**) | **5 call sites patchés** → `safe_error()` ✅ | + exception handler global `main.py` ✅ |
| Logs qui pourraient leaker `api-key=` dans RPC URL | **0 call site** ✅ | inchangé ✅ |
| SSRF via user-controlled URL | **0 call site** ✅ | + validation symboles regex `[A-Z0-9]{1,10}` ✅ |
| Input validation sur `feed_id` | **Ajouté** (64-char hex) ✅ | + validation symbols via Pydantic ✅ |
| Validation startup stricte (**C5**) | Différé Phase 3 | **RÉSOLU** — `core/config.py` refuse de démarrer sans `ENV`, et sans `API_KEY_PEPPER`+`DB_PATH` en staging/prod ✅ |
| JWT_SECRET persistant (**C6**) | N/A | **N/A** — décision Phase 3 #3 : pas de JWT, API key opaque + hash+pepper ✅ |
| Rate limiting persistant (**H7**) | N/A Phase 2 | **RÉSOLU** — `core/rate_limit.py` DB-backed fixed window 24h (SQLite, 100 req/jour) ✅ |
| Security headers HTTP (**H9**) | N/A Phase 2 | **RÉSOLU** — `core/security.py` middleware injecte CSP/XFO/nosniff/Referrer-Policy/Permissions-Policy/HSTS conditionnel ✅ |
| Swagger public (**H11**) | N/A Phase 2 | **RÉSOLU** — `main.py` : `docs_url=None, redoc_url=None, openapi_url=None` en prod ✅ |

**Aucun secret n'a été exposé par les modules oracle extraits.** Le MAXIA V12
audit avait trouvé les 6 critiques et la majorité des 14 hautes dans des
**fichiers non extraits** (`main.py`, `auth.py`, `agent_credit_score.py`,
`escrow_client.py`, `public_api.py`, etc.). Les modules oracle (`pyth_oracle`,
`chainlink_oracle`, `price_oracle`) étaient listés dans la section §8 "Ce qui
fonctionne bien" de l'audit V12. Notre extraction conserve cette propriété.

---

## 2. Vulnérabilités critiques V12 vs MAXIA Oracle

### C1 — Secret HMAC hardcodé `maxia-credit-2026`
- **Source** : `MAXIA V12/backend/agent_credit_score.py:21`
- **Applicable à MAXIA Oracle** : **Non**. Le module `agent_credit_score.py`
  n'est pas extrait (credit score = scope régulé).
- **Vérification proactive** : `grep -iE '(api[_-]?key|secret|password|token)\s*=\s*"[^"$]{10,}"'`
  sur `oracleforge/backend/` → **0 match**.

### C2 — Endpoint GPU public sans auth
- **Source** : `MAXIA V12/backend/main.py:3895`
- **Applicable** : **Non**. Pas de GPU, pas de route `/api/public/gpu/rent`.

### C3 — Admin key en URL query parameter
- **Source** : `MAXIA V12/backend/main.py:1443`
- **Applicable** : **Non**. Aucune route admin extraite. À re-vérifier si/quand
  une route admin est ajoutée en Phase 3.

### C4 — `ESCROW_PRIVKEY_B58` en `.env` sans KMS
- **Source** : `MAXIA V12/backend/config.py:62-66`
- **Applicable** : **Non**. Surgery volontaire en Phase 1 — le nouveau
  `oracleforge/backend/core/config.py` (83 lignes) ne touche jamais à
  `ESCROW_PRIVKEY_B58`. MAXIA Oracle n'a pas d'escrow, pas de custody.

### C5 — Secrets sans validation startup stricte
- **Source** : `MAXIA V12/backend/config.py:7-12`
- **Applicable à MAXIA Oracle** : **Partiellement**, mais différé.
- **Raison du différé** : en l'état actuel, **aucune** variable d'environnement
  n'est strictement requise par les modules oracle. Toutes ont un fallback
  public (Pyth Hermes public, Chainlink public Base, CoinGecko public, etc.).
  La validation stricte deviendra pertinente :
    - Phase 3 quand on aura `X-API-Key` pour les clients MAXIA Oracle
    - Phase 4 quand on configurera un wallet x402 (secret server-side)
    - Phase 7 (deploy VPS) quand on validera que les env Helius/Chainstack
      sont bien injectées en prod vs juste absentes
- **Action Phase 2** : ajouter une TODO explicite dans `core/config.py`
  pointant vers les phases cibles. Ne PAS masquer le risque.

### C6 — `JWT_SECRET` aléatoire (sessions perdues au restart)
- **Source** : `MAXIA V12/backend/auth.py:28-39`
- **Applicable** : **Différé Phase 3**. Pas d'authentification avant la
  Phase 3 (API FastAPI). Quand Phase 3 ajoutera `X-API-Key`, on n'aura
  probablement pas de JWT du tout (API key simple stockée en DB). Si JWT
  devient nécessaire plus tard, on suivra le pattern "validate-at-startup +
  persistent secret" dès le départ.

---

## 3. Vulnérabilités hautes V12 vs MAXIA Oracle

### H1 — Endpoints "coming soon" / 404 camouflés
- **Applicable** : **Non**. Pas de routes stub dans MAXIA Oracle.

### H2 — Sandbox fake data en production
- **Applicable** : **Non**. Pas de mode sandbox.

### H3, H4, H5, H6 — CEO executor / escrow startup / tier logic / dynamic pricing
- **Applicable** : **Non** (aucun de ces modules extrait).

### H7 — Rate limiting in-memory non persistant
- **Applicable** : **Différé Phase 3**. Il n'y a pas encore de rate limiter.
  Phase 3 devra implémenter un rate limiter **DB-backed** (pas `dict` en
  mémoire) pour le free tier 100 req/jour.

### H8 — Injection SQL ORDER BY
- **Applicable** : **Non**. Les modules oracle extraits n'exécutent aucune
  requête SQL (ils parlent HTTP à des APIs externes + font des lookups dans
  des dicts Python en mémoire).

### H9 — Security headers absents
- **Applicable** : **Différé Phase 3**. L'app FastAPI n'existe pas encore.
  Phase 3 devra ajouter un middleware qui injecte :
    - `Content-Security-Policy` (même si V1 n'a pas de frontend, protège
      l'éventuelle landing page Phase 8)
    - `X-Frame-Options: DENY`
    - `X-Content-Type-Options: nosniff`
    - `Strict-Transport-Security` (activé uniquement sur le vhost HTTPS)
    - `Referrer-Policy: strict-origin-when-cross-origin`

### H10 — XSS via innerHTML
- **Applicable** : **Non** (pas de frontend Phase 1-7). Phase 8 landing page
  sera statique.

### H11 — Swagger UI public (559 endpoints exposés)
- **Applicable** : **Différé Phase 3**. À Phase 3, le `FastAPI(...)` doit être
  instancié avec `docs_url=None, redoc_url=None, openapi_url=None` en
  production (override possible en dev via env var).

### H12 — `str(e)` retourné aux clients
- **Applicable** : **OUI — patché en Phase 2**. Voir §4.1.

### H13 — Race condition TOCTOU solde sandbox
- **Applicable** : **Non** (pas de solde sandbox).

### H14 — IP whitelist CEO optionnelle
- **Applicable** : **Non** (pas d'endpoint CEO).

---

## 4. Fixes appliqués en Phase 2

### 4.1 — Correctif H12 : centralisation de la gestion d'erreur

**Problème** : les 3 modules oracle avaient 5 call sites qui retournaient
`{"error": f"... {str(e)[:100]}", "source": "..."}` aux clients. Le `str(e)`
peut contenir des paths système (`/etc/...`, `C:/...`), des noms de tables
SQL, des IPs internes, des versions de lib, etc.

**Fix** : nouveau module `backend/core/errors.py` avec `safe_error()` qui :
1. log le **type** de l'exception + le contexte + le traceback complet côté
   serveur (via `exc_info=True`)
2. retourne au client uniquement `"{context} ({ExceptionType})"` — jamais
   `str(exc)`, jamais le traceback

**Call sites patchés** :

| Fichier | Ligne V1 | Avant | Après |
|---|---|---|---|
| `pyth_oracle.py` | 366 | `f"Pyth error: {str(e)[:100]}"` | `safe_error("Pyth Hermes fetch failed", e, logger)` |
| `pyth_oracle.py` | 410 | `str(e)[:100]` | `safe_error("Pyth on-chain verification failed", e, logger)` |
| `pyth_oracle.py` | 454 | `f"Finnhub error: {str(e)[:100]}"` | `safe_error("Finnhub fetch failed", e, logger)` |
| `chainlink_oracle.py` | 177 | `str(e)[:100]` | `safe_error(f"Chainlink eth_call failed for {sym}", e, logger)` |
| `chainlink_oracle.py` | 239 | `str(e)[:100]` | `safe_error(f"Chainlink feed verification failed for {sym}", e, logger)` |

**Vérification** : `grep 'str(e)' oracleforge/backend/` → 1 seul match
restant, dans le docstring de `core/errors.py` lui-même qui documente le
fix (pas du code).

**Test manuel de non-régression leak** :
```python
>>> from core.errors import safe_error
>>> try:
...     raise ValueError("secret internal path /etc/passwd")
... except Exception as e:
...     msg = safe_error("fetch failed", e, logging.getLogger("test"))
>>> msg
'fetch failed (ValueError)'
>>> "/etc/passwd" in msg
False
```
Le traceback complet apparaît dans les logs serveur, pas dans la réponse client.

### 4.2 — Input validation sur `feed_id` Pyth

**Problème** : `get_pyth_price(feed_id: str, hft: bool = False)` acceptait
n'importe quelle string sans validation. Un appelant malicieux (via SDK ou
route en Phase 3) pourrait :
- Polluer le cache `_price_cache` avec des clés arbitraires jusqu'à
  déclencher l'eviction LRU (mémoire bornée, mais comportement observable)
- Générer du trafic gaspillé vers `hermes.pyth.network` avec des IDs invalides
- Théoriquement tenter une injection dans les query params HTTP (mitigée par
  l'encoding `httpx params=`)

**Fix** : nouveau helper `_is_valid_feed_id(feed_id)` dans `pyth_oracle.py`
qui vérifie :
- `isinstance(feed_id, str)`
- `len(feed_id) == 64`
- Tous les caractères sont dans `[0-9a-f]` (case-insensitive)

Early-return `{"error": "invalid feed_id format", "source": "pyth"}` avant
d'incrémenter les métriques, avant de toucher au cache, avant tout appel réseau.

**Propagation transitive** : `verify_price_onchain()` appelle
`get_pyth_price(feed_id, hft=True)` en interne, donc la validation s'applique
aussi à cette fonction sans modification directe.

`get_batch_prices()` accepte des `symbols` (tickers, pas des feed_ids) et
effectue le lookup via `ALL_FEEDS.get(lookup)` qui retourne soit un feed_id
connu soit `None` — aucune string arbitraire ne peut atteindre le réseau.

### 4.3 — PEP 8 + type hints cleanup

Hors scope strict de sécurité mais fait pendant la passe d'édition :
- Imports réordonnés PEP 8 dans `chainlink_oracle.py` (stdlib / third-party / local)
- Docstrings `get_stock_price`/`get_crypto_price` mises à jour pour refléter
  Surgery B (plus de "source 5 : fallback statique")
- Annotations `list | None`, `float | None` explicites sur les signatures
  modifiées (Python 3.12 target)

---

## 5. Audits proactifs — résultats

### 5.1 — Hardcoded secrets (grep)

Pattern scanné :
```
grep -iE '(api[_-]?key|secret|password|token)\s*=\s*"[^"$]{10,}"' oracleforge/backend/
grep -iE 'Bearer\s+[A-Za-z0-9]' oracleforge/backend/
```
**Résultat** : 0 match. Les Pyth feed IDs en dur dans `EQUITY_FEEDS` /
`CRYPTO_FEEDS` / `CHAINLINK_FEEDS` ne sont pas des secrets — ce sont des
identifiants **publics** des feeds Pyth / adresses on-chain de contrats
Chainlink Base. Ils sont documentés sur `docs.pyth.network` et
`docs.chain.link`.

### 5.2 — Weak crypto

Pattern scanné : `grep -iE '(md5|sha1|hashlib\.(md5|sha1))' oracleforge/backend/`
**Résultat** : 0 match.

Le seul usage de `hashlib` dans MAXIA V12 était pour des **cache keys non
sécurisés** (moyenne #2 dans l'audit V12), pas pour de la crypto. Les
modules extraits n'utilisent aucun hash.

### 5.3 — Logs potentiellement leaky (api-key dans RPC URL)

`MAXIA V12/backend/core/config.py` avait un commentaire "V-20: Helius requires
API key in URL (no header option). Never log this URL." — un vrai risque.

Dans `oracleforge/backend/core/config.py` le helper `get_rpc_url_safe()` est
exposé et le docstring de `get_rpc_url()` rappelle la contrainte :
```python
def get_rpc_url() -> str:
    """Return the highest-priority Solana RPC URL currently configured.

    Never log the returned URL: it may contain an API key in the query string.
    Use get_rpc_url_safe() for log lines.
    """
```

**Vérification** : `grep 'get_rpc_url()' oracleforge/backend/` → 1 seul site
d'utilisation (`price_oracle.py` ligne 289, **utilisé pour fetch HTTP, pas
pour log**). Aucun call à `get_rpc_url()` n'est passé à `logger.*`, `print`,
ou `f"..."` dans un log.

### 5.4 — SSRF

Les URLs externes du code extrait sont **toutes hardcodées** (constantes de
module) :
- `https://mainnet.base.org` (Base mainnet RPC, via `BASE_RPC_URL` env)
- `https://hermes.pyth.network` (Pyth Hermes, via `PYTH_HERMES_URL` env)
- `https://api.coinpaprika.com/v1/tickers`
- `https://api.coingecko.com/api/v3/simple/price`
- `https://query1.finance.yahoo.com/v8/finance/spark`
- `https://query1.finance.yahoo.com/v7/finance/quote`
- `https://finnhub.io/api/v1/quote`

Les parts dynamiques sont des tickers / feed_ids contrôlés par des dicts
statiques (`TOKEN_MINTS`, `EQUITY_FEEDS`, `CRYPTO_FEEDS`, `CHAINLINK_FEEDS`,
`SYM_TO_COINPAPRIKA`, `SYM_TO_COINGECKO`) **jamais par l'utilisateur final**.
La seule partie user-controlled qui touche une URL est `feed_id` dans
`get_pyth_price`, désormais validée 64-char hex (§4.2).

Les env vars `BASE_RPC_URL`, `PYTH_HERMES_URL`, `SOLANA_RPC`, `CHAINSTACK_RPC`
sont **côté opérateur** (set par l'admin du service), pas user-controlled.
Elles peuvent pointer vers un endpoint privé sans risque d'exfiltration.

**Aucun risque SSRF identifié.**

### 5.5 — Input validation

| Fonction publique | Argument | Validation |
|---|---|---|
| `get_pyth_price(feed_id, hft)` | `feed_id` | **Ajouté** 64-char hex (§4.2) |
| `get_pyth_price` | `hft` | `bool` par typage |
| `verify_price_onchain(feed_id, ...)` | `feed_id` | Transitive via `get_pyth_price` |
| `get_stock_price(symbol)` | `symbol` | `.upper()` + dict lookup (safe) |
| `get_crypto_price(symbol)` | `symbol` | `.upper()` + dict lookup (safe) |
| `get_batch_prices(symbols)` | `symbols` | Iterable, lookup safe. Taille cappée à 50 dans la route Phase 3 (`api_batch_prices`) |
| `get_stock_price_finnhub(symbol)` | `symbol` | `.upper()` + passé à l'API Finnhub |
| `get_chainlink_price(symbol)` | `symbol` | `.upper()` + dict lookup |
| `verify_price_chainlink(symbol, expected_price, ...)` | `symbol`, `expected_price` | dict lookup + numeric |
| `get_prices(symbols=None)` | `symbols` | list ou None, lookup dans dict |

---

## 6. Items différés — résolution Phase 3

La Phase 2 avait différé 5 items critiques (C5, C6, H7, H9, H11) à la Phase 3
parce que la couche API FastAPI n'existait pas encore. Tous sont **RÉSOLUS**
dans la Phase 3 commitée avec ce document.

| Item V12 | Phase 2 status | Phase 3 résolution | Fichier |
|---|---|---|---|
| **C5** — validation startup | Différé | **RÉSOLU**. `core/config.py` lève `RuntimeError` si `ENV` absent. En staging/prod, `API_KEY_PEPPER` (>=32 chars) et `DB_PATH` sont aussi requis. Le process refuse de démarrer. | `backend/core/config.py` |
| **C6** — JWT_SECRET persistant | Différé | **N/A** (décision Phase 3 #3). MAXIA Oracle n'utilise pas JWT — `X-API-Key` opaque hashé avec pepper SHA256 côté serveur. Aucun secret de session à persister. | `backend/core/auth.py` |
| **H7** — rate limiting persistant | Différé | **RÉSOLU**. `core/rate_limit.py` implémente un rate limiter DB-backed SQLite (fixed window 24h, 100 req/jour/clé). Le compteur survit aux restarts. Un 2e rate limiter IP-based gate `/api/register` (1/60s) pour empêcher le mass-mint de clés. | `backend/core/rate_limit.py` |
| **H9** — security headers | Différé | **RÉSOLU**. `core/security.py` = Starlette middleware qui injecte `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Permissions-Policy` sur toutes les responses. `HSTS` conditionnel si `X-Forwarded-Proto: https` (évite de s'HSTS-piéger sur HTTP en dev). | `backend/core/security.py` |
| **H11** — Swagger en prod | Différé | **RÉSOLU**. `main.py` instancie `FastAPI(docs_url=None if IS_PROD else "/docs", redoc_url=None if IS_PROD else "/redoc", openapi_url=None if IS_PROD else "/openapi.json")`. Aucune surface Swagger en prod. | `backend/main.py` |
| **H10** — XSS via innerHTML | Phase 8 | Différé Phase 8 (landing statique, à auditer à la livraison) | — |

### Tests de validation Phase 3

Le fichier `backend/tests/test_phase3_api.py` contient **16 tests pytest** qui
exercent chaque item sécurité :

| Test | Item V12 validé |
|---|---|
| `test_security_headers_present` | H9 — vérifie les 5 headers + absence HSTS sur HTTP |
| `test_daily_rate_limit_exhausts_to_429` | H7 — 100 req consécutives OK, 101e = 429 |
| `test_register_rate_limit_per_ip` | H7 bis — 1 register OK, 2e = 429 avec `Retry-After` |
| `test_price_requires_auth` | auth obligatoire sans clé = 401 |
| `test_price_rejects_invalid_key` | auth valide seulement avec clé active en DB |
| `test_price_rejects_invalid_symbol` | input validation `^[A-Z0-9]{1,10}$` |
| `test_batch_validates_symbols` | Pydantic 422 sur symbole non-conforme |
| `test_batch_caps_at_50` | Pydantic 422 sur >50 symboles |
| `test_safe_error_never_leaks` | H12 — `safe_error()` ne leak pas la string d'exception |

Résultat pytest : **16 passed / 16** (local, 2.15s).

### Tests live Phase 3 (uvicorn + curl)

`uvicorn main:app` démarre avec `ENV=dev`, `API_KEY_PEPPER=...`. Tests manuels :
- `GET /health` → 200, disclaimer présent, headers sécurité OK
- `POST /api/register` → 201, retourne `mxo_...` clé, disclaimer
- `GET /api/price/BTC` avec clé → 3 sources (Pyth + Chainlink + CoinPaprika), divergence 0.28 %
- `POST /api/prices/batch` (BTC, ETH, SOL) → 3 prix via Pyth, confidence < 0.07 %
- `GET /api/sources` → 6 sources listées
- Sans clé ou clé bidon → 401

---

## 7. Checkpoints 2 + 3 — état des questions du plan

### Phase 2 (plan §3 Phase 2 Checkpoint)

| Question du plan | Phase 2 | Phase 3 |
|---|---|---|
| Aucun secret hardcodé ? | ✅ | ✅ |
| Validation startup en place pour tous les secrets critiques ? | ⚠️ Différé | ✅ **RÉSOLU** via `core/config.py` |
| `safe_error()` utilisé partout ? | ✅ | ✅ + exception handler global `main.py` |
| Security headers configurés ? | ⚠️ Différé | ✅ **RÉSOLU** via `core/security.py` middleware |

### Phase 3 additionnels (pas dans le plan, ajoutés pour durcissement)

| Question | Réponse |
|---|---|
| Les API keys sont-elles stockées en clair ? | ❌ **Non** — seul `SHA256(raw_key + pepper)` est persisté. Le pepper server-side empêche les rainbow tables même si la DB fuite. |
| Rate limiting survit-il à un restart ? | ✅ **OUI** — SQLite DB-backed. Les compteurs persistent. |
| Swagger exposé en prod ? | ❌ **Non** — `docs_url=None, redoc_url=None, openapi_url=None` quand `ENV=prod`. |
| `/api/register` peut-il être abusé par un bot ? | ❌ **Non** — 1 register / 60s / IP (via `register_limit` table). |
| Les erreurs internes leakent-elles des paths / secrets ? | ❌ **Non** — `safe_error()` côté services oracle + exception handler global côté FastAPI, tous deux loggent le traceback serveur-side uniquement. |
| Les headers `X-RateLimit-*` sont-ils présents dans les 429 ? | ✅ `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. |
| Le disclaimer est-il présent sur **toutes** les routes ? | ✅ Testé via pytest, helper `wrap_with_disclaimer` / `wrap_error` appelé explicitement par chaque route. |

**Phase 2 est validée** et tous les items différés sont résolus en Phase 3.
**Phase 3 est validée** après 16/16 pytest green et tests live curl end-to-end
OK (Pyth + Chainlink + CoinPaprika cross-validation divergence 0.28 % sur BTC).
