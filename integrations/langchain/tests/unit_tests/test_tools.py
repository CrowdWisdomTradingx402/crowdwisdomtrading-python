"""Unit tests: LangChain standard tool tests plus mocked HTTP (no network)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from crowdwisdomtrading import Client
from langchain_core.messages import ToolMessage
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_crowdwisdom import (
    CrowdWisdomSentimentToday,
    CrowdWisdomSentimentWeek,
    CrowdWisdomToolkit,
)

BASE = "https://api.crowdwisdomtrading.com"


def _body(ticker: str, cycle: str) -> dict[str, Any]:
    return {
        "data": {
            "ticker": ticker,
            "cycle": cycle,
            "date": "2026-11-23",
            "ProCrowdSentimentScore": -0.9,
            "ProTraders": 390,
        },
        "as_of": "2026-11-23",
        "disclaimer": "CrowdWisdom Trading data is aggregated crowd opinion for research purposes only.",
        "terms": "https://www.crowdwisdomtrading.com/api-terms",
    }


class FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code = status
        self._body = body
        self.headers: dict[str, str] = {}
        self.text = json.dumps(body)

    def json(self) -> Any:
        return self._body


class FakeSession:
    """Stands in for requests.Session; records every URL it was asked for."""

    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.status = status
        self.body = body
        self.urls: list[str] = []

    def get(self, url: str, **_: Any) -> FakeResponse:
        self.urls.append(url)
        if self.body is not None:
            return FakeResponse(self.status, self.body)
        ticker, cycle = url.rsplit("/", 1)[1], url.rsplit("/", 2)[1]
        return FakeResponse(self.status, _body(ticker, cycle))


def fake_client(session: FakeSession) -> Client:
    return Client(api_key="", wallet_key="", cache=False, session=session)  # type: ignore[arg-type]


# ----------------------------------------------------------- standard tests


class TestCrowdWisdomSentimentTodayUnit(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CrowdWisdomSentimentToday]:
        return CrowdWisdomSentimentToday

    @property
    def tool_constructor_params(self) -> dict:
        return {"client": fake_client(FakeSession())}

    @property
    def tool_invoke_params_example(self) -> dict:
        return {"ticker": "AAPL"}


class TestCrowdWisdomSentimentWeekUnit(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CrowdWisdomSentimentWeek]:
        return CrowdWisdomSentimentWeek

    @property
    def tool_constructor_params(self) -> dict:
        return {"client": fake_client(FakeSession())}

    @property
    def tool_invoke_params_example(self) -> dict:
        return {"ticker": "SPY"}


# ------------------------------------------------------------- mocked HTTP


def test_today_calls_free_daily_route_and_parses() -> None:
    session = FakeSession()
    tool = CrowdWisdomSentimentToday(client=fake_client(session))
    out = json.loads(tool.invoke({"ticker": " aapl "}))
    assert session.urls == [f"{BASE}/x402/daily/AAPL"]
    assert out["ticker"] == "AAPL"
    assert out["cycle"] == "daily"
    assert out["ProCrowdSentimentScore"] == -0.9
    assert out["ProTraders"] == 390
    assert out["date"] == "2026-11-23"
    assert "not investment advice" in out["disclaimer"] or "research" in out["disclaimer"]


def test_week_calls_free_weekly_route() -> None:
    session = FakeSession()
    tool = CrowdWisdomSentimentWeek(client=fake_client(session))
    out = json.loads(tool.invoke({"ticker": "BTC-USD"}))
    assert session.urls == [f"{BASE}/x402/weekly/BTC-USD"]
    assert out["cycle"] == "weekly"


def test_tool_call_returns_tool_message_with_artifact() -> None:
    tool = CrowdWisdomSentimentToday(client=fake_client(FakeSession()))
    msg = tool.invoke({"args": {"ticker": "GC=F"}, "id": "1", "name": tool.name, "type": "tool_call"})
    assert isinstance(msg, ToolMessage)
    assert json.loads(msg.content)["ticker"] == "GC=F"
    assert msg.artifact["data"]["ProTraders"] == 390


async def test_async_invoke() -> None:
    tool = CrowdWisdomSentimentWeek(client=fake_client(FakeSession()))
    out = json.loads(await tool.ainvoke({"ticker": "QQQ"}))
    assert out["ticker"] == "QQQ"


def test_unknown_ticker_404_returns_clear_message() -> None:
    session = FakeSession(status=404, body={"error": "NOT_FOUND"})
    tool = CrowdWisdomSentimentToday(client=fake_client(session))
    msg = tool.invoke({"args": {"ticker": "ZZZZ"}, "id": "1", "name": tool.name, "type": "tool_call"})
    assert msg.status == "error"
    assert "no crowd sentiment for 'ZZZZ'" in msg.content


def test_free_limit_429_returns_clear_message() -> None:
    session = FakeSession(status=429, body={"error": "FREE_LIMIT_REACHED"})
    tool = CrowdWisdomSentimentWeek(client=fake_client(session))
    out = tool.invoke({"ticker": "AAPL"})
    assert "free limit reached" in out


def test_default_client_is_free_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CWT_API_KEY", "should-be-ignored")
    monkeypatch.setenv("X402_WALLET_PRIVATE_KEY", "should-be-ignored")
    tool = CrowdWisdomSentimentToday()
    assert tool.client.mode == "free"


def test_empty_ticker_rejected_by_schema() -> None:
    tool = CrowdWisdomSentimentToday(client=fake_client(FakeSession()))
    with pytest.raises(Exception):
        tool.invoke({"ticker": ""})


def test_toolkit_returns_both_tools_sharing_client() -> None:
    client = fake_client(FakeSession())
    tools = CrowdWisdomToolkit(client=client).get_tools()
    assert [t.name for t in tools] == ["crowdwisdom_sentiment_today", "crowdwisdom_sentiment_week"]
    assert all(t.client is client for t in tools)


def test_tool_schema_for_models() -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    spec = convert_to_openai_tool(CrowdWisdomSentimentToday(client=fake_client(FakeSession())))
    assert spec["function"]["name"] == "crowdwisdom_sentiment_today"
    assert spec["function"]["parameters"]["required"] == ["ticker"]
