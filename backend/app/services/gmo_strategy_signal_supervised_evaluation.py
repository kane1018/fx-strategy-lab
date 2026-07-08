"""Supervised evaluation harness for the strategy signal engine (no-POST).

Behavior evaluation ONLY: it exercises the deterministic rule engine over a
bounded synthetic safe-label grid and reports safe counts / safe categories.
It never evaluates profit, win rate, PF, or PnL -- there is no field that
could carry such a value, and the report pins
``performance_proof_status = False`` plus
``excluded_from_performance_claim = True`` on every review record.

The operator review slot is a PLACEHOLDER by construction: the harness
writes ``NOT_PROVIDED`` and nothing here can fill in an operator judgment.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_strategy_signal_engine import (
    RULE_PATH_LABELS,
    GuardSafeLabel,
    MarketSafeLabel,
    MomentumSafeLabel,
    PositionContextSafeLabel,
    SessionSafeLabel,
    SpreadSafeLabel,
    StrategyDecisionCategory,
    StrategySignalSafeInput,
    TickerFreshSafeLabel,
    TrendSafeLabel,
    VolatilitySafeLabel,
    build_all_safe_entry_context_input,
    evaluate_strategy_signal,
)

OPERATOR_REVIEW_PLACEHOLDER = "NOT_PROVIDED"

IMPROVEMENT_CANDIDATE_CATEGORIES: tuple[str, ...] = (
    "IMPROVE_TREND_CONFIRMATION",
    "IMPROVE_RANGE_FILTER",
    "IMPROVE_CONFLICT_HANDLING",
    "IMPROVE_SESSION_FILTER",
    "IMPROVE_VOLATILITY_BLOCKER",
    "IMPROVE_SETTLEMENT_RULES",
    "IMPROVE_HOLD_RULES",
    "INTEGRATE_PREVIEW_MODULE_WITH_ENGINE",
    "NEEDS_BACKTEST_DATASET",
    "NEEDS_OUT_OF_SAMPLE_EVALUATION",
    "NEEDS_OPERATOR_REVIEW_SAMPLES",
    "NEEDS_PAPER_FORWARD_TEST",
)


class StrategyEvaluationStatus(str, Enum):
    STRATEGY_EVALUATION_BEHAVIOR_PASSED = "STRATEGY_EVALUATION_BEHAVIOR_PASSED"
    STRATEGY_EVALUATION_BEHAVIOR_BLOCKED = "STRATEGY_EVALUATION_BEHAVIOR_BLOCKED"
    STRATEGY_EVALUATION_NEEDS_OPERATOR_REVIEW = (
        "STRATEGY_EVALUATION_NEEDS_OPERATOR_REVIEW"
    )
    STRATEGY_EVALUATION_NOT_PERFORMANCE_PROOF = (
        "STRATEGY_EVALUATION_NOT_PERFORMANCE_PROOF"
    )


@dataclass(frozen=True)
class StrategyEvaluationScenario:
    """One deterministic scenario with an expected engine behavior."""

    scenario_family_safe_label: str
    signal_input: StrategySignalSafeInput
    expected_signal: AutoPreviewSignal
    expected_category: StrategyDecisionCategory


@dataclass(frozen=True)
class SupervisedReviewRecord:
    """Review-ready record. The operator slot is never filled by the AI."""

    scenario_family_safe_label: str
    auto_preview_signal: str
    strategy_decision_category: str
    rule_path_safe_label: str
    block_reason_safe_label: str
    matched_expectation: bool
    operator_review_label_name_only: str = "operator_review_label"
    operator_acceptance_placeholder: str = OPERATOR_REVIEW_PLACEHOLDER
    improvement_note_category: str = ""
    excluded_from_performance_claim: bool = True

    def __bool__(self) -> bool:
        return False


def _distribution(labels: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return tuple(sorted(counts.items()))


def build_required_scenario_families() -> tuple[StrategyEvaluationScenario, ...]:
    """The required behavior scenario families, all synthetic safe labels."""

    blocked = AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
    fail_closed = StrategyDecisionCategory.BLOCKED_FAIL_CLOSED
    entry = StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED
    hold = StrategyDecisionCategory.HOLD_NO_ORDER

    def _degraded(**overrides) -> StrategySignalSafeInput:
        return replace(
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.UPTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_UP,
            ),
            **overrides,
        )

    return (
        StrategyEvaluationScenario(
            "FAMILY_CLEAR_UPTREND_BUY",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.UPTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_UP,
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            entry,
        ),
        StrategyEvaluationScenario(
            "FAMILY_CLEAR_DOWNTREND_SELL",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.DOWNTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_DOWN,
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL,
            entry,
        ),
        StrategyEvaluationScenario(
            "FAMILY_RANGE_HOLD",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.RANGE,
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            hold,
        ),
        StrategyEvaluationScenario(
            "FAMILY_TREND_UNKNOWN_BLOCKED",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.TREND_UNKNOWN,
            ),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_TREND_CONFLICT_BLOCKED",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.TREND_CONFLICT,
            ),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_MOMENTUM_CONFLICT_HOLD",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.UPTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_DOWN,
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            hold,
        ),
        StrategyEvaluationScenario(
            "FAMILY_SPREAD_OUT_BLOCKED",
            _degraded(spread_safe_label=SpreadSafeLabel.SPREAD_OUT_OF_LIMIT),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_TICKER_STALE_BLOCKED",
            _degraded(
                ticker_fresh_safe_label=TickerFreshSafeLabel.TICKER_STALE
            ),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_MARKET_UNSAFE_BLOCKED",
            _degraded(market_safe_label=MarketSafeLabel.MARKET_UNSAFE),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_SESSION_BLOCKED",
            _degraded(session_safe_label=SessionSafeLabel.SESSION_BLOCKED),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_HIGH_VOLATILITY_BLOCKED",
            _degraded(
                volatility_safe_label=(
                    VolatilitySafeLabel.VOLATILITY_HIGH_BLOCKED
                )
            ),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_GUARD_HALT_BLOCKED",
            _degraded(guard_safe_label=GuardSafeLabel.GUARD_HALT),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_NO_POSITION_ENTRY_PREVIEW_ALLOWED",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.UPTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_UP,
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            entry,
        ),
        StrategyEvaluationScenario(
            "FAMILY_ONE_POSITION_SETTLEMENT_CONTEXT_ONLY",
            _degraded(
                position_context_safe_label=(
                    PositionContextSafeLabel.ONE_POSITION_CONTEXT
                )
            ),
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            StrategyDecisionCategory.SETTLEMENT_PREVIEW_CONTEXT_ONLY,
        ),
        StrategyEvaluationScenario(
            "FAMILY_POSITION_CONTEXT_UNKNOWN_BLOCKED",
            _degraded(
                position_context_safe_label=(
                    PositionContextSafeLabel.POSITION_CONTEXT_UNKNOWN
                )
            ),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_MISSING_LABELS_DEFAULT_BLOCKED",
            StrategySignalSafeInput(),
            blocked,
            fail_closed,
        ),
        StrategyEvaluationScenario(
            "FAMILY_MOMENTUM_UNKNOWN_BLOCKED",
            build_all_safe_entry_context_input(
                trend_safe_label=TrendSafeLabel.UPTREND,
                momentum_safe_label=MomentumSafeLabel.MOMENTUM_UNKNOWN,
            ),
            blocked,
            fail_closed,
        ),
    )


def build_deterministic_scenario_grid() -> tuple[StrategySignalSafeInput, ...]:
    """Bounded deterministic grid (>=50 rows) over safe labels only.

    Rows: every trend x momentum pair in the all-green entry context (20),
    every single-gate degradation of the clear-uptrend input, every
    position context, and the fully-unknown default input.
    """

    rows: list[StrategySignalSafeInput] = []
    for trend in TrendSafeLabel:
        for momentum in MomentumSafeLabel:
            rows.append(
                build_all_safe_entry_context_input(
                    trend_safe_label=trend, momentum_safe_label=momentum
                )
            )
    base = build_all_safe_entry_context_input(
        trend_safe_label=TrendSafeLabel.UPTREND,
        momentum_safe_label=MomentumSafeLabel.MOMENTUM_UP,
    )
    degradations: tuple[dict[str, object], ...] = (
        {"spread_safe_label": SpreadSafeLabel.SPREAD_OUT_OF_LIMIT},
        {"spread_safe_label": SpreadSafeLabel.SPREAD_UNKNOWN},
        {"ticker_fresh_safe_label": TickerFreshSafeLabel.TICKER_STALE},
        {"ticker_fresh_safe_label": TickerFreshSafeLabel.TICKER_UNKNOWN},
        {"market_safe_label": MarketSafeLabel.MARKET_UNSAFE},
        {"market_safe_label": MarketSafeLabel.MARKET_UNKNOWN},
        {"session_safe_label": SessionSafeLabel.SESSION_BLOCKED},
        {"session_safe_label": SessionSafeLabel.SESSION_UNKNOWN},
        {
            "volatility_safe_label": (
                VolatilitySafeLabel.VOLATILITY_HIGH_BLOCKED
            )
        },
        {"volatility_safe_label": VolatilitySafeLabel.VOLATILITY_UNKNOWN},
        {"guard_safe_label": GuardSafeLabel.GUARD_HALT},
        {"guard_safe_label": GuardSafeLabel.GUARD_UNKNOWN},
    )
    for overrides in degradations:
        rows.append(replace(base, **overrides))
    for context in PositionContextSafeLabel:
        rows.append(replace(base, position_context_safe_label=context))
    # Degradations repeated across the remaining trends for breadth.
    for trend in (
        TrendSafeLabel.DOWNTREND,
        TrendSafeLabel.RANGE,
        TrendSafeLabel.TREND_UNKNOWN,
        TrendSafeLabel.TREND_CONFLICT,
    ):
        for overrides in degradations[:4]:
            rows.append(
                replace(base, trend_safe_label=trend, **overrides)  # type: ignore[arg-type]
            )
    rows.append(StrategySignalSafeInput())
    return tuple(rows)


@dataclass(frozen=True)
class StrategySupervisedEvaluationReport:
    """Safe counts / safe categories only. Never truthy, never a permission."""

    status: StrategyEvaluationStatus
    scenario_family_count: int
    matched_family_count: int
    mismatched_families_safe: tuple[str, ...]
    grid_row_count: int
    signal_distribution: tuple[tuple[str, int], ...]
    category_distribution: tuple[tuple[str, int], ...]
    block_reason_distribution: tuple[tuple[str, int], ...]
    rule_path_distribution: tuple[tuple[str, int], ...]
    rule_paths_covered: tuple[str, ...]
    rule_paths_defined: tuple[str, ...]
    rule_coverage_complete: bool
    fail_closed_row_count: int
    hold_rows_created_orders: int
    review_records: tuple[SupervisedReviewRecord, ...]
    improvement_candidates: tuple[str, ...]
    operator_review_filled_by_ai: bool = False
    performance_proof_status: bool = False
    strategy_quality_proven: bool = False
    preview_is_permission: bool = False
    auto_preview_signal_is_operator_signal: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    real_post_count: int = 0
    raw_id_value_exposure: bool = False
    unattended_live_supported: bool = False
    unattended_full_auto_completed: bool = False

    def __bool__(self) -> bool:
        return False


def run_strategy_signal_supervised_evaluation() -> (
    StrategySupervisedEvaluationReport
):
    """Run the behavior evaluation once (deterministic, no-POST)."""

    families = build_required_scenario_families()
    review_records: list[SupervisedReviewRecord] = []
    mismatched: list[str] = []
    for scenario in families:
        decision = evaluate_strategy_signal(scenario.signal_input)
        matched = (
            decision.auto_preview_signal is scenario.expected_signal
            and decision.strategy_decision_category is scenario.expected_category
        )
        if not matched:
            mismatched.append(scenario.scenario_family_safe_label)
        review_records.append(
            SupervisedReviewRecord(
                scenario_family_safe_label=scenario.scenario_family_safe_label,
                auto_preview_signal=decision.auto_preview_signal.value,
                strategy_decision_category=(
                    decision.strategy_decision_category.value
                ),
                rule_path_safe_label=decision.rule_path_safe_label,
                block_reason_safe_label=decision.block_reason_safe_label,
                matched_expectation=matched,
            )
        )

    grid = build_deterministic_scenario_grid()
    decisions = [evaluate_strategy_signal(row) for row in grid]
    signal_labels = [d.auto_preview_signal.value for d in decisions]
    category_labels = [d.strategy_decision_category.value for d in decisions]
    block_reasons = [
        d.block_reason_safe_label for d in decisions if d.block_reason_safe_label
    ]
    rule_paths = [d.rule_path_safe_label for d in decisions]
    covered = tuple(sorted(set(rule_paths)))
    fail_closed_rows = sum(
        1
        for d in decisions
        if d.strategy_decision_category
        is StrategyDecisionCategory.BLOCKED_FAIL_CLOSED
    )
    hold_orders = sum(
        1
        for d in decisions
        if d.auto_preview_signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
        and d.order_attempt_created
    )

    behavior_ok = not mismatched and hold_orders == 0
    status = (
        StrategyEvaluationStatus.STRATEGY_EVALUATION_BEHAVIOR_PASSED
        if behavior_ok
        else StrategyEvaluationStatus.STRATEGY_EVALUATION_BEHAVIOR_BLOCKED
    )
    return StrategySupervisedEvaluationReport(
        status=status,
        scenario_family_count=len(families),
        matched_family_count=len(families) - len(mismatched),
        mismatched_families_safe=tuple(mismatched),
        grid_row_count=len(grid),
        signal_distribution=_distribution(signal_labels),
        category_distribution=_distribution(category_labels),
        block_reason_distribution=_distribution(block_reasons),
        rule_path_distribution=_distribution(rule_paths),
        rule_paths_covered=covered,
        rule_paths_defined=RULE_PATH_LABELS,
        rule_coverage_complete=set(RULE_PATH_LABELS) <= set(covered),
        fail_closed_row_count=fail_closed_rows,
        hold_rows_created_orders=hold_orders,
        review_records=tuple(review_records),
        improvement_candidates=IMPROVEMENT_CANDIDATE_CATEGORIES,
    )
