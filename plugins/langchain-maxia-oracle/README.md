# langchain-maxia-oracle

LangChain tool wrappers for **MAXIA Oracle** — multi-source crypto and
equity price feeds for AI agents.

> Data feed only. Not investment advice. No custody. No KYC.

## Install

```bash
pip install langchain-maxia-oracle
```

This plugin depends on [`maxia-oracle`](https://pypi.org/project/maxia-oracle/)
(the Python SDK) and `langchain-core`. The SDK ships a synchronous httpx
client with zero other runtime dependencies.

## Quick start

Register a free API key against the hosted backend:

```bash
curl -X POST https://oracle.maxiaworld.app/api/register
# → {"data": {"api_key": "mxo_xxxxxxxx...", "daily_limit": 100}, ...}
```

Then wire the tools into any LangChain agent:

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from langchain_maxia_oracle import get_all_tools

tools = get_all_tools(api_key="mxo_xxxxxxxx...")
# or rely on the MAXIA_ORACLE_API_KEY environment variable:
# tools = get_all_tools()

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a market data assistant. Use the tools to answer."),
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

executor.invoke({"input": "What is BTC trading at right now?"})
```

## Tools

All 8 tools mirror the MCP surface and the Python SDK methods:

| Tool class | SDK method | Purpose |
|---|---|---|
| `MaxiaOracleGetPriceTool` | `price(symbol)` | Multi-source median + divergence |
| `MaxiaOracleGetPricesBatchTool` | `prices_batch(symbols)` | Up to 50 symbols in one call |
| `MaxiaOracleGetSourcesStatusTool` | `sources()` | Upstream liveness probe |
| `MaxiaOracleGetCacheStatsTool` | `cache_stats()` | Aggregator cache + circuit breaker |
| `MaxiaOracleGetConfidenceTool` | `confidence(symbol)` | Compact agreement metric |
| `MaxiaOracleListSupportedSymbolsTool` | `list_symbols()` | Full symbol universe by source |
| `MaxiaOracleGetChainlinkOnchainTool` | `chainlink_onchain(symbol)` | Single-source Chainlink on Base |
| `MaxiaOracleHealthCheckTool` | `health()` | Backend liveness |

Every tool returns a JSON string that includes the mandatory
`disclaimer` field so the LLM sees the non-advice notice every time.

## Configuration

The tools read configuration from the SDK, which in turn reads from its
constructor arguments or from environment variables:

| Variable | Purpose |
|---|---|
| `MAXIA_ORACLE_API_KEY` | The `mxo_`-prefixed key returned by `/api/register` |
| `MAXIA_ORACLE_BASE_URL` | Override the backend URL (default `https://oracle.maxiaworld.app`) |

You can also pass a pre-built client instead of letting `get_all_tools`
construct one:

```python
from maxia_oracle import MaxiaOracleClient
from langchain_maxia_oracle import get_all_tools

with MaxiaOracleClient(api_key="mxo_...") as client:
    tools = get_all_tools(client=client)
    # ... use the tools ...
```

## Non-goals

These tools are **read-only**:

- No order routing, no swap execution, no custody
- No KYC, no wallet creation, no signing
- No tokenized securities (xStocks, etc.)
- No yield routing or DeFi execution

MAXIA Oracle is positioned as a **data feed**, not a trading engine.

## License

Apache-2.0 — same as the `maxia-oracle` SDK.
