"""Small client for the free CrowdWisdom Trading endpoints.

Only two fixed URLs are called:
  GET https://api.crowdwisdomtrading.com/x402/daily/{ticker}
  GET https://api.crowdwisdomtrading.com/x402/weekly/{ticker}
No API key is sent. The only user input that leaves Dify is the ticker.
"""

import re
from typing import Any
from urllib.parse import quote

import requests

BASE_URL = "https://api.crowdwisdomtrading.com/x402"
TIMEOUT_SECONDS = 15
DOCS_URL = "https://www.crowdwisdomtrading.com/x402"

# Stocks/ETFs (AAPL, BRK.B), crypto (BTC-USD), futures (GC=F), FX (EURUSD=X), indexes (^SPX).
_TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,19}$")

JsonPayload = dict[str, Any]


class CrowdWisdomError(Exception):
    """Error with a message that is safe to show to the user."""


def normalize_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    if ticker.startswith("$"):
        ticker = ticker[1:]
    if not ticker:
        raise CrowdWisdomError("Please give a ticker symbol, for example AAPL, SPY, BTC-USD or GC=F.")
    if not _TICKER_RE.match(ticker):
        raise CrowdWisdomError(
            f"'{ticker}' does not look like a ticker symbol. Use a symbol such as AAPL, SPY, "
            "BTC-USD, GC=F or EURUSD=X."
        )
    return ticker


def get_sentiment(ticker: Any, cycle: str, session: Any = None) -> JsonPayload:
    """Return the JSON payload for one ticker. cycle is 'daily' or 'weekly'."""
    if cycle not in ("daily", "weekly"):
        raise ValueError("cycle must be 'daily' or 'weekly'")
    symbol = normalize_ticker(ticker)
    url = f"{BASE_URL}/{cycle}/{quote(symbol, safe='')}"
    http = session or requests
    try:
        response = http.get(url, timeout=TIMEOUT_SECONDS, headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        raise CrowdWisdomError("Could not reach the CrowdWisdom Trading API. Please try again later.") from exc

    if response.status_code == 404:
        raise CrowdWisdomError(f"No crowd sentiment found for '{symbol}'. Check the ticker symbol.")
    if response.status_code == 429:
        raise CrowdWisdomError(
            "The free limit of 50 calls a day for this IP address has been reached. "
            f"Try again tomorrow, or see {DOCS_URL} for paid access."
        )
    if response.status_code != 200:
        raise CrowdWisdomError(
            f"The CrowdWisdom Trading API returned HTTP {response.status_code}. Please try again later."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise CrowdWisdomError("The CrowdWisdom Trading API returned an unreadable response.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise CrowdWisdomError("The CrowdWisdom Trading API returned an unexpected response.")
    return payload


def summarize(payload: JsonPayload, period: str) -> str:
    """One plain-language line for the LLM, with source and disclaimer."""
    data = payload.get("data") or {}
    ticker = data.get("ticker", "?")
    score = data.get("ProCrowdSentimentScore")
    traders = data.get("ProTraders")
    date = data.get("date") or payload.get("as_of") or "?"
    text = (
        f"CrowdWisdom Trading pro crowd sentiment for {ticker} ({period}, {date}): "
        f"ProCrowdSentimentScore {score} on a scale from -100 (everyone short) to +100 "
        f"(everyone long), from {traders} distinct pro traders. Source: CrowdWisdom Trading, {DOCS_URL}."
    )
    disclaimer = payload.get("disclaimer")
    if disclaimer:
        text += f" {disclaimer}"
    return text
