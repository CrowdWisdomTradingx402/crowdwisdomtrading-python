# langchain-crowdwisdom

LangChain tools for [CrowdWisdom Trading](https://www.crowdwisdomtrading.com/x402): the crowd's daily and weekly
sentiment for one ticker, as a single score from thousands of pro traders.

- **Free, no API key.** 50 calls a day per IP address.
- **Covers** US stocks, ETFs, crypto (e.g. `BTC-USD`), futures (e.g. `GC=F`) and FX.
- **Returns** `ProCrowdSentimentScore` from -100 (everyone short) to +100 (everyone long), `ProTraders`
  (how many distinct pro traders are behind it) and the session `date`.

The data is aggregated crowd opinion for research only. It is not investment advice.

## Installation

```bash
pip install -U langchain-crowdwisdom
```

## Tools

| Class | Tool name | Route |
|---|---|---|
| `CrowdWisdomSentimentToday` | `crowdwisdom_sentiment_today` | `GET /x402/daily/{ticker}` |
| `CrowdWisdomSentimentWeek` | `crowdwisdom_sentiment_week` | `GET /x402/weekly/{ticker}` |
| `CrowdWisdomToolkit` | both tools above | |

Both tools take one argument, `ticker`.

## Usage

### Call a tool directly

```python
from langchain_crowdwisdom import CrowdWisdomSentimentToday

tool = CrowdWisdomSentimentToday()
print(tool.invoke({"ticker": "AAPL"}))
```

```json
{"ticker": "AAPL", "cycle": "daily", "date": "2026-11-23", "ProCrowdSentimentScore": -0.9, "ProTraders": 390,
 "scale": "-100 = everyone short, 0 = split, +100 = everyone long", "source": "CrowdWisdom Trading",
 "learn_more": "https://www.crowdwisdomtrading.com/x402", "disclaimer": "..."}
```

When called with a `ToolCall`, the tool returns a `ToolMessage` whose `content` is the JSON above and whose
`artifact` is the full API response.

### Use the toolkit in an agent

```python
from langchain.agents import create_agent
from langchain_crowdwisdom import CrowdWisdomToolkit

tools = CrowdWisdomToolkit().get_tools()
agent = create_agent("anthropic:claude-sonnet-4-5", tools)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What is the crowd's weekly sentiment on SPY and on BTC-USD?"}]}
)
print(result["messages"][-1].content)
```

Any chat model with tool calling works the same way, e.g. `llm.bind_tools(tools)`.

### Errors

Errors come back to the model as a tool message, not an exception:

| Case | Message |
|---|---|
| Unknown ticker (HTTP 404) | `CrowdWisdom Trading has no crowd sentiment for 'XYZ'...` |
| Free limit reached (HTTP 429 `FREE_LIMIT_REACHED`) | `CrowdWisdom Trading free limit reached (50 calls a day per IP)...` |

The tools never pay and never send a key, even if `CWT_API_KEY` or `X402_WALLET_PRIVATE_KEY` is set. Answers are
cached on disk for 10 minutes, so repeat calls for the same ticker do not use up the free limit.

The tools are built on the MIT [`crowdwisdomtrading`](https://pypi.org/project/crowdwisdomtrading/) Python client,
which also has paid per-call routes (direction, per-source scores, history).

## Development

```bash
pip install -e ".[test]"
pytest tests/unit_tests --disable-socket -k "not async"   # offline, mocked HTTP
pytest tests/unit_tests                                    # incl. async test (needs a local socket on Windows)
pytest tests/integration_tests                             # live, at most 2 calls to the free API
```

## Links

- Docs: https://www.crowdwisdomtrading.com/x402
- Terms: https://www.crowdwisdomtrading.com/api-terms
- Source: https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python/tree/main/integrations/langchain

## License

MIT
