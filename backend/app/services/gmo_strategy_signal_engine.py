"""Strategy signal engine (deterministic, rule-based, safe-label-only, no-POST).

Formalizes the provisional preview signal logic as an explicit rule engine.
Every rule is a fixed table lookup over safe labels -- there is no LLM
judgment, no numeric threshold, and no raw price/spread/PnL/ID surface in
this module at all.

Relationship to existing code: ``gmo_supervised_auto_live_preview.
derive_auto_preview_signal`` remains the simple gate+trend subset used by
the preview package; this engine is the documented superset (momentum,
volatility, session, guard, position context, conflict handling) evaluated
by the supervised evaluation harness. Routing the preview module through
this engine is a recorded improvement candidate, not done here.

Hard rules enforced by construction:

- Output is an AUTO preview signal (``AUTO_PREVIEW_SIGNAL_*``) plus safe
  rule-path / block-reason labels. It is NEVER an operator signal
  (ENTRY_BUY / ENTRY_SELL / HOLD) and NEVER a permission:
  ``actual_entry_POST_allowed`` / ``actual_settlement_POST_allowed`` are
  hardcoded false and decisions are never truthy.
- Fail-closed: every UNKNOWN, CONFLICT, blocked, or missing label yields
  ``AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED`` with an explicit block reason.
- HOLD is never an order; an open-position context never yields an
  entry-shaped signal (settlement preview context only).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_supervised_auto_live_preview import (
    REQUIRED_FUTURE_GATES,
    REQUIRED_FUTURE_OPERATOR_INPUT_NAMES,
    WHY_PREVIEW_IS_NOT_PERMISSION,
)


class TrendSafeLabel(str, Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    RANGE = "RANGE"
    TREND_UNKNOWN = "TREND_UNKNOWN"
    TREND_CONFLICT = "TREND_CONFLICT"


class MomentumSafeLabel(str, Enum):
    MOMENTUM_UP = "MOMENTUM_UP"
    MOMENTUM_DOWN = "MOMENTUM_DOWN"
    MOMENTUM_FLAT = "MOMENTUM_FLAT"
    MOMENTUM_UNKNOWN = "MOMENTUM_UNKNOWN"


class VolatilitySafeLabel(str, Enum):
    VOLATILITY_NORMAL = "VOLATILITY_NORMAL"
    VOLATILITY_HIGH_BLOCKED = "VOLATILITY_HIGH_BLOCKED"
    VOLATILITY_UNKNOWN = "VOLATILITY_UNKNOWN"


class SpreadSafeLabel(str, Enum):
    SPREAD_WITHIN_LIMIT = "SPREAD_WITHIN_LIMIT"
    SPREAD_OUT_OF_LIMIT = "SPREAD_OUT_OF_LIMIT"
    SPREAD_UNKNOWN = "SPREAD_UNKNOWN"


class TickerFreshSafeLabel(str, Enum):
    TICKER_FRESH = "TICKER_FRESH"
    TICKER_STALE = "TICKER_STALE"
    TICKER_UNKNOWN = "TICKER_UNKNOWN"


class MarketSafeLabel(str, Enum):
    MARKET_SAFE = "MARKET_SAFE"
    MARKET_UNSAFE = "MARKET_UNSAFE"
    MARKET_UNKNOWN = "MARKET_UNKNOWN"


class SessionSafeLabel(str, Enum):
    SESSION_ALLOWED = "SESSION_ALLOWED"
    SESSION_BLOCKED = "SESSION_BLOCKED"
    SESSION_UNKNOWN = "SESSION_UNKNOWN"


class GuardSafeLabel(str, Enum):
    GUARD_PASS = "GUARD_PASS"
    GUARD_HALT = "GUARD_HALT"
    GUARD_UNKNOWN = "GUARD_UNKNOWN"


class PositionContextSafeLabel(str, Enum):
    NO_POSITION_CONTEXT = "NO_POSITION_CONTEXT"
    ONE_POSITION_CONTEXT = "ONE_POSITION_CONTEXT"
    POSITION_CONTEXT_UNKNOWN = "POSITION_CONTEXT_UNKNOWN"


class StrategyDecisionCategory(str, Enum):
    ENTRY_PREVIEW_PROPOSED = "ENTRY_PREVIEW_PROPOSED"
    HOLD_NO_ORDER = "HOLD_NO_ORDER"
    SETTLEMENT_PREVIEW_CONTEXT_ONLY = "SETTLEMENT_PREVIEW_CONTEXT_ONLY"
    BLOCKED_FAIL_CLOSED = "BLOCKED_FAIL_CLOSED"


@dataclass(frozen=True)
class StrategySignalSafeInput:
    """Safe-label-only engine input. Default state is fully unknown (blocks)."""

    trend_safe_label: TrendSafeLabel = TrendSafeLabel.TREND_UNKNOWN
    momentum_safe_label: MomentumSafeLabel = MomentumSafeLabel.MOMENTUM_UNKNOWN
    volatility_safe_label: VolatilitySafeLabel = (
        VolatilitySafeLabel.VOLATILITY_UNKNOWN
    )
    spread_safe_label: SpreadSafeLabel = SpreadSafeLabel.SPREAD_UNKNOWN
    ticker_fresh_safe_label: TickerFreshSafeLabel = (
        TickerFreshSafeLabel.TICKER_UNKNOWN
    )
    market_safe_label: MarketSafeLabel = MarketSafeLabel.MARKET_UNKNOWN
    session_safe_label: SessionSafeLabel = SessionSafeLabel.SESSION_UNKNOWN
    guard_safe_label: GuardSafeLabel = GuardSafeLabel.GUARD_UNKNOWN
    position_context_safe_label: PositionContextSafeLabel = (
        PositionContextSafeLabel.POSITION_CONTEXT_UNKNOWN
    )


# Environment gates checked before any trend rule, in fixed order. Each entry:
# (field name, safe value, block reason when not safe).
_ENVIRONMENT_GATES: tuple[tuple[str, object, str], ...] = (
    ("guard_safe_label", GuardSafeLabel.GUARD_PASS, "BLOCK_GUARD_NOT_PASS"),
    (
        "market_safe_label",
        MarketSafeLabel.MARKET_SAFE,
        "BLOCK_MARKET_NOT_SAFE",
    ),
    (
        "session_safe_label",
        SessionSafeLabel.SESSION_ALLOWED,
        "BLOCK_SESSION_NOT_ALLOWED",
    ),
    (
        "ticker_fresh_safe_label",
        TickerFreshSafeLabel.TICKER_FRESH,
        "BLOCK_TICKER_NOT_FRESH",
    ),
    (
        "spread_safe_label",
        SpreadSafeLabel.SPREAD_WITHIN_LIMIT,
        "BLOCK_SPREAD_NOT_WITHIN_LIMIT",
    ),
    (
        "volatility_safe_label",
        VolatilitySafeLabel.VOLATILITY_NORMAL,
        "BLOCK_VOLATILITY_NOT_NORMAL",
    ),
)

# Trend x momentum rule table for the NO_POSITION entry-preview context.
# Missing keys fall through to the fail-closed default.
_TREND_MOMENTUM_RULES: dict[
    tuple[TrendSafeLabel, MomentumSafeLabel],
    tuple[AutoPreviewSignal, StrategyDecisionCategory, str],
] = {
    (TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
        StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED,
        "RULE_UPTREND_MOMENTUM_ALIGNED_BUY",
    ),
    (TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_FLAT): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
        StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED,
        "RULE_UPTREND_MOMENTUM_NEUTRAL_BUY",
    ),
    (TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_DOWN): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        StrategyDecisionCategory.HOLD_NO_ORDER,
        "RULE_TREND_MOMENTUM_CONFLICT_HOLD",
    ),
    (TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_DOWN): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL,
        StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED,
        "RULE_DOWNTREND_MOMENTUM_ALIGNED_SELL",
    ),
    (TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_FLAT): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL,
        StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED,
        "RULE_DOWNTREND_MOMENTUM_NEUTRAL_SELL",
    ),
    (TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_UP): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        StrategyDecisionCategory.HOLD_NO_ORDER,
        "RULE_TREND_MOMENTUM_CONFLICT_HOLD",
    ),
    (TrendSafeLabel.RANGE, MomentumSafeLabel.MOMENTUM_UP): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        StrategyDecisionCategory.HOLD_NO_ORDER,
        "RULE_RANGE_HOLD",
    ),
    (TrendSafeLabel.RANGE, MomentumSafeLabel.MOMENTUM_DOWN): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        StrategyDecisionCategory.HOLD_NO_ORDER,
        "RULE_RANGE_HOLD",
    ),
    (TrendSafeLabel.RANGE, MomentumSafeLabel.MOMENTUM_FLAT): (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        StrategyDecisionCategory.HOLD_NO_ORDER,
        "RULE_RANGE_HOLD",
    ),
}

RULE_PATH_LABELS: tuple[str, ...] = tuple(
    sorted(
        {rule_path for (_, _, rule_path) in _TREND_MOMENTUM_RULES.values()}
        | {
            "RULE_ENVIRONMENT_GATE_BLOCKED",
            "RULE_TREND_NOT_DERIVABLE_BLOCKED",
            "RULE_MOMENTUM_UNKNOWN_BLOCKED",
            "RULE_SETTLEMENT_CONTEXT_ONLY",
            "RULE_POSITION_CONTEXT_UNKNOWN_BLOCKED",
        }
    )
)


@dataclass(frozen=True)
class StrategySignalDecision:
    """Engine decision. Safe labels only; never truthy, never a permission."""

    auto_preview_signal: AutoPreviewSignal
    strategy_decision_category: StrategyDecisionCategory
    rule_path_safe_label: str
    block_reason_safe_label: str
    required_future_gate_names: tuple[str, ...]
    required_operator_input_names: tuple[str, ...]
    why_not_permission: str = WHY_PREVIEW_IS_NOT_PERMISSION
    auto_preview_signal_is_operator_signal: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    order_attempt_created: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


def _decision(
    signal: AutoPreviewSignal,
    category: StrategyDecisionCategory,
    rule_path: str,
    block_reason: str = "",
) -> StrategySignalDecision:
    proposes_order = category is StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED
    return StrategySignalDecision(
        auto_preview_signal=signal,
        strategy_decision_category=category,
        rule_path_safe_label=rule_path,
        block_reason_safe_label=block_reason,
        required_future_gate_names=REQUIRED_FUTURE_GATES if proposes_order else (),
        required_operator_input_names=(
            REQUIRED_FUTURE_OPERATOR_INPUT_NAMES if proposes_order else ()
        ),
    )


def evaluate_strategy_signal(
    signal_input: StrategySignalSafeInput,
) -> StrategySignalDecision:
    """Evaluate the fixed rule table over safe labels only. Fail-closed.

    Order of evaluation: environment gates -> position context -> trend /
    momentum table. Anything not explicitly mapped blocks.
    """

    for field_name, safe_value, block_reason in _ENVIRONMENT_GATES:
        if getattr(signal_input, field_name) is not safe_value:
            return _decision(
                AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
                StrategyDecisionCategory.BLOCKED_FAIL_CLOSED,
                "RULE_ENVIRONMENT_GATE_BLOCKED",
                block_reason,
            )

    context = signal_input.position_context_safe_label
    if context is PositionContextSafeLabel.POSITION_CONTEXT_UNKNOWN:
        return _decision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED,
            "RULE_POSITION_CONTEXT_UNKNOWN_BLOCKED",
            "BLOCK_POSITION_CONTEXT_UNKNOWN",
        )
    if context is PositionContextSafeLabel.ONE_POSITION_CONTEXT:
        # An open position never yields an entry-shaped signal. The
        # settlement side itself stays a mechanical provenance of the prior
        # entry (see official settlement preflight), never a fresh engine
        # decision.
        return _decision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            StrategyDecisionCategory.SETTLEMENT_PREVIEW_CONTEXT_ONLY,
            "RULE_SETTLEMENT_CONTEXT_ONLY",
            "ENTRY_PREVIEW_BLOCKED_POSITION_ALREADY_OPEN",
        )

    trend = signal_input.trend_safe_label
    if trend in (TrendSafeLabel.TREND_UNKNOWN, TrendSafeLabel.TREND_CONFLICT):
        return _decision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED,
            "RULE_TREND_NOT_DERIVABLE_BLOCKED",
            (
                "BLOCK_TREND_CONFLICT"
                if trend is TrendSafeLabel.TREND_CONFLICT
                else "BLOCK_TREND_UNKNOWN"
            ),
        )
    momentum = signal_input.momentum_safe_label
    if momentum is MomentumSafeLabel.MOMENTUM_UNKNOWN:
        return _decision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED,
            "RULE_MOMENTUM_UNKNOWN_BLOCKED",
            "BLOCK_MOMENTUM_UNKNOWN",
        )

    rule = _TREND_MOMENTUM_RULES.get((trend, momentum))
    if rule is None:
        return _decision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED,
            "RULE_TREND_NOT_DERIVABLE_BLOCKED",
            "BLOCK_RULE_NOT_MAPPED",
        )
    signal, category, rule_path = rule
    return _decision(signal, category, rule_path)


def build_all_safe_entry_context_input(
    *,
    trend_safe_label: TrendSafeLabel,
    momentum_safe_label: MomentumSafeLabel = MomentumSafeLabel.MOMENTUM_FLAT,
) -> StrategySignalSafeInput:
    """All-green environment with flat entry context, for tests/scenarios."""

    return StrategySignalSafeInput(
        trend_safe_label=trend_safe_label,
        momentum_safe_label=momentum_safe_label,
        volatility_safe_label=VolatilitySafeLabel.VOLATILITY_NORMAL,
        spread_safe_label=SpreadSafeLabel.SPREAD_WITHIN_LIMIT,
        ticker_fresh_safe_label=TickerFreshSafeLabel.TICKER_FRESH,
        market_safe_label=MarketSafeLabel.MARKET_SAFE,
        session_safe_label=SessionSafeLabel.SESSION_ALLOWED,
        guard_safe_label=GuardSafeLabel.GUARD_PASS,
        position_context_safe_label=PositionContextSafeLabel.NO_POSITION_CONTEXT,
    )
