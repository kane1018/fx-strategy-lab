"""Market / ticker / spread safe labels for the actual entry gate (no-POST).

Maps the safe statuses of a fresh runtime safe-read snapshot to the safe
labels the actual entry gate reports and checks in one pass:

- MARKET_OPEN_SAFE / MARKET_CLOSED_SAFE / MARKET_UNKNOWN_SAFE
- TICKER_FRESH_SAFE / TICKER_STALE_SAFE / TICKER_UNKNOWN_SAFE
- SPREAD_WITHIN_LIMIT_SAFE / SPREAD_OUT_OF_LIMIT_SAFE / SPREAD_UNKNOWN_SAFE

Hard rules enforced by construction:

- The input carries safe status enums only. There is no field that can carry
  a raw bid, ask, price, spread value, or timestamp, so no raw market value
  can ever be reported from here.
- The freshness threshold and the spread limit are owned by the (future)
  real read-only safe-read client configuration. When no configured limit
  exists, that client must report UNKNOWN; this module treats UNKNOWN as the
  safe-side default and blocks on it.
- Fail-closed: missing ticker, UNKNOWN, STALE, CLOSED, and OUT_OF_LIMIT all
  block the entry gate. Only OPEN + FRESH + WITHIN_LIMIT passes.
- This module performs no HTTP. Fresh statuses must be obtained by the
  actual gate's own fresh runtime read, never reused from a prior step.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeMarketSafeStatus,
    GmoRuntimeSafeReadSnapshot,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
)


class GmoMarketStatusSafeLabel(str, Enum):
    MARKET_OPEN_SAFE = "MARKET_OPEN_SAFE"
    MARKET_CLOSED_SAFE = "MARKET_CLOSED_SAFE"
    MARKET_UNKNOWN_SAFE = "MARKET_UNKNOWN_SAFE"


class GmoTickerFreshnessSafeLabel(str, Enum):
    TICKER_FRESH_SAFE = "TICKER_FRESH_SAFE"
    TICKER_STALE_SAFE = "TICKER_STALE_SAFE"
    TICKER_UNKNOWN_SAFE = "TICKER_UNKNOWN_SAFE"


class GmoSpreadStatusSafeLabel(str, Enum):
    SPREAD_WITHIN_LIMIT_SAFE = "SPREAD_WITHIN_LIMIT_SAFE"
    SPREAD_OUT_OF_LIMIT_SAFE = "SPREAD_OUT_OF_LIMIT_SAFE"
    SPREAD_UNKNOWN_SAFE = "SPREAD_UNKNOWN_SAFE"


_MARKET_LABELS: dict[GmoRuntimeMarketSafeStatus, GmoMarketStatusSafeLabel] = {
    GmoRuntimeMarketSafeStatus.OPEN: GmoMarketStatusSafeLabel.MARKET_OPEN_SAFE,
    GmoRuntimeMarketSafeStatus.CLOSED: GmoMarketStatusSafeLabel.MARKET_CLOSED_SAFE,
    GmoRuntimeMarketSafeStatus.UNKNOWN: GmoMarketStatusSafeLabel.MARKET_UNKNOWN_SAFE,
}

_TICKER_LABELS: dict[
    GmoRuntimeTickerFreshnessSafeStatus, GmoTickerFreshnessSafeLabel
] = {
    GmoRuntimeTickerFreshnessSafeStatus.FRESH: (
        GmoTickerFreshnessSafeLabel.TICKER_FRESH_SAFE
    ),
    GmoRuntimeTickerFreshnessSafeStatus.STALE: (
        GmoTickerFreshnessSafeLabel.TICKER_STALE_SAFE
    ),
    GmoRuntimeTickerFreshnessSafeStatus.UNKNOWN: (
        GmoTickerFreshnessSafeLabel.TICKER_UNKNOWN_SAFE
    ),
}

_SPREAD_LABELS: dict[GmoRuntimeSpreadSafeStatus, GmoSpreadStatusSafeLabel] = {
    GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT: (
        GmoSpreadStatusSafeLabel.SPREAD_WITHIN_LIMIT_SAFE
    ),
    GmoRuntimeSpreadSafeStatus.OUT_OF_LIMIT: (
        GmoSpreadStatusSafeLabel.SPREAD_OUT_OF_LIMIT_SAFE
    ),
    GmoRuntimeSpreadSafeStatus.UNKNOWN: (
        GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE
    ),
}


@dataclass(frozen=True)
class MarketTickerSafeInput:
    """Safe-status-only input. No raw bid/ask/spread/timestamp field exists."""

    ticker_present: bool = False
    market_status: GmoRuntimeMarketSafeStatus = GmoRuntimeMarketSafeStatus.UNKNOWN
    ticker_status: GmoRuntimeTickerFreshnessSafeStatus = (
        GmoRuntimeTickerFreshnessSafeStatus.UNKNOWN
    )
    spread_status: GmoRuntimeSpreadSafeStatus = GmoRuntimeSpreadSafeStatus.UNKNOWN

    @classmethod
    def from_safe_snapshot(
        cls, snapshot: GmoRuntimeSafeReadSnapshot
    ) -> MarketTickerSafeInput:
        """Lift the market fields of a fresh safe snapshot. No raw values exist
        on the snapshot type, so none can be lifted."""

        return cls(
            ticker_present=snapshot.performed and snapshot.fresh,
            market_status=snapshot.market_status,
            ticker_status=snapshot.ticker_status,
            spread_status=snapshot.spread_status,
        )


@dataclass(frozen=True)
class MarketTickerSafeResult:
    """Safe labels plus a fail-closed pass flag. Never truthy."""

    market_status_safe_label: GmoMarketStatusSafeLabel
    ticker_freshness_safe_label: GmoTickerFreshnessSafeLabel
    spread_status_safe_label: GmoSpreadStatusSafeLabel
    passes_entry_gate: bool
    blocked_reasons: tuple[str, ...]
    raw_bid_ask_exposed: bool = False
    raw_spread_value_exposed: bool = False
    raw_timestamp_exposed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_market_ticker_safe_labels(
    safe_input: MarketTickerSafeInput,
) -> MarketTickerSafeResult:
    """Map safe statuses to safe labels; pass only on OPEN + FRESH + WITHIN."""

    market_label = _MARKET_LABELS.get(
        safe_input.market_status, GmoMarketStatusSafeLabel.MARKET_UNKNOWN_SAFE
    )
    if safe_input.ticker_present:
        ticker_label = _TICKER_LABELS.get(
            safe_input.ticker_status,
            GmoTickerFreshnessSafeLabel.TICKER_UNKNOWN_SAFE,
        )
        spread_label = _SPREAD_LABELS.get(
            safe_input.spread_status,
            GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE,
        )
    else:
        # Spread is derived from the ticker, so a missing ticker degrades
        # both to the blocking UNKNOWN labels.
        ticker_label = GmoTickerFreshnessSafeLabel.TICKER_UNKNOWN_SAFE
        spread_label = GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE

    blockers: list[str] = []
    if not safe_input.ticker_present:
        blockers.append("TICKER_MISSING_BLOCKED")
    if market_label is not GmoMarketStatusSafeLabel.MARKET_OPEN_SAFE:
        blockers.append("MARKET_NOT_OPEN_SAFE_BLOCKED")
    if ticker_label is not GmoTickerFreshnessSafeLabel.TICKER_FRESH_SAFE:
        blockers.append("TICKER_NOT_FRESH_SAFE_BLOCKED")
    if spread_label is not GmoSpreadStatusSafeLabel.SPREAD_WITHIN_LIMIT_SAFE:
        blockers.append("SPREAD_NOT_WITHIN_LIMIT_SAFE_BLOCKED")

    return MarketTickerSafeResult(
        market_status_safe_label=market_label,
        ticker_freshness_safe_label=ticker_label,
        spread_status_safe_label=spread_label,
        passes_entry_gate=not blockers,
        blocked_reasons=tuple(blockers),
    )
