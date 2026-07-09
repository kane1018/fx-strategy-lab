"""Safe-label supply for the operator pre-trade caution briefing (read-only).

The caution briefing generator
(``operator_pre_trade_caution_briefing.generate_caution_briefing``) consumes a
``BriefingInputs`` of SAFE LABELS. This module is the read-only entry point that
takes caller-supplied SAFE labels (as strings / safe counts / safe context
labels), validates and NORMALISES them fail-closed, and produces a
``BriefingInputs`` plus supply-level cautions.

This is NOT a trade-decision engine, NOT market-data acquisition, NOT a
trading-venue status query, and NOT execution preparation. It performs NO
network / private data read / filesystem / env / secret access, NO fetch,
and NO POST. It only maps SAFE labels the caller already holds.

Fail-closed rules (mirroring the briefing design):
- unknown / missing / invalid -> the ``*_UNKNOWN`` safe label (never a GO).
- ``no flag`` / ``not rejected`` / ``outside tested scope`` are cautions,
  never permission.
- No direction (up/down, buy/sell), no ENTRY decision, no confidence / alpha /
  expected-profit / win-rate. No raw price / spread / PnL / size and no
  account / order / transaction / position / trade ID are accepted or produced.
- Results are never truthy; ``performance_proof_status`` / ``live_ready`` stay
  false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.operator_pre_trade_caution_briefing import (
    BriefingInputs,
    CautionBriefing,
    EventProximitySafeLabel,
    ExposureSafeLabel,
    LiquiditySafeCategory,
    RiskBudgetSafeStatus,
    SafeExecutionReadiness,
    SpreadSafeCategory,
    TimeOfDaySafeCategory,
    TrendStateLabel,
    VolatilitySafeCategory,
    generate_caution_briefing,
)

# ---------------------------------------------------------------------------
# Accepted-string -> safe-label maps (case-insensitive). Anything not listed
# falls through to the ``*_UNKNOWN`` member (fail-closed) with a supply caution.
# ---------------------------------------------------------------------------
_EXPOSURE_MAP = {
    "FLAT": ExposureSafeLabel.FLAT,
    "NONE": ExposureSafeLabel.FLAT,
    "NO_POSITION": ExposureSafeLabel.FLAT,
    "ONE": ExposureSafeLabel.ONE_POSITION_OPEN,
    "ONE_POSITION_OPEN": ExposureSafeLabel.ONE_POSITION_OPEN,
    "OPEN": ExposureSafeLabel.ONE_POSITION_OPEN,
    "MULTIPLE": ExposureSafeLabel.MULTIPLE_POSITIONS_OPEN,
    "MULTIPLE_POSITIONS_OPEN": ExposureSafeLabel.MULTIPLE_POSITIONS_OPEN,
}
_BUDGET_MAP = {
    "WITHIN_BUDGET": RiskBudgetSafeStatus.WITHIN_BUDGET,
    "WITHIN": RiskBudgetSafeStatus.WITHIN_BUDGET,
    "OK": RiskBudgetSafeStatus.WITHIN_BUDGET,
    "NEAR_LIMIT": RiskBudgetSafeStatus.NEAR_LIMIT,
    "NEAR": RiskBudgetSafeStatus.NEAR_LIMIT,
    "BUDGET_EXCEEDED": RiskBudgetSafeStatus.BUDGET_EXCEEDED,
    "EXCEEDED": RiskBudgetSafeStatus.BUDGET_EXCEEDED,
    "OVER": RiskBudgetSafeStatus.BUDGET_EXCEEDED,
}
_READINESS_MAP = {
    "READY": SafeExecutionReadiness.READY,
    "NOT_READY": SafeExecutionReadiness.NOT_READY,
    "NOTREADY": SafeExecutionReadiness.NOT_READY,
}
_TREND_MAP = {
    "TRENDING": TrendStateLabel.TRENDING,
    "TREND": TrendStateLabel.TRENDING,
    "RANGING": TrendStateLabel.RANGING,
    "RANGE": TrendStateLabel.RANGING,
}
_VOL_MAP = {
    "LOW": VolatilitySafeCategory.LOW,
    "NORMAL": VolatilitySafeCategory.NORMAL,
    "HIGH": VolatilitySafeCategory.HIGH,
}
_SPREAD_MAP = {
    "NORMAL": SpreadSafeCategory.NORMAL,
    "WIDE": SpreadSafeCategory.WIDE,
    "ABNORMAL": SpreadSafeCategory.ABNORMAL,
}
_LIQUIDITY_MAP = {
    "NORMAL": LiquiditySafeCategory.NORMAL,
    "THIN": LiquiditySafeCategory.THIN,
}
_TIME_MAP = {
    "TOKYO": TimeOfDaySafeCategory.TOKYO,
    "LONDON": TimeOfDaySafeCategory.LONDON,
    "NY": TimeOfDaySafeCategory.NEW_YORK,
    "NEW_YORK": TimeOfDaySafeCategory.NEW_YORK,
    "NEWYORK": TimeOfDaySafeCategory.NEW_YORK,
    "OFF": TimeOfDaySafeCategory.OFF_HOURS,
    "OFF_HOURS": TimeOfDaySafeCategory.OFF_HOURS,
}
_EVENT_MAP = {
    "NONE": EventProximitySafeLabel.NONE,
    "CLEAR": EventProximitySafeLabel.NONE,
    "EVENT_PROXIMITY_CLEAR": EventProximitySafeLabel.NONE,
    "NEAR": EventProximitySafeLabel.NEAR_SCHEDULED_EVENT,
    "NEAR_SCHEDULED_EVENT": EventProximitySafeLabel.NEAR_SCHEDULED_EVENT,
    "EVENT_PROXIMITY_NEAR": EventProximitySafeLabel.NEAR_SCHEDULED_EVENT,
}
# uncertainty label -> is-uncertain bool; unknown/other => True (fail-closed)
_UNCERTAINTY_LOW = {"LOW", "NORMAL", "OK", "CLEAR"}
_UNCERTAINTY_HIGH = {"HIGH", "ELEVATED"}

# High-level intended-context label -> descriptive tags matched (or explicitly
# NOT matched) against the rejected ledger inside the briefing. Never a signal.
_CONTEXT_LABEL_TO_TAGS: dict[str, tuple[str, ...]] = {
    "M5_TECHNICAL": ("m5", "technical"),
    "H1_TREND_RIDE": ("h1", "trend_continuation", "atr_ride"),
    "SESSION_MOMENTUM": ("session_open", "momentum"),
    "GOTOBI_FIX_DRIFT": ("gotobi", "tokyo_fix"),
    "VOL_REGIME_CONDITIONAL_BREAKOUT": ("breakout", "high_vol", "regime"),
    # explicit "outside" => a non-ledger marker so the matcher returns
    # OUTSIDE_TESTED_SCOPE (a caution), not NOT_ASSESSED.
    "OUTSIDE_TESTED_SCOPE": ("outside_tested_scope_marker",),
    # explicit "unknown" => no tags => matcher returns NOT_ASSESSED (a caution).
    "UNKNOWN_CONTEXT": (),
}
_UNRECOGNISED_CONTEXT_MARKER = "unrecognised_context_marker"


class InputCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL_UNKNOWN = "PARTIAL_UNKNOWN"
    MOSTLY_UNKNOWN = "MOSTLY_UNKNOWN"


@dataclass(frozen=True)
class SafeLabelSupplyRequest:
    """Caller-supplied SAFE labels only (strings / safe counts / safe context
    labels). NO raw price/spread/PnL/size, NO ID, NO secret, NO direction,
    NO ENTRY. Missing fields default to None => normalised to ``*_UNKNOWN``."""

    exposure_status: str | None = None
    pending_order_status: str | None = None
    pending_order_safe_count: int | None = None
    risk_budget_status: str | None = None
    execution_readiness: str | None = None
    trend_range: str | None = None
    volatility: str | None = None
    spread_condition: str | None = None
    liquidity: str | None = None
    time_of_day: str | None = None
    event_proximity: str | None = None
    uncertainty: str | None = None
    intended_context_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class SafeLabelSupplyResult:
    """Normalised SAFE inputs for the briefing plus supply-level cautions. Never
    truthy; carries no raw value / ID / direction / confidence."""

    briefing_inputs: BriefingInputs
    supply_cautions: tuple[str, ...]
    input_completeness: InputCompleteness
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def _norm(value, mapping, unknown):  # type: ignore[no-untyped-def]
    if value is None:
        return unknown, False
    key = str(value).strip().upper()
    if key in mapping:
        return mapping[key], True
    return unknown, False


def _norm_pending(
    count: int | None, status: str | None
) -> tuple[int, bool, str | None]:
    if isinstance(count, bool):  # bool is an int subclass; reject it
        count = None
    if count is not None and isinstance(count, int) and count >= 0:
        return count, True, None
    label = str(status).strip().upper() if status is not None else ""
    if label in {"NONE", "NO_ORDERS", "ZERO", "FLAT"}:
        return 0, True, None
    if label in {"PRESENT", "ACTIVE", "OPEN"}:
        # known present but exact count unknown -> conservative "at least one"
        return 1, True, "PENDING_ORDER_COUNT_UNKNOWN_ASSUMED_AT_LEAST_ONE"
    return 0, False, "PENDING_ORDER_STATUS_UNKNOWN_TREATED_AS_CAUTION"


def _norm_uncertainty(value: str | None) -> tuple[bool, bool]:
    """Return (uncertainty_high, recognised). Fail-closed: unknown => high."""
    if value is None:
        return True, False
    key = str(value).strip().upper()
    if key in _UNCERTAINTY_LOW:
        return False, True
    if key in _UNCERTAINTY_HIGH:
        return True, True
    return True, False  # unrecognised => treat as high uncertainty


def _context_tags(
    labels: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (tags, cautions). Unknown labels contribute a non-ledger marker
    (=> OUTSIDE_TESTED_SCOPE caution) plus a supply caution."""
    tags: list[str] = []
    cautions: list[str] = []
    for raw in labels:
        key = str(raw).strip().upper()
        if not key:
            continue
        if key in _CONTEXT_LABEL_TO_TAGS:
            tags.extend(_CONTEXT_LABEL_TO_TAGS[key])
        else:
            tags.append(_UNRECOGNISED_CONTEXT_MARKER)
            cautions.append(f"UNRECOGNISED_CONTEXT_LABEL_TREATED_AS_CAUTION:{key}")
    # de-duplicate, preserve order
    seen: set[str] = set()
    deduped = tuple(t for t in tags if not (t in seen or seen.add(t)))
    return deduped, tuple(dict.fromkeys(cautions))


