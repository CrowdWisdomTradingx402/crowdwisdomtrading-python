# CrowdWisdom Trading MCP plugin

Connect an agent to CrowdWisdom Trading's hosted MCP server at
`https://api.crowdwisdomtrading.com/mcp` (Streamable HTTP, no sign-in, no keys in config).

It answers one question: what does the crowd of pro traders think about a ticker right now? Each
tool returns a crowd sentiment score from -100 (everyone short) to +100 (everyone long) and the
number of distinct pro traders behind it, for US stocks, ETFs, crypto, futures and FX.

## Tools

| Tool | Returns |
|---|---|
| `get_crowd_sentiment_today(ticker)` | today's crowd sentiment score and trader count |
| `get_crowd_sentiment_week(ticker)` | the same for this week |

Both tools are read-only. Free, 50 calls a day per IP address.

## Example prompts

- "What is the crowd sentiment on NVDA today?"
- "Is the crowd long or short SPY this week, and how many traders is that based on?"
- "Compare today's crowd sentiment on BTC-USD and ETH-USD."

## Data handling

This is a hosted-only connector: the package holds configuration only, no local code. Every tool
call goes to `api.crowdwisdomtrading.com`, which receives the ticker you ask about and your IP
address (used for the daily free-call limit). The hosted server is not open source; the tool set
is served by the server at runtime. Do not put secrets in prompts or tool arguments.

The data is aggregated crowd opinion for research. It is not investment advice.

## Links

- [Documentation](https://www.crowdwisdomtrading.com/x402)
- Official MCP Registry id: `com.crowdwisdomtrading.api/crowd-wisdom-trading`
- [Python client (MIT)](https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python)
- [Report an issue](https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python/issues)
