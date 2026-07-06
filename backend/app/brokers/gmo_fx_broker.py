"""GMO Coin 外国為替FX broker — Public read-only scaffold.

This phase implements ONLY the public, unauthenticated endpoints (latest rate,
klines, status). No API key/secret is read or sent here, no Private API call is
made, and order placement is intentionally disabled. `market_order` raises so the
class satisfies the Broker interface without ever sending a real order.

GMO 外国為替FX has NO demo/practice environment — the API targets real-money
production. Orders therefore stay disabled until a later, explicitly authorized
phase. See docs/SAFETY.md.

Public API base: https://forex-api.coin.z.com/public
Response envelope: {"status": 0, "data": ..., "responsetime": "..."}; a non-zero
"status" carries error "messages" with a "message_code" (e.g. ERR-5003 = rate limit).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.brokers.base import Broker, BrokerResult
from app.config import Settings, get_settings
from app.private_api.order_builders import build_gmo_fx_entry_request_plan
from app.schemas.trading import Candle, OrderRequest, RiskConfig, Side
from app.security.real_broker_post_hard_guard import (
    RealBrokerPostHardGuardError,
    assert_real_broker_post_allowed,
)
from app.services.market_data_service import pip_size
from app.services.risk_service import evaluate_order_risk


class GmoFxBrokerError(RuntimeError):
    pass


# Internal timeframe -> GMO kline interval.
GMO_INTERVALS = {
    "M1": "1min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1hour",
    "H4": "4hour",
    "H8": "8hour",
    "H12": "12hour",
    "D": "1day",
    "W": "1week",
    "MON": "1month",
}

_SYMBOL_PATTERN = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


def normalize_symbol(symbol: str) -> str:
    """Normalize to GMO's BASE_QUOTE form (e.g. usd/jpy -> USD_JPY)."""
    candidate = symbol.strip().upper().replace("/", "_").replace("-", "_")
    if not _SYMBOL_PATTERN.match(candidate):
        raise GmoFxBrokerError(f"未対応のシンボル形式です: {symbol}")
    return candidate


def _size_str(units: float) -> str:
    return f"{units:.10f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class GmoPrice:
    symbol: str
    bid: float
    ask: float
    midpoint: float
    spread_pips: float
    timestamp: datetime
    status: str


