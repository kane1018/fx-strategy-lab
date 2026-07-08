"""Strategy rule revalidation (train/validation comparison + one-time OOS).

No-POST, deterministic, aggregate-only. This module compares a small,
bounded set of CANDIDATE backtest configurations on the train and validation
slices ONLY, freezes at most one candidate by fixed selection rules, then
evaluates that frozen candidate on the out-of-sample (OOS) slice exactly
once. It never mutates the deterministic signal engine, never optimizes on
OOS, and never claims performance: every result pins
``performance_proof_status = False`` / ``live_ready = False``.

Candidates are backtest-level knobs on ``run_synthetic_backtest``
(entry-momentum strictness, opposite-signal debounce, candidate exit policy
profile). Adoption is refused structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_strategy_backtest_dataset import (
    BacktestDataset,
    ChronologicalSplit,
)
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    build_candidate_exit_policy_profiles,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_backtest_metrics import (
    MINIMUM_TRADE_COUNT_FOR_EVALUATION,
    BacktestMetricsSummary,
    compute_backtest_metrics,
)

REVALIDATION_RULE_VERSION = "REVALIDATION_RULES_V1_TRAIN_VALIDATION_ONLY"
# Meaningful-improvement margin over baseline validation profit factor.
_PF_IMPROVEMENT_MARGIN = 1.05
# Allow at most this relative worsening of the spread cost ratio.
_SPREAD_COST_TOLERANCE = 1.10
# OOS must not fall materially below the frozen candidate's validation PF.
_OOS_DEGRADATION_FLOOR = 0.80
_MIN_OOS_PROFIT_FACTOR = 1.0


class RevalidationCandidateError(RuntimeError):
    """Raised when a candidate is misused (e.g. marked officially adopted)."""


@dataclass(frozen=True)
class RevalidationCandidate:
    """A backtest-level CANDIDATE configuration. Never officially adopted."""

    candidate_name: str
    entry_momentum_strict: bool
    opposite_signal_debounce_bars: int
    exit_policy_key: str
    candidate_only: bool = True
    officially_adopted: bool = False

    def __post_init__(self) -> None:
        if self.officially_adopted:
            raise RevalidationCandidateError(
                "revalidation candidates are candidate-only; official "
                "adoption requires OOS review, paper-forward, and an operator "
                "decision in a future step"
            )
        if not self.candidate_only:
            raise RevalidationCandidateError("candidate must stay candidate-only")
        if self.opposite_signal_debounce_bars < 1:
            raise RevalidationCandidateError("debounce bars must be >= 1")
        if self.exit_policy_key not in build_candidate_exit_policy_profiles():
            raise RevalidationCandidateError("unknown exit policy key")

    def __bool__(self) -> bool:
        return False


BASELINE_CANDIDATE_NAME = "BASELINE"


def build_default_revalidation_candidates() -> tuple[RevalidationCandidate, ...]:
    """Baseline plus <=3 improvement families and one small A+B combo."""

    return (
        RevalidationCandidate(
            candidate_name=BASELINE_CANDIDATE_NAME,
            entry_momentum_strict=False,
            opposite_signal_debounce_bars=1,
            exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
        ),
        RevalidationCandidate(
            candidate_name="CANDIDATE_A_ENTRY_MOMENTUM_STRICT",
            entry_momentum_strict=True,
            opposite_signal_debounce_bars=1,
            exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
        ),
        RevalidationCandidate(
            candidate_name="CANDIDATE_B_OPPOSITE_SIGNAL_DEBOUNCE",
            entry_momentum_strict=False,
            opposite_signal_debounce_bars=3,
            exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
        ),
        RevalidationCandidate(
            candidate_name="CANDIDATE_C_TIGHT_EXIT_PROFILE",
            entry_momentum_strict=False,
            opposite_signal_debounce_bars=1,
            exit_policy_key="CANDIDATE_SMALL_TIGHT",
        ),
        RevalidationCandidate(
            candidate_name="CANDIDATE_AB_STRICT_AND_DEBOUNCE",
            entry_momentum_strict=True,
            opposite_signal_debounce_bars=3,
            exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
        ),
    )


# ---------------------------------------------------------------------------
# Chronological split slicing (indicator lead-in is warmup, never leakage)
# ---------------------------------------------------------------------------

_MIN_LEAD_IN_BARS = 4  # trend derivation needs >= 4 closes


def _slice_dataset(
    dataset: BacktestDataset, *, start: int, end: int, warmup: int
) -> BacktestDataset:
    return BacktestDataset(
        symbol_safe_label=dataset.symbol_safe_label,
        timeframe_safe_label=dataset.timeframe_safe_label,
        candles=dataset.candles[start:end],
        spreads=dataset.spreads[start:end],
        sessions=dataset.sessions[start:end],
        warmup_bars=warmup,
        synthetic_fixture=dataset.synthetic_fixture,
        validated_operator_local_csv=dataset.validated_operator_local_csv,
    )


def build_split_datasets(
    dataset: BacktestDataset, split: ChronologicalSplit
) -> dict[str, BacktestDataset]:
    """Slice the dataset into train / validation / OOS sub-datasets.

    The validation and OOS slices include a small indicator lead-in taken
    from the immediately preceding bars (used only as warmup, never for
    trades) so there is no look-ahead into future segments.
    """

    lead = max(dataset.warmup_bars, _MIN_LEAD_IN_BARS)
    return {
        "TRAIN": _slice_dataset(
            dataset, start=0, end=split.train_end, warmup=split.warmup_end
        ),
        "VALIDATION": _slice_dataset(
            dataset,
            start=max(0, split.train_end - lead),
            end=split.validation_end,
            warmup=min(lead, split.train_end),
        ),
        "OOS": _slice_dataset(
            dataset,
            start=max(0, split.validation_end - lead),
            end=split.oos_end,
            warmup=min(lead, split.validation_end),
        ),
    }


def evaluate_candidate_on_dataset(
    dataset: BacktestDataset,
    candidate: RevalidationCandidate,
    *,
    spread_included: bool = True,
) -> BacktestMetricsSummary:
    """Run one candidate on one (sub-)dataset and return aggregate metrics."""

    policy = build_candidate_exit_policy_profiles()[candidate.exit_policy_key]
    run_result = run_synthetic_backtest(
        dataset=dataset,
        exit_policy=policy,
        spread_included=spread_included,
        entry_momentum_strict=candidate.entry_momentum_strict,
        opposite_signal_debounce_bars=candidate.opposite_signal_debounce_bars,
    )
    return compute_backtest_metrics(
        run_result,
        real_data_single_sample=not dataset.synthetic_fixture,
    )


# ---------------------------------------------------------------------------
# Aggregate, sign-only metric view for reporting
# ---------------------------------------------------------------------------


def _sign(value: float) -> str:
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "ZERO"


@dataclass(frozen=True)
class CandidateSplitMetricsSafe:
    """Aggregate, mostly sign-only metric view. No raw prices/PnL."""

    candidate_name: str
    split_label: str
    trade_count: int
    win_rate_rounded: float
    profit_factor_rounded: float
    expectancy_sign: str
    max_consecutive_losses: int
    spread_cost_ratio_sign: str
    hold_rate_rounded: float
    unknown_blocked_rate_rounded: float

    def __bool__(self) -> bool:
        return False


def _safe_view(
    candidate_name: str, split_label: str, metrics: BacktestMetricsSummary
) -> CandidateSplitMetricsSafe:
    return CandidateSplitMetricsSafe(
        candidate_name=candidate_name,
        split_label=split_label,
        trade_count=metrics.trade_count,
        win_rate_rounded=round(metrics.win_rate, 4),
        profit_factor_rounded=round(metrics.profit_factor, 4),
        expectancy_sign=_sign(metrics.expectancy),
        max_consecutive_losses=metrics.max_consecutive_losses,
        spread_cost_ratio_sign=_sign(metrics.spread_cost_ratio),
        hold_rate_rounded=round(metrics.hold_rate, 4),
        unknown_blocked_rate_rounded=round(metrics.unknown_blocked_rate, 4),
    )


# ---------------------------------------------------------------------------
# Train/validation comparison + freeze
# ---------------------------------------------------------------------------


class RevalidationSelectionStatus(str, Enum):
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    NO_CANDIDATE_SELECTED = "NO_CANDIDATE_SELECTED"


@dataclass(frozen=True)
class CandidateComparison:
    """Train/validation comparison result. Selection uses validation only."""

    status: RevalidationSelectionStatus
    selected_candidate_name: str | None
    selection_reason_safe_category: str
    baseline_validation_profit_factor: float
    train_metrics: tuple[CandidateSplitMetricsSafe, ...]
    validation_metrics: tuple[CandidateSplitMetricsSafe, ...]
    parameter_search_count: int
    selected_using: str = "TRAIN_VALIDATION_ONLY"
    oos_not_seen_before_freeze: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def _is_eligible(
    baseline: BacktestMetricsSummary, candidate: BacktestMetricsSummary
) -> bool:
    if candidate.trade_count < MINIMUM_TRADE_COUNT_FOR_EVALUATION:
        return False
    if candidate.profit_factor <= baseline.profit_factor * _PF_IMPROVEMENT_MARGIN:
        return False
    if candidate.max_consecutive_losses > baseline.max_consecutive_losses:
        return False
    if candidate.spread_cost_ratio > baseline.spread_cost_ratio * _SPREAD_COST_TOLERANCE:
        return False
    if candidate.expectancy < 0 <= baseline.expectancy:
        return False
    return True


def compare_candidates_train_validation(
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    candidates: tuple[RevalidationCandidate, ...] | None = None,
) -> CandidateComparison:
    """Compare candidates on train+validation; select at most one candidate.

    OOS is never touched here. Selection rules are fixed and conservative:
    a candidate must beat the baseline validation profit factor by a margin
    while not worsening max consecutive losses or spread cost, keeping a
    minimum trade count, and not flipping expectancy negative.
    """

    candidate_set = candidates or build_default_revalidation_candidates()
    splits = build_split_datasets(dataset, split)
    train_ds = splits["TRAIN"]
    validation_ds = splits["VALIDATION"]

    train_views: list[CandidateSplitMetricsSafe] = []
    validation_views: list[CandidateSplitMetricsSafe] = []
    validation_metrics: dict[str, BacktestMetricsSummary] = {}
    for candidate in candidate_set:
        train_metrics = evaluate_candidate_on_dataset(train_ds, candidate)
        val_metrics = evaluate_candidate_on_dataset(validation_ds, candidate)
        train_views.append(_safe_view(candidate.candidate_name, "TRAIN", train_metrics))
        validation_views.append(
            _safe_view(candidate.candidate_name, "VALIDATION", val_metrics)
        )
        validation_metrics[candidate.candidate_name] = val_metrics

    baseline_val = validation_metrics[BASELINE_CANDIDATE_NAME]
    # parameter_search_count counts the non-baseline candidate evaluations.
    parameter_search_count = len(candidate_set) - 1

    eligible: list[tuple[str, BacktestMetricsSummary]] = [
        (candidate.candidate_name, validation_metrics[candidate.candidate_name])
        for candidate in candidate_set
        if candidate.candidate_name != BASELINE_CANDIDATE_NAME
        and _is_eligible(baseline_val, validation_metrics[candidate.candidate_name])
    ]
    if not eligible:
        return CandidateComparison(
            status=RevalidationSelectionStatus.NO_CANDIDATE_SELECTED,
            selected_candidate_name=None,
            selection_reason_safe_category="NO_CANDIDATE_MEETS_SELECTION_CRITERIA",
            baseline_validation_profit_factor=round(baseline_val.profit_factor, 4),
            train_metrics=tuple(train_views),
            validation_metrics=tuple(validation_views),
            parameter_search_count=parameter_search_count,
        )

    # Deterministic pick: highest validation PF, then fewest consecutive
    # losses, then name for a stable tie-break.
    eligible.sort(
        key=lambda item: (
            -item[1].profit_factor,
            item[1].max_consecutive_losses,
            item[0],
        )
    )
    selected_name = eligible[0][0]
    return CandidateComparison(
        status=RevalidationSelectionStatus.CANDIDATE_SELECTED,
        selected_candidate_name=selected_name,
        selection_reason_safe_category=(
            "VALIDATION_PROFIT_FACTOR_IMPROVED_WITHOUT_WORSE_RISK"
        ),
        baseline_validation_profit_factor=round(baseline_val.profit_factor, 4),
        train_metrics=tuple(train_views),
        validation_metrics=tuple(validation_views),
        parameter_search_count=parameter_search_count,
    )


@dataclass(frozen=True)
class FrozenCandidate:
    """A single candidate frozen before any OOS look."""

    candidate: RevalidationCandidate
    rule_version: str
    selection_reason_safe_category: str
    validation_profit_factor: float
    selected_using: str = "TRAIN_VALIDATION_ONLY"
    oos_not_seen_before_freeze: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def freeze_selected_candidate(
    comparison: CandidateComparison,
    candidates: tuple[RevalidationCandidate, ...] | None = None,
) -> FrozenCandidate | None:
    """Freeze the selected candidate (or None). No OOS has been seen yet."""

    if comparison.status is not RevalidationSelectionStatus.CANDIDATE_SELECTED:
        return None
    candidate_set = candidates or build_default_revalidation_candidates()
    by_name = {c.candidate_name: c for c in candidate_set}
    selected = by_name[comparison.selected_candidate_name]
    validation_pf = next(
        view.profit_factor_rounded
        for view in comparison.validation_metrics
        if view.candidate_name == selected.candidate_name
    )
    return FrozenCandidate(
        candidate=selected,
        rule_version=REVALIDATION_RULE_VERSION,
        selection_reason_safe_category=comparison.selection_reason_safe_category,
        validation_profit_factor=validation_pf,
    )


# ---------------------------------------------------------------------------
# One-time OOS evaluation
# ---------------------------------------------------------------------------


class OosResultCategory(str, Enum):
    OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW = (
        "OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW"
    )
    OOS_DEGRADED_REJECT_CANDIDATE = "OOS_DEGRADED_REJECT_CANDIDATE"
    OOS_INSUFFICIENT_TRADES = "OOS_INSUFFICIENT_TRADES"
    OOS_NOT_RUN_NO_CANDIDATE = "OOS_NOT_RUN_NO_CANDIDATE"


@dataclass(frozen=True)
class OosEvaluation:
    """One-time OOS confirmation. Never a performance proof."""

    result_category: OosResultCategory
    oos_metrics: CandidateSplitMetricsSafe | None
    exit_reason_distribution: tuple[tuple[str, int], ...]
    evaluated_once: bool
    retuned_after_oos: bool = False
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


_EXIT_REASONS = (
    BacktestExitReason.EXIT_TAKE_PROFIT,
    BacktestExitReason.EXIT_STOP_LOSS,
    BacktestExitReason.EXIT_MAX_HOLD,
    BacktestExitReason.EXIT_OPPOSITE_SIGNAL,
    BacktestExitReason.EXIT_END_OF_WINDOW,
)


def evaluate_frozen_candidate_on_oos_once(
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    frozen: FrozenCandidate | None,
) -> OosEvaluation:
    """Evaluate the frozen candidate on OOS exactly once. No retuning."""

    if frozen is None:
        return OosEvaluation(
            result_category=OosResultCategory.OOS_NOT_RUN_NO_CANDIDATE,
            oos_metrics=None,
            exit_reason_distribution=(),
            evaluated_once=False,
        )
    oos_ds = build_split_datasets(dataset, split)["OOS"]
    policy = build_candidate_exit_policy_profiles()[frozen.candidate.exit_policy_key]
    run_result = run_synthetic_backtest(
        dataset=oos_ds,
        exit_policy=policy,
        spread_included=True,
        entry_momentum_strict=frozen.candidate.entry_momentum_strict,
        opposite_signal_debounce_bars=(
            frozen.candidate.opposite_signal_debounce_bars
        ),
    )
    metrics = compute_backtest_metrics(
        run_result, real_data_single_sample=not oos_ds.synthetic_fixture
    )
    view = _safe_view(frozen.candidate.candidate_name, "OOS", metrics)
    exit_counts = {
        reason.value: sum(
            1
            for trade in run_result.trades
            if trade.exit_reason_safe_label is reason
        )
        for reason in _EXIT_REASONS
    }
    exit_distribution = tuple(
        (label, count) for label, count in sorted(exit_counts.items()) if count
    )

    if metrics.trade_count < MINIMUM_TRADE_COUNT_FOR_EVALUATION:
        category = OosResultCategory.OOS_INSUFFICIENT_TRADES
    elif (
        metrics.profit_factor
        >= max(
            _MIN_OOS_PROFIT_FACTOR,
            frozen.validation_profit_factor * _OOS_DEGRADATION_FLOOR,
        )
    ):
        category = OosResultCategory.OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW
    else:
        category = OosResultCategory.OOS_DEGRADED_REJECT_CANDIDATE

    return OosEvaluation(
        result_category=category,
        oos_metrics=view,
        exit_reason_distribution=exit_distribution,
        evaluated_once=True,
    )
