# llama-index-tools-maxia-oracle

LlamaIndex (`llama-index-core` 0.11+) tool wrappers for **MAXIA Oracle** —
multi-source crypto and equity price feeds for AI agents.

> Data feed only. Not investment advice. No custody. No KYC.

## Install

```bash
pip install llama-index-tools-maxia-oracle
```

Depends on [`maxia-oracle`](https://pypi.org/project/maxia-oracle/)
(the Python SDK) and `llama-index-core>=0.11`.

## Quick start

```python
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent

from llama_index_tools_maxia_oracle import get_all_tools

tools = get_all_tools(api_key="mxo_xxxxxxxx...")
# or rely on MAXIA_ORACLE_API_KEY env var:
# tools = get_all_tools()

llm = OpenAI(model="gpt-4o-mini")
agent = ReActAgent.from_tools(tools, llm=llm, verbose=True)
agent.chat("What is BTC trading at right now?")
```

## Tools

All 17 tools are `FunctionTool` instances, one per SDK method:

| Tool name | SDK method |
|---|---|
| `maxia_oracle_get_price` | `price(symbol)` |
| `maxia_oracle_get_prices_batch` | `prices_batch(symbols)` |
| `maxia_oracle_get_sources_status` | `sources()` |
| `maxia_oracle_get_cache_stats` | `cache_stats()` |
| `maxia_oracle_get_confidence` | `confidence(symbol)` |
| `maxia_oracle_list_supported_symbols` | `list_symbols()` |
| `maxia_oracle_get_chainlink_onchain` | `chainlink_onchain(symbol, chain)` |
| `maxia_oracle_health_check` | `health()` |
| `maxia_oracle_get_redstone` | `redstone(symbol)` |
| `maxia_oracle_get_pyth_solana` | `pyth_solana(symbol)` |
| `maxia_oracle_get_twap` | `twap(symbol, chain, window_s)` |
| `maxia_oracle_get_price_context` | `price_context(symbol)` |
| `maxia_oracle_get_metadata` | `metadata(symbol)` |
| `maxia_oracle_get_price_history` | `price_history(symbol, range)` |
| `maxia_oracle_create_alert` | `create_alert(...)` |
| `maxia_oracle_list_alerts` | `list_alerts()` |
| `maxia_oracle_delete_alert` | `delete_alert(alert_id)` |

## Configuration

| Variable | Purpose |
|---|---|
| `MAXIA_ORACLE_API_KEY` | The `mxo_`-prefixed key from `POST /api/register` |
| `MAXIA_ORACLE_BASE_URL` | Override backend URL (default `https://oracle.maxiaworld.app`) |

## Non-goals

Read-only data feed: no order routing, no swap, no custody, no KYC, no
tokenized securities, no yield execution.

## License

Apache-2.0.