def build_briefing_inputs(request: SafeLabelSupplyRequest) -> SafeLabelSupplyResult:
    """Validate + normalise SAFE labels into ``BriefingInputs`` (fail-closed).

    Read-only and side-effect-free. Unknown/missing/invalid => ``*_UNKNOWN`` and
    a supply caution; nothing here is a permission, a direction, or a signal.
    """

    cautions: list[str] = []
    recognised = 0
    fields_total = 0

    def track(recognised_flag: bool, unknown_caution: str) -> None:
        nonlocal recognised, fields_total
        fields_total += 1
        if recognised_flag:
            recognised += 1
        else:
            cautions.append(unknown_caution)

    exposure, ok = _norm(
        request.exposure_status, _EXPOSURE_MAP, ExposureSafeLabel.EXPOSURE_UNKNOWN
    )
    track(ok, "EXPOSURE_STATUS_UNKNOWN_TREATED_AS_CAUTION")
    budget, ok = _norm(
        request.risk_budget_status, _BUDGET_MAP, RiskBudgetSafeStatus.BUDGET_UNKNOWN
    )
    track(ok, "RISK_BUDGET_STATUS_UNKNOWN_TREATED_AS_CAUTION")
    readiness, ok = _norm(
        request.execution_readiness,
        _READINESS_MAP,
        SafeExecutionReadiness.READINESS_UNKNOWN,
    )
    track(ok, "EXECUTION_READINESS_UNKNOWN_TREATED_AS_CAUTION")
    trend, ok = _norm(
        request.trend_range, _TREND_MAP, TrendStateLabel.TREND_STATE_UNKNOWN
    )
    track(ok, "TREND_RANGE_UNKNOWN")
    volatility, ok = _norm(
        request.volatility, _VOL_MAP, VolatilitySafeCategory.VOLATILITY_UNKNOWN
    )
    track(ok, "VOLATILITY_UNKNOWN")
    spread, ok = _norm(
        request.spread_condition, _SPREAD_MAP, SpreadSafeCategory.SPREAD_UNKNOWN
    )
    track(ok, "SPREAD_CONDITION_UNKNOWN")
    liquidity, ok = _norm(
        request.liquidity, _LIQUIDITY_MAP, LiquiditySafeCategory.LIQUIDITY_UNKNOWN
    )
    track(ok, "LIQUIDITY_UNKNOWN")
    time_of_day, ok = _norm(
        request.time_of_day, _TIME_MAP, TimeOfDaySafeCategory.TIME_OF_DAY_UNKNOWN
    )
    track(ok, "TIME_OF_DAY_UNKNOWN")
    event, ok = _norm(
        request.event_proximity,
        _EVENT_MAP,
        EventProximitySafeLabel.EVENT_PROXIMITY_UNKNOWN,
    )
    track(ok, "EVENT_PROXIMITY_UNKNOWN_TREATED_AS_CAUTION")

    pending_count, pending_ok, pending_caution = _norm_pending(
        request.pending_order_safe_count, request.pending_order_status
    )
    track(pending_ok, "PENDING_ORDER_STATUS_UNKNOWN_TREATED_AS_CAUTION")
    if pending_caution is not None and pending_caution not in cautions:
        cautions.append(pending_caution)

    uncertainty_high, unc_ok = _norm_uncertainty(request.uncertainty)
    track(unc_ok, "UNCERTAINTY_UNKNOWN_TREATED_AS_HIGH")

    tags, tag_cautions = _context_tags(request.intended_context_labels)
    cautions.extend(tag_cautions)

    briefing_inputs = BriefingInputs(
        exposure=exposure,
        pending_order_safe_count=pending_count,
        risk_budget=budget,
        safe_execution_readiness=readiness,
        trend_state=trend,
        volatility=volatility,
        spread=spread,
        liquidity=liquidity,
        time_of_day=time_of_day,
        event_proximity=event,
        uncertainty_high=uncertainty_high,
        intended_context_tags=tags,
    )

    unknown_fields = fields_total - recognised
    if unknown_fields == 0:
        completeness = InputCompleteness.COMPLETE
    elif unknown_fields <= fields_total // 2:
        completeness = InputCompleteness.PARTIAL_UNKNOWN
    else:
        completeness = InputCompleteness.MOSTLY_UNKNOWN

    return SafeLabelSupplyResult(
        briefing_inputs=briefing_inputs,
        supply_cautions=tuple(cautions),
        input_completeness=completeness,
    )


def build_caution_briefing_from_labels(
    request: SafeLabelSupplyRequest,
) -> tuple[SafeLabelSupplyResult, CautionBriefing]:
    """Convenience: normalise SAFE labels, then generate the caution briefing.

    Read-only; never a recommendation, never triggers execution.
    """

    result = build_briefing_inputs(request)
    briefing = generate_caution_briefing(result.briefing_inputs)
    return result, briefing
