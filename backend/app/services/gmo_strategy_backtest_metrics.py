"""Backtest metrics pipeline (synthetic aggregates only, no-POST).

Computes the defined evaluation metrics over synthetic trade events. This
verifies the metric PIPELINE, not the strategy: every summary pins
``performance_proof_status = False``, the default overfitting status is
``OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA``, and OOS stays
``OOS_NOT_EVALUATED`` until a future real-data step. Evaluation is withheld
below the minimum trade count regardless of how good the numbers look.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    BacktestRunResult,
    BacktestTradeEvent,
)

MINIMUM_TRADE_COUNT_FOR_EVALUATION = 30


class GmoBacktestMetricsStatus(str, Enum):
    METRICS_COMPUTED_SYNTHETIC = "METRICS_COMPUTED_SYNTHETIC"
    EVALUATION_WITHHELD_INSUFFICIENT_TRADES = (
        "EVALUATION_WITHHELD_INSUFFICIENT_TRADES"
    )
    METRICS_BLOCKED_SPREAD_EXCLUDED = "METRICS_BLOCKED_SPREAD_EXCLUDED"


class GmoOverfittingStatus(str, Enum):
    OVERFITTING_GUARD_READY = "OVERFITTING_GUARD_READY"
    OVERFITTING_RISK_HIGH_DATA_INSUFFICIENT = (
        "OVERFITTING_RISK_HIGH_DATA_INSUFFICIENT"
    )
    OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA = (
        "OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA"
    )
    OVERFITTING_RISK_UNKNOWN_SINGLE_SAMPLE_REAL_DATA = (
        "OVERFITTING_RISK_UNKNOWN_SINGLE_SAMPLE_REAL_DATA"
    )


class GmoOosStatus(str, Enum):
    OOS_NOT_EVALUATED = "OOS_NOT_EVALUATED"
    OOS_EVALUATED = "OOS_EVALUATED"


@dataclass(frozen=True)
class BacktestMetricsSummary:
    """Aggregate synthetic metrics. Never a performance proof."""

    status: GmoBacktestMetricsStatus
    trade_count: int
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    expectancy: float
    max_drawdown: float
    max_consecutive_losses: int
    average_hold_duration_bars: float
    median_hold_duration_bars: float
    exposure_time_ratio: float
    spread_cost_ratio: float
    signal_count: int
    hold_rate: float
    unknown_blocked_rate: float
    guard_block_rate: float
    tp_exit_count: int
    sl_exit_count: int
    max_hold_exit_count: int
    opposite_signal_exit_count: int
    end_of_window_exit_count: int
    no_trade: bool
    spread_included: bool
    minimum_trade_count_required: int = MINIMUM_TRADE_COUNT_FOR_EVALUATION
    overfitting_status: GmoOverfittingStatus = (
        GmoOverfittingStatus.OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA
    )
    oos_status: GmoOosStatus = GmoOosStatus.OOS_NOT_EVALUATED
    performance_proof_status: bool = False
    real_data_used: bool = False
    synthetic_fixture_only: bool = True

    def __bool__(self) -> bool:
        return False


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _max_drawdown(pnls: list[float]) -> float:
    peak = 0.0
    cumulative = 0.0
    drawdown = 0.0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def _max_consecutive_losses(pnls: list[float]) -> int:
    worst = 0
    streak = 0
    for pnl in pnls:
        if pnl < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def _exit_count(
    trades: tuple[BacktestTradeEvent, ...], reason: BacktestExitReason
) -> int:
    return sum(1 for trade in trades if trade.exit_reason_safe_label is reason)


def compute_backtest_metrics(
    run_result: BacktestRunResult,
    *,
    real_data_single_sample: bool = False,
) -> BacktestMetricsSummary:
    """Compute the metric pipeline over one run result.

    ``real_data_single_sample=True`` only refines the (still conservative)
    overfitting label for a validated real-data run over a single sample; it
    never turns any result into a performance proof.
    """

    trades = run_result.trades
    pnls = [trade.synthetic_pnl_value for trade in trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    holds = [float(trade.hold_duration_bars) for trade in trades]
    signal_counts = dict(run_result.signal_distribution)
    total_signals = sum(signal_counts.values())
    gross_abs = sum(abs(pnl) for pnl in pnls)
    total_spread_cost = sum(
        trade.synthetic_spread_cost_value for trade in trades
    )
    block_counts = dict(run_result.block_reason_distribution)
    guard_blocks = block_counts.get("BLOCK_GUARD_NOT_PASS", 0)

    if not run_result.spread_included:
        # A spread-excluded run can never be evaluated as official.
        status = GmoBacktestMetricsStatus.METRICS_BLOCKED_SPREAD_EXCLUDED
    elif len(trades) < MINIMUM_TRADE_COUNT_FOR_EVALUATION:
        status = (
            GmoBacktestMetricsStatus.EVALUATION_WITHHELD_INSUFFICIENT_TRADES
        )
    else:
        status = GmoBacktestMetricsStatus.METRICS_COMPUTED_SYNTHETIC

    overfitting_status = (
        GmoOverfittingStatus.OVERFITTING_RISK_UNKNOWN_SINGLE_SAMPLE_REAL_DATA
        if real_data_single_sample
        else GmoOverfittingStatus.OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA
    )
    return BacktestMetricsSummary(
        status=status,
        overfitting_status=overfitting_status,
        trade_count=len(trades),
        win_rate=(len(wins) / len(trades)) if trades else 0.0,
        profit_factor=(
            (sum(wins) / abs(sum(losses))) if losses and wins else 0.0
        ),
        average_win=(sum(wins) / len(wins)) if wins else 0.0,
        average_loss=(sum(losses) / len(losses)) if losses else 0.0,
        expectancy=(sum(pnls) / len(pnls)) if pnls else 0.0,
        max_drawdown=_max_drawdown(pnls),
        max_consecutive_losses=_max_consecutive_losses(pnls),
        average_hold_duration_bars=(sum(holds) / len(holds)) if holds else 0.0,
        median_hold_duration_bars=_median(holds),
        exposure_time_ratio=(
            sum(holds) / run_result.bars_processed
            if run_result.bars_processed
            else 0.0
        ),
        spread_cost_ratio=(
            total_spread_cost / gross_abs if gross_abs else 0.0
        ),
        signal_count=total_signals,
        hold_rate=(
            signal_counts.get("AUTO_PREVIEW_SIGNAL_HOLD", 0) / total_signals
            if total_signals
            else 0.0
        ),
        unknown_blocked_rate=(
            signal_counts.get("AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED", 0)
            / total_signals
            if total_signals
            else 0.0
        ),
        guard_block_rate=(
            guard_blocks / total_signals if total_signals else 0.0
        ),
        tp_exit_count=_exit_count(trades, BacktestExitReason.EXIT_TAKE_PROFIT),
        sl_exit_count=_exit_count(trades, BacktestExitReason.EXIT_STOP_LOSS),
        max_hold_exit_count=_exit_count(trades, BacktestExitReason.EXIT_MAX_HOLD),
        opposite_signal_exit_count=_exit_count(
            trades, BacktestExitReason.EXIT_OPPOSITE_SIGNAL
        ),
        end_of_window_exit_count=_exit_count(
            trades, BacktestExitReason.EXIT_END_OF_WINDOW
        ),
        no_trade=not trades,
        spread_included=run_result.spread_included,
    )
