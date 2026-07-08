"""Backtest report format (safe aggregates only, no-POST).

Assembles the fixed report sections from a synthetic run + metrics summary.
The report surface is aggregates and safe labels only: there is no field
for a per-bar price list, a broker/order/account/position/trade ID, a
credential, or a raw broker value, and the renderer emits ``key: value``
lines from those fields alone.

An official report REQUIRES spread-included evaluation; a spread-excluded
run renders only as a reference report. ``performance_proof_status`` and
``live_ready`` are hardcoded false in this phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_strategy_backtest_dataset import (
    BacktestDataset,
    ChronologicalSplit,
)
from app.services.gmo_strategy_backtest_engine import (
    BacktestRunResult,
    ExitPolicyCandidate,
)
from app.services.gmo_strategy_backtest_metrics import (
    BacktestMetricsSummary,
    GmoOosStatus,
)

# Claims that must never appear in a report in this phase.
FORBIDDEN_REPORT_CLAIM_FRAGMENTS: tuple[str, ...] = (
    "profitable",
    "winning strategy",
    "edge proven",
    "performance proven",
)


class GmoBacktestReportStatus(str, Enum):
    REPORT_SYNTHETIC_REFERENCE_ONLY = "REPORT_SYNTHETIC_REFERENCE_ONLY"
    REPORT_SYNTHETIC_SPREAD_INCLUDED = "REPORT_SYNTHETIC_SPREAD_INCLUDED"
    REPORT_BLOCKED_UNSAFE = "REPORT_BLOCKED_UNSAFE"


class GmoBacktestReportError(RuntimeError):
    """Raised when a report would carry a forbidden claim or unsafe value."""


@dataclass(frozen=True)
class BacktestReport:
    """Fixed report sections. Aggregates and safe labels only."""

    report_status: GmoBacktestReportStatus
    # 1. dataset summary
    dataset_symbol_safe_label: str
    dataset_timeframe_safe_label: str
    dataset_bar_count: int
    dataset_warmup_bars: int
    dataset_synthetic_fixture_only: bool
    # 2. split summary
    split_method_safe_label: str
    split_train_bars: int
    split_validation_bars: int
    split_oos_bars: int
    # 3. strategy configuration
    exit_policy_tp_profile: str
    exit_policy_sl_profile: str
    exit_policy_max_hold_profile: str
    exit_policy_candidate_only: bool
    # 4. signal distribution
    signal_distribution: tuple[tuple[str, int], ...]
    # 5. trade summary
    trade_count: int
    # 6. exit reason summary
    tp_exit_count: int
    sl_exit_count: int
    max_hold_exit_count: int
    opposite_signal_exit_count: int
    end_of_window_exit_count: int
    # 7. spread inclusion status
    spread_included: bool
    spread_excluded_is_reference_only: bool
    # 8. metrics summary
    metrics_status: str
    win_rate: float
    profit_factor: float
    expectancy: float
    # 9. drawdown summary
    max_drawdown: float
    max_consecutive_losses: int
    # 10. guard/block summary
    block_reason_distribution: tuple[tuple[str, int], ...]
    # 11. overfitting checks
    overfitting_status: str
    oos_status: str
    parameter_search_count: int
    # 12. limitations
    limitations_safe_label: str
    # 13. performance proof status (fixed)
    performance_proof_status: bool = False
    # 14. recommended next step
    recommended_next_step: str = "HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST"
    # fixed safety flags
    actual_post: bool = False
    broker_write: bool = False
    real_http: bool = False
    credential_read: bool = False
    env_read: bool = False
    synthetic_fixture_only: bool = True
    real_data_used: bool = False
    oos_evaluated: bool = False
    live_ready: bool = False
    operator_confirmation_required: bool = True

    def __bool__(self) -> bool:
        return False


def build_backtest_report(
    *,
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    run_result: BacktestRunResult,
    metrics: BacktestMetricsSummary,
    exit_policy: ExitPolicyCandidate,
    parameter_search_count: int = 0,
) -> BacktestReport:
    """Assemble the fixed-format report from safe aggregates only."""

    if metrics.oos_status is GmoOosStatus.OOS_EVALUATED:
        # OOS evaluation belongs to a future real-data step.
        raise GmoBacktestReportError(
            "OOS cannot be marked evaluated in the synthetic-only phase"
        )
    status = (
        GmoBacktestReportStatus.REPORT_SYNTHETIC_SPREAD_INCLUDED
        if run_result.spread_included
        else GmoBacktestReportStatus.REPORT_SYNTHETIC_REFERENCE_ONLY
    )
    return BacktestReport(
        report_status=status,
        dataset_symbol_safe_label=dataset.symbol_safe_label,
        dataset_timeframe_safe_label=dataset.timeframe_safe_label,
        dataset_bar_count=len(dataset.candles),
        dataset_warmup_bars=dataset.warmup_bars,
        dataset_synthetic_fixture_only=dataset.synthetic_fixture,
        split_method_safe_label=split.split_method_safe_label,
        split_train_bars=split.train_end - split.warmup_end,
        split_validation_bars=split.validation_end - split.train_end,
        split_oos_bars=split.oos_end - split.validation_end,
        exit_policy_tp_profile=exit_policy.take_profit_profile.value,
        exit_policy_sl_profile=exit_policy.stop_loss_profile.value,
        exit_policy_max_hold_profile=exit_policy.max_hold_profile.value,
        exit_policy_candidate_only=exit_policy.candidate_only,
        signal_distribution=run_result.signal_distribution,
        trade_count=metrics.trade_count,
        tp_exit_count=metrics.tp_exit_count,
        sl_exit_count=metrics.sl_exit_count,
        max_hold_exit_count=metrics.max_hold_exit_count,
        opposite_signal_exit_count=metrics.opposite_signal_exit_count,
        end_of_window_exit_count=metrics.end_of_window_exit_count,
        spread_included=run_result.spread_included,
        spread_excluded_is_reference_only=not run_result.spread_included,
        metrics_status=metrics.status.value,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        expectancy=metrics.expectancy,
        max_drawdown=metrics.max_drawdown,
        max_consecutive_losses=metrics.max_consecutive_losses,
        block_reason_distribution=run_result.block_reason_distribution,
        overfitting_status=metrics.overfitting_status.value,
        oos_status=metrics.oos_status.value,
        parameter_search_count=parameter_search_count,
        limitations_safe_label=(
            "SYNTHETIC_FIXTURE_ONLY_NOT_REAL_DATA_NOT_PERFORMANCE_PROOF"
        ),
    )


def render_backtest_report_safe_lines(report: BacktestReport) -> tuple[str, ...]:
    """Render the report as ``key: value`` lines (aggregates only)."""

    lines = [
        f"report_status: {report.report_status.value}",
        f"dataset_symbol: {report.dataset_symbol_safe_label}",
        f"dataset_timeframe: {report.dataset_timeframe_safe_label}",
        f"dataset_bar_count: {report.dataset_bar_count}",
        f"dataset_synthetic_fixture_only: {report.dataset_synthetic_fixture_only}",
        f"split_method: {report.split_method_safe_label}",
        f"split_train_bars: {report.split_train_bars}",
        f"split_validation_bars: {report.split_validation_bars}",
        f"split_oos_bars: {report.split_oos_bars}",
        f"exit_policy_tp_profile: {report.exit_policy_tp_profile}",
        f"exit_policy_sl_profile: {report.exit_policy_sl_profile}",
        f"exit_policy_max_hold_profile: {report.exit_policy_max_hold_profile}",
        f"exit_policy_candidate_only: {report.exit_policy_candidate_only}",
        f"signal_distribution: {dict(report.signal_distribution)}",
        f"trade_count: {report.trade_count}",
        f"tp_exit_count: {report.tp_exit_count}",
        f"sl_exit_count: {report.sl_exit_count}",
        f"max_hold_exit_count: {report.max_hold_exit_count}",
        f"opposite_signal_exit_count: {report.opposite_signal_exit_count}",
        f"end_of_window_exit_count: {report.end_of_window_exit_count}",
        f"spread_included: {report.spread_included}",
        f"metrics_status: {report.metrics_status}",
        f"win_rate: {report.win_rate:.4f}",
        f"profit_factor: {report.profit_factor:.4f}",
        f"expectancy: {report.expectancy:.6f}",
        f"max_drawdown: {report.max_drawdown:.6f}",
        f"max_consecutive_losses: {report.max_consecutive_losses}",
        f"block_reason_distribution: {dict(report.block_reason_distribution)}",
        f"overfitting_status: {report.overfitting_status}",
        f"oos_status: {report.oos_status}",
        f"parameter_search_count: {report.parameter_search_count}",
        f"limitations: {report.limitations_safe_label}",
        f"performance_proof_status: {report.performance_proof_status}",
        f"live_ready: {report.live_ready}",
        f"real_data_used: {report.real_data_used}",
        f"operator_confirmation_required: {report.operator_confirmation_required}",
        f"recommended_next_step: {report.recommended_next_step}",
    ]
    joined = "\n".join(lines).lower()
    for fragment in FORBIDDEN_REPORT_CLAIM_FRAGMENTS:
        if fragment in joined:
            raise GmoBacktestReportError(
                "report rendering contains a forbidden performance claim"
            )
    return tuple(lines)
