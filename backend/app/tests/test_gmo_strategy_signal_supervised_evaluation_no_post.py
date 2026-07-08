"""No-POST tests for the strategy signal supervised evaluation harness."""

from __future__ import annotations

import inspect

from app.services import gmo_strategy_signal_supervised_evaluation as module
from app.services.gmo_strategy_signal_supervised_evaluation import (
    IMPROVEMENT_CANDIDATE_CATEGORIES,
    OPERATOR_REVIEW_PLACEHOLDER,
    StrategyEvaluationStatus,
    build_deterministic_scenario_grid,
    build_required_scenario_families,
    run_strategy_signal_supervised_evaluation,
)


class TestScenarioFamilies:
    def test_required_families_are_present(self) -> None:
        names = {
            scenario.scenario_family_safe_label
            for scenario in build_required_scenario_families()
        }
        required = {
            "FAMILY_CLEAR_UPTREND_BUY",
            "FAMILY_CLEAR_DOWNTREND_SELL",
            "FAMILY_RANGE_HOLD",
            "FAMILY_TREND_UNKNOWN_BLOCKED",
            "FAMILY_TREND_CONFLICT_BLOCKED",
            "FAMILY_MOMENTUM_CONFLICT_HOLD",
            "FAMILY_SPREAD_OUT_BLOCKED",
            "FAMILY_TICKER_STALE_BLOCKED",
            "FAMILY_MARKET_UNSAFE_BLOCKED",
            "FAMILY_SESSION_BLOCKED",
            "FAMILY_HIGH_VOLATILITY_BLOCKED",
            "FAMILY_GUARD_HALT_BLOCKED",
            "FAMILY_NO_POSITION_ENTRY_PREVIEW_ALLOWED",
            "FAMILY_ONE_POSITION_SETTLEMENT_CONTEXT_ONLY",
            "FAMILY_POSITION_CONTEXT_UNKNOWN_BLOCKED",
            "FAMILY_MISSING_LABELS_DEFAULT_BLOCKED",
        }
        assert required <= names

    def test_grid_is_deterministic_and_large_enough(self) -> None:
        first = build_deterministic_scenario_grid()
        second = build_deterministic_scenario_grid()
        assert first == second
        assert len(first) >= 50


class TestEvaluationRun:
    def test_behavior_evaluation_passes(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.status is (
            StrategyEvaluationStatus.STRATEGY_EVALUATION_BEHAVIOR_PASSED
        )
        assert report.matched_family_count == report.scenario_family_count
        assert report.mismatched_families_safe == ()
        assert report.grid_row_count >= 50

    def test_distributions_are_safe_labels_only(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        for label, count in report.signal_distribution:
            assert label.startswith("AUTO_PREVIEW_SIGNAL_")
            assert count > 0
        for label, _ in report.block_reason_distribution:
            assert label.startswith("BLOCK_") or label.startswith("ENTRY_PREVIEW_")
        for label, _ in report.rule_path_distribution:
            assert label.startswith("RULE_")

    def test_rule_coverage_is_complete(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.rule_coverage_complete is True
        assert set(report.rule_paths_defined) <= set(report.rule_paths_covered)

    def test_fail_closed_rows_exist_and_hold_never_orders(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.fail_closed_row_count > 0
        assert report.hold_rows_created_orders == 0

    def test_operator_review_placeholder_is_never_filled_by_ai(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.operator_review_filled_by_ai is False
        for record in report.review_records:
            assert record.operator_acceptance_placeholder == (
                OPERATOR_REVIEW_PLACEHOLDER
            )
            assert record.operator_acceptance_placeholder not in (
                "ENTRY_BUY",
                "ENTRY_SELL",
                "HOLD",
            )
            assert record.excluded_from_performance_claim is True
            assert not record

    def test_report_is_never_permission_or_performance_proof(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.performance_proof_status is False
        assert report.strategy_quality_proven is False
        assert report.preview_is_permission is False
        assert report.auto_preview_signal_is_operator_signal is False
        assert report.actual_entry_POST_allowed is False
        assert report.actual_settlement_POST_allowed is False
        assert report.real_post_count == 0
        assert report.raw_id_value_exposure is False
        assert report.unattended_live_supported is False
        assert report.unattended_full_auto_completed is False
        assert not report

    def test_improvement_candidates_are_fixed_safe_categories(self) -> None:
        report = run_strategy_signal_supervised_evaluation()
        assert report.improvement_candidates == IMPROVEMENT_CANDIDATE_CATEGORIES
        assert "NEEDS_BACKTEST_DATASET" in report.improvement_candidates
        assert "NEEDS_OPERATOR_REVIEW_SAMPLES" in report.improvement_candidates


class TestModuleIsolation:
    def test_module_has_no_broker_env_or_raw_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "/private/v1" not in source
        assert "build_auth_headers" not in source
        assert "random" not in source
