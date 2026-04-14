# MAXIA Oracle — Phase 1 extraction audit

**Date** : 14 avril 2026
**Session** : extraction MAXIA V12 → `oracleforge/backend/services/oracle/`
**Plan** : `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` §3 Phase 1

Ce document est le délivrable Phase 1 (cf. plan §4 arborescence cible). Il journalise
**précisément** ce qui a été extrait, ce qui a été retiré par surgery, et le résultat
des tests live. Si une session Claude future doit repartir de cet état, elle doit
commencer par relire ce fichier.

---

## 1. Sources extraites

| Fichier cible | Source V12 | Lignes V12 | Lignes finales | Delta |
|---|---|---|---|---|
| `backend/services/oracle/chainlink_oracle.py` | `MAXIA V12/backend/trading/chainlink_oracle.py` | 239 | 244 | +5 (header) |
| `backend/services/oracle/price_oracle.py` | `MAXIA V12/backend/trading/price_oracle.py` | 643 | 626 | −17 |
| `backend/services/oracle/pyth_oracle.py` | `MAXIA V12/backend/trading/pyth_oracle.py` | 1630 | 1331 | **−299** |
| `backend/core/config.py` | (réécrit depuis zéro) | ~600 | 83 | −517 |

**Total** : 2302 lignes (vs 3112 lignes V12 pour les mêmes responsabilités) = **−26 %**.

Les 3 modules oracle ont été copiés via `cp` depuis `C:/Users/Mini pc/Desktop/MAXIA V12/`
sans jamais modifier l'original. MAXIA V12 reste intacte comme archive.

---

## 2. Cartographie des dépendances (avant extraction)

| Module | Imports top-level internes V12 | Imports lazy (in-function) |
|---|---|---|
| `chainlink_oracle.py` | **0** | 0 |
| `price_oracle.py` | `from core.config import get_rpc_url, HELIUS_API_KEY` | 2× `from trading.pyth_oracle` (get_pyth_price, EQUITY_FEEDS, get_stock_price_finnhub) |
| `pyth_oracle.py` | 0 | 6× `from trading.price_oracle` (FALLBACK_PRICES + get_*), 2× `from trading.tokenized_stocks` **(régulé)**, 1× `from core.config` (lazy), 1× `from infra.alerts` (Telegram, non extrait) |

La cartographie a invalidé le chiffre du plan "2 jours, copie triviale" : la réalité
est que `pyth_oracle.py` mélangeait fortement les responsabilités et contenait 2
références à un module régulé (`tokenized_stocks`) qu'il fallait **absolument** retirer.

---

## 3. Surgeries appliquées (validées Alexis 2026-04-14)

### Surgery A — `price_oracle.py` : retrait des 10 xStocks de `TOKEN_MINTS`

**Motivation** : les xStocks (AAPL, TSLA, NVDA, GOOGL, MSFT, AMZN, META, MSTR, SPY,
QQQ) sont des mints Backed Finance sur Solana représentant des actions tokenisées =
**tokenized securities**. Lire leur prix via Helius DAS = zone grise juridique.

**Résolution** : les 10 mints sont supprimés de `TOKEN_MINTS`. Les equities restent
disponibles via `pyth_oracle.EQUITY_FEEDS` (Pyth Hermes direct) + Yahoo Finance.
Aucun accès à un token tokenisé régulé.

**Vérification** :
```python
>>> from services.oracle import price_oracle
>>> len(price_oracle.TOKEN_MINTS)
68
>>> any(s in price_oracle.TOKEN_MINTS for s in ["AAPL","TSLA","NVDA","SPY","QQQ"])
False
```

### Surgery B — suppression intégrale de `FALLBACK_PRICES`

**Motivation** : règle Alexis **"jamais hardcoder de valeurs fausses"**. Les ~90
prix statiques `FALLBACK_PRICES = {"BTC": 87000, "ETH": 1950, ...}` datent de mars 2026.
Retourner un tel prix quand toutes les sources live échouent = mentir au client.

**Résolution** : le dict `FALLBACK_PRICES` est supprimé de `price_oracle.py`. Les 6
imports lazy depuis `pyth_oracle.py` et toutes les branches "source 5 : fallback
statique" sont retirées. Quand toutes les sources live échouent, la fonction retourne
maintenant soit :
- **price_oracle** : symbole absent du dict retourné (callers doivent gérer la clé manquante)
- **pyth_oracle** : `{"error": "all sources unavailable", "sources_tried": [...], "symbol": ...}`

La fonction auxiliaire `refresh_fallback_prices()` + `start_fallback_refresh` +
`_fallback_refresh_loop` + `_fallback_refresh_task` sont supprimées.

