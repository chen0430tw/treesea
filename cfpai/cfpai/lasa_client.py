"""
CFPAI ↔ LASA HTTP client — thin wrapper around LASA's HTTP API.

Usage
-----
>>> from cfpai.lasa_client import LASAClient
>>> client = LASAClient("http://localhost:3000")
>>> portfolio = client.get_portfolio()
>>> client.post_events([{"id": "cfpai_buy_AAPL", ...}])

The client talks to the server endpoints:
- GET  /lasa/portfolio   → aggregated LASAPortfolioInput + historical cashflow/periods
- POST /event            → submit one event
- GET  /state            → raw engine state (for debugging)
- POST /reset            → reset engine (dev only)
"""
from __future__ import annotations

import json
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from cfpai.lasa_bridge import LASAPortfolioInput


class LASAClientError(RuntimeError):
    """Raised when the LASA server returns an error or is unreachable."""


class LASAClient:
    def __init__(self, base_url: str = "http://localhost:3000", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ── internal ──────────────────────────────────────────────────────────────
    def _get(self, path: str) -> dict[str, Any]:
        req = urlrequest.Request(self.base_url + path, method="GET")
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as e:
            raise LASAClientError(f"GET {path} failed: {e}") from e

    def _post(self, path: str, payload: dict | list) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as e:
            raise LASAClientError(f"POST {path} failed: {e}") from e

    # ── public ────────────────────────────────────────────────────────────────
    def get_portfolio(self) -> dict[str, Any]:
        """Fetch the full portfolio snapshot (input + history)."""
        return self._get("/lasa/portfolio")

    def get_portfolio_input(self) -> LASAPortfolioInput:
        """Fetch and deserialize as LASAPortfolioInput (ignores history)."""
        raw = self.get_portfolio()
        i = raw["input"]
        return LASAPortfolioInput(
            disposable_cash=float(i["disposable_cash"]),
            realized_income=float(i["realized_income"]),
            free_net_assets=float(i["free_net_assets"]),
            restricted_amount=float(i["restricted_amount"]),
            risk_reserve=float(i["risk_reserve"]),
            pending_amount=float(i["pending_amount"]),
        )

    def get_state(self) -> dict[str, Any]:
        return self._get("/state")

    def post_event(self, event: dict) -> dict[str, Any]:
        return self._post("/event", event)

    def post_events(self, events: list[dict]) -> list[dict[str, Any]]:
        """Submit events one by one (server has no batch endpoint for stateful /event)."""
        return [self.post_event(e) for e in events]

    def reset(self, initial_cash: float = 0, emergency_reserve: float = 0,
              base_currency: str = "TWD") -> dict[str, Any]:
        return self._post("/reset", {
            "initialCash": initial_cash,
            "emergencyReserve": emergency_reserve,
            "baseCurrency": base_currency,
        })
