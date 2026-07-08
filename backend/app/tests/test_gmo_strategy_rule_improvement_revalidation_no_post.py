"""No-POST tests for the strategy rule revalidation module (synthetic only)."""

from __future__ import annotations

import inspect

import pytest

from app.services import gmo_strategy_rule_revalidation as module
from app.services.gmo_strategy_backtest_dataset import (
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
    split_backtest_dataset_chronologically,
)
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    build_candidate_exit_policy_profiles,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_rule_revalidation import (
    BASELINE_CANDIDATE_NAME,
    REVALIDATION_RULE_VERSION,
    CandidateComparison,
    CandidateSplitMetricsSafe,
    FrozenCandidate,
    OosResultCategory,
    RevalidationCandidate,
    RevalidationCandidateError,
    RevalidationSelectionStatus,
    build_default_revalidation_candidates,
    build_split_datasets,
    compare_candidates_train_validation,
    evaluate_frozen_candidate_on_oos_once,
    freeze_selected_candidate,
)


def _oscillating_dataset(*, cycles: int = 30, run_len: int = 8) -> BacktestDataset:
    """Deterministic up/down oscillation to create multiple trend flips."""

    candles = []
    spreads = []
    sessions = []
    value = 100.0
    index = 0
    for cycle in range(cycles):
        rising = cycle % 2 == 0
        for _ in range(run_len):
            delta = 0.06 if rising else -0.06
            open_v = value
            close_v = value + delta
            high_v = max(open_v, close_v) + 0.02
            low_v = min(open_v, close_v) - 0.02
            candles.append(
                BacktestCandleRecord(
                    timestamp=index,
                    symbol_safe_label="USD_JPY",
                    timeframe_safe_label="M5",
                    open_value=open_v,
                    high_value=high_v,
                    low_value=low_v,
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


def _policy():
    return build_candidate_exit_policy_profiles()["CANDIDATE_MEDIUM_BALANCED"]


class TestCandidate:
    def test_default_candidates_are_baseline_plus_families(self) -> None:
        candidates = build_default_revalidation_candidates()
        names = [c.candidate_name for c in candidates]
        assert names[0] == BASELINE_CANDIDATE_NAME
        assert len(candidates) == 5
        for candidate in candidates:
            assert candidate.candidate_only is True
            assert candidate.officially_adopted is False
            assert not candidate

    def test_official_adoption_is_refused(self) -> None:
        with pytest.raises(RevalidationCandidateError):
            RevalidationCandidate(
                candidate_name="X",
                entry_momentum_strict=False,
                opposite_signal_debounce_bars=1,
                exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
                officially_adopted=True,
            )

    def test_bad_debounce_is_refused(self) -> None:
        with pytest.raises(RevalidationCandidateError):
            RevalidationCandidate(
                candidate_name="X",
                entry_momentum_strict=False,
                opposite_signal_debounce_bars=0,
                exit_policy_key="CANDIDATE_MEDIUM_BALANCED",
            )

    def test_unknown_exit_policy_key_is_refused(self) -> None:
        with pytest.raises(RevalidationCandidateError):
            RevalidationCandidate(
                candidate_name="X",
                entry_momentum_strict=False,
                opposite_signal_debounce_bars=1,
                exit_policy_key="NOPE",
            )


class TestEngineKnobs:
    def test_strict_entry_never_increases_trade_count(self) -> None:
        dataset = _oscillating_dataset()
        loose = run_synthetic_backtest(
            dataset=dataset, exit_policy=_policy(), entry_momentum_strict=False
        )
        strict = run_synthetic_backtest(
            dataset=dataset, exit_policy=_policy(), entry_momentum_strict=True
        )
        assert len(strict.trades) <= len(loose.trades)

    def test_debounce_never_increases_opposite_exits(self) -> None:
        dataset = _oscillating_dataset()

        def _opp(count: int) -> int:
            result = run_synthetic_backtest(
                dataset=dataset,
                exit_policy=_policy(),
                opposite_signal_debounce_bars=count,
            )
            return sum(
                1
                for trade in result.trades
                if trade.exit_reason_safe_label
                is BacktestExitReason.EXIT_OPPOSITE_SIGNAL
            )

        assert _opp(3) <= _opp(1)

    def test_default_knobs_reproduce_baseline_exactly(self) -> None:
        dataset = _oscillating_dataset()
        a = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        b = run_synthetic_backtest(
            dataset=dataset,
            exit_policy=_policy(),
            entry_momentum_strict=False,
            opposite_signal_debounce_bars=1,
        )
        assert a == b

    def test_real_data_flags_default_false_on_synthetic(self) -> None:
        dataset = _oscillating_dataset()
        result = run_synthetic_backtest(dataset=dataset, exit_policy=_policy())
        assert result.real_data_used is False
        assert result.synthetic_fixture_only is True


class TestSplitDatasets:
    def test_split_slices_preserve_flags_and_cover_ranges(self) -> None:
        dataset = _oscillating_dataset()
        usable = len(dataset.candles) - dataset.warmup_bars
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
        )
        splits = build_split_datasets(dataset, split)
        assert set(splits) == {"TRAIN", "VALIDATION", "OOS"}
        for sub in splits.values():
            assert sub.symbol_safe_label == "USD_JPY"
            assert sub.synthetic_fixture is True
            assert sub.validated_operator_local_csv is False
            assert len(sub.candles) > sub.warmup_bars


class TestComparison:
    def _split(self, dataset):
        usable = len(dataset.candles) - dataset.warmup_bars
        return split_backtest_dataset_chronologically(
            dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
        )

    def test_comparison_is_deterministic_and_train_validation_only(self) -> None:
        dataset = _oscillating_dataset()
        split = self._split(dataset)
        first = compare_candidates_train_validation(dataset, split)
        second = compare_candidates_train_validation(dataset, split)
        assert first == second
        assert first.selected_using == "TRAIN_VALIDATION_ONLY"
        assert first.oos_not_seen_before_freeze is True
        assert first.parameter_search_count == 4
        assert first.performance_proof_status is False
        assert first.live_ready is False
        assert not first

    def test_monotonic_dataset_selects_no_candidate(self) -> None:
        # Too few trades on each split -> every candidate ineligible.
        from app.services.gmo_strategy_backtest_dataset import (
            build_synthetic_trend_dataset,
        )

        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=90
        )
        split = self._split(dataset)
        comparison = compare_candidates_train_validation(dataset, split)
        assert comparison.status is (
            RevalidationSelectionStatus.NO_CANDIDATE_SELECTED
        )
        assert comparison.selected_candidate_name is None

    def test_freeze_returns_none_when_no_candidate(self) -> None:
        dataset = _oscillating_dataset()
        split = self._split(dataset)
        comparison = compare_candidates_train_validation(dataset, split)
        if comparison.status is (
            RevalidationSelectionStatus.NO_CANDIDATE_SELECTED
        ):
            assert freeze_selected_candidate(comparison) is None


