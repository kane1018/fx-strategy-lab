"""No-POST tests for the backtest report format."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_strategy_backtest_report as module
from app.services.gmo_strategy_backtest_dataset import (
    build_synthetic_trend_dataset,
    split_backtest_dataset_chronologically,
)
from app.services.gmo_strategy_backtest_engine import (
    ExitPolicyCandidate,
    MaxHoldProfileLabel,
    StopLossProfileLabel,
    TakeProfitProfileLabel,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_backtest_metrics import (
    GmoOosStatus,
    compute_backtest_metrics,
)
from app.services.gmo_strategy_backtest_report import (
    GmoBacktestReportError,
    GmoBacktestReportStatus,
    build_backtest_report,
    render_backtest_report_safe_lines,
)


def _policy() -> ExitPolicyCandidate:
    return ExitPolicyCandidate(
        take_profit_profile=TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_SMALL,
        stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_SMALL,
        max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_SHORT,
        tp_distance_synthetic=0.2,
        sl_distance_synthetic=0.2,
        max_hold_bars=50,
    )


def _report(*, spread_included: bool = True):
    dataset = build_synthetic_trend_dataset(direction_safe_label="UP", bars=60)
    split = split_backtest_dataset_chronologically(
        dataset, train_bars=30, validation_bars=15
    )
    run_result = run_synthetic_backtest(
        dataset=dataset, exit_policy=_policy(), spread_included=spread_included
    )
    metrics = compute_backtest_metrics(run_result)
    return build_backtest_report(
        dataset=dataset,
        split=split,
        run_result=run_result,
        metrics=metrics,
        exit_policy=_policy(),
    )


class TestReportBuild:
    def test_spread_included_report_status(self) -> None:
        report = _report()
        assert report.report_status is (
            GmoBacktestReportStatus.REPORT_SYNTHETIC_SPREAD_INCLUDED
        )
        assert report.spread_included is True
        assert report.spread_excluded_is_reference_only is False

    def test_spread_excluded_report_is_reference_only(self) -> None:
        report = _report(spread_included=False)
        assert report.report_status is (
            GmoBacktestReportStatus.REPORT_SYNTHETIC_REFERENCE_ONLY
        )
        assert report.spread_excluded_is_reference_only is True

    def test_report_pins_unproven_and_not_live_ready(self) -> None:
        report = _report()
        assert report.performance_proof_status is False
        assert report.live_ready is False
        assert report.real_data_used is False
        assert report.synthetic_fixture_only is True
        assert report.oos_evaluated is False
        assert report.operator_confirmation_required is True
        assert report.exit_policy_candidate_only is True
        assert not report

    def test_report_sections_are_populated(self) -> None:
        report = _report()
        assert report.dataset_bar_count == 60
        assert report.split_method_safe_label == "CHRONOLOGICAL_NO_SHUFFLE"
        assert report.split_oos_bars > 0
        assert report.trade_count >= 1
        assert report.overfitting_status == (
            "OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA"
        )
        assert report.oos_status == "OOS_NOT_EVALUATED"
        assert "NOT_PERFORMANCE_PROOF" in report.limitations_safe_label

    def test_oos_evaluated_metrics_are_rejected_this_phase(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=60
        )
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=30, validation_bars=15
        )
        run_result = run_synthetic_backtest(
            dataset=dataset, exit_policy=_policy()
        )
        metrics = replace(
            compute_backtest_metrics(run_result),
            oos_status=GmoOosStatus.OOS_EVALUATED,
        )
        with pytest.raises(GmoBacktestReportError):
            build_backtest_report(
                dataset=dataset,
                split=split,
                run_result=run_result,
                metrics=metrics,
                exit_policy=_policy(),
            )


class TestReportRendering:
    def test_rendered_lines_are_safe_aggregates_only(self) -> None:
        lines = render_backtest_report_safe_lines(_report())
        joined = "\n".join(lines)
        assert "performance_proof_status: False" in joined
        assert "live_ready: False" in joined
        assert "real_data_used: False" in joined
        lowered = joined.lower()
        assert "profitable" not in lowered
        assert "winning strategy" not in lowered
        assert "edge proven" not in lowered
        assert "order_id" not in lowered
        assert "position_id" not in lowered
        assert "api-key" not in lowered

    def test_rendered_lines_contain_no_per_bar_price_list(self) -> None:
        lines = render_backtest_report_safe_lines(_report())
        # The report has no field that could carry per-bar prices; sanity
        # check the rendered surface stays a bounded fixed-size summary.
        assert len(lines) < 50


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
