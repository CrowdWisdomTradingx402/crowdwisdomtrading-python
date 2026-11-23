"""CrowdWisdom Trading client.

Free, no wallet, no key:
  daily_sentiment(ticker)  - daily crowd score for one ticker (all sources, newest session)
  weekly_sentiment(ticker) - weekly crowd score for one ticker (all sources, newest Monday session)
                             50 free calls a day per IP address for each.

Two ways to the full data:
  wallet mode  - Client(wallet_key=...) or env X402_WALLET_PRIVATE_KEY: pays per call on the /x402 routes
                 (USDC on Base, same wallet ai-hedge-fund uses for Financial Datasets).
  key mode     - Client(api_key=...) or env CWT_API_KEY: a Bearer key for the /v1 routes (monthly plan).
                 A key wins over a wallet, so a subscriber is never billed per call.

Every method returns {"data": ..., "as_of": ..., "meta": {...}}. Point-in-time: pass as_of / date_to and
the server only returns what was published by then. Answers with an as_of are cached forever on disk,
live answers for 10 minutes, so a backtest never pays twice for the same (ticker, date). Errors are
never cached.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

from crowdwisdomtrading.payment import BASE_MAINNET, PaymentFailed, decode_receipt, payment_session

DEFAULT_BASE_URL = "https://api.crowdwisdomtrading.com"
# 2026-11-08: every request names the package, so the API can count package users apart from other callers
# (stored in cwt_api.api_request_log.client_agent). No personal data, only the package and version.
LANDING_URL = "https://crowdwisdomtrading.com/x402"


def user_agent() -> str:
    from crowdwisdomtrading import __version__

    return f"crowdwisdomtrading-python/{__version__} (+{LANDING_URL})"
DEFAULT_CACHE_DIR = Path.home() / ".crowdwisdomtrading" / "cache"
LIVE_TTL_S = 600


class CrowdWisdomError(Exception):
    """HTTP or data error from the CrowdWisdom API (status and body excerpt in the message)."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


