"""No-POST tests for the backtest metrics pipeline."""

from __future__ import annotations

import inspect

from app.services import gmo_strategy_backtest_metrics as module
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    BacktestRunResult,
    BacktestTradeEvent,
    GmoBacktestRunStatus,
)
from app.services.gmo_strategy_backtest_metrics import (
    MINIMUM_TRADE_COUNT_FOR_EVALUATION,
    GmoBacktestMetricsStatus,
    GmoOosStatus,
    GmoOverfittingStatus,
    compute_backtest_metrics,
)


def _trade(
    index: int,
    pnl: float,
    *,
    exit_reason: BacktestExitReason = BacktestExitReason.EXIT_TAKE_PROFIT,
    hold: int = 4,
    spread_cost: float = 0.002,
) -> BacktestTradeEvent:
    return BacktestTradeEvent(
        trade_index=index,
        side_safe_label="PAPER_LONG",
        entry_signal_safe_label="AUTO_PREVIEW_SIGNAL_BUY",
        exit_reason_safe_label=exit_reason,
        hold_duration_bars=hold,
        synthetic_pnl_value=pnl,
        synthetic_spread_cost_value=spread_cost,
        spread_included=True,
    )


def _run_result(
    trades: tuple[BacktestTradeEvent, ...],
    *,
    spread_included: bool = True,
) -> BacktestRunResult:
    return BacktestRunResult(
        status=GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED,
        blocked_reasons=(),
        bars_processed=100,
        trades=trades,
        signal_distribution=(
            ("AUTO_PREVIEW_SIGNAL_BUY", 10),
            ("AUTO_PREVIEW_SIGNAL_HOLD", 20),
            ("AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED", 70),
        ),
        category_distribution=(),
        block_reason_distribution=(("BLOCK_GUARD_NOT_PASS", 5),),
        spread_included=spread_included,
    )


class TestMetricsPipeline:
    def test_metrics_computed_over_sufficient_synthetic_trades(self) -> None:
        trades = tuple(
            _trade(i, 0.1 if i % 3 else -0.05)
            for i in range(MINIMUM_TRADE_COUNT_FOR_EVALUATION)
        )
        metrics = compute_backtest_metrics(_run_result(trades))
        assert metrics.status is (
            GmoBacktestMetricsStatus.METRICS_COMPUTED_SYNTHETIC
        )
        assert metrics.trade_count == MINIMUM_TRADE_COUNT_FOR_EVALUATION
        assert 0.0 < metrics.win_rate < 1.0
        assert metrics.profit_factor > 0.0
        assert metrics.average_win > 0.0
        assert metrics.average_loss < 0.0
        assert metrics.max_drawdown >= 0.0
        assert metrics.max_consecutive_losses >= 1
        assert metrics.average_hold_duration_bars == 4.0
        assert metrics.median_hold_duration_bars == 4.0
        assert metrics.exposure_time_ratio > 0.0
        assert metrics.spread_cost_ratio > 0.0

    def test_insufficient_trades_withholds_evaluation(self) -> None:
        trades = tuple(_trade(i, 1.0) for i in range(3))
        metrics = compute_backtest_metrics(_run_result(trades))
        assert metrics.status is (
            GmoBacktestMetricsStatus.EVALUATION_WITHHELD_INSUFFICIENT_TRADES
        )

    def test_spread_excluded_run_is_blocked_for_official_metrics(self) -> None:
        trades = tuple(
            _trade(i, 1.0, spread_cost=0.0)
            for i in range(MINIMUM_TRADE_COUNT_FOR_EVALUATION)
        )
        metrics = compute_backtest_metrics(
            _run_result(trades, spread_included=False)
        )
        assert metrics.status is (
            GmoBacktestMetricsStatus.METRICS_BLOCKED_SPREAD_EXCLUDED
        )
        assert metrics.spread_included is False

    def test_signal_rates_are_computed_from_distributions(self) -> None:
        metrics = compute_backtest_metrics(_run_result(()))
        assert metrics.signal_count == 100
        assert metrics.hold_rate == 0.2
        assert metrics.unknown_blocked_rate == 0.7
        assert metrics.guard_block_rate == 0.05
        assert metrics.no_trade is True

    def test_exit_reason_counts(self) -> None:
        trades = (
            _trade(0, 0.1),
            _trade(1, -0.1, exit_reason=BacktestExitReason.EXIT_STOP_LOSS),
            _trade(2, 0.0, exit_reason=BacktestExitReason.EXIT_MAX_HOLD),
            _trade(3, 0.0, exit_reason=BacktestExitReason.EXIT_END_OF_WINDOW),
        )
        metrics = compute_backtest_metrics(_run_result(trades))
        assert metrics.tp_exit_count == 1
        assert metrics.sl_exit_count == 1
        assert metrics.max_hold_exit_count == 1
        assert metrics.end_of_window_exit_count == 1

    def test_defaults_pin_unproven_status(self) -> None:
        metrics = compute_backtest_metrics(_run_result(()))
        assert metrics.performance_proof_status is False
        assert metrics.real_data_used is False
        assert metrics.synthetic_fixture_only is True
        assert metrics.overfitting_status is (
            GmoOverfittingStatus.OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA
        )
        assert metrics.oos_status is GmoOosStatus.OOS_NOT_EVALUATED
        assert not metrics


class TestModuleIsolation:
    def test_module_has_no_network_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "requests" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "/private/v1" not in source
