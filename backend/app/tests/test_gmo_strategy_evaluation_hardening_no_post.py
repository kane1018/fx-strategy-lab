"""No-POST tests for the strategy evaluation hardening module (synthetic)."""

from __future__ import annotations

import inspect

from app.services import gmo_strategy_evaluation_hardening as module
from app.services.gmo_strategy_backtest_dataset import (
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
)
from app.services.gmo_strategy_evaluation_hardening import (
    RobustnessVerdictCategory,
    build_walk_forward_windows,
    evaluate_candidate_robustness,
    run_random_entry_backtest,
    run_walk_forward_for_candidate,
)
from app.services.gmo_strategy_redesign import (
    EXIT_RIDE,
    EXIT_TIGHT,
    RedesignCandidate,
    RedesignEntryFamily,
)


def _oscillating(*, cycles: int = 60, run_len: int = 10) -> BacktestDataset:
    candles, spreads, sessions = [], [], []
    value = 100.0
    index = 0
    for cycle in range(cycles):
        rising = cycle % 2 == 0
        for _ in range(run_len):
            delta = 0.06 if rising else -0.06
            open_v, close_v = value, value + delta
            candles.append(
                BacktestCandleRecord(
                    timestamp=index,
                    symbol_safe_label="USD_JPY",
                    timeframe_safe_label="M5",
                    open_value=open_v,
                    high_value=max(open_v, close_v) + 0.02,
                    low_value=min(open_v, close_v) - 0.02,
                    close_value=close_v,
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
            value = close_v
            index += 1
    return BacktestDataset(
        symbol_safe_label="USD_JPY",
        timeframe_safe_label="M5",
        candles=tuple(candles),
        spreads=tuple(spreads),
        sessions=tuple(sessions),
    )


def _candidate() -> RedesignCandidate:
    return RedesignCandidate(
        candidate_name="T",
        family=RedesignEntryFamily.BREAKOUT,
        exit_config=EXIT_RIDE,
    )


class TestWalkForwardWindows:
    def test_windows_are_chronological_and_non_overlapping(self) -> None:
        windows = build_walk_forward_windows(
            1000, window_bars=200, lead=40, max_windows=12
        )
        assert len(windows) == 4  # [40,240),[240,440),[440,640),[640,840)
        previous_end = None
        for w in windows:
            assert w.slice_start == w.traded_start - 40
            assert w.traded_end - w.traded_start == 200
            if previous_end is not None:
                assert w.traded_start == previous_end
            previous_end = w.traded_end

    def test_max_windows_is_respected(self) -> None:
        windows = build_walk_forward_windows(
            100000, window_bars=1000, lead=40, max_windows=5
        )
        assert len(windows) == 5

    def test_too_small_dataset_yields_no_windows(self) -> None:
        assert build_walk_forward_windows(30, window_bars=200, lead=40) == ()


class TestCostSensitivity:
    def test_higher_cost_never_increases_total_pnl(self) -> None:
        from app.services.gmo_strategy_redesign import run_redesign_backtest

        dataset = _oscillating()
        candidate = _candidate()
        low = run_redesign_backtest(
            dataset=dataset, candidate=candidate, spread_cost_multiplier=1.0
        )
        high = run_redesign_backtest(
            dataset=dataset, candidate=candidate, spread_cost_multiplier=2.0
        )
        # Same trades (cost never changes decisions), so higher cost strictly
        # lowers total PnL whenever any trade paid a positive spread.
        assert len(low.trades) == len(high.trades)
        if low.trades:
            assert sum(t.synthetic_pnl_value for t in high.trades) < sum(
                t.synthetic_pnl_value for t in low.trades
            )


class TestRandomBenchmark:
    def test_random_entry_is_deterministic_for_a_seed(self) -> None:
        dataset = _oscillating()
        a = run_random_entry_backtest(
            dataset=dataset, exit_config=EXIT_TIGHT, seed=123
        )
        b = run_random_entry_backtest(
            dataset=dataset, exit_config=EXIT_TIGHT, seed=123
        )
        assert a == b
        assert a.real_data_used is False
        assert not a

    def test_random_entry_uses_random_label(self) -> None:
        dataset = _oscillating()
        result = run_random_entry_backtest(
            dataset=dataset, exit_config=EXIT_RIDE, seed=7
        )
        for trade in result.trades:
            assert trade.entry_signal_safe_label == "RANDOM_ENTRY"


class TestWalkForwardSummary:
    def test_summary_is_deterministic_and_bounded(self) -> None:
        dataset = _oscillating()
        windows = build_walk_forward_windows(
            len(dataset.candles), window_bars=150, lead=40, max_windows=6
        )
        a = run_walk_forward_for_candidate(dataset, _candidate(), windows)
        b = run_walk_forward_for_candidate(dataset, _candidate(), windows)
        assert a == b
        assert a.window_count == len(windows)
        assert 0.0 <= a.pass_rate_rounded <= 1.0
        assert a.passed_window_count <= a.qualified_window_count <= a.window_count
        assert a.performance_proof_status is False
        assert a.live_ready is False
        assert not a


class TestRobustnessReport:
    def test_report_is_deterministic_and_never_a_proof(self) -> None:
        dataset = _oscillating()
        first = evaluate_candidate_robustness(
            dataset, window_bars=150, max_windows=8
        )
        second = evaluate_candidate_robustness(
            dataset, window_bars=150, max_windows=8
        )
        assert first == second
        assert first.performance_proof_status is False
        assert first.live_ready is False
        assert first.overall_conclusion_safe_label in {
            "ROBUST_CANDIDATE_FOUND_PAPER_FORWARD_NEXT",
            "NO_ROBUST_EDGE_ACROSS_WALK_FORWARD_AND_COST_STRESS",
        }
        assert len(first.verdicts) == 8  # 4 families x 2 exit configs
        for verdict in first.verdicts:
            assert verdict.verdict in RobustnessVerdictCategory
            assert verdict.performance_proof_status is False
            assert not verdict
        assert not first

    def test_insufficient_windows_when_dataset_is_short(self) -> None:
        dataset = _oscillating(cycles=8, run_len=10)  # 80 bars
        report = evaluate_candidate_robustness(
            dataset, window_bars=200, max_windows=8
        )
        # No window fits -> every candidate is INSUFFICIENT_WINDOWS.
        assert report.window_count == 0
        assert all(
            v.verdict is RobustnessVerdictCategory.INSUFFICIENT_WINDOWS
            for v in report.verdicts
        )
        assert report.any_robust_candidate is False


class TestModuleIsolation:
    def test_module_has_no_network_broker_env_or_random_module(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "requests" not in source
        assert "urllib" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "/private/v1" not in source
        assert "import random" not in source
        assert "random.random" not in source
        assert "random.randint" not in source
        assert "profitable" not in source
