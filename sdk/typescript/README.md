# @maxia/oracle

Multi-source price data feed for AI agents — TypeScript SDK. Pay-per-call
in USDC on Base mainnet or use a free 100 req/day API key. No custody,
no KYC.

**Data feed only. Not investment advice. No custody. No KYC.**

## Install

```bash
npm install @maxia/oracle
```

Requires Node 18+ (uses the native `fetch` — no `node-fetch`, no `axios`).

## Quick start

```typescript
import { MaxiaOracleClient } from "@maxia/oracle";

// Register a free key (100 req/day, no KYC)
const bootstrap = new MaxiaOracleClient();
const registered = await bootstrap.register();
const key = registered.data.api_key;

// Then use it
const client = new MaxiaOracleClient({ apiKey: key });

const btc = await client.price("BTC");
console.log(btc.data.price);

// Up to 50 symbols in one call
const batch = await client.pricesBatch(["BTC", "ETH", "SOL", "AAPL"]);

// Cross-check divergence across sources
const conf = await client.confidence("BTC");
console.log(conf.data.divergence_pct);

// Force a single-source Chainlink on-chain fetch
const onchain = await client.chainlinkOnchain("BTC");
```

You can also pass the API key via environment variable:

```bash
export MAXIA_ORACLE_API_KEY=mxo_your_key_here
```

and point the client at a different backend (e.g. a local dev instance):

```bash
export MAXIA_ORACLE_BASE_URL=http://127.0.0.1:8003
```

## 9 methods

| Method | REST path | Auth |
|---|---|---|
| `register()` | POST /api/register | No |
| `health()` | GET /health | No |
| `price(symbol)` | GET /api/price/{symbol} | API key |
| `pricesBatch(symbols)` | POST /api/prices/batch | API key |
| `sources()` | GET /api/sources | API key |
| `cacheStats()` | GET /api/cache/stats | API key |
| `listSymbols()` | GET /api/symbols | API key |
| `chainlinkOnchain(symbol)` | GET /api/chainlink/{symbol} | API key |
| `confidence(symbol)` | GET /api/price/{symbol} (divergence only) | API key |

Every method returns a `Promise<MaxiaResponse<T>>` where
`MaxiaResponse<T>` is `{ data: T, disclaimer: string }`. The disclaimer
is always present and always carries the mandatory legal string.

## Error handling

Every call throws a typed exception on failure, all subclassed from
`MaxiaOracleError`:

```typescript
import {
  MaxiaOracleClient,
  MaxiaOracleAuthError,
  MaxiaOracleRateLimitError,
  MaxiaOracleUpstreamError,
  MaxiaOracleValidationError,
} from "@maxia/oracle";

const client = new MaxiaOracleClient({ apiKey: "mxo_..." });

try {
  const btc = await client.price("BTC");
} catch (err) {
  if (err instanceof MaxiaOracleAuthError) {
    // Missing or invalid key
  } else if (err instanceof MaxiaOracleRateLimitError) {
    // Daily quota exhausted
    console.log(`retry in ${err.retryAfterSeconds}s`);
  } else if (err instanceof MaxiaOracleUpstreamError) {
    // Every upstream source failed for this symbol
  } else if (err instanceof MaxiaOracleValidationError) {
    // Malformed symbol, oversized batch
  }
}
```

## Non-goals

MAXIA Oracle is a data feed, not a regulated financial service. This
SDK deliberately does NOT expose:

- Order routing or trade execution
- Wallet custody or signing
- Swap, DeFi lending, yield farming, staking
- Escrow or marketplace intermediation
- Tokenized securities
- "Investment advice" — no buy/sell signals, no portfolio construction

For a stdio MCP server suitable for Claude Desktop / Cursor / Zed, use
the Python SDK `pip install maxia-oracle` which ships the
`maxia-oracle-mcp` entry point. A native TypeScript MCP bridge is on the
roadmap but not part of V1.

## License

Apache-2.0. See `LICENSE`.

## Links

- Backend: [oracle.maxiaworld.app](https://oracle.maxiaworld.app)
- Python SDK: [`pip install maxia-oracle`](https://pypi.org/project/maxia-oracle/)
- Issues: [github.com/maxiaworld/oracleforge](https://github.com/maxiaworld/oracleforge)
- Contact: `ceo@maxiaworld.app`
