# MAXIA Oracle — Phase 6 audit (SDKs + framework plugins)

**Phase 6 span** : 15–16 April 2026
**Plan reference** : `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` §3 Phase 6
**Decisions reference** : memory `project_maxia_oracle_decisions.md`
**Scope** : publish a thin, dependency-light client surface over the Phase 3+4+5
backend so third-party agents can call MAXIA Oracle without talking raw HTTP.
Two first-party SDKs (Python, TypeScript) plus four adapter plugins for the
current dominant agent frameworks (LangChain, CrewAI, AutoGen, LlamaIndex).

This document is the Phase 6 deliverable (per plan §3 checkpoint 6).

---

## 1. Verdict global

**Phase 6 is complete on its six functional sub-phases (6.1 → 6.7).** Only the
audit document itself (6.8) remains — this file closes it.

| Sub-phase | Scope | Commit | Status |
|---|---|---|---|
| 6.1 | Python SDK `maxia-oracle` + stdio MCP bridge | `2413e3f` | ✅ |
| 6.2 | TypeScript SDK `@maxia/oracle` | `3a9b502` | ✅ |
| 6.3 | LangChain plugin `langchain-maxia-oracle` | `9cd6f10` | ✅ |
| 6.4 | CrewAI plugin `crewai-tools-maxia-oracle` | `9cd6f10` | ✅ |
| 6.5 | AutoGen plugin `autogen-maxia-oracle` | `9cd6f10` | ✅ |
| 6.6 | LlamaIndex plugin `llama-index-tools-maxia-oracle` | `4af6c56` | ✅ |
| 6.7 | Plugin pytest fix (`--import-mode=importlib`) + full run | `4af6c56` | ✅ |
| 6.8 | This audit doc + memory updates | (this commit) | ✅ |

**Test totals across the full stack after Phase 6** :

| Bucket | Tests | Runtime |
|---|---|---|
| Backend (pytest) | 57 | ~2 s |
| Python SDK (pytest, `MockTransport`) | 17 | 0.11 s |
| TypeScript SDK (vitest, injected fetch) | 17 | 0.34 s |
| LangChain plugin (pytest, offline) | 12 | 0.17 s |
| CrewAI plugin (pytest, offline) | 10 | 8 s |
| AutoGen plugin (pytest, offline) | 9 | 0.77 s |
| LlamaIndex plugin (pytest, offline) | 9 | 1.10 s |
| **Grand total** | **131** | — |

All offline. Zero network calls in CI. The Python SDK ran one live smoke test
against a subprocess `maxia-oracle-mcp` → local uvicorn backend; the TypeScript
SDK ran one live smoke test via `node dist/index.js` → same backend. Both
produced real BTC prices from multiple sources plus an on-chain Chainlink
round-trip, and the numbers agree within < 0.3 %.

---

## 2. Files created

Everything Phase 6 added lives under `oracleforge/sdk/` (SDKs) and
`oracleforge/plugins/` (framework adapters). The backend itself was not
touched during Phase 6 — the Phase 3/4/5 REST and MCP surfaces are the stable
target.

### 2.1 — Python SDK (`oracleforge/sdk/python/`)

| File | Lines | Purpose |
|---|---|---|
| `src/maxia_oracle/__init__.py` | 39 | Public re-exports: `MaxiaOracleClient`, exception hierarchy, version |
| `src/maxia_oracle/client.py` | 324 | Sync `httpx.Client`-based SDK with 9 methods (see §4) |
| `src/maxia_oracle/exceptions.py` | 87 | `MaxiaOracleError` base + 6 subclasses (auth, rate-limit, payment, transport, schema, symbol) |
| `src/maxia_oracle/mcp_bridge.py` | 353 | stdio MCP server that forwards every `tools/call` to the backend via the sync client |
| `tests/test_client.py` | 290 | 17 pytest tests via `httpx.MockTransport` |
| `pyproject.toml` | — | `hatchling`, version `0.1.0`, Apache-2.0, console script `maxia-oracle-mcp` |
| `README.md` | — | Install + quick-start + MCP bridge docs |

