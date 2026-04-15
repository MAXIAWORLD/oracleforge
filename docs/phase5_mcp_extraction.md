# MAXIA Oracle — Phase 5 extraction audit (MCP server)

**Phase 5 date** : 15 April 2026
**Plan reference** : `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` §3 Phase 5
**Decisions reference** : memory `project_maxia_oracle_decisions.md` §"Phase 5 — 5 décisions design MCP server"
**Scope** : build a spec-compliant Model Context Protocol server that exposes
MAXIA Oracle's 8 V1 tools over both `stdio` (local installs, e.g. Claude
Desktop) and `HTTP SSE` (remote agents), reusing the existing oracle services
as Python calls rather than HTTP round-trips.

This document is the Phase 5 deliverable (per plan §3 checkpoint 5).

---

## 1. Verdict global

**Phase 5 is complete on all 9 steps.** 51 pytest tests pass (33 legacy
Phase 3/4 + 18 new Phase 5 MCP). Both transports have been verified
empirically:

- **stdio**: JSON-RPC round-trip (`initialize` → `tools/list` → `tools/call`)
  against a live `python -m mcp_server` subprocess returned all 8 tools and
  dispatched successfully on `health_check` and `list_supported_symbols`.
- **HTTP SSE**: End-to-end session against a live `uvicorn main:app`
  instance verified the 401 auth path, the 200 SSE handshake, the endpoint
  discovery, and the full JSON-RPC flow through the SSE stream for
  `initialize`, `notifications/initialized`, `tools/list`, and two
  `tools/call` invocations. The rate limit mechanic was stressed by
  patching the daily counter to `DAILY_LIMIT=100` and confirming the
  next `tools/call` returned `isError=true` with a structured payload
  (`error`, `limit`, `window_s`, `retry_after_s`, `reset_at`).

| Category | Status |
|---|---|
| Drop V12 custom MCP server (46 tools), adopt official SDK | ✅ |
| Install `mcp>=1.0` (got `1.27.0`), handle transitive FastAPI upgrade | ✅ |
| Package scaffold `mcp_server/` | ✅ |
| Extract `multi_source.py` helper (reused by REST + MCP paths) | ✅ |
| 8 V1 tools implemented in `tools.py` (never raise, always disclaim) | ✅ |
| `server.py` factory with JSON schemas and `isError` propagation | ✅ |
| stdio entry point `python -m mcp_server` | ✅ |
| HTTP SSE transport mounted on FastAPI (`/mcp/sse` + `/mcp/messages/`) | ✅ |
| X-API-Key auth on SSE handshake, daily quota ticked per `tools/call` | ✅ |
| pytest coverage on discovery, handler, rate limit, schema validation | ✅ |
| `mcp_server/README.md` with install docs for both transports | ✅ |
| Drop `get_price_history` + `subscribe_price_stream` (→ V1.1) | ✅ |

---

## 2. Files created or modified

### 2.1 — New modules

| File | Lines | Purpose |
|---|---|---|
| `backend/mcp_server/__init__.py` | 30 | Package marker + philosophy note |
| `backend/mcp_server/__main__.py` | 62 | stdio entry point (`python -m mcp_server`), sets `ENV=dev` default before importing `core.config` |
| `backend/mcp_server/server.py` | 262 | `build_server()` factory: instantiates `mcp.server.lowlevel.Server`, declares 8 `Tool` definitions with strict JSON schemas, registers `@list_tools` and `@call_tool` handlers, embeds optional `rate_limit_key_hash` in the handler closure for HTTP SSE sessions |
| `backend/mcp_server/tools.py` | 325 | 8 async tool functions wrapping the oracle services; never raise, always return `{"data"\|"error": ..., "disclaimer": ...}` |
| `backend/mcp_server/README.md` | 175 | Install docs for both transports, rate-limit model, architecture notes, non-goals |
| `backend/services/oracle/multi_source.py` | 95 | `collect_sources(symbol)` + `compute_divergence(prices)` extracted from `api/routes_price.py` so REST route and MCP tool share one implementation |
| `backend/api/routes_mcp.py` | 120 | `GET /mcp/sse` + X-API-Key validator + per-session server construction. Module-level `SseServerTransport` shared with the ASGI mount in `main.py`. |
| `backend/tests/test_phase5_mcp.py` | 290 | 18 pytest tests: discovery (5), handler round-trip on offline tools (3), schema validation error paths (3), unknown tool (1), rate limit (3), SSE auth (3) |
| `oracleforge/docs/phase5_mcp_extraction.md` | (this file) | Phase 5 deliverable |

### 2.2 — Modified modules