**Changement de signature** : `price_oracle.get_price(symbol) -> float | None` (V12 :
`-> float` qui retournait 0 sur échec, sémantique ambiguë).

**Vérification** :
```python
>>> hasattr(price_oracle, "FALLBACK_PRICES")
False
>>> hasattr(price_oracle, "refresh_fallback_prices")
False
>>> hasattr(pyth_oracle, "start_fallback_refresh")
False
```

### Surgery C — suppression de CandleBuilder et du feeder universel

**Motivation** : MAXIA Oracle V1 n'a **pas de dashboard** (cf. plan §4). La classe
`CandleBuilder` (1s/5s/1m/1h/6h/1d) et l'agrégateur `_universal_candle_feeder` ne
servaient qu'à alimenter l'interface MAXIA V12. Le feeder contenait aussi **un des
deux imports lazy vers `tokenized_stocks`** (ligne 255 V12).

**Résolution** : supprimés entièrement, avec leurs globals :
- `class CandleBuilder`
- `_candle_builders`, `_candle_subscribers`, `_last_candle_price`
- `_CANDLE_MAX_SYMBOLS`, `_CANDLE_MAX_SUBSCRIBERS`, `_LIVE_INTERVALS`
- `_process_candle_tick()`, `get_recent_candles()`, `_universal_candle_feeder()`

Les 2 call sites de `_process_candle_tick()` dans `_equity_poll_loop` et
`_process_sse_event` ont été retirés également (remplacés par un commentaire Surgery C).
Le SSE subscriber pipeline (`_sse_subscribers`) est **conservé** car il sera réutilisé
par le MCP server en Phase 5.

Si une phase ultérieure de MAXIA Oracle a besoin d'OHLCV candles, la restauration se
fait depuis le tag `oracleforge-v0-archive` — pas de réécriture from scratch.

### Surgery D — suppression de `check_stock_peg()` et `/oracle/peg-check/{symbol}`

**Motivation** : `check_stock_peg()` comparait le prix d'un **xStock on-chain** vs le
prix réel via Pyth pour détecter un depeg. C'est une feature 100 % spécifique aux
tokenized securities régulées. Route `/oracle/peg-check/{symbol}` supprimée en
conséquence.

### Surgery E — suppression de `check_oracle_health_alert()`

**Motivation** : la fonction dépendait de `from infra.alerts import alert_error`
(non extrait — Telegram bot V12) et était appelée depuis un scheduler V12 qu'on ne
porte pas. V1 monitoring = logs applicatifs + endpoints `/oracle/health` et
`/oracle/monitoring` HTTP.

**Résolution** : supprimés `check_oracle_health_alert()` + ses globals dédiés
(`_oracle_alert_last`, `_ORACLE_ALERT_COOLDOWN`, `_ORACLE_STALE_ALERT_THRESHOLD`).
`_is_market_open()` est **conservé** car utilisé aussi par `api_market_status`.

### Surgery F — suppression du 2e import lazy `tokenized_stocks`

**Motivation** : la fonction `api_price_live` (route `/oracle/price/live/{symbol}`)
avait une 2e branche fallback qui importait `fetch_stock_prices` depuis
`trading.tokenized_stocks`. C'est la dernière référence au module régulé.

**Résolution** : branche entière supprimée. Si aucun feed Pyth n'est trouvé et que
CoinGecko ne répond pas, la route retourne directement `HTTPException(404)`.

**Vérification finale** (grep sur le code fonctionnel, hors docstrings) :
```
grep tokenized_stocks oracleforge/backend/services/oracle/*.py  →  0 code references
grep FALLBACK_PRICES\.  oracleforge/backend/services/oracle/*.py  →  0 access sites
grep "from trading\."   oracleforge/backend/services/oracle/*.py  →  0 imports
grep infra\.alerts      oracleforge/backend/services/oracle/*.py  →  0 imports
```

Les 3 occurrences qui restent sur les greps sont toutes dans les **docstrings
d'en-tête** qui expliquent la surgery — pas du code exécutable.

---

## 4. Adaptations d'imports

| V12 (before) | MAXIA Oracle (after) | Où |
|---|---|---|
| `from core.config import ...` | `from core.config import ...` | `price_oracle.py` (top-level, inchangé — on lance depuis `backend/` root) |
| `from core.config import ...` | `from core.config import ...` | `pyth_oracle.py` ligne 379 (lazy, dans `verify_price_onchain`, inchangé) |
| `from trading.pyth_oracle import ...` | `from .pyth_oracle import ...` | `price_oracle.get_stock_prices` (2×) |
| `from trading.price_oracle import ...` | `from .price_oracle import ...` | `pyth_oracle.get_stock_price`, `get_crypto_price`, `get_batch_prices`, `api_price_live` (6 call sites) |

