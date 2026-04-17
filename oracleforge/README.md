# MAXIA Oracle

**Multi-source price data feed for AI agents.** Six independent upstream sources aggregated into a single call with confidence scoring and anomaly detection. Pay-per-call in USDC via x402. No custody. No KYC. No investment advice. Just data.

## Quick Start

```bash
# 1. Get a free API key (100 req/day, no signup)
KEY=$(curl -s -X POST https://oracle.maxiaworld.app/api/register \
  | python -c "import sys,json;print(json.load(sys.stdin)['data']['api_key'])")

# 2. Get a price
curl -s -H "X-API-Key: $KEY" https://oracle.maxiaworld.app/api/price/BTC | python -m json.tool
```

## Install

```bash
# Python SDK
pip install maxia-oracle

# TypeScript SDK
npm install @maxia/oracle

# Framework plugins
pip install langchain-maxia-oracle
pip install crewai-tools-maxia-oracle
pip install autogen-maxia-oracle
pip install llama-index-tools-maxia-oracle
npm install eliza-plugin-maxia-oracle
```

## Sources

| Source | Type | Coverage |
|---|---|---|
| Pyth Hermes | Off-chain REST | 80+ crypto + equities |
| Chainlink | On-chain (Base/Ethereum/Arbitrum) | 48 feeds |
| Coinpaprika | Spot aggregator | Broad crypto |
| RedStone | Oracle REST | 400+ assets |
| Pyth Solana | On-chain (Solana) | 13 majors |
| Uniswap v3 TWAP | On-chain DEX (Base/Ethereum) | ETH, BTC |

## API Surface

17 tools available through REST, MCP, Python SDK, TypeScript SDK, and five framework adapters:

| Tool | Description |
|---|---|
| `get_price` | Aggregated multi-source price |
| `get_prices_batch` | Up to 50 symbols in one call |
| `get_sources_status` | Upstream liveness and status |
| `get_cache_stats` | Cache hit ratio and circuit breaker state |
| `get_confidence` | Source agreement metric |
| `list_supported_symbols` | All available symbols by source |
| `get_chainlink_onchain` | Direct Chainlink on-chain read |
| `health_check` | Service liveness probe |
| `get_redstone_price` | Single-source RedStone price |
| `get_pyth_solana_onchain` | Pyth on-chain Solana read |
| `get_twap_onchain` | Uniswap v3 TWAP on-chain |
| `get_price_context` | Confidence score + anomaly detection |
| `get_asset_metadata` | CoinGecko market data |
| `get_price_history` | Historical snapshots (30-day retention) |
| `create_price_alert` | Webhook alert on price threshold |
| `list_price_alerts` | List active alerts |
| `delete_price_alert` | Delete an alert |

## Pricing

| Tier | Cost | Limit |
|---|---|---|
| Free | $0 | 100 requests/day per key |
| x402 (Base/Arbitrum/Optimism/Polygon) | 0.001 USDC/request | Unlimited, anonymous |

## Documentation

- **Landing**: [oracle.maxiaworld.app](https://oracle.maxiaworld.app)
- **API Reference**: [oracle.maxiaworld.app/docs](https://oracle.maxiaworld.app/docs/)
- **LLM-readable**: [oracle.maxiaworld.app/llms.txt](https://oracle.maxiaworld.app/llms.txt)

## Disclaimers

- **Data feed only.** Not investment advice. Not a trading tool.
- **No custody.** Direct sale, no intermediation, no escrow.
- **No KYC.** Free tier issued on demand, no identity fields.
- **Best-effort multi-source.** No guarantee of uptime or accuracy.

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Contact

ceo@maxiaworld.app
