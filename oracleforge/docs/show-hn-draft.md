# Show HN: MAXIA Oracle — multi-source price feed for AI agents (MCP + Python + npm)

**URL:** https://oracle.maxiaworld.app

---

I built a price data feed specifically designed for AI agents and MCP clients.

**The problem:** AI agents that need price data are forced to call a single exchange API, trust it blindly, and deal with downtime. There's no cross-validation, no confidence signal, no "are these two sources agreeing right now?"

**What MAXIA Oracle does:**

- Aggregates Pyth (Solana), Chainlink (Base mainnet), CoinPaprika, RedStone, and Uniswap v3 TWAP into a single price
- Returns a confidence score (0–100) and inter-source divergence in percent — so an agent can decide whether to trust the price or flag it
- 91 symbols: crypto majors, Solana ecosystem, equities (AAPL, TSLA, NVDA…), forex (EUR, GBP), stablecoins, memecoins
- Price history (24h/7d/30d at 5m/1h/1d intervals, 5-min sampler)
- Price alerts with webhook callbacks (one-shot, fires once then deactivates)
- SSE streaming for live prices

**Integration points:**

- MCP server at `https://oracle.maxiaworld.app/mcp/sse` — works with Claude Desktop, Cursor, Continue, Zed
- Python SDK: `pip install maxia-oracle`
- TypeScript SDK: `npm install @maxia/oracle`
- Plugins: `langchain-maxia-oracle`, `crewai-tools-maxia-oracle`, `autogen-maxia-oracle`, `llama-index-tools-maxia-oracle`
- x402 micropayments on Base (pay-per-call for agents without API keys)

**Free tier:** 100 req/day, no email, no credit card — just `POST /api/register`.

**Not:** investment advice, a broker, a custodian, a marketplace, or anything regulated. Pure data feed.

**Tech:** FastAPI + SQLite + httpx on a VPS. The aggregation logic uses a cascade: Pyth Hermes batch call first (79 symbols in one HTTP round-trip), then Chainlink on-chain as an independent verifier, then CeFi fallbacks for anything Pyth doesn't cover.

Happy to answer questions about the multi-source aggregation logic, the MCP server setup, or the x402 pay-per-call flow.

---

**Links:**
- API reference: https://oracle.maxiaworld.app/docs/
- GitHub: https://github.com/maxiaworld/oracleforge
