# crowdwisdomtrading

[![PyPI](https://img.shields.io/pypi/v/crowdwisdomtrading)](https://pypi.org/project/crowdwisdomtrading/)
[![Python](https://img.shields.io/pypi/pyversions/crowdwisdomtrading)](https://pypi.org/project/crowdwisdomtrading/)
[![tests](https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python/actions/workflows/tests.yml/badge.svg)](https://github.com/CrowdWisdomTradingx402/crowdwisdomtrading-python/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CrowdWisdom Trading MCP connector](https://glama.ai/mcp/connectors/com.crowdwisdomtrading.api/crowd-wisdom-trading/badges/score.svg)](https://glama.ai/mcp/connectors/com.crowdwisdomtrading.api/crowd-wisdom-trading)
[![mcptry](https://mcptry.com/badge/com.crowdwisdomtrading.api/crowd-wisdom-trading)](https://mcptry.com/servers/com.crowdwisdomtrading.api/crowd-wisdom-trading)

**What thousands of pro traders think about any ticker, in one number.**

Every day [CrowdWisdom Trading](https://crowdwisdomtrading.com/x402?utm_source=pypi&utm_medium=readme&utm_campaign=crowdwisdomtrading)
reads what pro traders say on YouTube, X, StockTwits, Reddit, broker platforms, podcasts and newsletters, and turns
it into a **ProCrowdSentimentScore** from -100 (everyone short) to +100 (everyone long), with **ProTraders**: how many
distinct traders stand behind it.

Covers **US stocks and ETFs, crypto, futures, indices and FX**. Daily and weekly. Start free, no account, no key.

```bash
pip install crowdwisdomtrading
```

```python
from crowdwisdomtrading import Client

c = Client()
c.daily_sentiment("NVDA")      # free: today's crowd score
c.weekly_sentiment("BTC-USD")  # free: this week's
```

```json
{"ticker": "NVDA", "cycle": "daily", "date": "2026-11-06",
 "ProCrowdSentimentScore": 26.5, "ProTraders": 1746}
```

## Free and paid

| Call | Price | What you get |
|---|---|---|
| `daily_sentiment(ticker)` | **free** | today's `ProCrowdSentimentScore` and `ProTraders` (`low_coverage` when fewer than 10 traders) |
| `weekly_sentiment(ticker)` | **free** | the same for the week |
| `sample()` | **free** | one real crowd prediction, at least 7 days old |
| `catalog()` | **free** | every call, price and field |
| `consensus(ticker)` | $0.10 | direction, confidence, the score and trader count per source, versus the ticker's own past, any past date (`as_of`) |
| `setup_latest(ticker)` | $0.50 | the crowd's prediction: direction, entry, 2 targets, 2 stops, confidence, risk/reward |
| `setups_today()` | $10.00 | every prediction of the day |
| `crowdmap(ticker)` | $0.30 | CrowdMap: the crowd's support / resistance levels with how many traders named each |
| `history(ticker, from, to)` | $0.10 | past predictions as published at the time (backtest-safe) |

Free calls: 50 a day per IP address for each. Tickers: `AAPL`, `NVDA`, `BTC-USD`, `GC=F`, `^SPX`, `EURUSD=X`, ...

## Paying per call (no account)

Paid calls use [x402](https://x402.org): the API states the price, the package pays it in USDC on Base and returns
the data with a receipt. No sign-up, no API key, a failed call is never charged.

```bash
pip install "crowdwisdomtrading[x402]"
export X402_WALLET_PRIVATE_KEY=0x...    # a wallet with a few dollars of USDC on Base
```

```python
c = Client()
c.consensus("AAPL")            # $0.10
c.setup_latest("AAPL")         # $0.50
c.crowdmap("AAPL")             # $0.30
c.last_receipt                 # {"transaction": "0x...", "network": "eip155:8453", ...}
```

Monthly plan customers use their key instead (`CWT_API_KEY=cwt_live_...`); a key always wins over a wallet.
Fund the wallet with small amounts: the package pays only the quoted price.

## More

```python
c.consensus("NVDA", as_of="2026-11-04")        # the crowd as it was on that day
c.history("NVDA", "2026-10-01", "2026-10-31")  # only predictions published by the end date
```

Answers for past dates are cached on disk (`~/.crowdwisdomtrading/cache`), so a backtest pays once per ticker and day;
live answers are cached for 10 minutes. `Client(cache=False)` turns it off.

Command line:

```bash
crowdwisdomtrading daily NVDA
crowdwisdomtrading weekly BTC-USD
crowdwisdomtrading catalog
```

## Examples

[`examples/quickstart.py`](examples/quickstart.py) (free scores) · [`examples/weekly_watchlist.py`](examples/weekly_watchlist.py)
(rank a watch list) · [`examples/paid_consensus.py`](examples/paid_consensus.py) (x402 paid call)

## MCP server (Claude, ChatGPT, Cursor)

The same free daily and weekly scores are available as a remote MCP server, no key:

```
https://api.crowdwisdomtrading.com/mcp
```

Tools: `get_crowd_sentiment_today(ticker)` and `get_crowd_sentiment_week(ticker)`. In Claude Code:
`claude mcp add --transport http crowdwisdomtrading https://api.crowdwisdomtrading.com/mcp`

## Integrations

**virattt/ai-hedge-fund**: a ready ProCrowdSentimentScore model. `pip install "crowdwisdomtrading[aihf]"`, then

```python
from crowdwisdomtrading.aihf import CrowdWisdomModel
ALPHA_MODEL_REGISTRY["crowdwisdom"] = CrowdWisdomModel
```

It returns a signal from -1 to +1 per ticker and date, never looks at data after that date, and abstains when the
crowd data is older than 10 days.

## Terms of use

The data is provided under the CrowdWisdom Trading API Terms: https://www.crowdwisdomtrading.com/api-terms
**Personal or internal use only. Redistribution, republishing or resale of the data, raw or derived, is prohibited.**
The package's MIT license covers its code only, not the data it returns.

## Links and notes

- Docs, prices and plans: https://crowdwisdomtrading.com/x402?utm_source=pypi&utm_medium=readme&utm_campaign=crowdwisdomtrading
- Live price list: https://api.crowdwisdomtrading.com/x402/catalog
- API terms: https://www.crowdwisdomtrading.com/api-terms
- Aggregated crowd opinion for research. Not investment advice. Payments are final; a failed call is not charged.
