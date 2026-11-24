# CrowdWisdom Pro Crowd Sentiment for Dify

Read-only Dify tools that return what professional traders as a crowd think about
one ticker, from [CrowdWisdom Trading](https://www.crowdwisdomtrading.com/x402).
Works for US stocks, ETFs, crypto (`BTC-USD`), futures (`GC=F`) and FX
(`EURUSD=X`).

## Tools

| Tool | What it returns |
|---|---|
| **Pro crowd sentiment today** (`get_crowd_sentiment_today`) | Today's score and pro trader count for one ticker |
| **Pro crowd sentiment this week** (`get_crowd_sentiment_week`) | This week's score and pro trader count for one ticker |

Each tool takes one parameter, `ticker`, and returns a short text line for the
LLM plus the full JSON response, for example:

```json
{
  "data": {
    "ticker": "AAPL",
    "cycle": "daily",
    "date": "2026-11-23",
    "ProCrowdSentimentScore": -0.9,
    "ProTraders": 390
  },
  "disclaimer": "CrowdWisdom Trading data is aggregated crowd opinion for research purposes only. ...",
  "terms": "https://www.crowdwisdomtrading.com/api-terms"
}
```

- `ProCrowdSentimentScore`: -100 (everyone short) to +100 (everyone long).
- `ProTraders`: number of distinct pro traders behind the score.

The data is aggregated crowd opinion for research. It is not investment advice.

## Setup

1. Install the plugin from the Dify Marketplace.
2. No API key, credential or authorization step is needed. The tools are ready to use.
3. Add a tool to an Agent, Chatflow or Workflow and pass a ticker.

## Usage example

In an Agent app, enable both tools and ask: "What do pro traders think about
NVDA today, and how does that compare with this week?" The agent calls
`get_crowd_sentiment_today` and `get_crowd_sentiment_week` with `NVDA`.

In a Workflow, add the tool node and map a ticker variable to `ticker`; use the
JSON output (`data.ProCrowdSentimentScore`, `data.ProTraders`) in later nodes.

## Connection requirements and limits

- Network: outbound HTTPS to `api.crowdwisdomtrading.com` only (endpoints
  `GET /x402/daily/{ticker}` and `GET /x402/weekly/{ticker}`), 15-second timeout.
- Free limit: 50 calls a day per IP address. After that the API answers
  HTTP 429 and the tool says the free limit is reached. On Dify Cloud the IP is
  shared, so heavy users should self-host.
- An unknown ticker returns a clear "no crowd sentiment found" message.
- Paid detail (direction, confidence, per-source scores, history) exists over
  x402 at https://www.crowdwisdomtrading.com/x402; this plugin uses only the free
  endpoints.

## Privacy

The plugin sends only the ticker to `api.crowdwisdomtrading.com`. Our server sees
and logs the caller's IP address for the free limit and service logs. See
[PRIVACY.md](PRIVACY.md) and https://www.crowdwisdomtrading.com/privacy.
Terms: https://www.crowdwisdomtrading.com/api-terms

## Source and contact

- Source repository:
  https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python/tree/main/integrations/dify/crowdwisdom
- Contact: gilad@crowdwisdomtrading.com

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest tests -q
dify-plugin plugin package .
```
