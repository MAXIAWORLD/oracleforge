# crewai-tools-maxia-oracle

CrewAI tool wrappers for **MAXIA Oracle** — multi-source crypto and
equity price feeds for AI agents.

> Data feed only. Not investment advice. No custody. No KYC.

## Install

```bash
pip install crewai-tools-maxia-oracle
```

Depends on [`maxia-oracle`](https://pypi.org/project/maxia-oracle/)
(the Python SDK) and `crewai>=0.80`.

## Quick start

```python
from crewai import Agent, Crew, Task
from crewai_tools_maxia_oracle import get_all_tools

tools = get_all_tools(api_key="mxo_xxxxxxxx...")
# or rely on MAXIA_ORACLE_API_KEY env var:
# tools = get_all_tools()

analyst = Agent(
    role="Market data analyst",
    goal="Answer market data questions with verified multi-source prices.",
    backstory="You are cautious and always cite the source divergence.",
    tools=tools,
)

task = Task(
    description="What is BTC trading at right now?",
    expected_output="A median price in USD with the source count and divergence.",
    agent=analyst,
)

Crew(agents=[analyst], tasks=[task]).kickoff()
```

## Tools

All 17 tools, one per SDK method:

| Tool class | SDK method | Purpose |
|---|---|---|
| `MaxiaOracleGetPriceTool` | `price(symbol)` | Multi-source median + divergence |
| `MaxiaOracleGetPricesBatchTool` | `prices_batch(symbols)` | Up to 50 symbols in one call |
| `MaxiaOracleGetSourcesStatusTool` | `sources()` | Upstream liveness probe |
| `MaxiaOracleGetCacheStatsTool` | `cache_stats()` | Aggregator cache + circuit breaker |
| `MaxiaOracleGetConfidenceTool` | `confidence(symbol)` | Compact agreement metric |
| `MaxiaOracleListSupportedSymbolsTool` | `list_symbols()` | Symbol universe by source |
| `MaxiaOracleGetChainlinkOnchainTool` | `chainlink_onchain(symbol, chain)` | Single-source Chainlink (Base/Ethereum/Arbitrum) |
| `MaxiaOracleHealthCheckTool` | `health()` | Backend liveness |
| `MaxiaOracleGetRedstoneTool` | `redstone(symbol)` | Single-source RedStone price |
| `MaxiaOracleGetPythSolanaTool` | `pyth_solana(symbol)` | Pyth on-chain Solana price |
| `MaxiaOracleGetTwapTool` | `twap(symbol, chain, window_s)` | Uniswap v3 TWAP on-chain |
| `MaxiaOracleGetPriceContextTool` | `price_context(symbol)` | Confidence + anomaly + context |
| `MaxiaOracleGetMetadataTool` | `metadata(symbol)` | CoinGecko market data |
| `MaxiaOracleGetPriceHistoryTool` | `price_history(symbol, range)` | Historical price snapshots |
| `MaxiaOracleCreateAlertTool` | `create_alert(...)` | One-shot webhook price alert |
| `MaxiaOracleListAlertsTool` | `list_alerts()` | List active alerts |
| `MaxiaOracleDeleteAlertTool` | `delete_alert(alert_id)` | Delete an alert |

## Configuration

| Variable | Purpose |
|---|---|
| `MAXIA_ORACLE_API_KEY` | The `mxo_`-prefixed key from `POST /api/register` |
| `MAXIA_ORACLE_BASE_URL` | Override backend URL (default `https://oracle.maxiaworld.app`) |

## Non-goals

These tools are read-only: no order routing, no swap, no custody, no
KYC, no tokenized securities, no yield execution. MAXIA Oracle is a
**data feed**, not a trading engine.

## License

Apache-2.0.