| File | Changes |
|---|---|
| `backend/main.py` | +3 lines: import `routes_mcp`, `include_router(routes_mcp.router)`, `app.mount("/mcp/messages/", routes_mcp.sse_transport.handle_post_message)` |
| `backend/api/routes_price.py` | Refactored to use `multi_source.collect_sources` / `compute_divergence` instead of the private `_collect_sources` / `_compute_divergence` that used to live inline. Behavior unchanged, 33/33 legacy tests still pass. |

---

## 3. Phase 5 design decisions — implementation notes

The 5 decisions validated before writing code (memory
`project_maxia_oracle_decisions.md` §"Phase 5"):

### D1 — Official `mcp>=1.0` SDK, not the V12 custom server

Implemented. `mcp 1.27.0` was installed into the venv. The transitive
`starlette 1.0` upgrade forced FastAPI to move from `0.116.2` to `0.135.3`.
No regression in the 33 legacy Phase 3/4 tests after the upgrade.
**Follow-up for Phase 7 deploy**: pin these versions in a proper
`requirements.txt` so the VPS install mirrors the dev venv exactly.

### D2 — 8 tools in V1, drop `get_price_history` and `subscribe_price_stream`

Implemented as declared. `get_price_history` would require the historical
candle store that Phase 1 Surgery C removed. `subscribe_price_stream` would
require the MCP notification subscribe primitive plus upstream SSE
wrapping — deferred to V1.1 if demand arises.

### D3 — Dual transport: stdio + HTTP SSE

Implemented. Both transports share `build_server()` so the exact same 8
tools are exposed on either path. The stdio path runs without any quota
(local install, caller owns the upstream costs). The HTTP SSE path builds
a fresh server per session with the caller's key hash embedded in the
closure, so the daily quota is enforced per-agent.

### D4 — Bundled in the `maxia-oracle` Phase 6 package, entry point `maxia-oracle-mcp`

**Not yet implemented.** The package layout and entry point are Phase 6
work. In Phase 5 the MCP server lives inside the `oracleforge/backend/`
tree and is invoked as `python -m mcp_server` directly. Phase 6 will
restructure this into a publishable `maxia-oracle` package.

### D5 — Authentication via `MAXIA_ORACLE_API_KEY` env var (stdio)

**Partially implemented with a scope adjustment**. The stdio path
currently does not require a key at all: the tools call the oracle
services directly as Python functions (no HTTP round-trip to a remote
backend), so there is nothing to authenticate. The decision #5 was
written under the assumption that the MCP server would proxy HTTP to a
remote backend — Phase 5 took a different, better path by wiring the
tools straight to the services.

On the HTTP SSE path, authentication was implemented as **option A** from
the checkpoint discussion: mandatory `X-API-Key` header on the SSE
handshake, validated via the existing Phase 3 `lookup_key`. Missing or
invalid keys return `401` before any stream is opened. This is the
cleanest mapping of "100 free tool calls per day per key" onto the SSE
transport, and it reuses the Phase 3 rate-limiter atom-for-atom.

---

## 4. Rate-limit mechanic (what the tests verify)

The daily quota lives in the Phase 3 `core.rate_limit.check_daily` function.
For the MCP HTTP SSE transport, the quota is enforced at the tool-call
level, not at the session level:

- `initialize` and `tools/list` requests that arrive through the
  `/mcp/messages/` mount do **not** increment the counter. Agents can
  discover the tool set without burning their quota.
- Each `tools/call` invocation passes through the `_call_tool` closure,
  which calls `check_daily(db, rate_limit_key_hash)` before dispatching
  to the tool handler. A quota-cramped call is returned as
  `CallToolResult(isError=True, content=[TextContent(...)])` with a JSON
  payload containing `{error, limit, window_s, retry_after_s, reset_at}`.
- The SSE session itself is **not** closed on quota exhaustion. The agent
  can keep browsing the tool set and retry the call when the counter
  resets at UTC midnight.

The pytest suite covers all three cases:

- `test_rate_limit_ticks_on_tools_call` — 3 calls → `count=3` in DB
- `test_rate_limit_refuses_when_quota_exceeded` — `count=100` pre-seeded,
  next call returns `isError=true`
- `test_stdio_build_server_has_no_rate_limit` — 10 calls through a server
  built without `rate_limit_key_hash`, none of which touch the DB

---

## 5. Transport wiring notes

### 5.1 — stdio