class TestFreezeAndOos:
    def _selected_comparison(self) -> CandidateComparison:
        # Construct a CANDIDATE_SELECTED comparison for a real candidate name.
        name = "CANDIDATE_B_OPPOSITE_SIGNAL_DEBOUNCE"
        view = CandidateSplitMetricsSafe(
            candidate_name=name,
            split_label="VALIDATION",
            trade_count=120,
            win_rate_rounded=0.4,
            profit_factor_rounded=1.2,
            expectancy_sign="POSITIVE",
            max_consecutive_losses=5,
            spread_cost_ratio_sign="POSITIVE",
            hold_rate_rounded=0.5,
            unknown_blocked_rate_rounded=0.1,
        )
        return CandidateComparison(
            status=RevalidationSelectionStatus.CANDIDATE_SELECTED,
            selected_candidate_name=name,
            selection_reason_safe_category="TEST_SELECTION",
            baseline_validation_profit_factor=0.9,
            train_metrics=(),
            validation_metrics=(view,),
            parameter_search_count=4,
        )

    def test_freeze_records_train_validation_only_and_no_oos_seen(self) -> None:
        frozen = freeze_selected_candidate(self._selected_comparison())
        assert frozen is not None
        assert frozen.rule_version == REVALIDATION_RULE_VERSION
        assert frozen.selected_using == "TRAIN_VALIDATION_ONLY"
        assert frozen.oos_not_seen_before_freeze is True
        assert frozen.performance_proof_status is False
        assert frozen.live_ready is False
        assert frozen.candidate.candidate_name == (
            "CANDIDATE_B_OPPOSITE_SIGNAL_DEBOUNCE"
        )
        assert not frozen

    def test_oos_not_run_when_no_frozen_candidate(self) -> None:
        dataset = _oscillating_dataset()
        usable = len(dataset.candles) - dataset.warmup_bars
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
        )
        oos = evaluate_frozen_candidate_on_oos_once(dataset, split, None)
        assert oos.result_category is (
            OosResultCategory.OOS_NOT_RUN_NO_CANDIDATE
        )
        assert oos.evaluated_once is False
        assert oos.retuned_after_oos is False

    def test_oos_runs_once_for_frozen_candidate(self) -> None:
        dataset = _oscillating_dataset()
        usable = len(dataset.candles) - dataset.warmup_bars
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
        )
        frozen = FrozenCandidate(
            candidate=build_default_revalidation_candidates()[2],
            rule_version=REVALIDATION_RULE_VERSION,
            selection_reason_safe_category="TEST",
            validation_profit_factor=1.1,
        )
        oos = evaluate_frozen_candidate_on_oos_once(dataset, split, frozen)
        assert oos.evaluated_once is True
        assert oos.retuned_after_oos is False
        assert oos.performance_proof_status is False
        assert oos.live_ready is False
        assert oos.result_category in {
            OosResultCategory.OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW,
            OosResultCategory.OOS_DEGRADED_REJECT_CANDIDATE,
            OosResultCategory.OOS_INSUFFICIENT_TRADES,
        }

    def test_oos_insufficient_trades_on_tiny_dataset(self) -> None:
        from app.services.gmo_strategy_backtest_dataset import (
            build_synthetic_trend_dataset,
        )

        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=90
        )
        usable = len(dataset.candles) - dataset.warmup_bars
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
        )
        frozen = FrozenCandidate(
            candidate=build_default_revalidation_candidates()[0],
            rule_version=REVALIDATION_RULE_VERSION,
            selection_reason_safe_category="TEST",
            validation_profit_factor=1.0,
        )
        oos = evaluate_frozen_candidate_on_oos_once(dataset, split, frozen)
        assert oos.result_category is OosResultCategory.OOS_INSUFFICIENT_TRADES


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
        assert "profitable" not in source