class GmoFxBroker(Broker):
    PUBLIC_BASE_URL = "https://forex-api.coin.z.com/public"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        allow_real_broker_post: bool = False,
    ) -> None:
        self.settings = settings or get_settings()
        # Public API needs no authentication. We deliberately do not read or send
        # GMO_FX_API_KEY / GMO_FX_API_SECRET in this read-only phase.
        self.client = client or httpx.Client(
            base_url=self.settings.gmo_fx_public_url,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        # Entry order-write skeleton only: no production caller sets this to
        # True anywhere. Real transport is not implemented yet, so even a
        # future True value would still stop at "transport not implemented".
        self._allow_real_broker_post = allow_real_broker_post

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if status_code == 429:
                raise GmoFxBrokerError("GMO API rate limit (HTTP 429)") from error
            raise GmoFxBrokerError(f"GMO API HTTP error ({status_code})") from error
        except (httpx.RequestError, ValueError) as error:
            raise GmoFxBrokerError("GMO API connection error") from error
        if payload.get("status") != 0:
            messages = payload.get("messages") or []
            codes = [str(item.get("message_code") or "") for item in messages]
            if "ERR-5003" in codes:
                raise GmoFxBrokerError("GMO API rate limit (ERR-5003)")
            detail = ", ".join(code for code in codes if code) or "unknown error"
            raise GmoFxBrokerError(f"GMO API error: {detail}")
        return payload

    def service_status(self) -> str:
        payload = self._request("GET", "/v1/status")
        return str(payload["data"]["status"])

    def connection_test(self) -> bool:
        # Reachability check only; a closed/maintenance market is still "connected".
        self.service_status()
        return True

    def current_price(self, symbol: str) -> GmoPrice:
        symbol = normalize_symbol(symbol)
        payload = self._request("GET", "/v1/ticker")
        rows = payload.get("data") or []
        row = next((item for item in rows if item.get("symbol") == symbol), None)
        if not row:
            raise GmoFxBrokerError(f"{symbol}のレートが取得できません")
        if row.get("status") != "OPEN":
            raise GmoFxBrokerError(f"{symbol}は現在取引できません")
        bid = float(row["bid"])
        ask = float(row["ask"])
        timestamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
        return GmoPrice(
            symbol=symbol,
            bid=bid,
            ask=ask,
            midpoint=(bid + ask) / 2,
            spread_pips=(ask - bid) / pip_size(symbol),
            timestamp=timestamp,
            status=str(row["status"]),
        )

    def candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        *,
        price_type: str = "BID",
        date: str | None = None,
    ) -> list[Candle]:
        symbol = normalize_symbol(symbol)
        interval = GMO_INTERVALS.get(timeframe)
        if not interval:
            raise GmoFxBrokerError(f"未対応のtimeframeです: {timeframe}")
        date = date or datetime.now(UTC).strftime("%Y%m%d")
        payload = self._request(
            "GET",
            "/v1/klines",
            params={
                "symbol": symbol,
                "priceType": price_type,
                "interval": interval,
                "date": date,
            },
        )
        rows = payload.get("data") or []
        candles = [
            Candle(
                timestamp=datetime.fromtimestamp(int(item["openTime"]) / 1000, UTC),
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=0,
            )
            for item in rows
        ]
        if not candles:
            raise GmoFxBrokerError(f"{symbol}のKlineが取得できません")
        return candles[-count:] if count else candles

    def market_order(self, request: OrderRequest) -> BrokerResult:
        """Entry-only order-write skeleton; no real transport yet.

        This never closes an existing position, and never treats a reverse
        trade as a close-out -- closing an existing position uses a separate
        dedicated method added in a later Step. It builds a pure entry
        request plan, then must pass the shared real-broker-post hard guard
        before any transport could ever be attempted. No production caller
        flips the real-broker-post allow flag on, so this always stops at
        the guard.
        """
        plan = build_gmo_fx_entry_request_plan(
            symbol=normalize_symbol(request.symbol),
            side="BUY" if request.side == Side.BUY else "SELL",
            size=_size_str(request.units),
        )
        try:
            assert_real_broker_post_allowed(allow=self._allow_real_broker_post)
        except RealBrokerPostHardGuardError as error:
            raise GmoFxBrokerError(
                "GMO order placement is blocked by the real-broker-post hard "
                f"guard (request_kind={plan.request_kind}). Enable only in a "
                "later, explicitly authorized phase."
            ) from error
        # Real transport is intentionally not implemented yet. Even if a
        # future caller flipped the real-broker-post allow flag on, there is
        # still no HTTP client wired here -- that is a separate, later Step.
        raise GmoFxBrokerError(
            "GMO order transport is not implemented (no-POST skeleton phase)."
        )


def build_gmo_order_payload(request: OrderRequest, *, max_units: float) -> dict[str, Any]:
    """Build a GMO /v1/order request body from an OrderRequest. Pure: no network.

    Used for dry-run design verification only. Raises if size exceeds the
    configured GMO_FX_MAX_UNITS guard.
    """
    if request.units > max_units:
        raise GmoFxBrokerError(
            f"size {request.units} exceeds GMO_FX_MAX_UNITS {max_units}"
        )
    return {
        "symbol": normalize_symbol(request.symbol),
        "side": "BUY" if request.side == Side.BUY else "SELL",
        "size": _size_str(request.units),
        "executionType": "MARKET",
    }


def gmo_dry_run_order(
    request: OrderRequest,
    risk: RiskConfig,
    settings: Settings,
) -> dict[str, Any]:
    """Run the shared RiskManager and build a dry-run order record WITHOUT sending.

    This is design-phase only: it never touches the GMO Private API. stopLoss /
    takeProfit are required by the OrderRequest schema, so an order without them
    cannot reach this function.
    """
    decision = evaluate_order_risk(
        request,
        risk,
        settings,
        open_positions=0,
        daily_loss=0,
        consecutive_losses=0,
    )
    if not decision.allowed:
        return {"accepted": False, "status": "risk_rejected", "reasons": decision.reasons}
    return {
        "accepted": True,
        "status": "dry_run",
        "payload": build_gmo_order_payload(request, max_units=settings.gmo_fx_max_units),
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "note": "dry_run only — not sent to GMO. SL/TP order wiring is a later phase.",
    }
