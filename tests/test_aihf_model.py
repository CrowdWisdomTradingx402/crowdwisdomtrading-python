"""CrowdWisdomModel: Signal shape, point-in-time, abstain, no data_client use (QA-10, QA-13 offline part).

  python -m pytest crowdwisdom-sdk/tests/test_aihf_model.py -q
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

from crowdwisdomtrading.aihf import HAVE_AIHF, CrowdWisdomModel, Signal  # noqa: E402


class FakeClient:
    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []

    def consensus(self, ticker: str, as_of=None, cycle=None):
        self.calls.append({"ticker": ticker, "as_of": as_of, "cycle": cycle})
        key = f"{ticker}:{as_of}"
        if key not in self.answers:
            raise RuntimeError("boom")
        return self.answers[key]


def _answer(day: str, value: float, score: float, direction: str = "BULLISH", session_day: str | None = None, cached: bool = False):
    return {
        "data": {
            "ticker": "NVDA",
            "value": value,
            "ProCrowdSentimentScore": score,
            "direction": direction,
            "confidence": 70,
            "session": {"date": session_day or day, "cycle": "daily"},
            "mentions": {"youtube": 2, "x": 8, "reddit": 0, "total": 10},
            "sources": {"youtube": 80.0, "x": 20.0, "reddit": None},
            "ProTraders": {"youtube": 3, "x": 9, "total": 12},
        },
        "as_of": day,
        "meta": {"payment": {"transaction": "0xtx"}, "cached": cached},
    }


class Explodes:
    def __getattr__(self, name: str):
        raise AssertionError(f"data_client.{name} must not be used")


def test_predict_returns_signal_in_unit_interval_with_components():
    client = FakeClient({"NVDA:2026-11-04": _answer("2026-11-04", 0.32, 32.0)})
    model = CrowdWisdomModel(client)
    signal = model.predict("NVDA", "2026-11-04", Explodes())
    assert isinstance(signal, Signal)
    assert signal.model_name == "crowdwisdom" and signal.ticker == "NVDA" and signal.date == "2026-11-04"
    assert signal.value == 0.32
    assert signal.components == {"youtube": 0.8, "x": 0.2}
    assert signal.metadata["as_of"] == "2026-11-04" and signal.metadata["payment_tx"] == "0xtx"
    assert signal.metadata["mentions"]["total"] == 10
    assert signal.horizon_days == 5
    assert "BULLISH" in signal.reasoning and "ProCrowdSentimentScore +32" in signal.reasoning and "12 ProTraders" in signal.reasoning
    assert signal.metadata["ProTraders"] == 12 and signal.metadata["ProCrowdSentimentScore"] == 32.0
    assert model.name == "crowdwisdom"
    assert CrowdWisdomModel.investment_approach == "long_short"
    assert "investment_approach" in vars(CrowdWisdomModel) and "horizon_days" in vars(CrowdWisdomModel)


def test_point_in_time_as_of_equals_date_and_date_objects_accepted():
    client = FakeClient({"NVDA:2026-11-02": _answer("2026-11-02", 0.1, 10.0, session_day="2026-11-01")})
    signal = CrowdWisdomModel(client).predict("NVDA", date(2026, 11, 2))
    assert client.calls == [{"ticker": "NVDA", "as_of": "2026-11-02", "cycle": None}]
    assert signal.metadata["as_of"] == "2026-11-01"  # the session used, never after the date
    assert signal.value == 0.1


def test_abstains_when_session_is_stale_or_missing():
    client = FakeClient(
        {
            "NVDA:2026-11-20": _answer("2026-11-20", 0.5, 50.0, session_day="2026-11-01"),
            "NVDA:2026-11-21": {"data": {"value": None, "session": None}, "as_of": "2026-11-21", "meta": {}},
        }
    )
    model = CrowdWisdomModel(client, max_staleness_days=10)
    stale = model.predict("NVDA", "2026-11-20")
    assert stale.value == 0.0 and stale.metadata.get("abstained") is True and "19 days old" in stale.reasoning
    missing = model.predict("NVDA", "2026-11-21")
    assert missing.value == 0.0 and missing.metadata.get("abstained") is True
    failed = model.predict("NVDA", "2026-11-22")  # client raises
    assert failed.value == 0.0 and failed.metadata.get("abstained") is True and "unavailable" in failed.reasoning


def test_value_clamped_and_neutral_band():
    client = FakeClient({"NVDA:2026-11-04": _answer("2026-11-04", 1.7, 170.0), "TSLA:2026-11-04": _answer("2026-11-04", 0.03, 3.0, "NEUTRAL")})
    assert CrowdWisdomModel(client).predict("NVDA", "2026-11-04").value == 1.0
    assert CrowdWisdomModel(client, neutral_band=0.05).predict("TSLA", "2026-11-04").value == 0.0


def test_real_aihf_classes_when_installed():
    if not HAVE_AIHF:
        import pytest

        pytest.skip("aihf not installed; shim classes in use")
    from hedge_fund.signals.base import AlphaModel

    assert issubclass(CrowdWisdomModel, AlphaModel)


def test_old_name_still_imports():
    from crowdwisdomtrading.aihf import CrowdConsensusModel

    assert CrowdConsensusModel is CrowdWisdomModel
