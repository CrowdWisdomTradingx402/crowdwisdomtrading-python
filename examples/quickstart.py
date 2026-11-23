"""Free crowd score for a few tickers (no account, no key). Run: python examples/quickstart.py"""
from crowdwisdomtrading import Client

c = Client()
for ticker in ["NVDA", "AAPL", "TSLA", "BTC-USD", "GC=F"]:
    d = c.daily_sentiment(ticker)["data"]
    print(f"{ticker:8} score {d.get('ProCrowdSentimentScore'):>6}  pro traders {d.get('ProTraders')}")
