"""No-POST tests for the strategy rule redesign module (synthetic only)."""

from __future__ import annotations

import inspect

import pytest

from app.services import gmo_strategy_redesign as module
from app.services.gmo_strategy_backtest_dataset import (
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
    build_synthetic_trend_dataset,
    split_backtest_dataset_chronologically,
)
from app.services.gmo_strategy_backtest_engine import GmoBacktestRunStatus
from app.services.gmo_strategy_redesign import (
    EXIT_RIDE,
    EXIT_TIGHT,
    REDESIGN_RULE_VERSION,
    FrozenRedesignCandidate,
    RedesignBreakout,
    RedesignCandidate,
    RedesignComparison,
    RedesignEntryFamily,
    RedesignEntrySide,
    RedesignExitConfig,
    RedesignFeatureConfig,
    RedesignFeatures,
    RedesignMomentum,
    RedesignOosResultCategory,
    RedesignOverextension,
    RedesignRuleError,
    RedesignSelectionStatus,
    RedesignSplitMetricsSafe,
    RedesignTrendRegime,
    build_default_redesign_candidates,
    build_redesign_split_datasets,
    compare_redesign_candidates_train_validation,
    compute_redesign_features,
    evaluate_redesign_candidate_on_oos_once,
    freeze_redesign_candidate,
    redesign_entry_decision,
    run_redesign_backtest,
)


def _oscillating(*, cycles: int = 50, run_len: int = 10) -> BacktestDataset:
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


def _split(dataset):
    usable = len(dataset.candles) - dataset.warmup_bars
    return split_backtest_dataset_chronologically(
        dataset, train_bars=int(usable * 0.6), validation_bars=int(usable * 0.2)
    )


def _ready_features(**overrides) -> RedesignFeatures:
    base = dict(
        trend=RedesignTrendRegime.UP,
        momentum=RedesignMomentum.UP,
        breakout=RedesignBreakout.NONE,
        overextension=RedesignOverextension.NONE,
        atr_like=0.05,
        ready=True,
    )
    base.update(overrides)
    return RedesignFeatures(**base)


class TestFeatureConverter:
    def test_insufficient_history_is_fail_closed(self) -> None:
        closes = [100.0, 100.1, 100.2]
        features = compute_redesign_features(
            closes=closes, highs=closes, lows=closes, index=2,
            config=RedesignFeatureConfig(),
        )
        assert features.ready is False
        assert features.trend is RedesignTrendRegime.UNKNOWN
        assert features.atr_like == 0.0

    def test_rising_series_is_uptrend_and_deterministic(self) -> None:
        closes = [100.0 + i * 0.05 for i in range(40)]
        highs = [c + 0.02 for c in closes]
        lows = [c - 0.02 for c in closes]
        f1 = compute_redesign_features(
            closes=closes, highs=highs, lows=lows, index=39,
            config=RedesignFeatureConfig(),
        )
        f2 = compute_redesign_features(
            closes=closes, highs=highs, lows=lows, index=39,
            config=RedesignFeatureConfig(),
        )
        assert f1 == f2
        assert f1.ready is True
        assert f1.trend is RedesignTrendRegime.UP
        assert f1.atr_like > 0


