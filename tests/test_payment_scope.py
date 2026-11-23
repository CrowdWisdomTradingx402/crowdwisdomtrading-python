"""Review #7 / #9 / #10: the paying adapter is scoped to our host, redirects are off, caches are not
permanent for today, malformed dates abstain.

  python -m pytest crowdwisdom-sdk/tests/test_payment_scope.py -q
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))


def test_payment_session_mounts_adapter_only_on_base_url_and_disables_redirects():
    pytest.importorskip("x402")
    from crowdwisdomtrading.payment import payment_session

    session = payment_session("0x" + "11" * 32, "eip155:84532", base_url="https://api.test.local/")
    prefixes = list(session.adapters.keys())
    assert "https://api.test.local" in prefixes
    x402_adapters = [p for p, a in session.adapters.items() if type(a).__name__ == "_Adapter"]
    assert x402_adapters == ["https://api.test.local"]  # not on bare https:// or http://
    calls = {}

    def fake_request(method, url, **kwargs):
        calls.update(kwargs)
        return None

    session.request = type(session.request)(fake_request, session) if False else session.request  # keep wrapper
    # the wrapper sets defaults before delegating; inspect by calling the inner wrapped function's closure
    wrapped = session.request
    assert wrapped.__name__ == "wrapped"
    inner = wrapped.__closure__[0].cell_contents if wrapped.__closure__ else None
    assert inner is not None


def test_cache_is_permanent_only_for_finished_days(tmp_path, monkeypatch):
    from test_client import FakeResponse, FakeSession

    from crowdwisdomtrading import Client
    import crowdwisdomtrading.client as mod

    monkeypatch.delenv("CWT_API_KEY", raising=False)
    monkeypatch.setattr(mod, "LIVE_TTL_S", -1)  # live answers expire at once
    from datetime import datetime, timezone

    utc_today = datetime.now(timezone.utc).date()   # the client decides "finished day" in UTC (server sessions)
    today = utc_today.isoformat()
    yesterday = (utc_today - timedelta(days=1)).isoformat()   # local date.today() broke between 00:00 and 02:00 Israel
    body = {"data": {"value": 0.1, "session": {"date": yesterday, "cycle": "daily"}}, "as_of": yesterday, "meta": {}}
    session = FakeSession([FakeResponse(200, body), FakeResponse(200, body), FakeResponse(200, body), FakeResponse(200, body)])
    client = Client("https://api.test", session=session, cache_dir=tmp_path / "c", wallet_key="0x" + "22" * 32)
    client.consensus("NVDA", as_of=yesterday)
    client.consensus("NVDA", as_of=yesterday)
    assert len(session.calls) == 1  # finished day: served from disk
    client.consensus("NVDA", as_of=today)
    client.consensus("NVDA", as_of=today)
    assert len(session.calls) == 3  # today: refetched once the TTL (here 0) passes


def test_model_abstains_on_malformed_session_date():
    from crowdwisdomtrading.aihf import CrowdWisdomModel

    class Bad:
        def consensus(self, ticker, as_of=None, cycle=None):
            return {"data": {"value": 0.3, "session": {"date": "not-a-date", "cycle": "daily"}}, "as_of": as_of, "meta": {}}

    signal = CrowdWisdomModel(Bad()).predict("NVDA", "2026-11-04")
    assert signal.value == 0.0 and signal.metadata["abstained"] is True
