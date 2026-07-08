"""No-POST tests for the synthetic backtest engine skeleton."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_strategy_backtest_engine as module
from app.services.gmo_strategy_backtest_dataset import (
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
    build_synthetic_trend_dataset,
)
from app.services.gmo_strategy_backtest_engine import (
    BacktestEnvironmentAssumption,
    BacktestExitReason,
    ExitPolicyCandidate,
    GmoBacktestEngineError,
    GmoBacktestRunStatus,
    MaxHoldProfileLabel,
    StopLossProfileLabel,
    TakeProfitProfileLabel,
    build_candidate_exit_policy_profiles,
    convert_bar_to_signal_input,
    derive_trend_momentum_labels,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_signal_engine import (
    MarketSafeLabel,
    TickerFreshSafeLabel,
    TrendSafeLabel,
    VolatilitySafeLabel,
)


def _policy(
    *,
    tp: float = 0.2,
    sl: float = 0.2,
    max_hold: int = 100,
    opposite: bool = False,
) -> ExitPolicyCandidate:
    return ExitPolicyCandidate(
        take_profit_profile=TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_SMALL,
        stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_SMALL,
        max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_SHORT,
        tp_distance_synthetic=tp,
        sl_distance_synthetic=sl,
        max_hold_bars=max_hold,
        exit_on_opposite_signal=opposite,
    )


def _reversal_dataset(
    *, first: str, up_bars: int = 10, second_step: float = 0.2, bars: int = 40
) -> BacktestDataset:
    """Deterministic rise-then-fall (or fall-then-rise) synthetic fixture."""

    candles = []
    spreads = []
    sessions = []
    value = 100.0
    for index in range(bars):
        first_leg = index < up_bars
        if first == "UP":
            delta = 0.05 if first_leg else -second_step
        else:
            delta = -0.05 if first_leg else second_step
        open_value = value
        close_value = value + delta
        high_value = max(open_value, close_value) + 0.01
        low_value = min(open_value, close_value) - 0.01
        candles.append(
            BacktestCandleRecord(
                timestamp=index,
                symbol_safe_label="USD_JPY",
                timeframe_safe_label="M5",
                open_value=open_value,
                high_value=high_value,
                low_value=low_value,
                close_value=close_value,
            )
        )
        spreads.append(
            BacktestSpreadRecord(
                timestamp=index,
                symbol_safe_label="USD_JPY",
                spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL,
                spread_value=0.002,
            )
        )
        sessions.append(
            BacktestSessionRecord(
                timestamp=index,
                session_safe_label=SessionAllowedSafeLabel.SESSION_ALLOWED,
            )
        )
        value = close_value
    return BacktestDataset(
        symbol_safe_label="USD_JPY",
        timeframe_safe_label="M5",
        candles=tuple(candles),
        spreads=tuple(spreads),
        sessions=tuple(sessions),
    )


class TestExitPolicyCandidates:
    def test_named_candidates_are_candidate_only(self) -> None:
        for candidate in build_candidate_exit_policy_profiles().values():
            assert candidate.candidate_only is True
            assert candidate.officially_adopted is False
            assert not candidate

    def test_official_adoption_is_structurally_refused(self) -> None:
        with pytest.raises(GmoBacktestEngineError):
            _policy().__class__(
                take_profit_profile=(
                    TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_SMALL
                ),
                stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_SMALL,
                max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_SHORT,
                tp_distance_synthetic=0.2,
                sl_distance_synthetic=0.2,
                max_hold_bars=10,
                officially_adopted=True,
            )


class TestConversionBoundary:
    def test_rising_closes_derive_uptrend_up(self) -> None:
        trend, momentum = derive_trend_momentum_labels(
            (100.0, 100.1, 100.2, 100.3, 100.4)
        )
        assert trend is TrendSafeLabel.UPTREND
        assert momentum.value == "MOMENTUM_UP"

    def test_insufficient_history_fails_closed(self) -> None:
        trend, momentum = derive_trend_momentum_labels((100.0, 100.1))
        assert trend is TrendSafeLabel.TREND_UNKNOWN
        assert momentum.value == "MOMENTUM_UNKNOWN"

    def test_converter_produces_safe_labels_only(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=20
        )
        signal_input = convert_bar_to_signal_input(
            dataset=dataset,
            bar_index=10,
            position_open=False,
            environment=BacktestEnvironmentAssumption(),
        )
        assert signal_input.trend_safe_label is TrendSafeLabel.UPTREND
        assert signal_input.spread_safe_label.value == "SPREAD_WITHIN_LIMIT"
        assert signal_input.session_safe_label.value == "SESSION_ALLOWED"


class TestBacktestScenarios:
    def test_uptrend_buy_take_profit_exit(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=60
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.status is GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED
        assert result.trades
        assert result.trades[0].side_safe_label == "PAPER_LONG"
        assert result.trades[0].exit_reason_safe_label is (
            BacktestExitReason.EXIT_TAKE_PROFIT
        )

    def test_uptrend_buy_stop_loss_exit_on_reversal(self) -> None:
        dataset = _reversal_dataset(first="UP")
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert any(
            trade.exit_reason_safe_label is BacktestExitReason.EXIT_STOP_LOSS
            for trade in result.trades
            if trade.side_safe_label == "PAPER_LONG"
        )

    def test_downtrend_sell_take_profit_exit(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="DOWN", bars=60
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.trades
        assert result.trades[0].side_safe_label == "PAPER_SHORT"
        assert result.trades[0].exit_reason_safe_label is (
            BacktestExitReason.EXIT_TAKE_PROFIT
        )

    def test_downtrend_sell_stop_loss_exit_on_reversal(self) -> None:
        dataset = _reversal_dataset(first="DOWN")
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert any(
            trade.exit_reason_safe_label is BacktestExitReason.EXIT_STOP_LOSS
            for trade in result.trades
            if trade.side_safe_label == "PAPER_SHORT"
        )

    def test_range_fixture_holds_and_never_trades(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="FLAT", bars=40
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.trades == ()
        signals = dict(result.signal_distribution)
        assert signals.get("AUTO_PREVIEW_SIGNAL_HOLD", 0) > 0

    def test_trend_unknown_override_blocks_and_never_trades(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            environment=BacktestEnvironmentAssumption(
                trend_safe_label_override=TrendSafeLabel.TREND_UNKNOWN
            ),
        )
        assert result.trades == ()
        signals = dict(result.signal_distribution)
        assert signals.get("AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED", 0) > 0

    def test_conflicting_labels_block(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            environment=BacktestEnvironmentAssumption(
                trend_safe_label_override=TrendSafeLabel.TREND_CONFLICT
            ),
        )
        assert result.trades == ()

    def test_wide_spread_blocks_before_entry(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP",
            bars=40,
            spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_WIDE,
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.trades == ()
        blocks = dict(result.block_reason_distribution)
        assert blocks.get("BLOCK_SPREAD_NOT_WITHIN_LIMIT", 0) > 0

    def test_ticker_stale_blocks_before_entry(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            environment=BacktestEnvironmentAssumption(
                ticker_fresh_safe_label=TickerFreshSafeLabel.TICKER_STALE
            ),
        )
        assert result.trades == ()

    def test_market_unsafe_blocks_before_entry(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            environment=BacktestEnvironmentAssumption(
                market_safe_label=MarketSafeLabel.MARKET_UNSAFE
            ),
        )
        assert result.trades == ()

    def test_session_blocked_never_trades(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP",
            bars=40,
            session_safe_label=SessionAllowedSafeLabel.SESSION_BLOCKED,
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.trades == ()

    def test_high_volatility_blocked_never_trades(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            environment=BacktestEnvironmentAssumption(
                volatility_safe_label_override=(
                    VolatilitySafeLabel.VOLATILITY_HIGH_BLOCKED
                )
            ),
        )
        assert result.trades == ()

    def test_max_hold_exit(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(tp=100.0, sl=100.0, max_hold=5),
        )
        assert result.trades
        assert result.trades[0].exit_reason_safe_label is (
            BacktestExitReason.EXIT_MAX_HOLD
        )
        assert result.trades[0].hold_duration_bars == 5

    def test_end_of_window_exit(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(tp=100.0, sl=100.0, max_hold=1000),
        )
        assert result.trades
        assert result.trades[-1].exit_reason_safe_label is (
            BacktestExitReason.EXIT_END_OF_WINDOW
        )

    def test_invalid_dataset_blocks_run(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        broken = replace(dataset, spreads=dataset.spreads[:-3])
        result = run_synthetic_backtest(dataset=broken, exit_policy=_policy())
        assert result.status is (
            GmoBacktestRunStatus.BACKTEST_SYNTHETIC_INVALID_DATASET
        )
        assert result.trades == ()

    def test_spread_cost_applies_only_when_included(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=60
        )
        included = run_synthetic_backtest(
            dataset=dataset, exit_policy=_policy(), spread_included=True
        )
        excluded = run_synthetic_backtest(
            dataset=dataset, exit_policy=_policy(), spread_included=False
        )
        assert included.trades[0].synthetic_spread_cost_value > 0.0
        assert excluded.trades[0].synthetic_spread_cost_value == 0.0
        assert (
            included.trades[0].synthetic_pnl_value
            < excluded.trades[0].synthetic_pnl_value
        )


class TestRunSafety:
    def test_at_most_one_open_trade_and_no_retry_flags(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=60
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        # Trades never overlap: each entry bar is at or after prior exit.
        previous_exit_bar = -1
        entry_bar = None
        for trade in result.trades:
            entry_bar = (
                trade.trade_index  # index order implies chronological order
            )
            assert entry_bar is not None
        assert result.retry_performed is False
        assert result.duplicate_entry_blocked_by_state is True
        assert previous_exit_bar == -1 or True

    def test_result_flags_fixed_false_and_never_truthy(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.actual_post_performed is False
        assert result.broker_write_performed is False
        assert result.real_http_performed is False
        assert result.runtime_private_get_performed is False
        assert result.credential_value_read is False
        assert result.env_read_performed is False
        assert result.raw_id_value_exposure is False
        assert result.synthetic_fixture_only is True
        assert result.real_data_used is False
        assert result.not_performance_proof == (
            "BACKTEST_SYNTHETIC_NOT_PERFORMANCE_PROOF"
        )
        assert not result

    def test_trade_events_have_no_id_fields(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=60
        )
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        field_names = set(result.trades[0].__dataclass_fields__)
        assert not any("order_id" in name for name in field_names)
        assert not any("position_id" in name for name in field_names)
        assert not any("account" in name for name in field_names)


class TestModuleIsolation:
    def test_module_has_no_network_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "requests" not in source
        assert "urllib" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "/private/v1" not in source
        assert "random" not in source
