# Changelog

All notable changes to MAXIA Oracle are documented in this file.

## [0.1.9] — 2026-04-19

### Added
- Price alerts CRUD (`POST/GET/DELETE /api/alerts`) — one-shot webhook callbacks (above/below threshold)
- SSE price streaming (`GET /api/prices/stream`) — live prices, max 10 symbols, 1-hour session
- MCP tools: `create_price_alert`, `list_price_alerts`, `delete_price_alert` — alert management from any MCP client
- SSRF protection on alert callback URLs — HTTPS-only, private IP reject, DNS resolve guard

### Fixed
- Batch quota drain bug — rejected batches no longer consume remaining daily quota (atomic SQL `WHERE count + cost <= DAILY_LIMIT`)
- `TypeError` detail leak in MCP server — internal exception messages no longer forwarded to callers
- Forex 404 hint — known tickers (JPY, CHF, AUD…) return a clear message instead of silent 404
- History cold-start note — `get_price_history` returns an explanatory message when sampler hasn't run yet
- 422 Pydantic errors now include `disclaimer` field (custom `RequestValidationError` handler)
- Alert threshold capped at `1e12` to prevent quasi-infinite sentinel thresholds

## [0.1.8] — 2026-04-18

### Added
- Historical price sampling — background sampler every 5 minutes, 30-day retention in SQLite
- `GET /api/price/{symbol}/history` endpoint (24h/7d/30d × 5m/1h/1d intervals, 7 valid combos)
- MCP tool `get_price_history` — same surface via MCP
- Downsampling via bucketed SQL AVG — efficient serve at any interval

## [0.1.7] — 2026-04-18

### Added
- Forex dispatch — EUR and GBP routed via Pyth Hermes shard 0
- Asset metadata — `GET /api/metadata/{symbol}` via CoinGecko (market cap, 24h volume, ATH/ATL)
- MCP tool `get_asset_metadata`

## [0.1.6] — 2026-04-18

### Added
- Agent intelligence layer — confidence score (0–100), anomaly detection, sources agreement classification
- `GET /api/price/{symbol}/context` endpoint
- MCP tool `get_price_context`
- Plugin tool `MaxiaOracleGetPriceContextTool` (all 4 Python frameworks)

## [0.1.5] — 2026-04-17

### Added
- Uniswap v3 TWAP on-chain reader (Base + Ethereum) — 6th upstream source
- `GET /api/twap/{symbol}` endpoint, MCP tool `get_twap_onchain`
- SDK method `twap(symbol, chain, window_s)` (Python + TypeScript)
- Plugin tool `MaxiaOracleGetTwapTool` (langchain, crewai, autogen, llama-index)
- Eliza action `GET_TWAP_ONCHAIN`

### Audit fixes (post-V1.5)
- Deep health check (`/health`) — reports DB + 8 circuit breakers, `ok`/`degraded`
- Request ID middleware (pure ASGI) — UUID4 on every request, propagated to logs + response
- Structured JSON logging in prod, request_id in dev text logs
- Removed ankr Solana RPC (403 systematic)
- Refactored `pyth_oracle.py` 983→396 lines, extracted cascade to `price_cascade.py`
- Broke circular import pyth_oracle ↔ price_oracle
- Removed dead code: streaming functions, `_is_market_open()`
- Hermes retry (1 retry + 500ms backoff on transient timeout)
- Finnhub upstream rate limiter (55/min server-side guard)
- Public `GET /api/status` endpoint (per-source health, no auth)
- SDK auto-retry on 429 rate limit (Python + TypeScript)
- API version bumped 0.1.0 → 0.1.5

## [0.1.4] — 2026-04-16

### Added
- Pyth native Solana on-chain reader (Push Oracle shard 0)
- 13 majors: BTC, ETH, SOL, USDT, USDC, WIF, BONK, PYTH, JTO, JUP, RAY, EUR, GBP
- `GET /api/pyth/solana/{symbol}` endpoint, MCP tool `get_pyth_solana_onchain`
- SDK method `pyth_solana(symbol)` (Python + TypeScript)

## [0.1.3] — 2026-04-16

### Added
- RedStone as 4th independent upstream source (400+ assets, dynamic coverage)
- `GET /api/redstone/{symbol}` endpoint, MCP tool `get_redstone_price`
- SDK method `redstone(symbol)` (Python + TypeScript)
- Eliza plugin (`eliza-plugin-maxia-oracle`) — 5th framework, 9 actions

## [0.1.2] — 2026-04-16

### Added
- x402 multi-chain EVM: Base + Arbitrum + Optimism + Polygon (USDC native)
- `X-Payment-Network` header for chain selection
- Per-chain treasury addresses (segregated or shared)

## [0.1.1] — 2026-04-16

### Added
- Chainlink multi-chain: Base + Ethereum + Arbitrum (48 feeds)
- `GET /api/chainlink/{symbol}?chain=` with 3 chain options
- Per-chain RPC pools with automatic fallback

## [0.1.0] — 2026-04-16

### Added
- Initial release — 6 upstream sources, REST API, MCP server (11 tools)
- Python SDK (`maxia-oracle`), TypeScript SDK (`@maxia/oracle`)
- 4 Python plugins (langchain, crewai, autogen, llama-index)
- x402 micropayment middleware (Base mainnet, USDC)
- SQLite-backed rate limiting + API key management
- Deploy on VPS with systemd + nginx + Let's Encrypt
