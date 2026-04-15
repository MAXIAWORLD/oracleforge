# maxia-oracle

Multi-source price data feed for AI agents. Pay-per-call in USDC on Base
mainnet or use a free 100 req/day API key. No custody. No KYC.

**Data feed only. Not investment advice. No custody. No KYC.**

## Install

```bash
pip install maxia-oracle
```

## Quick start — Python SDK

```python
from maxia_oracle import MaxiaOracleClient

# Register a free key (100 req/day, no KYC)
with MaxiaOracleClient() as client:
    registered = client.register()
    key = registered["data"]["api_key"]

# Then use it
with MaxiaOracleClient(api_key=key) as client:
    btc = client.price("BTC")
    print(btc["data"]["price"])

    # Up to 50 symbols in one call
    batch = client.prices_batch(["BTC", "ETH", "SOL", "AAPL"])

    # Cross-check divergence across sources
    conf = client.confidence("BTC")
    print(conf["data"]["divergence_pct"])

    # Force a single-source Chainlink on-chain fetch
    onchain = client.chainlink_onchain("BTC")
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
| `prices_batch(symbols)` | POST /api/prices/batch | API key |
| `sources()` | GET /api/sources | API key |
| `cache_stats()` | GET /api/cache/stats | API key |
| `list_symbols()` | GET /api/symbols | API key |
| `chainlink_onchain(symbol)` | GET /api/chainlink/{symbol} | API key |
| `confidence(symbol)` | GET /api/price/{symbol} (divergence only) | API key |

## Quick start — MCP server for Claude Desktop / Cursor / Zed

This package ships a stdio MCP server that speaks the Model Context
Protocol natively. Every tool is a thin wrapper that forwards calls to
the MAXIA Oracle REST API, so no backend needs to run on your machine.

Paste this in your Claude Desktop config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "maxia-oracle": {
      "command": "maxia-oracle-mcp",
      "env": {
        "MAXIA_ORACLE_API_KEY": "mxo_your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. The 8 tools appear in its tool picker:

- `get_price(symbol)`
- `get_prices_batch(symbols)`
- `get_sources_status()`
- `get_cache_stats()`
- `get_confidence(symbol)`
- `list_supported_symbols()`
- `get_chainlink_onchain(symbol)`
- `health_check()`

## Error handling

Every SDK call raises a typed exception on failure, rooted at
`MaxiaOracleError`. Catch the specific subclass you care about:

```python
from maxia_oracle import (
    MaxiaOracleClient,
    MaxiaOracleAuthError,
    MaxiaOracleRateLimitError,
    MaxiaOracleUpstreamError,
    MaxiaOracleValidationError,
)

with MaxiaOracleClient(api_key="mxo_...") as client:
    try:
        btc = client.price("BTC")
    except MaxiaOracleAuthError:
        # Missing or invalid key — re-register
        ...
    except MaxiaOracleRateLimitError as e:
        # Daily quota exhausted
        print(f"Retry in {e.retry_after_seconds}s")
    except MaxiaOracleUpstreamError:
        # Every source failed for this symbol
        ...
    except MaxiaOracleValidationError:
        # Malformed symbol, oversized batch, etc.
        ...
```

## Non-goals

MAXIA Oracle is a data feed, not a regulated financial service. This
SDK deliberately does NOT expose:

- Order routing or trade execution
- Wallet custody or signing
- Swap, DeFi lending, yield farming, staking
- Escrow or marketplace intermediation
- Tokenized securities (xStocks, etc.)
- "Investment advice" — no buy/sell signals, no portfolio construction

## License

Apache-2.0. See `LICENSE`.

## Links

- Backend: [oracle.maxiaworld.app](https://oracle.maxiaworld.app)
- Issues: [github.com/maxiaworld/oracleforge](https://github.com/maxiaworld/oracleforge)
- Contact: `ceo@maxiaworld.app`
