# Social media drafts — MAXIA Oracle v0.1.9 launch

---

## Reddit — r/MachineLearning / r/LLMDevs / r/algotrading

**Title:** Multi-source price oracle for AI agents — MCP + Python + TypeScript, free tier

I built MAXIA Oracle, a price data feed designed specifically for AI agents and MCP clients.

**Why not just call Binance/CoinGecko directly?**
- Single source = single point of failure + no cross-validation
- No confidence signal: your agent can't tell if the price is fresh or stale
- No divergence detection: if two sources disagree by 5%, you want to know before your agent acts

**What it does:**
- Aggregates Pyth (Solana), Chainlink (Base mainnet), CoinPaprika, RedStone, Uniswap v3 TWAP
- Returns confidence score (0–100) + inter-source divergence % on every price call
- 91 symbols: crypto majors, US equities (AAPL, TSLA, NVDA via Pyth), forex, stablecoins, memecoins
- Price history (24h/7d/30d), price alerts (webhook), SSE streaming

**Integration:**
```bash
pip install maxia-oracle          # Python SDK
npm install @maxia-marketplace/oracle         # TypeScript SDK
# Or use the MCP server directly in Claude Desktop / Cursor / Zed
```

MCP server: `https://oracle.maxiaworld.app/mcp/sse`
Free tier: 100 req/day, no email, no credit card — `POST /api/register`

API reference: https://oracle.maxiaworld.app/docs/

Not investment advice. Not a broker. Just data.

---

## Discord — AI Agents / MCP communities

**Short version:**

Just launched MAXIA Oracle — a multi-source price feed for AI agents with MCP support.

The key thing: every price response includes a **confidence score + inter-source divergence** so your agent knows whether to trust the number or flag it.

- 91 symbols (crypto + equities + forex)
- MCP server live at `oracle.maxiaworld.app/mcp/sse`
- `pip install maxia-oracle` / `npm install @maxia-marketplace/oracle`
- Free: 100 req/day, no signup

Data feed only — not investment advice, no custody, no KYC.

https://oracle.maxiaworld.app

---

## Twitter/X thread

1/ Just shipped MAXIA Oracle — a multi-source price feed built for AI agents.

The problem: agents trust a single price source blindly. If that source is stale or wrong, your agent acts on bad data.

2/ MAXIA Oracle aggregates Pyth + Chainlink (Base) + CoinPaprika + RedStone + Uniswap v3 TWAP and returns:
- Cross-validated median price
- Confidence score (0–100)
- Inter-source divergence %
- Per-source breakdown with freshness

3/ 91 symbols: BTC, ETH, SOL, memecoins (PEPE, BONK, FARTCOIN), US equities (AAPL, TSLA, NVDA via Pyth), forex (EUR, GBP), stablecoins.

Plus: price history, alerts, SSE streaming.

4/ Works with every agent framework:
- MCP server (Claude Desktop, Cursor, Zed)
- `pip install maxia-oracle`
- `npm install @maxia-marketplace/oracle`
- langchain / crewai / autogen / llama-index / eliza plugins

5/ Free tier: 100 req/day. No email. No credit card. Just:
`POST https://oracle.maxiaworld.app/api/register`

Data feed only. Not investment advice. No custody. No KYC.

API docs: https://oracle.maxiaworld.app/docs/
