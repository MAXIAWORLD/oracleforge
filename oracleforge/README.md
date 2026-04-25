# MAXIA Oracle

[![Glama](https://glama.ai/mcp/servers/badge/MAXIAWORLD/oracleforge)](https://glama.ai/mcp/servers/MAXIAWORLD/oracleforge)

**Multi-source price data feed for AI agents.** Aggregates Pyth, Chainlink, CoinPaprika, RedStone, and Uniswap v3 TWAP into a cross-validated median price with confidence score and inter-source divergence.

**Live at:** https://oracle.maxiaworld.app — **MCP server:** `https://oracle.maxiaworld.app/mcp/sse`

> Data feed only. Not investment advice. No custody. No KYC.

---

## What it does

Every price response returns:
- **Cross-validated median price** across up to 5 independent sources
- **Confidence score (0–100)** — penalized by divergence, staleness, single-source results
- **Inter-source divergence %** — your agent knows when sources disagree before acting
- Per-source breakdown with freshness timestamps

**91 symbols:** crypto majors, Solana ecosystem, US equities (AAPL, TSLA, NVDA via Pyth), forex (EUR, GBP, JPY), stablecoins, memecoins (PEPE, BONK, FARTCOIN).

---

## MCP Server

Works with Claude Desktop, Cursor, Zed, Continue, and any MCP-compatible client.

**SSE endpoint:** `https://oracle.maxiaworld.app/mcp/sse`

### Claude Desktop config

```json
{
  "mcpServers": {
    "maxia-oracle": {
      "command": "npx",
      "args": ["-y", "@maxia-marketplace/oracle", "mcp"]
    }
  }
}
```

### Available tools (8)

| Tool | Description |
|---|---|
| `get_price` | Cross-validated median price for a single symbol |
| `get_prices_batch` | Prices for up to 50 symbols in one call |
| `get_price_history` | OHLC history (24h/7d/30d, intervals: 5m/1h/1d) |
| `get_confidence` | Confidence score + divergence for a symbol |
| `get_chainlink_onchain` | Direct on-chain Chainlink price (Base mainnet) |
| `list_supported_symbols` | Full list of 91 supported symbols |
| `get_sources_status` | Liveness of every upstream source |
| `health_check` | Minimal liveness check |

---

## Installation

### Python SDK

```bash
pip install maxia-oracle
```

```python
from maxia_oracle import OracleClient

client = OracleClient(api_key="your-key")
result = await client.get_price("BTC")
print(result.price, result.confidence, result.divergence_pct)
```

### TypeScript SDK

```bash
npm install @maxia-marketplace/oracle
```

```typescript
import { OracleClient } from "@maxia-marketplace/oracle";

const client = new OracleClient({ apiKey: "your-key" });
const result = await client.getPrice("ETH");
console.log(result.price, result.confidence);
```

### Framework plugins

```bash
pip install langchain-maxia-oracle         # LangChain
pip install crewai-tools-maxia-oracle      # CrewAI
pip install autogen-maxia-oracle           # AutoGen
pip install llama-index-tools-maxia-oracle # LlamaIndex
npm install eliza-plugin-maxia-oracle      # Eliza / ai16z
```

---

## Free tier

100 requests/day — no email, no credit card required:

```bash
curl -X POST https://oracle.maxiaworld.app/api/register
# returns: { "api_key": "mxo_..." }
```

---

## Pay-per-call (x402)

Agents without API keys can pay $0.001 USDC per call via x402 micropayments on Base mainnet. No registration needed.

---

## API Reference

Full docs: https://oracle.maxiaworld.app/docs/

### Quick example

```bash
curl https://oracle.maxiaworld.app/api/price/BTC \
  -H "X-API-Key: mxo_your_key"
```

```json
{
  "symbol": "BTC",
  "price": 83421.50,
  "confidence": 94,
  "divergence_pct": 0.18,
  "sources": {
    "pyth": { "price": 83410.0, "age_s": 2 },
    "chainlink": { "price": 83438.0, "age_s": 45 },
    "coinpaprika": { "price": 83416.5, "age_s": 12 }
  },
  "disclaimer": "Data feed only. Not investment advice."
}
```

---

## Self-hosting

```bash
git clone https://github.com/MAXIAWORLD/oracleforge
cd oracleforge
docker build -t maxia-oracle .
docker run -p 8003:8003 \
  -e ENV=dev \
  -e API_KEY_PEPPER=your-secret \
  maxia-oracle
```

Or with uvicorn:

```bash
cd backend
pip install -r requirements.txt
ENV=dev uvicorn main:app --reload --port 8003
```

---

## Architecture

```
Pyth Hermes (Solana)       ─┐
Chainlink on-chain (Base)   ├─→ Aggregator → median + confidence + divergence
CoinPaprika (CeFi)          ├─┘
RedStone                    │
Uniswap v3 TWAP (Ethereum)  ┘
```

The aggregation cascade: Pyth batch (79 symbols in one HTTP round-trip) → Chainlink as independent on-chain verifier → CoinPaprika/RedStone for remaining gaps → Uniswap v3 TWAP for DeFi-native assets (manipulation-resistant, 10-min window).

---

## License

- Backend: MAXIA Oracle Proprietary
- SDK + plugins: MIT

Contact: contact@maxialab.com
