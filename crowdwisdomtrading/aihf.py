"""CrowdWisdomModel: an ai-hedge-fund AlphaModel that buys the CrowdWisdom ProCrowdSentimentScore per call.

Register it in hedge_fund/signals/__init__.py:
    from crowdwisdomtrading.aihf import CrowdWisdomModel
    ALPHA_MODEL_REGISTRY["crowdwisdom"] = CrowdWisdomModel
It pays with the wallet in
X402_WALLET_PRIVATE_KEY (the same one ai-hedge-fund uses for Financial Datasets) or uses a
CWT_API_KEY Bearer key. predict() only ever asks for data dated on or before `date`
(point-in-time), and disk caching means one payment per (ticker, date) in a backtest.

Works without ai-hedge-fund installed (a small shim replaces Signal / QuantModel) so the
package can be tested standalone; with aihf installed the real classes are used.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

from crowdwisdomtrading.client import Client

try:  # real ai-hedge-fund classes
    from hedge_fund.models import Signal  # type: ignore
    from hedge_fund.signals.base import QuantModel  # type: ignore

    HAVE_AIHF = True
except Exception:  # pragma: no cover - shim path is tested explicitly below
    HAVE_AIHF = False
    from dataclasses import dataclass, field

    @dataclass
    class Signal:  # type: ignore[no-redef]
        model_name: str
        ticker: str
        date: str
        value: float
        reasoning: str | None = None
        components: dict[str, float] = field(default_factory=dict)
        metadata: dict[str, Any] = field(default_factory=dict)
        horizon_days: int | None = None

    class QuantModel:  # type: ignore[no-redef]
        investment_approach: ClassVar[str] = "long_short"
        horizon_days: ClassVar[int] = 5


def _as_day(value: date | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


class CrowdWisdomModel(QuantModel):
    """ProCrowdSentimentScore / 100 (-1 short .. +1 long) as of the backtest date; abstains when stale."""

    investment_approach = "long_short"
    horizon_days = 5

    def __init__(
        self,
        client: Client | None = None,
        *,
        cycle: str | None = None,
        max_staleness_days: int = 10,
        neutral_band: float = 0.0,
    ) -> None:
        self._client = client
        self._cycle = cycle
        self._max_staleness_days = max_staleness_days
        self._neutral_band = neutral_band

    @property
    def name(self) -> str:
        return "crowdwisdom"

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client()
        return self._client

    def predict(self, ticker: str, date: date | str, data_client: Any = None) -> Signal:  # noqa: A002
        """Signal for `ticker` using only crowd sessions dated on or before `date`. data_client is unused."""
        day = _as_day(date)
        try:
            answer = self.client.consensus(ticker, as_of=day, cycle=self._cycle)
        except Exception as exc:
            return self._abstain(ticker, day, f"crowd data unavailable: {type(exc).__name__}")
        data = answer.get("data") or {}
        session = data.get("session") or {}
        value = data.get("value")
        if value is None or not session.get("date"):
            return self._abstain(ticker, day, "no crowd session on or before this date")
        try:
            age = (datetime.strptime(day, "%Y-%m-%d").date() - datetime.strptime(str(session["date"]), "%Y-%m-%d").date()).days
        except ValueError:
            return self._abstain(ticker, day, "malformed crowd session date")
        if age > self._max_staleness_days:
            return self._abstain(ticker, day, f"latest crowd session {session['date']} is {age} days old")
        if abs(float(value)) < self._neutral_band:
            value = 0.0
        sources = data.get("sources") or {}
        components = {k: float(v) / 100.0 for k, v in sources.items() if v is not None}
        mentions = data.get("mentions") or {}
        traders = data.get("ProTraders")
        pro_traders = traders.get("total") if isinstance(traders, dict) else traders
        receipt = (answer.get("meta") or {}).get("payment") or {}
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=day,
            value=max(-1.0, min(1.0, float(value))),
            reasoning=(
                f"ProCrowdSentimentScore {float(data.get('ProCrowdSentimentScore') or 0):+.0f} "
                f"({data.get('direction') or 'n/a'}) on {session['date']} ({session.get('cycle')}) "
                f"from {pro_traders if pro_traders is not None else '?'} ProTraders"
            ),
            components=components,
            metadata={
                "as_of": session["date"],
                "cycle": session.get("cycle"),
                "confidence": data.get("confidence"),
                "ProCrowdSentimentScore": data.get("ProCrowdSentimentScore"),
                "ProTraders": pro_traders,
                "mentions": mentions,
                "payment_tx": receipt.get("transaction"),
                "cached": (answer.get("meta") or {}).get("cached"),
            },
            horizon_days=self.horizon_days,
        )

    def _abstain(self, ticker: str, day: str, reason: str) -> Signal:
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=day,
            value=0.0,
            reasoning=reason,
            metadata={"abstained": True},
            horizon_days=self.horizon_days,
        )


# 0.2.2 name, kept so existing imports keep working (model name is now "crowdwisdom")
CrowdConsensusModel = CrowdWisdomModel