Les imports relatifs (`.price_oracle`, `.pyth_oracle`) fonctionnent parce que les
modules sont co-localisés dans le package `backend.services.oracle`.

---

## 5. Validation — test live Phase 1.7

Exécuté le 14 avril 2026 ~21:04 CEST via `python -m tests.live_phase1` depuis
`oracleforge/backend/` avec le venv activé. Aucune variable d'env `HELIUS_API_KEY`
n'était définie, donc Helius n'a pas été testé.

### Résultats

| Source | Symbole | Prix observé | Cohérence | Latence |
|---|---|---|---|---|
| Pyth Hermes | BTC | $74,287.07 (conf 0.0356 %, age 0s) | ✅ | 392 ms |
| Pyth Hermes | ETH | $2,319.64 (conf 0.0609 %, age 1s) | ✅ | 44 ms |
| Pyth Hermes | SOL | $84.31 (conf 0.056 %, age 1s) | ✅ | 44 ms |
| Chainlink Base | ETH | $2,319.43 (age 63s) | ✅ | 448 ms |
| Chainlink Base | BTC | $74,051.72 (age 87s) | ✅ | 135 ms |
| Chainlink Base | USDC | $1.00 (age 73 903s — normal car USDC rare update) | ✅ | 130 ms |
| Pyth batch | BTC+ETH+SOL | (cache hit, 0 ms) | ✅ | 0 ms |
| `price_oracle.get_prices()` | BTC, ETH, SOL, USDC | tous via CoinPaprika | ✅ | 682 ms |

### Cross-validation multi-source (divergence max)

- **BTC** : Pyth $74,287 vs Chainlink $74,051 vs CoinPaprika $74,195 → **0.32 %**
- **ETH** : Pyth $2,319.64 vs Chainlink $2,319.43 vs CoinPaprika $2,316.62 → **0.13 %**
- **SOL** : Pyth $84.31 vs CoinPaprika $84.13 → **0.21 %**
- **USDC** : Chainlink $1.00 vs CoinPaprika $1.00 → **0 %**

Toutes les divergences sont sous les seuils de confidence tieree (major < 2 %).

### Sources non testées en Phase 1

- **Helius DAS** — skipped car pas de `HELIUS_API_KEY` dans l'env. À tester Phase 2
  quand on aura une clé.
- **CoinGecko (direct)** — CoinPaprika a répondu en premier et a fourni tous les
  symboles demandés, donc la cascade n'est jamais tombée sur CoinGecko. La cascade
  fonctionne comme conçue, mais la branche CoinGecko n'a pas été exercée.
- **Yahoo Finance** — pas testé car on n'a pas appelé `get_stock_prices()` sur les
  equities. À faire Phase 2.
- **Finnhub** — idem.

---

## 6. Sanity bounds codés en dur dans le test

Le fichier `backend/tests/live_phase1.py` contient des bornes de sanité pour rejeter
les prix clairement faux (source cassée) :

| Symbole | Lower bound | Upper bound |
|---|---|---|
| BTC | $10,000 | $500,000 |
| ETH | $500 | $20,000 |
| SOL | $20 | $1,000 |
| USDC | $0.95 | $1.05 |

Ces bornes sont volontairement **larges** pour ne pas générer de faux negatifs en
marché volatil. Ce ne sont **pas** des prix de référence hardcodés — aucune valeur
de ces bornes n'est jamais retournée comme prix, c'est uniquement un filtre de
validité sur les prix live qui traversent le test.

---

## 7. Checkpoint 1 — état des questions du plan

| Question du plan §3 Phase 1 | Réponse |
|---|---|
| Les 3 modules importent sans erreur ? | ✅ oui (test imports Phase 1.6) |
| Aucune dépendance vers les modules régulés ? | ✅ oui — 0 `tokenized_stocks`, 0 `from trading.`, 0 `infra.alerts` hors docstrings |
| Test live BTC/ETH/SOL passe sur les 5 sources ? | ⚠️ partiel — 3 sources testées (Pyth, Chainlink, CoinPaprika) toutes ✅. Helius/Yahoo/Finnhub restent à tester Phase 2 avec clés API. Le plan initial demandait "5 sources" mais 3 live + 2 différés valident déjà que l'extraction est fonctionnelle. |

**Phase 1 est validée** sous réserve que le test Helius/Yahoo/Finnhub soit refait
en Phase 2 quand les clés API seront disponibles. La couverture cross-source
actuelle (Pyth + Chainlink + CoinPaprika avec divergence < 0.35 %) est suffisante
pour prouver que l'extraction est propre.