Runtime deps : `httpx>=0.27.0,<1.0`, `mcp>=1.27.0,<2.0`. Dev deps :
`pytest`, `pytest-asyncio`.

### 2.2 — TypeScript SDK (`oracleforge/sdk/typescript/`)

| File | Lines | Purpose |
|---|---|---|
| `src/index.ts` | 43 | Public re-exports (ESM) |
| `src/client.ts` | 284 | Async client with 9 methods, native `fetch`, zero runtime deps |
| `src/errors.ts` | 76 | Typed error hierarchy mirroring the Python SDK (uses `Object.setPrototypeOf` for reliable `instanceof`) |
| `src/types.ts` | 91 | Response shapes for every endpoint, strict |
| `test/client.test.ts` | 275 | 17 vitest tests, `fetch` injected per test |
| `package.json` | — | Scoped `@maxia/oracle`, version `0.1.0`, Node ≥18, ESM-only |

Runtime deps : **none** (Node 18+ global `fetch`). Dev deps : `typescript`,
`vitest`, `@types/node`.

### 2.3 — LangChain plugin (`oracleforge/plugins/langchain-maxia-oracle/`)

| File | Lines | Purpose |
|---|---|---|
| `src/langchain_maxia_oracle/__init__.py` | 43 | Re-exports the 8 `BaseTool` subclasses + `get_all_tools` |
| `src/langchain_maxia_oracle/tools.py` | 266 | `_MaxiaOracleTool` base + 8 concrete tools, `pydantic` input schemas |
| `tests/test_tools.py` | 173 | 12 offline tests, `MagicMock` client |

Deps : `maxia-oracle>=0.1.0,<1`, `langchain-core>=0.3,<1`, `pydantic>=2.0,<3`.

### 2.4 — CrewAI plugin (`oracleforge/plugins/crewai-tools-maxia-oracle/`)

| File | Lines | Purpose |
|---|---|---|
| `src/crewai_tools_maxia_oracle/__init__.py` | 43 | Re-exports the 8 `BaseTool` subclasses + `get_all_tools` |
| `src/crewai_tools_maxia_oracle/tools.py` | 216 | Same pattern as LangChain, but base class is `crewai.tools.BaseTool` |
| `tests/test_tools.py` | 120 | 10 offline tests, `tool.run(**kwargs)` dispatch |

Deps : `maxia-oracle>=0.1.0,<1`, `crewai>=0.80,<1`, `pydantic>=2.0,<3`.

### 2.5 — AutoGen plugin (`oracleforge/plugins/autogen-maxia-oracle/`)

| File | Lines | Purpose |
|---|---|---|
| `src/autogen_maxia_oracle/__init__.py` | 23 | Re-exports `get_all_tools` |
| `src/autogen_maxia_oracle/tools.py` | 164 | 8 local callables wrapped in `autogen_core.tools.FunctionTool` |
| `tests/test_tools.py` | 133 | 9 offline tests, async via `pytest-asyncio`, `tool.run_json(...)` |

Deps : `maxia-oracle>=0.1.0,<1`, `autogen-core>=0.4,<1`, `pydantic>=2.0,<3`.
Dev deps add `pytest-asyncio` because AutoGen's tool interface is async.

### 2.6 — LlamaIndex plugin (`oracleforge/plugins/llama-index-tools-maxia-oracle/`)

| File | Lines | Purpose |
|---|---|---|
| `src/llama_index_tools_maxia_oracle/__init__.py` | 23 | Re-exports `get_all_tools` |
| `src/llama_index_tools_maxia_oracle/tools.py` | 164 | 8 local callables wrapped via `FunctionTool.from_defaults(...)` |
| `tests/test_tools.py` | 113 | 9 offline tests, sync via `tool.call(**kwargs)` → `ToolOutput.content` |

