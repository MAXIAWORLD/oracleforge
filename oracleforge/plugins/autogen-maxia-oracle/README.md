# autogen-maxia-oracle

AutoGen (`autogen-core` 0.4+) tool wrappers for **MAXIA Oracle** —
multi-source crypto and equity price feeds for AI agents.

> Data feed only. Not investment advice. No custody. No KYC.

## Install

```bash
pip install autogen-maxia-oracle
```

Depends on [`maxia-oracle`](https://pypi.org/project/maxia-oracle/)
(the Python SDK) and `autogen-core>=0.4`.

## Quick start

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from autogen_maxia_oracle import get_all_tools

tools = get_all_tools(api_key="mxo_xxxxxxxx...")
# or rely on MAXIA_ORACLE_API_KEY env var:
# tools = get_all_tools()

model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")

agent = AssistantAgent(
    name="market_data_analyst",
    model_client=model_client,
    tools=tools,
    system_message=(
        "You are a cautious market data analyst. Always report the source "
        "count and divergence when returning a price."
    ),
)
```

## Tools

All 8 tools are `FunctionTool` instances, one per SDK method:

| Tool name | SDK method |
|---|---|
| `maxia_oracle_get_price` | `price(symbol)` |
| `maxia_oracle_get_prices_batch` | `prices_batch(symbols)` |
| `maxia_oracle_get_sources_status` | `sources()` |
| `maxia_oracle_get_cache_stats` | `cache_stats()` |
| `maxia_oracle_get_confidence` | `confidence(symbol)` |
| `maxia_oracle_list_supported_symbols` | `list_symbols()` |
| `maxia_oracle_get_chainlink_onchain` | `chainlink_onchain(symbol)` |
| `maxia_oracle_health_check` | `health()` |

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
