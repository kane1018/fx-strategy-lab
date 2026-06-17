"""GMO 外国為替FX **Public** read-only market-data adapter for shadow trading.

Implements the shadow `MarketDataClient` Protocol against the official Public API
(base https://forex-api.coin.z.com/public). PUBLIC / unauthenticated only:
- NO API key / secret / .env (the Public endpoints need no auth).
- NO Private API (balances / positions / orders / executions).
- NO order placement. This adapter only GETs market data and normalizes it into the
  internal shadow Ticker / Candle.

Confirmed shapes (same as app/brokers/gmo_fx_broker.py, built from the official spec):
- envelope: {"status": 0, "data": ..., "responsetime": "..."}; non-zero status carries
  messages[].message_code (ERR-5003 = rate limit).
- GET /v1/status         -> data.status (OPEN / CLOSE / MAINTENANCE)
- GET /v1/ticker         -> data = [{symbol, bid, ask, timestamp(ISO Z), status}]
- GET /v1/klines?symbol&priceType&interval&date(YYYYMMDD)
                          -> data = [{openTime(ms epoch str), open, high, low, close}]

local-only: not wired into any FastAPI route. See docs/GMO_PUBLIC_API_PLAN.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.shadow.models import Candle, Ticker

PUBLIC_BASE_URL = "https://forex-api.coin.z.com/public"

# Internal timeframe -> GMO kline interval (subset; mirrors the existing broker).
GMO_INTERVALS = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1hour",
    "H4": "4hour",
    "D": "1day",
}


class GmoPublicError(RuntimeError):
    """Raised on any Public API fetch failure (never falls back to Private/auth)."""


def _num(raw: Any) -> float:
    """Parse a possibly-string numeric safely via Decimal, return float."""
    try:
        return float(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise GmoPublicError(f"Public API取得失敗: invalid numeric value {raw!r}") from error


class GmoPublicMarketDataClient:
    """Public, read-only GMO market-data client (implements MarketDataClient).

    Inject an `httpx.Client` (e.g. with a MockTransport) for offline tests. No auth
    headers are ever set; no API key / secret is read.
    """

    def __init__(self, client: httpx.Client | None = None, *, timeout: float = 10.0) -> None:
        self.client = client or httpx.Client(
            base_url=PUBLIC_BASE_URL,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            code = error.response.status_code
            if code == 429:
                raise GmoPublicError("Public API取得失敗: rate limit (HTTP 429)") from error
            raise GmoPublicError(f"Public API取得失敗: HTTP {code}") from error
        except (httpx.RequestError, ValueError) as error:
            raise GmoPublicError("Public API取得失敗: connection/parse error") from error
        if payload.get("status") != 0:
            messages = payload.get("messages") or []
            codes = [str(m.get("message_code") or "") for m in messages]
            if "ERR-5003" in codes:
                raise GmoPublicError("Public API取得失敗: rate limit (ERR-5003)")
            detail = ", ".join(c for c in codes if c) or "unknown error"
            raise GmoPublicError(f"Public API取得失敗: {detail}")
        return payload.get("data")

    def service_status(self) -> str:
        data = self._get("/v1/status")
        return str(data["status"])

    def fetch_ticker(self, symbol: str) -> Ticker:
        rows = self._get("/v1/ticker") or []
        row = next((r for r in rows if r.get("symbol") == symbol), None)
        if not row:
            raise GmoPublicError(f"Public API取得失敗: ticker not found for {symbol}")
        return Ticker(
            symbol=str(row["symbol"]),
            bid=_num(row["bid"]),
            ask=_num(row["ask"]),
            time=str(row.get("timestamp", "")),
        )

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        *,
        price_type: str = "BID",
        date: str | None = None,
    ) -> list[Candle]:
        # `interval` is a GMO interval string (e.g. "1min"); map internal timeframes too.
        gmo_interval = GMO_INTERVALS.get(interval, interval)
        date = date or datetime.now(UTC).strftime("%Y%m%d")
        rows = self._get(
            "/v1/klines",
            params={
                "symbol": symbol,
                "priceType": price_type,
                "interval": gmo_interval,
                "date": date,
            },
        ) or []
        candles = [
            Candle(
                time=datetime.fromtimestamp(int(r["openTime"]) / 1000, UTC).isoformat(),
                open=_num(r["open"]),
                high=_num(r["high"]),
                low=_num(r["low"]),
                close=_num(r["close"]),
                volume=None,
            )
            for r in rows
        ]
        if not candles:
            raise GmoPublicError(
                f"Public API取得失敗: no klines for {symbol} {gmo_interval} {date}"
            )
        return candles[-limit:] if limit else candles