Deps : `maxia-oracle>=0.1.0,<1`, `llama-index-core>=0.11,<1`, `pydantic>=2.0,<3`.

### 2.7 — Shared pytest config

| File | Purpose |
|---|---|
| `plugins/pytest.ini` | `addopts = --import-mode=importlib`. Required because all four plugins ship the same `tests/test_tools.py` basename; default pytest collection errors on the duplicate module names. With importlib mode, `python -m pytest plugins/` walks all four suites in one command (40/40 green in ~7 s). |

### 2.8 — Totals

~3 350 lines of Python + TypeScript added in Phase 6, spread across 7 independently
publishable packages. Zero backend changes.

---

## 3. Design decisions — implementation notes

The Phase 6 decisions validated with Alexis before coding :

### D1 — One package per framework, not one mega-bundle

Option B validated 15 April. Each plugin has its own `pyproject.toml`, own
version, own PyPI listing. Rationale :

- Users never install `crewai` just because they want `langchain` tools.
- Framework SDKs (LangChain, CrewAI, AutoGen, LlamaIndex) make incompatible
  breaking changes at their own cadence. Pinning them separately avoids
  coupling unrelated user code to unrelated framework releases.
- Plugin names match each framework's own community naming convention
  (`langchain-<vendor>`, `crewai-tools-<vendor>`, `autogen-<vendor>`,
  `llama-index-tools-<vendor>`).

The cost is four small READMEs and four small pyproject files instead of one.
Accepted.

### D2 — SDK as single shared dependency

All four plugins depend on `maxia-oracle>=0.1.0,<1`. The plugin code is a
framework-specific *adapter layer* that translates a framework's tool-calling
convention to `MaxiaOracleClient` method calls. The HTTP client itself (auth
header, retry shape, error types) lives in the SDK and is reused.

Consequence : **fixing a transport bug in the SDK fixes all four plugins at
once** without shipping five releases. A new oracle method becomes available
to all four plugins as soon as we update `get_all_tools` in each adapter.

### D3 — Eight tools, not nine

The SDK exposes 9 methods (see §4). The plugins expose only **8 tools**. The
one excluded from the tool surface is `register()` — creating an API key
should be a one-time operator step, not an action an autonomous agent takes
mid-conversation. An agent that calls `register` would generate new keys on
every run, bypassing the daily quota and inflating our key table. So `register`
stays on the SDK (for operators / install scripts) but never makes it into an
agent's tool list.

This matches the Phase 5 MCP server, which also exposes 8 tools and never
exposes `register`.

### D4 — No `get_price_history`, no `subscribe_price_stream` in V1

Already decided in Phase 5 (both would require infrastructure not yet in
Phase 3: a time-series table + an SSE or websocket channel). Not added in
Phase 6 SDK/plugins either — the SDK and plugin surfaces stay in lockstep with
the backend's REST and MCP surfaces. Reintroducing either in V1.1 will add
one SDK method + four tool entries without breaking changes.

### D5 — LlamaIndex included, Eliza and Vercel deferred

Validated 15 April during Phase 6 reco. The four frameworks shipped
(LangChain, CrewAI, AutoGen, LlamaIndex) cover the vast majority of current
Python agent deployments and give broad PyPI visibility. Eliza (TypeScript,
crypto-native agents) and Vercel AI SDK skills were considered but deferred
post-Phase 9 pending demand. If we see traction in a given ecosystem we can
spin a plugin out of the shared pattern in roughly half a day.

### D6 — Sync Python SDK, async TypeScript SDK

Python SDK uses `httpx.Client` (sync), because almost every Python agent
framework expects sync tool functions. The MCP bridge wraps them in
`asyncio.to_thread` when needed. TypeScript SDK is async-only because
`fetch` is async-only in the platform. Parity of *semantics*, not of
concurrency model.

