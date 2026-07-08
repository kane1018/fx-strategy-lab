"""No-POST tests for the limited unattended paper soak orchestrator."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_limited_unattended_paper_soak as module
from app.services.gmo_limited_unattended_paper_soak import (
    LIMITED_SOAK_MIN_CYCLE_COUNT,
    GmoLimitedPaperSoakPlan,
    GmoLimitedPaperSoakStatus,
    build_limited_soak_scenario_batch,
    observe_preview_signal_distribution,
    run_limited_unattended_paper_soak,
    validate_limited_paper_soak_plan,
)
from app.services.gmo_unattended_paper_soak_runner import (
    build_default_paper_soak_scenario_suite,
)


class TestPlanValidation:
    def test_default_plan_validates(self) -> None:
        ok, reasons = validate_limited_paper_soak_plan(GmoLimitedPaperSoakPlan())
        assert ok
        assert reasons == ()

    @pytest.mark.parametrize(
        ("overrides", "reason_fragment"),
        [
            ({"mode_safe_label": "LIVE"}, "MODE_SAFE_LABEL"),
            ({"transport_safe_label": "REAL"}, "TRANSPORT_SAFE_LABEL"),
            ({"notifier_safe_label": "WEBHOOK"}, "NOTIFIER_SAFE_LABEL"),
            ({"runtime_safe_label": "DAEMON"}, "RUNTIME_SAFE_LABEL"),
            ({"target_synthetic_cycle_count": 10}, "CYCLE_COUNT_BELOW_MINIMUM"),
            ({"max_paper_entry_attempt_per_cycle": 2}, "ENTRY_ATTEMPT_MAX"),
            (
                {"max_paper_settlement_attempt_per_cycle": 2},
                "SETTLEMENT_ATTEMPT_MAX",
            ),
            ({"retry_within_cycle_allowed": True}, "RETRY_REQUESTED_BLOCKED"),
            ({"halt_on_unknown": False}, "HALT_ON_UNKNOWN"),
            ({"halt_on_guard": False}, "HALT_ON_GUARD"),
            ({"duplicate_attempt_block": False}, "DUPLICATE_ATTEMPT_BLOCK"),
        ],
    )
    def test_unsupported_plan_values_block(self, overrides, reason_fragment) -> None:
        ok, reasons = validate_limited_paper_soak_plan(
            replace(GmoLimitedPaperSoakPlan(), **overrides)
        )
        assert not ok
        assert any(reason_fragment in reason for reason in reasons)

    def test_blocked_plan_yields_blocked_report_without_cycles(self) -> None:
        report = run_limited_unattended_paper_soak(
            replace(GmoLimitedPaperSoakPlan(), retry_within_cycle_allowed=True)
        )
        assert report.status is (
            GmoLimitedPaperSoakStatus.LIMITED_PAPER_SOAK_BLOCKED_SAFE
        )
        assert report.synthetic_cycle_count == 0
        assert report.blocked_reasons


class TestScenarioBatch:
    def test_batch_starts_with_full_readiness_suite(self) -> None:
        base = build_default_paper_soak_scenario_suite()
        batch = build_limited_soak_scenario_batch(55)
        assert batch[: len(base)] == base
        assert len(batch) == 55

    def test_batch_names_are_unique_and_deterministic(self) -> None:
        first = build_limited_soak_scenario_batch(60)
        second = build_limited_soak_scenario_batch(60)
        assert first == second
        names = [scenario.scenario_name_safe_label for scenario in first]
        assert len(names) == len(set(names))


class TestLimitedSoakRun:
    def test_default_soak_passes_with_planned_cycle_count(self) -> None:
        report = run_limited_unattended_paper_soak()
        assert report.status is (
            GmoLimitedPaperSoakStatus.LIMITED_PAPER_SOAK_PASSED
        )
        assert report.synthetic_cycle_count >= LIMITED_SOAK_MIN_CYCLE_COUNT
        assert report.matched_cycle_count == report.synthetic_cycle_count
        assert report.mismatched_scenarios_safe == ()

    def test_soak_holds_attempt_and_no_retry_invariants(self) -> None:
        report = run_limited_unattended_paper_soak()
        assert report.attempt_invariant_ok is True
        assert report.no_retry_invariant_ok is True
        assert report.max_entry_attempts_observed <= 1
        assert report.max_settlement_attempts_observed <= 1
        assert report.duplicate_blocked_cycle_count >= 2

    def test_soak_distributions_are_safe_categories_only(self) -> None:
        report = run_limited_unattended_paper_soak()
        for label, count in report.outcome_distribution:
            assert label.startswith("SCENARIO_")
            assert count > 0
        for label, _count in report.guard_halt_distribution:
            assert label.startswith("GUARD_HALT_")
        for label, _count in report.notification_distribution:
            assert label.startswith("NOTIFY_")
        for label, _count in report.terminal_state_distribution:
            assert label in {"COMPLETED", "HALTED", "IDLE"}
        for label, _count in report.soak_signal_distribution:
            assert label.startswith("AUTO_PREVIEW_SIGNAL_")

    def test_soak_covers_required_outcome_families(self) -> None:
        report = run_limited_unattended_paper_soak()
        outcomes = dict(report.outcome_distribution)
        assert outcomes.get("SCENARIO_COMPLETED_SAFE", 0) >= 2
        assert outcomes.get("SCENARIO_HOLD_NO_ORDER_SAFE", 0) >= 1
        assert outcomes.get("SCENARIO_SIGNAL_BLOCKED_SAFE", 0) >= 1
        assert outcomes.get("SCENARIO_GUARD_HALTED_SAFE", 0) >= 8
        assert outcomes.get("SCENARIO_HALTED_NO_RETRY_SAFE", 0) >= 4
        assert outcomes.get("SCENARIO_DUPLICATE_BLOCKED_SAFE", 0) >= 2
        assert outcomes.get("SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE", 0) >= 1
        assert outcomes.get("SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE", 0) >= 1
        assert outcomes.get("SCENARIO_REAL_TRANSPORT_REFUSED_SAFE", 0) >= 1

    def test_report_is_never_a_permission_or_live_claim(self) -> None:
        report = run_limited_unattended_paper_soak()
        assert report.real_post_count == 0
        assert report.actual_entry_POST_allowed is False
        assert report.actual_settlement_POST_allowed is False
        assert report.broker_write_performed is False
        assert report.real_http_performed is False
        assert report.runtime_private_get_performed is False
        assert report.credential_value_read is False
        assert report.env_read_performed is False
        assert report.raw_id_value_exposure is False
        assert report.unattended_live_supported is False
        assert report.unattended_full_auto_completed is False
        assert report.live_performance_claim is False
        assert not report


class TestPreviewObservation:
    def test_preview_distribution_covers_all_auto_labels(self) -> None:
        observation = observe_preview_signal_distribution()
        labels = dict(observation.preview_signal_distribution)
        assert labels.get("AUTO_PREVIEW_SIGNAL_BUY", 0) >= 1
        assert labels.get("AUTO_PREVIEW_SIGNAL_SELL", 0) >= 1
        assert labels.get("AUTO_PREVIEW_SIGNAL_HOLD", 0) >= 1
        assert labels.get("AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED", 0) >= 1

    def test_preview_is_never_operator_signal_or_permission(self) -> None:
        observation = observe_preview_signal_distribution()
        assert observation.auto_preview_signal_is_operator_signal is False
        assert observation.any_preview_was_permission is False
        assert not observation


class TestModuleIsolation:
    def test_module_has_no_broker_env_or_scheduler_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "/private/v1" not in source
        assert "build_auth_headers" not in source
        assert "sleep" not in source
        assert "threading" not in source
        assert "subprocess" not in source
