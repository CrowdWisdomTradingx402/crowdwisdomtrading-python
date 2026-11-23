"""crowdwisdomtrading.Client with a fake transport (no network, no payment) (QA-10, SEC-11).

  python -m pytest crowdwisdom-sdk/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

from crowdwisdomtrading import Client, CrowdWisdomError, PaymentFailed  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = str(body)

    def json(self) -> Any:
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: Any = None, headers: Any = None, timeout: Any = None) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.responses.pop(0)


def _client(tmp_path, responses, **kw) -> tuple[Client, FakeSession]:
    session = FakeSession(responses)
    client = Client("https://api.test", session=session, cache_dir=tmp_path / "cache", **kw)
    return client, session


def test_key_mode_sends_bearer_and_wins_over_wallet(tmp_path, monkeypatch):
    monkeypatch.setenv("X402_WALLET_PRIVATE_KEY", "0x" + "11" * 32)
    client, session = _client(tmp_path, [FakeResponse(200, {"path": [{"date": "2026-11-04", "cycle": "daily", "score": 42.0, "direction": "BULLISH"}], "meta": {}})], api_key="cwt_live_abc")
    assert client.mode == "key" and not client.pays_per_call()
    out = client.consensus("nvda")
    assert session.calls[0]["url"] == "https://api.test/v1/sentiment/NVDA"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer cwt_live_abc"
    assert out["data"]["value"] == 0.42 and out["data"]["session"]["date"] == "2026-11-04"


def test_wallet_mode_calls_x402_and_reads_receipt(tmp_path, monkeypatch):
    from x402.http import encode_payment_response_header
    from x402.schemas import SettleResponse

    monkeypatch.delenv("CWT_API_KEY", raising=False)
    receipt = encode_payment_response_header(SettleResponse(success=True, transaction="0xtx", network="eip155:8453", payer="0xme", amount="100000"))
    body = {"data": {"ticker": "NVDA", "value": 0.32, "session": {"date": "2026-11-04", "cycle": "daily"}}, "as_of": "2026-11-04", "meta": {"request_id": "r1"}}
    client, session = _client(tmp_path, [FakeResponse(200, body, {"PAYMENT-RESPONSE": receipt})], wallet_key="0x" + "22" * 32)
    assert client.mode == "wallet" and client.pays_per_call()
    out = client.consensus("NVDA", as_of="2026-11-04")
    assert session.calls[0]["url"] == "https://api.test/x402/consensus/NVDA"
    assert session.calls[0]["params"] == {"as_of": "2026-11-04"}
    assert "Authorization" not in session.calls[0]["headers"]
    assert out["meta"]["payment"]["transaction"] == "0xtx"
    assert client.last_receipt["payer"] == "0xme"


def test_point_in_time_answers_cached_live_answers_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    body = {"data": {"value": 0.1, "session": {"date": "2026-11-01", "cycle": "daily"}}, "as_of": "2026-11-01", "meta": {}}
    client, session = _client(tmp_path, [FakeResponse(200, body), FakeResponse(200, body)], wallet_key="0x" + "22" * 32)
    first = client.consensus("NVDA", as_of="2026-11-01")
    second = client.consensus("NVDA", as_of="2026-11-01")
    assert len(session.calls) == 1  # cache hit: no second payment
    assert first["meta"]["cached"] is False and second["meta"]["cached"] is True
    # live (no as_of) is cached only for the TTL
    client.consensus("NVDA")
    assert len(session.calls) == 2
    import crowdwisdomtrading.client as mod

    monkeypatch.setattr(mod, "LIVE_TTL_S", -1)
    client2 = Client("https://api.test", session=session, cache_dir=tmp_path / "cache", wallet_key="0x" + "22" * 32)
    session.responses.append(FakeResponse(200, body))
    client2.consensus("NVDA")
    assert len(session.calls) == 3


def test_errors_are_not_cached_and_carry_status(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    client, session = _client(tmp_path, [FakeResponse(503, {"error": "down"}), FakeResponse(200, {"data": {"value": 0.5, "session": {"date": "2026-11-01"}}, "meta": {}})], wallet_key="0x" + "22" * 32)
    with pytest.raises(CrowdWisdomError) as info:
        client.consensus("NVDA", as_of="2026-11-01")
    assert info.value.status == 503
    assert client.consensus("NVDA", as_of="2026-11-01")["data"]["value"] == 0.5
    assert len(session.calls) == 2


def test_402_without_wallet_raises_payment_failed(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    monkeypatch.delenv("X402_WALLET_PRIVATE_KEY", raising=False)
    client, _ = _client(tmp_path, [FakeResponse(402, {"error": "Payment required"})])
    assert client.mode == "free"
    with pytest.raises(PaymentFailed):
        client.consensus("NVDA")


def test_history_and_levels_routes(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    client, session = _client(
        tmp_path,
        [FakeResponse(200, {"data": {"count": 1, "setups": []}, "as_of": "2026-10-31", "meta": {}}), FakeResponse(200, {"data": {"bins": []}, "as_of": "2026-11-04", "meta": {}})],
        wallet_key="0x" + "22" * 32,
    )
    client.history("nvda", "2026-10-01", "2026-10-31", cycle="weekly")
    assert session.calls[0]["url"].endswith("/x402/setups/history/NVDA")
    assert session.calls[0]["params"] == {"from": "2026-10-01", "to": "2026-10-31", "cycle": "weekly"}
    client.crowdmap("NVDA")
    assert session.calls[1]["url"].endswith("/x402/crowdmap/NVDA")


def test_wallet_key_never_in_error_text():
    from crowdwisdomtrading.payment import _scrub

    key = "0x" + "ab" * 32
    assert key not in _scrub(f"insufficient funds for {key}", key)
    assert ("ab" * 32) not in _scrub(f"raw {'ab' * 32} key", key)


def test_key_mode_setup_latest_picks_newest(tmp_path):
    rows = [{"date": "2026-11-01", "ticker": "NVDA"}, {"date": "2026-11-04", "ticker": "NVDA"}]
    client, _ = _client(tmp_path, [FakeResponse(200, {"data": rows, "meta": {}})], api_key="cwt_live_abc")
    out = client.setup_latest("NVDA")
    assert out["data"]["date"] == "2026-11-04" and out["as_of"] == "2026-11-04"


def test_weekly_sentiment_is_free_without_key_or_wallet(tmp_path, monkeypatch):
    for name in ("CWT_API_KEY", "X402_WALLET_PRIVATE_KEY"):
        monkeypatch.delenv(name, raising=False)
    body = {"data": {"ticker": "NVDA", "cycle": "weekly", "week_of": "2026-11-02", "score": 42.0, "value": 0.42,
                     "direction": "BULLISH", "mentions": 380}, "as_of": "2026-11-02",
            "meta": {"price": "free"}}
    client, session = _client(tmp_path, [FakeResponse(200, body)])
    assert client.mode == "free"
    out = client.weekly_sentiment(" nvda ")
    assert session.calls[0]["url"] == "https://api.test/x402/weekly/NVDA"
    assert "Authorization" not in session.calls[0]["headers"]
    assert out["data"]["direction"] == "BULLISH" and out["meta"]["payment"] in ({}, None)


def test_weekly_free_cap_reached_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    client, _session = _client(tmp_path, [FakeResponse(429, {"error": {"code": "FREE_LIMIT_REACHED"}})])
    with pytest.raises(CrowdWisdomError) as exc:
        client.weekly_sentiment("NVDA")
    assert "429" in str(exc.value) and "FREE_LIMIT_REACHED" in str(exc.value)


def test_package_is_named_crowdwisdomtrading():
    import tomllib

    meta = tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert meta["name"] == "crowdwisdomtrading"
    assert meta["scripts"] == {"crowdwisdomtrading": "crowdwisdomtrading.cli:main"}
    import crowdwisdomtrading

    assert crowdwisdomtrading.__version__ == meta["version"]


def test_daily_sentiment_is_free_without_key_or_wallet(tmp_path, monkeypatch):
    for name in ("CWT_API_KEY", "X402_WALLET_PRIVATE_KEY"):
        monkeypatch.delenv(name, raising=False)
    body = {"data": {"ticker": "AAPL", "cycle": "daily", "date": "2026-11-06", "score": 25.6}, "as_of": "2026-11-06",
            "meta": {"price": "free"}}
    client, session = _client(tmp_path, [FakeResponse(200, body)])
    out = client.daily_sentiment("aapl")
    assert session.calls[0]["url"] == "https://api.test/x402/daily/AAPL"
    assert "Authorization" not in session.calls[0]["headers"] and out["data"]["score"] == 25.6


def test_every_request_names_the_package(tmp_path, monkeypatch):
    monkeypatch.delenv("CWT_API_KEY", raising=False)
    import crowdwisdomtrading

    client, session = _client(tmp_path, [FakeResponse(200, {"data": {}, "meta": {}})])
    client.daily_sentiment("AAPL")
    ua = session.calls[0]["headers"]["User-Agent"]
    assert ua.startswith(f"crowdwisdomtrading-python/{crowdwisdomtrading.__version__}") and "crowdwisdomtrading.com/x402" in ua


def test_pypi_and_readme_links_are_tagged():
    text = (PKG / "pyproject.toml").read_text(encoding="utf-8") + (PKG / "README.md").read_text(encoding="utf-8")
    assert "crowdwisdomtrading.com/x402?utm_source=pypi" in text