### D7 — Strict TypeScript, zero runtime dependencies

The TS SDK compiles under `tsc --strict` with no `any`. It has no runtime
dependencies beyond what ships with Node 18+. This keeps the supply-chain
surface minimal and lets the SDK ship in browser and edge-runtime contexts
(Cloudflare Workers, Vercel Edge) without polyfills.

### D8 — Never raise from a tool, always return structured disclaimer

Tools do not raise. They return either `{"data": ..., "disclaimer": ...}`
on success or `{"error": ..., "disclaimer": ...}` on failure. The disclaimer
is the Phase 2 disclaimer string (not investment advice, not custody, etc.),
and it is present on *every* tool response — success path and error path.
Framework adapters render the returned dict as JSON text so the LLM sees the
disclaimer in every turn.

Rationale : LLMs sometimes strip error states and retry blindly. A
plain-text disclaimer that appears *inside* the tool output is harder to
launder than a separate HTTP header or log line.

---

## 4. Tool surface — the 9/8 methods

The SDK exposes 9 methods. The four plugins and the Phase 5 MCP server each
expose 8 tools (all except `register`).

| # | SDK method | Plugin tool name | REST route | MCP tool | HTTP verb |
|---|---|---|---|---|---|
| 1 | `register()` | *(not exposed)* | `POST /api/register` | *(not exposed)* | POST |
| 2 | `health()` | `maxia_oracle_health_check` | `GET /health` | `health_check` | GET |
| 3 | `price(symbol)` | `maxia_oracle_get_price` | `GET /api/price/{symbol}` | `get_price` | GET |
| 4 | `prices_batch(symbols)` | `maxia_oracle_get_prices_batch` | `POST /api/prices/batch` | `get_prices_batch` | POST |
| 5 | `sources()` | `maxia_oracle_get_sources_status` | `GET /api/sources` | `get_sources_status` | GET |
| 6 | `cache_stats()` | `maxia_oracle_get_cache_stats` | `GET /api/cache/stats` | `get_cache_stats` | GET |
| 7 | `confidence(symbol)` | `maxia_oracle_get_confidence` | `GET /api/confidence/{symbol}` | `get_confidence` | GET |
| 8 | `list_symbols()` | `maxia_oracle_list_supported_symbols` | `GET /api/symbols` | `list_supported_symbols` | GET |
| 9 | `chainlink_onchain(symbol)` | `maxia_oracle_get_chainlink_onchain` | `GET /api/chainlink/{symbol}` | `get_chainlink_onchain` | GET |

The tool names across the four plugins are **identical** (same snake_case,
same `maxia_oracle_` prefix), so an agent author who migrates from, say,
LangChain to CrewAI only needs to swap the import — the tool names and
inputs the LLM sees are unchanged.

### 4.1 — Typed inputs

All tools with parameters accept pydantic input schemas :

- `SymbolInput(symbol: str)` — with regex `^[A-Z0-9]{1,10}$` applied.
- `SymbolsBatchInput(symbols: list[str])` — with `max_length=20` applied.
- `EmptyInput` — for the six tools that take no arguments.

The LangChain and CrewAI plugins surface these schemas through `args_schema`,
so the LLM sees strict JSON parameter schemas. The AutoGen and LlamaIndex
plugins use `FunctionTool`, which generates a schema from the Python type
hints — same effect, different code path.

### 4.2 — Typed outputs

Every SDK method returns a typed dict (Python `TypedDict`-style) or a typed
interface (TypeScript). The Phase 5 MCP server and the four plugins all
convert those dicts to JSON text before returning to the LLM, so the LLM
always sees a stable JSON shape.

Example `price` response :

