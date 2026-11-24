"""Live tests against the free CrowdWisdom Trading API.

Run: pytest tests/integration_tests

Live call budget: the standard suite invokes each tool 4 times, but one shared
client with a 10-minute cache answers repeats locally, so this file makes at most
2 network calls (1 daily + 1 weekly). The free routes allow 50 calls a day per IP.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from crowdwisdomtrading import Client
from langchain_tests.integration_tests import ToolsIntegrationTests

from langchain_crowdwisdom import CrowdWisdomSentimentToday, CrowdWisdomSentimentWeek

pytestmark = pytest.mark.integration

_CACHE_DIR = Path(tempfile.mkdtemp(prefix="cwt-langchain-"))
_CLIENT = Client(api_key="", wallet_key="", cache_dir=_CACHE_DIR)


class TestCrowdWisdomSentimentTodayIntegration(ToolsIntegrationTests):
    @property
    def tool_constructor(self) -> type[CrowdWisdomSentimentToday]:
        return CrowdWisdomSentimentToday

    @property
    def tool_constructor_params(self) -> dict:
        return {"client": _CLIENT}

    @property
    def tool_invoke_params_example(self) -> dict:
        return {"ticker": "AAPL"}


class TestCrowdWisdomSentimentWeekIntegration(ToolsIntegrationTests):
    @property
    def tool_constructor(self) -> type[CrowdWisdomSentimentWeek]:
        return CrowdWisdomSentimentWeek

    @property
    def tool_constructor_params(self) -> dict:
        return {"client": _CLIENT}

    @property
    def tool_invoke_params_example(self) -> dict:
        return {"ticker": "AAPL"}


def test_live_shape() -> None:
    """Checks the real fields (served from the shared cache, no extra call)."""
    out = json.loads(CrowdWisdomSentimentToday(client=_CLIENT).invoke({"ticker": "AAPL"}))
    assert out["ticker"] == "AAPL"
    assert -100 <= float(out["ProCrowdSentimentScore"]) <= 100
    assert int(out["ProTraders"]) >= 0
    assert out["date"]
    # one cache file per real network call: the whole module stays within 2 live calls
    assert len(list(_CACHE_DIR.glob("*.json"))) <= 2
