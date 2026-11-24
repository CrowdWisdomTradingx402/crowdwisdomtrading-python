"""Unit tests for the CrowdWisdom Dify plugin (no network unless CROWDWISDOM_LIVE=1)."""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import client  # noqa: E402

SAMPLE = {
    "data": {
        "ticker": "AAPL",
        "cycle": "daily",
        "date": "2026-11-23",
        "ProCrowdSentimentScore": -0.9,
        "ProTraders": 390,
    },
    "as_of": "2026-11-23",
    "disclaimer": "CrowdWisdom Trading data is aggregated crowd opinion for research purposes only.",
    "terms": "https://www.crowdwisdomtrading.com/api-terms",
}


class FakeResponse:
    def __init__(self, status_code, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("bad json")
        return self._payload


def fake_session(response=None, exc=None):
    session = mock.Mock()
    if exc is not None:
        session.get.side_effect = exc
    else:
        session.get.return_value = response
    return session


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("aapl", "AAPL"), (" $nvda ", "NVDA"), ("btc-usd", "BTC-USD"), ("GC=F", "GC=F"),
     ("EURUSD=X", "EURUSD=X"), ("brk.b", "BRK.B"), ("^SPX", "^SPX")],
)
def test_normalize_ticker_accepts_supported_symbols(raw, expected):
    assert client.normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "../etc", "AAPL/x", "a b", "http://x", "A" * 25, "AAPL?x=1"])
def test_normalize_ticker_rejects_bad_input(raw):
    with pytest.raises(client.CrowdWisdomError):
        client.normalize_ticker(raw)


@pytest.mark.parametrize(("cycle", "path"), [("daily", "/x402/daily/GC%3DF"), ("weekly", "/x402/weekly/GC%3DF")])
def test_get_sentiment_calls_fixed_url_with_timeout(cycle, path):
    session = fake_session(FakeResponse(200, SAMPLE))
    assert client.get_sentiment("gc=f", cycle, session=session) == SAMPLE
    url = session.get.call_args.args[0]
    assert url == "https://api.crowdwisdomtrading.com" + path
    assert session.get.call_args.kwargs["timeout"] == client.TIMEOUT_SECONDS


def test_bad_cycle_rejected():
    with pytest.raises(ValueError):
        client.get_sentiment("AAPL", "monthly", session=fake_session(FakeResponse(200, SAMPLE)))


@pytest.mark.parametrize(
    ("response", "needle"),
    [
        (FakeResponse(404, {}), "No crowd sentiment found for 'ZZZZ'"),
        (FakeResponse(429, {"error": "FREE_LIMIT_REACHED"}), "free limit of 50 calls a day"),
        (FakeResponse(500, {}), "HTTP 500"),
        (FakeResponse(200, bad_json=True), "unreadable"),
        (FakeResponse(200, {"oops": 1}), "unexpected"),
    ],
)
def test_error_responses_give_clear_messages(response, needle):
    with pytest.raises(client.CrowdWisdomError, match=needle):
        client.get_sentiment("zzzz", "daily", session=fake_session(response))


def test_network_error_message():
    session = fake_session(exc=requests.ConnectionError("boom"))
    with pytest.raises(client.CrowdWisdomError, match="Could not reach"):
        client.get_sentiment("AAPL", "daily", session=session)


def test_summarize_mentions_score_traders_source_and_disclaimer():
    text = client.summarize(SAMPLE, "today")
    for part in ("AAPL", "today", "2026-11-23", "-0.9", "390", "-100", "+100",
                 "CrowdWisdom Trading", "https://www.crowdwisdomtrading.com/x402", "research purposes only"):
        assert part in text


def test_tool_classes_load_with_official_dify_class_loader():
    from dify_plugin import Tool
    from dify_plugin.core.utils.class_loader import load_single_subclass_from_source

    for name, cls_name in (("sentiment_today", "SentimentTodayTool"), ("sentiment_week", "SentimentWeekTool")):
        cls = load_single_subclass_from_source(
            module_name=f"tools.{name}", script_path=str(ROOT / "tools" / f"{name}.py"), parent_type=Tool
        )
        assert cls.__name__ == cls_name


def test_yaml_files_match_python_sources_and_manifest():
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["privacy"] == "PRIVACY.md" and (ROOT / "PRIVACY.md").is_file()
    assert (ROOT / "_assets" / manifest["icon"]).is_file()
    assert manifest["tags"] == ["finance"]
    provider = yaml.safe_load((ROOT / manifest["plugins"]["tools"][0]).read_text(encoding="utf-8"))
    assert "credentials_for_provider" not in provider
    names = []
    for tool_path in provider["tools"]:
        tool = yaml.safe_load((ROOT / tool_path).read_text(encoding="utf-8"))
        assert (ROOT / tool["extra"]["python"]["source"]).is_file()
        assert [p["name"] for p in tool["parameters"]] == ["ticker"]
        names.append(tool["identity"]["name"])
    assert names == ["get_crowd_sentiment_today", "get_crowd_sentiment_week"]


@pytest.mark.skipif(os.environ.get("CROWDWISDOM_LIVE") != "1", reason="live call only with CROWDWISDOM_LIVE=1")
@pytest.mark.parametrize("cycle", ["daily", "weekly"])
def test_live_endpoint(cycle):
    payload = client.get_sentiment("SPY", cycle)
    data = payload["data"]
    assert data["ticker"] == "SPY"
    assert -100 <= data["ProCrowdSentimentScore"] <= 100
    assert data["ProTraders"] > 0
    assert payload["terms"].startswith("https://")