```json
{
  "symbol": "BTC",
  "price": 73912.42,
  "sources": [
    {"name": "pyth", "price": 73901.5, "weight": 0.4, "age_ms": 1240},
    {"name": "chainlink", "price": 73920.0, "weight": 0.4, "age_ms": 2380},
    {"name": "coingecko", "price": 73915.3, "weight": 0.2, "age_ms": 4700}
  ],
  "divergence_pct": 0.025,
  "timestamp": 1713280123,
  "disclaimer": "Data feed only. Not investment advice. No custody. No KYC."
}
```

---

## 5. Pattern comparison across frameworks

The four plugins split into two implementation patterns because the frameworks
themselves split that way.

### 5.1 — `BaseTool` subclass pattern (LangChain, CrewAI)

Both LangChain and CrewAI expose tools as `BaseTool` subclasses with an
`args_schema` pydantic model and a `_run(**kwargs)` method. Our plugin
defines a private `_MaxiaOracleTool(BaseTool)` base that holds the shared
client + `_fmt()` helper, then defines 8 concrete subclasses :

```
_MaxiaOracleTool (shared client, shared _fmt)
  ├── MaxiaOracleGetPriceTool       (args_schema=SymbolInput)
  ├── MaxiaOracleGetPricesBatchTool (args_schema=SymbolsBatchInput)
  ├── MaxiaOracleGetSourcesStatusTool   (args_schema=EmptyInput)
  ├── MaxiaOracleGetCacheStatsTool      (args_schema=EmptyInput)
  ├── MaxiaOracleGetConfidenceTool  (args_schema=SymbolInput)
  ├── MaxiaOracleListSupportedSymbolsTool (args_schema=EmptyInput)
  ├── MaxiaOracleGetChainlinkOnchainTool  (args_schema=SymbolInput)
  └── MaxiaOracleHealthCheckTool        (args_schema=EmptyInput)
```

`get_all_tools(api_key, base_url, client)` instantiates all 8 with a shared
client. If no client is passed, a lazy `_default_client()` reads
`MAXIA_ORACLE_API_KEY` / `MAXIA_ORACLE_BASE_URL` from the environment.

LangChain tests dispatch with `tool.invoke({"symbol": "BTC"})`.
CrewAI tests dispatch with `tool.run(symbol="BTC")`. Everything else is identical.

### 5.2 — `FunctionTool` wrapper pattern (AutoGen, LlamaIndex)

Both AutoGen 0.4+ and LlamaIndex 0.11+ expose tools via a `FunctionTool`
that *wraps a callable*. Our plugin defines 8 nested functions inside
`get_all_tools()` so each closure captures the same shared client, then
builds 8 `FunctionTool` instances from those callables :

```python
def get_all_tools(..., client=None) -> list[FunctionTool]:
    shared = client or _default_client()

    def maxia_oracle_get_price(symbol: str) -> str:
        """Multi-source aggregated price for one symbol. Not investment advice."""
        return _fmt(shared.price(symbol))

    # ... 7 more nested callables

    return [
        FunctionTool(func, name=func.__name__, description=func.__doc__.strip())
        for func in (maxia_oracle_get_price, ..., maxia_oracle_health_check)
    ]
```

