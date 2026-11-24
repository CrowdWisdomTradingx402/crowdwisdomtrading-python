"""LangChain tools for the free CrowdWisdom Trading crowd sentiment endpoints.

Both tools call the free routes (no key, no wallet, never pay):

* ``GET https://api.crowdwisdomtrading.com/x402/daily/{ticker}``
* ``GET https://api.crowdwisdomtrading.com/x402/weekly/{ticker}``

The free routes allow 50 calls a day per IP address. The data is aggregated crowd
opinion for research only, not investment advice.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from crowdwisdomtrading import Client
from crowdwisdomtrading.client import CrowdWisdomError
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field, model_validator

DOCS_URL = "https://www.crowdwisdomtrading.com/x402"


class CrowdWisdomSentimentInput(BaseModel):
    """Input for the CrowdWisdom sentiment tools."""

    ticker: str = Field(
        description=(
            "Ticker symbol, e.g. AAPL (US stock), SPY (ETF), BTC-USD (crypto), "
            "GC=F (futures) or EURUSD=X (FX)."
        ),
        min_length=1,
        max_length=20,
    )


def _free_client() -> Client:
    # Explicit empty key and wallet: the tools only use the free routes and never pay,
    # even if CWT_API_KEY or X402_WALLET_PRIVATE_KEY happen to be set in the environment.
    return Client(api_key="", wallet_key="")


class _CrowdWisdomSentimentBase(BaseTool):
    """Shared logic for the daily and weekly tools."""

    args_schema: type[BaseModel] = CrowdWisdomSentimentInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    handle_tool_error: bool = True

    client: Any = Field(default=None, exclude=True)
    """A ``crowdwisdomtrading.Client``. Built with free settings when not given."""

    _cycle: str = "daily"

    @model_validator(mode="after")
    def _ensure_client(self) -> "_CrowdWisdomSentimentBase":
        if self.client is None:
            self.client = _free_client()
        return self

    def _fetch(self, ticker: str) -> dict[str, Any]:
        raise NotImplementedError

    def _run(
        self,
        ticker: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        symbol = ticker.upper().strip()
        try:
            body = self._fetch(symbol)
        except CrowdWisdomError as exc:
            if exc.status == 404:
                raise ToolException(
                    f"CrowdWisdom Trading has no crowd sentiment for '{symbol}'. "
                    "Check the ticker symbol (e.g. AAPL, SPY, BTC-USD, GC=F)."
                ) from None
            if exc.status == 429:
                raise ToolException(
                    "CrowdWisdom Trading free limit reached (50 calls a day per IP). "
                    f"Try again tomorrow or see {DOCS_URL}."
                ) from None
            raise ToolException(f"CrowdWisdom Trading request failed: {exc}") from None

        data = body.get("data") or {}
        summary = {
            "ticker": data.get("ticker", symbol),
            "cycle": data.get("cycle", self._cycle),
            "date": data.get("date"),
            "ProCrowdSentimentScore": data.get("ProCrowdSentimentScore"),
            "ProTraders": data.get("ProTraders"),
            "scale": "-100 = everyone short, 0 = split, +100 = everyone long",
            "source": "CrowdWisdom Trading",
            "learn_more": DOCS_URL,
            "disclaimer": body.get("disclaimer")
            or "Aggregated crowd opinion for research only, not investment advice.",
        }
        return json.dumps(summary), body


class CrowdWisdomSentimentToday(_CrowdWisdomSentimentBase):
    """Today's crowd sentiment for one ticker from CrowdWisdom Trading.

    Setup:
        .. code-block:: bash

            pip install -U langchain-crowdwisdom

        No API key is needed. The free route allows 50 calls a day per IP.

    Instantiate:
        .. code-block:: python

            from langchain_crowdwisdom import CrowdWisdomSentimentToday

            tool = CrowdWisdomSentimentToday()

    Invoke directly with args:
        .. code-block:: python

            tool.invoke({"ticker": "AAPL"})

    Invoke with ToolCall:
        .. code-block:: python

            tool.invoke(
                {"args": {"ticker": "AAPL"}, "id": "1", "name": tool.name, "type": "tool_call"}
            )
    """

    name: str = "crowdwisdom_sentiment_today"
    description: str = (
        "Get the latest daily crowd sentiment for one ticker (US stock, ETF, crypto such "
        "as BTC-USD, futures such as GC=F, or FX). Returns ProCrowdSentimentScore from "
        "-100 (everyone short) to +100 (everyone long), the number of distinct pro "
        "traders behind it (ProTraders) and the session date. Aggregated crowd opinion "
        "for research, not investment advice."
    )
    _cycle: str = "daily"

    def _fetch(self, ticker: str) -> dict[str, Any]:
        return self.client.daily_sentiment(ticker)


class CrowdWisdomSentimentWeek(_CrowdWisdomSentimentBase):
    """This week's crowd sentiment for one ticker from CrowdWisdom Trading.

    Setup:
        .. code-block:: bash

            pip install -U langchain-crowdwisdom

        No API key is needed. The free route allows 50 calls a day per IP.

    Instantiate:
        .. code-block:: python

            from langchain_crowdwisdom import CrowdWisdomSentimentWeek

            tool = CrowdWisdomSentimentWeek()

    Invoke directly with args:
        .. code-block:: python

            tool.invoke({"ticker": "SPY"})
    """

    name: str = "crowdwisdom_sentiment_week"
    description: str = (
        "Get the latest weekly crowd sentiment for one ticker (US stock, ETF, crypto such "
        "as BTC-USD, futures such as GC=F, or FX). Returns ProCrowdSentimentScore from "
        "-100 (everyone short) to +100 (everyone long), the number of distinct pro "
        "traders behind it (ProTraders) and the week's session date. Aggregated crowd "
        "opinion for research, not investment advice."
    )
    _cycle: str = "weekly"

    def _fetch(self, ticker: str) -> dict[str, Any]:
        return self.client.weekly_sentiment(ticker)