`python -m mcp_server` runs `asyncio.run(_run())` which opens an
`mcp.server.stdio.stdio_server()` session and calls `server.run()` with
the read/write memory object streams. The `ENV` environment variable is
set to `"dev"` inside `__main__.py` **before** importing anything from
`mcp_server.server`, because `core.config` raises at import-time if
`ENV` is absent (Phase 3 decision #8 "le plus sûr"). Claude Desktop
clients can still override `ENV` via the `env` block in their JSON config.

### 5.2 — HTTP SSE

The SDK's `SseServerTransport("/mcp/messages/")` instance is created once
at module load in `api/routes_mcp.py`. Two handlers share it:

1. `GET /mcp/sse` (FastAPI APIRoute) — authenticates the caller, calls
   `build_server(rate_limit_key_hash=...)` for the session, then enters
   the `sse_transport.connect_sse(...)` context and drives
   `server.run()` to completion. Returns an empty `Response()` on
   disconnect (the SDK docs explicitly require this to avoid a
   `NoneType` error).
2. `POST /mcp/messages/?session_id=...` (ASGI mount in `main.py`) —
   handles incoming JSON-RPC messages via
   `sse_transport.handle_post_message`. The SDK routes messages to the
   correct session by the `session_id` query parameter.

The `x402` middleware registered in `main.py` does not interfere with
`/mcp/*`: neither `/mcp/sse` nor `/mcp/messages/*` is listed in
`X402_PRICE_MAP`, so `_match_price(path)` returns `None` and the
middleware passes the request through untouched. MCP SSE uses the API
key path, not the pay-per-call path.

---

## 6. Validation evidence

### 6.1 — Pytest

```
51 passed in 2.15s
```

Breakdown:
- 16 Phase 3 API tests
- 8 Phase 4 DB tests (x402 replay protection)
- 9 Phase 4 x402 middleware tests
- 18 Phase 5 MCP tests (new in this phase)

### 6.2 — Live stdio smoke test

`python -m mcp_server` subprocess with a JSON-RPC pipeline on stdin.
Expected responses observed on stdout:

| Request | Observed result |
|---|---|
| `initialize` | `serverInfo = {"name": "maxia-oracle", "version": "0.1.0"}`, `protocolVersion = "2025-03-26"` |
| `tools/list` | 8 tools in the declared order |
| `tools/call health_check` | `isError = false`, JSON payload with `data.status = "ok"` and `data.service = "maxia-oracle-mcp"` |
| `tools/call list_supported_symbols` | `isError = false`, `total_symbols = 79` |

### 6.3 — Live HTTP SSE round-trip

`uvicorn main:app --port 8765` with httpx end-to-end session. Expected
responses observed:

| Step | Observed result |
|---|---|
| `GET /mcp/sse` without `X-API-Key` | `401`, body `{"error": "missing X-API-Key...", "disclaimer": "..."}` |
| `GET /mcp/sse` with invalid key | `401`, body `{"error": "invalid or inactive API key", "disclaimer": "..."}` |
| `GET /mcp/sse` with valid key | `200`, `Content-Type: text/event-stream; charset=utf-8`, first event carries `/mcp/messages/?session_id=...` |
| `POST .../messages/?session_id=...` initialize | `202 Accepted`, response streamed back over SSE with serverInfo |
| `POST .../messages/?session_id=...` tools/list | 8 tools streamed back |
| `POST .../messages/?session_id=...` tools/call health_check | `isError = false`, data payload |
| `POST .../messages/?session_id=...` tools/call list_supported_symbols | `isError = false`, `total_symbols = 79` |
| DB snapshot after the two tools/call invocations | `rate_limit.count = 2` for the caller's key_hash (initialize and tools/list did not tick) |
| Patch `rate_limit.count = 100`, retry `tools/call` | `isError = true`, payload `{error, limit=100, window_s=86400, retry_after_s>0, reset_at>now}` |

---

## 7. Non-goals and what was explicitly not shipped

MAXIA Oracle is a data feed, not a regulated investment service. The MCP
surface reflects that scope:

- No order routing, no execution, no settlement tools
- No wallet custody, no private keys, no signing tools
- No KYC, no onboarding beyond a free API key
- No tokenized-stock mints, no xStocks (dropped in Phase 1 Surgery A)
- No "investment advice" tools — no position sizing, no buy/sell signals,
  no portfolio construction, no pegs tracking
- No V1.1 tools yet (`get_price_history`, `subscribe_price_stream`)
- No Phase 6 SDK package yet — the MCP server still lives in the
  `oracleforge/backend/` tree and is invoked directly

---

## 8. Open items for the next phases

| # | Item | Phase |
|---|---|---|
| 1 | Freeze `mcp 1.27.0`, `starlette 1.0.0`, `fastapi 0.135.3` in a proper `requirements.txt` | Phase 7 deploy |
| 2 | Package the MCP server as an entry point in `maxia-oracle` PyPI distribution | Phase 6 SDK |
| 3 | Live integration test with Claude Desktop against `oracle.maxiaworld.app/mcp/sse` | Phase 7 post-deploy |
| 4 | Submit to MCP marketplaces (mcpmarket.com, MCP-Hive, Glama) | Phase 9 distribution |
| 5 | Optionally revisit the quota model on `health_check` (does a no-op tool really deserve a quota tick?) | Post-Phase 9 feedback |

---

**End of Phase 5 audit — 15 April 2026.**