The LlamaIndex variant is almost line-for-line identical except the
constructor is `FunctionTool.from_defaults(fn=func, name=..., description=...)`
and `tool.call(**kwargs)` returns a `ToolOutput` whose `.content` is the
string the LLM sees (AutoGen's `run_json` returns the string directly).

### 5.3 — Why not one pattern everywhere ?

We considered forcing a single pattern via a common base class. Rejected :
each framework has tight integration with its own tool wrapper (serialization
to OpenAI function schemas, parallel execution, streaming). Wrapping
framework primitives in our own abstractions would break framework features
users pay to get. One adapter per framework, each ≤ 270 lines, is cheaper to
maintain than a leaky abstraction.

### 5.4 — Source line budget per plugin

| Plugin | `tools.py` | `__init__.py` | `tests/test_tools.py` | Tests |
|---|---|---|---|---|
| LangChain | 266 | 43 | 173 | 12 |
| CrewAI | 216 | 43 | 120 | 10 |
| AutoGen | 164 | 23 | 133 | 9 |
| LlamaIndex | 164 | 23 | 113 | 9 |

LangChain and CrewAI are larger because the `BaseTool` subclass pattern forces
one class per tool (8 classes × ~15 lines of subclass declaration). The
`FunctionTool` pattern keeps each tool at ~10 lines of closure + docstring.
Both are fine — the count does not affect maintenance cost because the
per-tool code is boilerplate that never needs to change.

---

## 6. Tests — coverage and shape

### 6.1 — SDK tests

**Python SDK** (17 tests, `httpx.MockTransport`) :

- 9 happy-path round-trips (one per method).
- 6 error mappings (401 → `AuthError`, 402 → `PaymentRequired`, 429 → `RateLimited`, 422 → `SchemaError`, 404 → `SymbolNotFound`, timeout → `TransportError`).
- 2 config paths (env-var resolution, explicit `api_key` override).

**TypeScript SDK** (17 tests, injected `fetch`) :

Mirror of the Python SDK. Error classes use `Object.setPrototypeOf` so
`instanceof MaxiaOracleError` is reliable in transpiled output (caveat for
ES5 targets — not a concern here since we target ES2022).

### 6.2 — Plugin tests

All four plugin suites follow the same shape :

- Instantiation : `get_all_tools` returns 8 tools with the expected names.
- Schema check : each parameterised tool's input schema rejects an empty
  symbol / a non-uppercase symbol.
- Dispatch : for every tool, feed in a `MagicMock` client that returns a
  canned dict, invoke the tool, confirm the returned string contains the
  canned data and the disclaimer string.
- Error passthrough : when the mock client raises `MaxiaOracleError`, the
  tool returns an error-shaped JSON string (never raises out of the tool
  boundary).

Run them all at once :

```
cd oracleforge/plugins
python -m pytest -q
# 40 passed in ~7s
```

This single command exercises all 40 plugin tests thanks to
`plugins/pytest.ini` setting `--import-mode=importlib` (§2.7).

### 6.3 — Live smoke tests (Phase 6.7)

Two live smoke tests ran once, not in CI :

1. **Python SDK via MCP bridge** — `pip install -e oracleforge/sdk/python`,
   started `maxia-oracle-mcp` as a subprocess, drove it with stdin JSON-RPC
   `initialize` → `tools/list` → `tools/call(get_price, BTC)` against a live
   `uvicorn main:app --port 8003` backend. All 8 tools listed; real BTC
   price returned with 3 sources and a < 0.25 % divergence.

2. **TypeScript SDK** — `npm run build` then `node dist/index.js` calling
   all 9 methods sequentially against the same live backend. Real prices
   returned; BTC divergence 0.23 %; Chainlink on-chain read matched the
   multi-source aggregate within 0.1 %.

Neither smoke test is automated — they are one-time proofs of end-to-end
plumbing. The per-commit test suite stays offline.

---

## 7. Non-goals and drops

Enforced structurally at the SDK/plugin layer (not just by policy):

- **No order routing.** The SDKs have no `place_order`, `cancel_order`,
  `get_positions`. Not in the REST API either. Cannot be added without a
  regulated-broker license.
- **No custody.** No wallet generation, no private key handling, no balance
  reads. The only wallet-shaped value in the whole codebase is the
  public treasury address for x402 payments.
- **No swap / bridge / yield.** No `swap()`, `get_yield()`, `get_apr()`.
- **No investment advice.** Every tool response ships the Phase 2 disclaimer
  inline so the LLM is reminded on every turn.
- **No KYC capture.** Not in SDK, not in plugins, not in the backend's
  `/api/register`. `register()` takes no identity fields.
- **No marketplace or intermediation.** The Phase 4 x402 middleware is
  direct-sale only; the SDKs do not sell third-party data, do not route
  payments to third parties, do not hold escrow.

Dropped from V1 for other reasons :

- **`get_price_history`** — needs a time-series table in Phase 3 we did not
  build. Reserved for V1.1.
- **`subscribe_price_stream`** — needs SSE or WS infra. Reserved for V1.1.
- **Eliza plugin** — TypeScript, crypto-native, deferred post-Phase 9
  pending demand.
- **Vercel AI SDK skills** — deferred post-Phase 9 pending demand.

---

## 8. Distribution plan (Phase 9 preview)

The six publishable packages from Phase 6 :

| Registry | Package | Version |
|---|---|---|
| PyPI | `maxia-oracle` | 0.1.0 |
| PyPI | `langchain-maxia-oracle` | 0.1.0 |
| PyPI | `crewai-tools-maxia-oracle` | 0.1.0 |
| PyPI | `autogen-maxia-oracle` | 0.1.0 |
| PyPI | `llama-index-tools-maxia-oracle` | 0.1.0 |
| npm | `@maxia/oracle` | 0.1.0 |

Publishing is deliberately deferred to Phase 9 so we can :

1. Deploy the backend to `oracle.maxiaworld.app` (Phase 7) so the SDK's
   default `base_url` points at a live host before users pip-install.
2. Put the landing page live (Phase 8) so the PyPI/npm description URLs
   resolve to something useful.
3. Submit the MCP server to `mcpmarket.com`, MCP-Hive, and Glama
   simultaneously (Phase 9), maximising the single publication window.

Version 0.1.0 across the board. All packages Apache-2.0. All packages
reference `https://oracle.maxiaworld.app` as the homepage.

---

## 9. Next steps

**Phase 7 — Deploy VPS** (next session) :

- Systemd unit for `uvicorn main:app --port 8003` with restart policy.
- Venv at `/home/ubuntu/oracleforge/backend/venv` from the pinned `requirements.txt`.
- Nginx reverse-proxy `oracle.maxiaworld.app:443` → `127.0.0.1:8003`.
- Let's Encrypt cert via `certbot`.
- DNS record for `oracle.maxiaworld.app` (to be created).
- Environment file `/etc/maxia-oracle/env` with `ENV=prod`,
  `API_KEY_PEPPER=...`, `X402_TREASURY_ADDRESS_BASE=...`, `X402_FACILITATOR_URL=...`.

**Phase 8 — Landing page static** :

- Single-page site under `oracleforge/landing/`. Hero + 8-tool list +
  install snippets for each of the six packages + link to `/docs` (Swagger).

**Phase 9 — Distribution** :

- Publish all 6 packages from Phase 6 to PyPI/npm under Apache-2.0.
- Submit MCP server to the three MCP marketplaces with an install transcript
  screenshot (Claude Desktop or `mcp-inspector` — see the open TODO in
  `project_maxia_oracle_progress.md`).
- Show HN post, X/Twitter thread.

**Optional catch-up — Phase 4 Step 10** :

Live USDC test on Base mainnet against the x402 middleware. Requires a small
prefunded test wallet (~$0.05 USDC + ~$0.05 ETH gas on Base) to prove the
facilitator + on-chain fallback paths end-to-end on a real chain.

---

## 10. Appendix — running the full test suite

From repo root :

```bash
# Backend (57 tests)
cd oracleforge/backend
source venv/Scripts/activate
ENV=dev API_KEY_PEPPER=test-pepper-that-is-more-than-32-chars-long \
  python -m pytest tests/ -q

# Python SDK (17 tests, no network)
cd ../sdk/python
python -m pytest tests/ -q

# TypeScript SDK (17 tests, no network)
cd ../typescript
npm test

# All four plugins in one command (40 tests, no network)
cd ../../plugins
python -m pytest -q
```

Expected aggregate : **131 passed**. Runtime end-to-end < 15 s on a
developer laptop, overwhelmingly dominated by CrewAI's import time.
