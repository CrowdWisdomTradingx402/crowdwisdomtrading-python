"""Rank a watch list by this week's crowd score (free). Run: python examples/weekly_watchlist.py"""
from crowdwisdomtrading import Client, CrowdWisdomError

c = Client()
rows = []
for ticker in ["SPY", "QQQ", "NVDA", "MSFT", "AMZN", "META", "TSLA", "AMD", "PLTR"]:
    try:
        d = c.weekly_sentiment(ticker)["data"]
        rows.append((d.get("ProCrowdSentimentScore") or 0, d.get("ProTraders") or 0, ticker))
    except CrowdWisdomError as e:
        print(f"{ticker}: {e}")
for score, traders, ticker in sorted(rows, reverse=True):
    print(f"{ticker:6} {score:+7.1f}  ({traders} pro traders)")
