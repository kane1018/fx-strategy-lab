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
from enum import Enum
from typing import Any

import httpx

from app.brokers.base import Broker, BrokerResult
from app.config import Settings, get_settings
from app.private_api.order_builders import (
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_official_settlement_request_plan,
)
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


ENTRY_SIDE_SAFE_LABEL_BUY = "ENTRY_BUY"
ENTRY_SIDE_SAFE_LABEL_SELL = "ENTRY_SELL"

SETTLEMENT_SIDE_SOURCE_FROM_ENTRY_SAFE_LABEL = "SETTLEMENT_SIDE_FROM_ENTRY_SAFE_LABEL"
SETTLEMENT_SIDE_SOURCE_MISSING = "SETTLEMENT_SIDE_SOURCE_MISSING"
SETTLEMENT_SIDE_SOURCE_UNKNOWN_SAFE = "SETTLEMENT_SIDE_SOURCE_UNKNOWN_SAFE"

# Mechanical, fixed mapping: closing a long requires a sell, closing a short
# requires a buy. This mapping is now reflected as a confirmed official-docs
# interpretation by the current operator safe-label (OPPOSITE_SIDE).
SETTLEMENT_SIDE_OFFICIAL_DOCS_SEMANTICS_CONFIRMED = True
_ENTRY_TO_SETTLEMENT_SIDE = {
    ENTRY_SIDE_SAFE_LABEL_BUY: "SELL",
    ENTRY_SIDE_SAFE_LABEL_SELL: "BUY",
}


class GmoFxSettlementSideProvenanceStatus(str, Enum):
    DERIVED_FROM_ENTRY_SAFE_LABEL = "DERIVED_FROM_ENTRY_SAFE_LABEL"
    BLOCKED_MISSING_ENTRY_SIDE = "BLOCKED_MISSING_ENTRY_SIDE"
    BLOCKED_UNKNOWN_ENTRY_SIDE = "BLOCKED_UNKNOWN_ENTRY_SIDE"


@dataclass(frozen=True)
class GmoFxSettlementSideProvenance:
    """Safe-label-only settlement side derivation result.

    Never carries a real position ID, quantity, price, or credential. The
    settlement side is mechanically derived from an entry side safe label
    only; it is never inferred, guessed, or chosen freely.
    """

    status: GmoFxSettlementSideProvenanceStatus
    settlement_side_ready: bool
    settlement_side_safe_label: str | None
    settlement_side_source_safe_label: str
    settlement_side_official_docs_semantics_confirmed: bool
    codex_inferred_settlement_side: bool = False


def derive_settlement_side_from_entry_side_safe_label(
    entry_side_safe_label: str | None,
) -> GmoFxSettlementSideProvenance:
    """Derive the settlement (closing) side from an entry side safe label.

    Only `ENTRY_BUY` / `ENTRY_SELL` are accepted. Anything else -- missing,
    empty, or an unrecognized label -- blocks the derivation instead of
    guessing. `codex_inferred_settlement_side` is always False: the side
    comes from the fixed mapping above, not from any inference performed
    here.
    """
    if not entry_side_safe_label:
        return GmoFxSettlementSideProvenance(
            status=GmoFxSettlementSideProvenanceStatus.BLOCKED_MISSING_ENTRY_SIDE,
            settlement_side_ready=False,
            settlement_side_safe_label=None,
            settlement_side_source_safe_label=SETTLEMENT_SIDE_SOURCE_MISSING,
            settlement_side_official_docs_semantics_confirmed=False,
        )
    if entry_side_safe_label not in _ENTRY_TO_SETTLEMENT_SIDE:
        return GmoFxSettlementSideProvenance(
            status=GmoFxSettlementSideProvenanceStatus.BLOCKED_UNKNOWN_ENTRY_SIDE,
            settlement_side_ready=False,
            settlement_side_safe_label=None,
            settlement_side_source_safe_label=SETTLEMENT_SIDE_SOURCE_UNKNOWN_SAFE,
            settlement_side_official_docs_semantics_confirmed=False,
        )
    return GmoFxSettlementSideProvenance(
        status=GmoFxSettlementSideProvenanceStatus.DERIVED_FROM_ENTRY_SAFE_LABEL,
        settlement_side_ready=True,
        settlement_side_safe_label=_ENTRY_TO_SETTLEMENT_SIDE[entry_side_safe_label],
        settlement_side_source_safe_label=SETTLEMENT_SIDE_SOURCE_FROM_ENTRY_SAFE_LABEL,
        settlement_side_official_docs_semantics_confirmed=SETTLEMENT_SIDE_OFFICIAL_DOCS_SEMANTICS_CONFIRMED,
    )


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

    def official_settlement_order(
        self,
        *,
        symbol: str,
        entry_side_safe_label: str | None,
        size: float,
    ) -> BrokerResult:
        """Dedicated, size-based official settlement skeleton; no real
        transport yet.

        This is a separate method from `market_order` and never reuses it --
        it never places a fresh order in a reverse direction and calls that
        a close. It only accepts a size-based settlement request; there is
        no position-specific identifier parameter here at all, so a safe
        opaque handle for that path simply does not exist yet.

        The settlement side is never chosen by this method or by whatever
        calls it -- it is mechanically derived from `entry_side_safe_label`
        via `derive_settlement_side_from_entry_side_safe_label`. If that
        derivation is not ready (missing or unrecognized entry side safe
        label), no settlement request plan is built at all.
        """
        provenance = derive_settlement_side_from_entry_side_safe_label(
            entry_side_safe_label,
        )
        if not provenance.settlement_side_ready:
            raise GmoFxBrokerError(
                "GMO official settlement is blocked: settlement side "
                f"provenance not ready (status={provenance.status.value})."
            )
        plan = build_gmo_fx_official_settlement_request_plan(
            symbol=normalize_symbol(symbol),
            side=provenance.settlement_side_safe_label,
            size=_size_str(size),
        )
        try:
            assert_real_broker_post_allowed(allow=self._allow_real_broker_post)
        except RealBrokerPostHardGuardError as error:
            raise GmoFxBrokerError(
                "GMO official settlement is blocked by the real-broker-post "
                f"hard guard (request_kind={plan.request_kind}). Enable "
                "only in a later, explicitly authorized phase."
            ) from error
        # Real transport is intentionally not implemented yet. Even if a
        # future caller flipped the real-broker-post allow flag on, there is
        # still no HTTP client wired here -- that is a separate, later Step.
        raise GmoFxBrokerError(
            "GMO official settlement transport is not implemented "
            "(no-POST skeleton phase)."
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