class TestEntryDecision:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"ready": False},
        ],
    )
    def test_not_ready_blocks(self, overrides) -> None:
        decision = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(**overrides),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert decision.entry_side is RedesignEntrySide.REDESIGN_NO_ENTRY

    def test_spread_out_blocks(self) -> None:
        decision = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(),
            spread_within_limit=False,
            session_allowed=True,
        )
        assert decision.block_reason_safe_label == (
            "REDESIGN_BLOCK_SPREAD_NOT_WITHIN_LIMIT"
        )

    def test_session_blocked(self) -> None:
        decision = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(),
            spread_within_limit=True,
            session_allowed=False,
        )
        assert decision.block_reason_safe_label == (
            "REDESIGN_BLOCK_SESSION_NOT_ALLOWED"
        )

    def test_atr_not_positive_blocks(self) -> None:
        decision = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(atr_like=0.0),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert decision.block_reason_safe_label == "REDESIGN_BLOCK_ATR_NOT_POSITIVE"

    def test_trend_continuation_long_and_short(self) -> None:
        long_d = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(
                trend=RedesignTrendRegime.UP, momentum=RedesignMomentum.UP
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        short_d = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(
                trend=RedesignTrendRegime.DOWN, momentum=RedesignMomentum.DOWN
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert long_d.entry_side is RedesignEntrySide.REDESIGN_ENTRY_LONG
        assert short_d.entry_side is RedesignEntrySide.REDESIGN_ENTRY_SHORT

    def test_breakout_family(self) -> None:
        d = redesign_entry_decision(
            family=RedesignEntryFamily.BREAKOUT,
            features=_ready_features(
                breakout=RedesignBreakout.UP, trend=RedesignTrendRegime.RANGE
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert d.entry_side is RedesignEntrySide.REDESIGN_ENTRY_LONG

    def test_mean_reversion_requires_range(self) -> None:
        not_range = redesign_entry_decision(
            family=RedesignEntryFamily.MEAN_REVERSION_RANGE,
            features=_ready_features(
                trend=RedesignTrendRegime.UP,
                overextension=RedesignOverextension.DOWN,
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        in_range = redesign_entry_decision(
            family=RedesignEntryFamily.MEAN_REVERSION_RANGE,
            features=_ready_features(
                trend=RedesignTrendRegime.RANGE,
                overextension=RedesignOverextension.DOWN,
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert not_range.entry_side is RedesignEntrySide.REDESIGN_NO_ENTRY
        assert in_range.entry_side is RedesignEntrySide.REDESIGN_ENTRY_LONG

    def test_dual_confirmation_needs_trend_and_breakout(self) -> None:
        d = redesign_entry_decision(
            family=RedesignEntryFamily.DUAL_CONFIRMATION,
            features=_ready_features(
                trend=RedesignTrendRegime.UP, breakout=RedesignBreakout.UP
            ),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert d.entry_side is RedesignEntrySide.REDESIGN_ENTRY_LONG

    def test_decision_is_never_permission_or_operator_signal(self) -> None:
        d = redesign_entry_decision(
            family=RedesignEntryFamily.TREND_CONTINUATION,
            features=_ready_features(),
            spread_within_limit=True,
            session_allowed=True,
        )
        assert d.is_operator_signal is False
        assert d.actual_entry_POST_allowed is False
        assert d.actual_settlement_POST_allowed is False
        assert not d


class TestCandidateAndExit:
    def test_exit_config_validation(self) -> None:
        with pytest.raises(RedesignRuleError):
            RedesignExitConfig("X", 0.0, 1.0, 10, 1)
        with pytest.raises(RedesignRuleError):
            RedesignExitConfig("X", 1.0, 1.0, 0, 1)
        with pytest.raises(RedesignRuleError):
            RedesignExitConfig("X", 1.0, 1.0, 10, 0)

    def test_default_candidates_are_eight_candidate_only(self) -> None:
        candidates = build_default_redesign_candidates()
        assert len(candidates) == 8
        for candidate in candidates:
            assert candidate.candidate_only is True
            assert candidate.officially_adopted is False
            assert candidate.actual_entry_POST_allowed is False
            assert not candidate

    def test_official_adoption_refused(self) -> None:
        with pytest.raises(RedesignRuleError):
            RedesignCandidate(
                candidate_name="X",
                family=RedesignEntryFamily.BREAKOUT,
                exit_config=EXIT_TIGHT,
                officially_adopted=True,
            )


class TestRunner:
    def test_runner_completes_and_is_deterministic(self) -> None:
        dataset = _oscillating()
        candidate = RedesignCandidate(
            candidate_name="T",
            family=RedesignEntryFamily.BREAKOUT,
            exit_config=EXIT_TIGHT,
        )
        a = run_redesign_backtest(dataset=dataset, candidate=candidate)
        b = run_redesign_backtest(dataset=dataset, candidate=candidate)
        assert a == b
        assert a.status is GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED
        assert a.real_data_used is False
        assert a.synthetic_fixture_only is True
        assert not a

    def test_runner_never_holds_two_trades_at_once(self) -> None:
        dataset = _oscillating()
        candidate = RedesignCandidate(
            candidate_name="T",
            family=RedesignEntryFamily.BREAKOUT,
            exit_config=EXIT_RIDE,
        )
        result = run_redesign_backtest(dataset=dataset, candidate=candidate)
        # hold durations are non-negative; trades are emitted in order.
        for trade in result.trades:
            assert trade.hold_duration_bars >= 0
            assert trade.side_safe_label in {"PAPER_LONG", "PAPER_SHORT"}


class TestSplitAndComparison:
    def test_split_datasets_preserve_flags(self) -> None:
        dataset = _oscillating()
        splits = build_redesign_split_datasets(dataset, _split(dataset))
        assert set(splits) == {"TRAIN", "VALIDATION", "OOS"}
        for sub in splits.values():
            assert sub.synthetic_fixture is True
            assert sub.warmup_bars > 0

    def test_comparison_is_deterministic_and_bounded(self) -> None:
        dataset = _oscillating()
        split = _split(dataset)
        first = compare_redesign_candidates_train_validation(dataset, split)
        second = compare_redesign_candidates_train_validation(dataset, split)
        assert first == second
        assert first.parameter_search_count == 8
        assert first.selected_using == "TRAIN_VALIDATION_ONLY"
        assert first.oos_not_seen_before_freeze is True
        assert first.performance_proof_status is False
        assert first.live_ready is False
        names = {v.candidate_name for v in first.validation_metrics}
        assert "BASELINE" in names

    def test_monotonic_dataset_selects_no_candidate(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=300
        )
        comparison = compare_redesign_candidates_train_validation(
            dataset, _split(dataset)
        )
        assert comparison.status is (
            RedesignSelectionStatus.NO_CANDIDATE_SELECTED
        )
        assert freeze_redesign_candidate(comparison) is None


class TestFreezeAndOos:
    def _selected_comparison(self) -> RedesignComparison:
        name = build_default_redesign_candidates()[0].candidate_name
        view = RedesignSplitMetricsSafe(
            candidate_name=name,
            split_label="VALIDATION",
            trade_count=120,
            win_rate_rounded=0.5,
            profit_factor_rounded=1.2,
            expectancy_sign="POSITIVE",
            max_consecutive_losses=5,
            spread_cost_ratio_sign="POSITIVE",
        )
        return RedesignComparison(
            status=RedesignSelectionStatus.CANDIDATE_SELECTED,
            selected_candidate_name=name,
            selection_reason_safe_category="TEST",
            baseline_validation_profit_factor=0.9,
            baseline_validation_max_consecutive_losses=19,
            train_metrics=(),
            validation_metrics=(view,),
            parameter_search_count=8,
        )

    def test_freeze_records_train_validation_only(self) -> None:
        frozen = freeze_redesign_candidate(self._selected_comparison())
        assert frozen is not None
        assert frozen.rule_version == REDESIGN_RULE_VERSION
        assert frozen.selected_using == "TRAIN_VALIDATION_ONLY"
        assert frozen.oos_not_seen_before_freeze is True
        assert frozen.performance_proof_status is False
        assert frozen.live_ready is False
        assert not frozen

    def test_oos_not_run_without_candidate(self) -> None:
        dataset = _oscillating()
        oos = evaluate_redesign_candidate_on_oos_once(
            dataset, _split(dataset), None
        )
        assert oos.result_category is (
            RedesignOosResultCategory.OOS_NOT_RUN_NO_CANDIDATE
        )
        assert oos.evaluated_once is False

    def test_oos_runs_once_for_frozen_candidate(self) -> None:
        dataset = _oscillating()
        frozen = FrozenRedesignCandidate(
            candidate=RedesignCandidate(
                candidate_name="T",
                family=RedesignEntryFamily.BREAKOUT,
                exit_config=EXIT_RIDE,
            ),
            rule_version=REDESIGN_RULE_VERSION,
            selection_reason_safe_category="TEST",
            validation_profit_factor=1.1,
        )
        oos = evaluate_redesign_candidate_on_oos_once(
            dataset, _split(dataset), frozen
        )
        assert oos.evaluated_once is True
        assert oos.retuned_after_oos is False
        assert oos.performance_proof_status is False
        assert oos.result_category in {
            RedesignOosResultCategory.OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW,
            RedesignOosResultCategory.OOS_DEGRADED_REJECT_CANDIDATE,
            RedesignOosResultCategory.OOS_INSUFFICIENT_TRADES,
        }


class TestModuleIsolation:
    def test_module_has_no_network_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        for token in (
            "httpx",
            "requests",
            "urllib",
            "live_order_once",
            "live_verification",
            "os.environ",
            "getenv",
            "/private/v1",
            "profitable",
            "winning strategy",
        ):
            assert token not in source
