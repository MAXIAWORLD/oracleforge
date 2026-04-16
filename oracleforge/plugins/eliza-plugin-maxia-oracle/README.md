# eliza-plugin-maxia-oracle

ElizaOS plugin for the [MAXIA Oracle](https://oracle.maxiaworld.app) price feed.

> **Data feed only. Not investment advice. No custody. No KYC.**

Gives any Eliza character access to MAXIA Oracle's cross-validated
multi-source price pipeline (Pyth Hermes + Pyth native Solana, Chainlink on
Base/Ethereum/Arbitrum, RedStone public REST, and a 4-way aggregator).
Works over X-API-Key (free tier) or x402 (paid, micropayments).

## Install

```bash
npm install eliza-plugin-maxia-oracle
```

Peer dependency: `@elizaos/core >= 1.0.0`.

## Usage

```ts
import { maxiaOraclePlugin } from "eliza-plugin-maxia-oracle";

const character = {
  name: "MAXIA",
  // …
  plugins: [maxiaOraclePlugin],
  settings: {
    secrets: {
      MAXIA_ORACLE_API_KEY: process.env.MAXIA_ORACLE_API_KEY,
    },
  },
};
```

Register a free-tier key on https://oracle.maxiaworld.app.

## Actions (9)

| Name | Description |
|---|---|
| `GET_PRICE` | Cross-validated multi-source price for one symbol |
| `GET_PRICES_BATCH` | Up to 50 tickers in one upstream call |
| `GET_SOURCES_STATUS` | Liveness probe on every upstream oracle |
| `GET_CACHE_STATS` | Cache hit rate + circuit breakers |
| `GET_CONFIDENCE` | Multi-source divergence (“do sources agree?”) |
| `LIST_SUPPORTED_SYMBOLS` | Full symbol catalog, grouped by source |
| `GET_CHAINLINK_ONCHAIN` | Single-source Chainlink price on Base / Ethereum / Arbitrum |
| `GET_REDSTONE_PRICE` | V1.3 — Single-source RedStone REST (400+ assets) |
| `HEALTH_CHECK` | Minimal backend liveness |

A `GET_PYTH_SOLANA_ONCHAIN` action was scoped for V1.3 but dropped
before ship after live audit showed Pyth V2 price accounts on Solana
mainnet-beta have been decommissioned. Rescheduled to V1.4 with the
new Pyth Solana Receiver program.

## License

Apache-2.0
