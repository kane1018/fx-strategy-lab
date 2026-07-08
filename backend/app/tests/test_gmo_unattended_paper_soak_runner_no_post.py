"""No-POST tests for the paper soak readiness runner and fake notifier."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_unattended_paper_soak_runner as module
from app.services.gmo_paper_auto_cycle_runner import (
    AutoPreviewSignal,
    PaperOrderResultCategory,
)
from app.services.gmo_unattended_fake_notifier import (
    FailingFakeUnattendedNotifier,
    FakeUnattendedNotifier,
    GmoUnattendedNotificationCategory,
    GmoUnattendedNotifierResult,
)
from app.services.gmo_unattended_monitoring_guard import (
    SpreadSafeStatus,
    build_all_safe_guard_snapshot,
)
from app.services.gmo_unattended_paper_soak_runner import (
    GmoPaperSoakReadinessStatus,
    GmoPaperSoakScenarioOutcome,
    PaperSoakScenario,
    build_default_paper_soak_scenario_suite,
    run_paper_soak_readiness_suite,
    run_paper_soak_scenario,
)


def _scenario(**overrides) -> PaperSoakScenario:
    base = PaperSoakScenario(
        scenario_name_safe_label="TEST_SCENARIO",
        expected_outcome=GmoPaperSoakScenarioOutcome.SCENARIO_COMPLETED_SAFE,
        auto_preview_signal=AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
    )
    return replace(base, **overrides)


class TestFakeNotifier:
    def test_fake_notifier_collects_safe_categories_only(self) -> None:
        notifier = FakeUnattendedNotifier()
        result = notifier.notify_safe_category(
            GmoUnattendedNotificationCategory.NOTIFY_PREVIEW_READY
        )
        assert result is GmoUnattendedNotifierResult.NOTIFY_RECORDED_SAFE
        assert notifier.external_send is False
        assert notifier.collected_categories == [
            GmoUnattendedNotificationCategory.NOTIFY_PREVIEW_READY
        ]
        assert not notifier

    def test_non_category_input_fails_safe(self) -> None:
        notifier = FakeUnattendedNotifier()
        result = notifier.notify_safe_category("raw text")  # type: ignore[arg-type]
        assert result is GmoUnattendedNotifierResult.NOTIFY_FAILED_SAFE
        assert notifier.collected_categories == []

    def test_failing_notifier_never_records(self) -> None:
        notifier = FailingFakeUnattendedNotifier()
        result = notifier.notify_safe_category(
            GmoUnattendedNotificationCategory.NOTIFY_PREVIEW_READY
        )
        assert result is GmoUnattendedNotifierResult.NOTIFY_FAILED_SAFE
        assert notifier.external_send is False


class TestScenarioRunner:
    def test_buy_cycle_completes_with_one_entry_and_one_settlement(self) -> None:
        result = run_paper_soak_scenario(_scenario())
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_COMPLETED_SAFE
        )
        assert result.final_state_safe_label == "COMPLETED"
        assert result.paper_entry_attempt_count == 1
        assert result.paper_settlement_attempt_count == 1
        assert result.retry_performed is False
        assert result.real_post_count == 0
        assert "NOTIFY_PAPER_NO_POSITION_CONFIRMED" in result.notifications_safe

    def test_hold_makes_no_paper_order(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(
                auto_preview_signal=AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
                expected_outcome=(
                    GmoPaperSoakScenarioOutcome.SCENARIO_HOLD_NO_ORDER_SAFE
                ),
            )
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_HOLD_NO_ORDER_SAFE
        )
        assert result.paper_entry_attempt_count == 0

    def test_unknown_signal_blocks(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(
                auto_preview_signal=(
                    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
                ),
            )
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_SIGNAL_BLOCKED_SAFE
        )
        assert result.paper_entry_attempt_count == 0

    def test_guard_halt_happens_before_any_attempt(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(
                guard_snapshot=replace(
                    build_all_safe_guard_snapshot(),
                    spread_safe_status=SpreadSafeStatus.SPREAD_OUT_OF_LIMIT,
                ),
            )
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_GUARD_HALTED_SAFE
        )
        assert result.guard_decision_safe_label == (
            "GUARD_HALT_SPREAD_OUT_OF_LIMIT"
        )
        assert result.paper_entry_attempt_count == 0
        assert "NOTIFY_GUARD_HALTED" in result.notifications_safe

    def test_kill_switch_halt_uses_kill_switch_notification(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(
                guard_snapshot=replace(
                    build_all_safe_guard_snapshot(), kill_switch_engaged=True
                ),
            )
        )
        assert result.guard_decision_safe_label == "GUARD_HALT_KILL_SWITCH"
        assert "NOTIFY_KILL_SWITCH_HALTED" in result.notifications_safe

    @pytest.mark.parametrize(
        "entry_result",
        [
            PaperOrderResultCategory.PAPER_RESULT_REJECTED_SANITIZED,
            PaperOrderResultCategory.PAPER_RESULT_UNKNOWN_SANITIZED,
        ],
    )
    def test_entry_not_accepted_halts_without_retry(self, entry_result) -> None:
        result = run_paper_soak_scenario(
            _scenario(paper_entry_result=entry_result)
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_HALTED_NO_RETRY_SAFE
        )
        assert result.paper_entry_attempt_count == 1
        assert result.paper_settlement_attempt_count == 0
        assert result.retry_performed is False

    def test_settlement_not_accepted_halts_without_retry(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(
                paper_settlement_result=(
                    PaperOrderResultCategory.PAPER_RESULT_REJECTED_SANITIZED
                ),
            )
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_HALTED_NO_RETRY_SAFE
        )
        assert result.paper_settlement_attempt_count == 1
        assert result.second_post_performed is False

    def test_duplicate_entry_attempt_is_blocked(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(inject_duplicate_entry_attempt=True)
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE
        )
        assert result.paper_entry_attempt_count == 1
        assert "NOTIFY_DUPLICATE_ATTEMPT_BLOCKED" in result.notifications_safe

    def test_duplicate_settlement_attempt_is_blocked(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(inject_duplicate_settlement_attempt=True)
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE
        )
        assert result.paper_settlement_attempt_count == 1

    def test_illegal_transition_is_blocked(self) -> None:
        result = run_paper_soak_scenario(_scenario(inject_illegal_transition=True))
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome
            .SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE
        )
        assert result.final_state_safe_label == "HALTED"

    def test_required_notification_failure_halts(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(notifier_fails=True, notification_required=True)
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE
        )
        assert result.paper_entry_attempt_count == 0

    def test_real_like_transport_is_refused(self) -> None:
        result = run_paper_soak_scenario(
            _scenario(inject_real_like_transport=True)
        )
        assert result.outcome is (
            GmoPaperSoakScenarioOutcome.SCENARIO_REAL_TRANSPORT_REFUSED_SAFE
        )
        assert result.paper_entry_attempt_count == 0

    def test_result_flags_fixed_false_and_never_truthy(self) -> None:
        result = run_paper_soak_scenario(_scenario())
        assert result.actual_entry_POST_allowed is False
        assert result.actual_settlement_POST_allowed is False
        assert result.broker_write_performed is False
        assert result.real_http_performed is False
        assert result.runtime_private_get_performed is False
        assert result.credential_value_read is False
        assert result.env_read_performed is False
        assert result.raw_id_value_exposure is False
        assert not result


class TestReadinessSuite:
    def test_default_suite_passes_all_required_scenarios(self) -> None:
        report = run_paper_soak_readiness_suite()
        assert report.status is (
            GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_PASSED
        )
        assert report.scenario_count == len(
            build_default_paper_soak_scenario_suite()
        )
        assert report.matched_count == report.scenario_count
        assert report.mismatched_scenarios_safe == ()
        assert report.unattended_live_supported is False
        assert report.unattended_full_auto_completed is False
        assert report.real_post_count == 0
        assert not report

    def test_default_suite_covers_required_families(self) -> None:
        names = {
            scenario.scenario_name_safe_label
            for scenario in build_default_paper_soak_scenario_suite()
        }
        assert len(names) >= 20

    def test_mismatched_expectation_fails_safe(self) -> None:
        wrong = (
            _scenario(
                expected_outcome=(
                    GmoPaperSoakScenarioOutcome.SCENARIO_GUARD_HALTED_SAFE
                ),
            ),
        )
        report = run_paper_soak_readiness_suite(wrong)
        assert report.status is (
            GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_FAILED_SAFE
        )
        assert report.mismatched_scenarios_safe == ("TEST_SCENARIO",)

    def test_empty_suite_is_blocked_safe(self) -> None:
        report = run_paper_soak_readiness_suite(())
        assert report.status is (
            GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_BLOCKED_SAFE
        )


class TestModuleIsolation:
    def test_runner_has_no_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "/private/v1" not in source
        assert "build_auth_headers" not in source