def _day(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _is_past_day(day: str | None) -> bool:
    """Only a finished day is immutable; today's sessions can still be published later today."""
    from datetime import datetime, timezone

    return bool(day) and day < datetime.now(timezone.utc).date().isoformat()


class Client:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        wallet_key: str | None = None,
        network: str | None = None,
        cache_dir: str | Path | None = None,
        timeout: float = 30.0,
        session: requests.Session | None = None,
        cache: bool = True,
    ) -> None:
        self.base_url = (base_url or os.getenv("CWT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = (api_key if api_key is not None else os.getenv("CWT_API_KEY") or "").strip()
        wallet = wallet_key if wallet_key is not None else os.getenv("X402_WALLET_PRIVATE_KEY") or ""
        self._wallet_key = wallet.strip()
        self.network = (network or os.getenv("X402_NETWORK") or BASE_MAINNET).strip()
        self.timeout = timeout
        self.cache_enabled = cache
        self.cache_dir = Path(cache_dir) if cache_dir else Path(os.getenv("CWT_CACHE_DIR") or DEFAULT_CACHE_DIR)
        self._session = session
        self.last_receipt: dict[str, Any] | None = None

    # ------------------------------------------------------------------ mode

    @property
    def mode(self) -> str:
        if self.api_key:
            return "key"
        if self._wallet_key:
            return "wallet"
        return "free"

    def pays_per_call(self) -> bool:
        return self.mode == "wallet"

    def _http(self) -> requests.Session:
        if self._session is None:
            if self.mode == "wallet":
                self._session = payment_session(
                    self._wallet_key, self.network, timeout=max(self.timeout, 60.0), base_url=self.base_url
                )
            else:
                self._session = requests.Session()
        return self._session

    # ----------------------------------------------------------------- cache

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _cache_get(self, key: str, ttl: float | None) -> dict[str, Any] | None:
        if not self.cache_enabled:
            return None
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if ttl is not None and time.time() - float(entry.get("fetched_at", 0)) > ttl:
            return None
        return entry.get("body")

    def _cache_put(self, key: str, body: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(key).write_text(json.dumps({"fetched_at": time.time(), "body": body}), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------- http

    def _get(self, path: str, params: dict[str, Any] | None = None, *, point_in_time: bool = False) -> dict[str, Any]:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        key = hashlib.sha256(f"{self.mode}|{self.base_url}|{path}|{json.dumps(params, sort_keys=True)}".encode()).hexdigest()[:24]
        cached = self._cache_get(key, None if point_in_time else LIVE_TTL_S)
        if cached is not None:
            cached.setdefault("meta", {})["cached"] = True
            return cached
        headers = {"Accept": "application/json", "User-Agent": user_agent()}
        if self.mode == "key":
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = self._http().get(f"{self.base_url}{path}", params=params, headers=headers, timeout=self.timeout)
        except PaymentFailed:
            raise
        except requests.RequestException as exc:
            raise CrowdWisdomError(0, f"{type(exc).__name__}: {exc}") from None
        if response.status_code == 402:
            raise PaymentFailed("payment required: set X402_WALLET_PRIVATE_KEY (with USDC on Base) or CWT_API_KEY")
        if response.status_code >= 400:
            raise CrowdWisdomError(response.status_code, response.text[:300])
        body = response.json()
        if not isinstance(body, dict):
            raise CrowdWisdomError(response.status_code, "unexpected body")
        self.last_receipt = decode_receipt(response)
        body.setdefault("meta", {})
        body["meta"]["payment"] = self.last_receipt
        body["meta"]["cached"] = False
        self._cache_put(key, body)
        return body

    # ---------------------------------------------------------------- free

    def catalog(self) -> dict[str, Any]:
        return self._get("/x402/catalog")

    def sample(self) -> dict[str, Any]:
        return self._get("/x402/sample")

    def daily_sentiment(self, ticker: str) -> dict[str, Any]:
        """Free daily all-source crowd sentiment score for one ticker (-100..+100, newest session). Never pays, needs
        no key or wallet. Capped per IP per day."""
        t = ticker.upper().strip()
        return self._get(f"/x402/daily/{t}")

    def weekly_sentiment(self, ticker: str) -> dict[str, Any]:
        """Free weekly all-source crowd sentiment score for one ticker (-100..+100, newest Monday). Never pays, needs
        no key or wallet. Capped per IP per day."""
        t = ticker.upper().strip()
        return self._get(f"/x402/weekly/{t}")

    # ---------------------------------------------------------------- data

    def consensus(self, ticker: str, as_of: date | str | None = None, cycle: str | None = None) -> dict[str, Any]:
        """Crowd score in [-1, +1] for one ticker, latest session on or before as_of."""
        t = ticker.upper().strip()
        day = _day(as_of)
        if self.mode == "key":
            body = self._get(f"/v1/sentiment/{t}", point_in_time=False)
            path = [p for p in body.get("path") or [] if day is None or p.get("date", "") <= day]
            if cycle:
                path = [p for p in path if p.get("cycle") == cycle]
            latest = path[-1] if path else None
            score = float(latest["score"]) if latest and latest.get("score") is not None else None
            data = {
                "ticker": t,
                "as_of": day,
                "cycle": cycle,
                "session": {"date": latest["date"], "cycle": latest.get("cycle")} if latest else None,
                "value": max(-1.0, min(1.0, score / 100.0)) if score is not None else None,
                "ProCrowdSentimentScore": score,
                "direction": latest.get("direction") if latest else None,
                "confidence": None,
                "mentions": None,
                "sources": None,
                "latest_setup": None,
            }
            return {"data": data, "as_of": day or (latest["date"] if latest else None), "meta": {**body.get("meta", {}), "route": "/v1/sentiment (key mode)"}}
        return self._get(f"/x402/consensus/{t}", {"as_of": day, "cycle": cycle}, point_in_time=_is_past_day(day))

    def setup_latest(self, ticker: str, cycle: str | None = None) -> dict[str, Any]:
        t = ticker.upper().strip()
        if self.mode == "key":
            body = self._get("/v1/signals", {"ticker": t, "cycle": cycle, "limit": 100})
            rows = sorted(body.get("data") or [], key=lambda r: (r.get("date") or "", r.get("published_at") or ""))
            row = rows[-1] if rows else None
            return {"data": row, "as_of": row.get("date") if row else None, "meta": {**body.get("meta", {}), "route": "/v1/signals (key mode)"}}
        return self._get(f"/x402/setups/latest/{t}", {"cycle": cycle})

    def setups_today(self, cycle: str | None = None) -> dict[str, Any]:
        if self.mode == "key":
            body = self._get("/v1/signals", {"cycle": cycle, "limit": 500})
            rows = body.get("data") or []
            latest = max((r.get("date") or "" for r in rows), default=None)
            rows = [r for r in rows if r.get("date") == latest]
            return {"data": {"date": latest, "cycle": cycle, "count": len(rows), "setups": rows}, "as_of": latest, "meta": {**body.get("meta", {}), "route": "/v1/signals (key mode)"}}
        return self._get("/x402/setups/today", {"cycle": cycle})

    def crowdmap(self, ticker: str) -> dict[str, Any]:
        """CrowdMap: the crowd's support / resistance levels for one ticker (newest day)."""
        t = ticker.upper().strip()
        if self.mode == "key":
            body = self._get(f"/v1/socialmap/{t}", {"days": 1})
            sessions = body.get("sessions") or []
            latest = sessions[-1] if sessions else None
            return {"data": latest, "as_of": latest.get("ladder_date") if latest else None, "meta": {**body.get("meta", {}), "route": "/v1/socialmap (key mode)"}}
        return self._get(f"/x402/crowdmap/{t}")

    def history(self, ticker: str, date_from: date | str, date_to: date | str, cycle: str | None = None) -> dict[str, Any]:
        """Setups between the two dates. Wallet mode is point-in-time (nothing published after date_to)."""
        t = ticker.upper().strip()
        start, end = _day(date_from), _day(date_to)
        if self.mode == "key":
            body = self._get("/v1/signals", {"ticker": t, "date_from": start, "date_to": end, "cycle": cycle, "limit": 500})
            rows = body.get("data") or []
            return {"data": {"ticker": t, "from": start, "to": end, "count": len(rows), "setups": rows, "point_in_time": False}, "as_of": end, "meta": {**body.get("meta", {}), "route": "/v1/signals (key mode)"}}
        return self._get(f"/x402/setups/history/{t}", {"from": start, "to": end, "cycle": cycle}, point_in_time=_is_past_day(end))
