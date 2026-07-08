"""No-POST tests for the paper auto cycle runner. Fake transports only."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from app.services import gmo_paper_auto_cycle_runner as module
from app.services.gmo_paper_auto_cycle_runner import (
    AutoPreviewSignal,
    FakePaperCycleTransport,
    GmoPaperAutoCycleRunnerError,
    GmoPaperAutoCycleStatus,
    PaperAutoCycleScenario,
    PaperMarketScenarioSafeInput,
    PaperOrderResultCategory,
    build_all_safe_paper_scenario_input,
    run_gmo_paper_auto_cycle_once,
    run_paper_auto_cycle_scenario,
)


@dataclass
class _CountingFakeTransport:
    preset_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )
    is_real_transport: bool = False
    call_count: int = 0

    def send_paper_order_sanitized(self) -> PaperOrderResultCategory:
        self.call_count += 1
        return self.preset_result


def _run(
    signal: AutoPreviewSignal | str,
    *,
    scenario: PaperMarketScenarioSafeInput | None = None,
    entry: _CountingFakeTransport | None = None,
    settlement: _CountingFakeTransport | None = None,
):
    return run_gmo_paper_auto_cycle_once(
        auto_preview_signal=signal,
        scenario=scenario or build_all_safe_paper_scenario_input(),
        entry_transport=entry or _CountingFakeTransport(),
        settlement_transport=settlement or _CountingFakeTransport(),
    )


class TestFullPaperCycles:
    def test_buy_cycle_completes_with_one_entry_and_one_settlement(self) -> None:
        entry = _CountingFakeTransport()
        settlement = _CountingFakeTransport()
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            entry=entry,
            settlement=settlement,
        )
        assert result.status is GmoPaperAutoCycleStatus.PAPER_CYCLE_COMPLETE
        assert entry.call_count == 1
        assert settlement.call_count == 1
        assert result.paper_entry_attempt_count == 1
        assert result.paper_settlement_attempt_count == 1
        assert result.paper_entry_order_kind_safe_label == "PAPER_ENTRY_OPEN_BUY"
        assert result.paper_settlement_side_safe_label == "PAPER_SETTLEMENT_SELL"
        assert result.paper_position_states_safe == (
            "PAPER_NO_POSITION",
            "PAPER_ONE_POSITION_OPEN",
            "PAPER_NO_POSITION",
        )

    def test_sell_cycle_completes_with_mirrored_labels(self) -> None:
        result = _run(AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL)
        assert result.status is GmoPaperAutoCycleStatus.PAPER_CYCLE_COMPLETE
        assert result.paper_entry_order_kind_safe_label == "PAPER_ENTRY_OPEN_SELL"
        assert result.paper_settlement_side_safe_label == "PAPER_SETTLEMENT_BUY"

    def test_hold_makes_no_paper_order(self) -> None:
        entry = _CountingFakeTransport()
        settlement = _CountingFakeTransport()
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            entry=entry,
            settlement=settlement,
        )
        assert result.status is GmoPaperAutoCycleStatus.PAPER_CYCLE_HOLD_NO_ORDER
        assert entry.call_count == 0
        assert settlement.call_count == 0
        assert result.paper_entry_attempt_count == 0

    def test_unknown_signal_blocks_hard(self) -> None:
        entry = _CountingFakeTransport()
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED, entry=entry
        )
        assert result.status is (
            GmoPaperAutoCycleStatus.PAPER_CYCLE_BLOCKED_SIGNAL_UNKNOWN
        )
        assert entry.call_count == 0


class TestFailClosedBehaviour:
    @pytest.mark.parametrize(
        "missing_field",
        [
            "market_open_safe",
            "ticker_fresh_safe",
            "spread_within_limit_safe",
            "paper_position_flat_safe",
            "active_pending_clear_safe",
        ],
    )
    def test_each_scenario_gate_blocks_before_entry(self, missing_field) -> None:
        kwargs = {
            "market_open_safe": True,
            "ticker_fresh_safe": True,
            "spread_within_limit_safe": True,
            "paper_position_flat_safe": True,
            "active_pending_clear_safe": True,
        }
        kwargs[missing_field] = False
        entry = _CountingFakeTransport()
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            scenario=PaperMarketScenarioSafeInput(**kwargs),
            entry=entry,
        )
        assert result.status is (
            GmoPaperAutoCycleStatus.PAPER_CYCLE_BLOCKED_SCENARIO_GATE
        )
        assert entry.call_count == 0
        assert result.blocked_reasons

    @pytest.mark.parametrize(
        "entry_result",
        [
            PaperOrderResultCategory.PAPER_RESULT_REJECTED_SANITIZED,
            PaperOrderResultCategory.PAPER_RESULT_UNKNOWN_SANITIZED,
        ],
    )
    def test_non_accepted_paper_entry_stops_without_retry(
        self, entry_result
    ) -> None:
        entry = _CountingFakeTransport(preset_result=entry_result)
        settlement = _CountingFakeTransport()
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            entry=entry,
            settlement=settlement,
        )
        assert result.status is (
            GmoPaperAutoCycleStatus.PAPER_CYCLE_STOPPED_ENTRY_NOT_ACCEPTED
        )
        assert entry.call_count == 1
        assert settlement.call_count == 0
        assert result.retry_performed is False
        assert result.second_post_performed is False

    def test_non_accepted_paper_settlement_stops_without_retry(self) -> None:
        settlement = _CountingFakeTransport(
            preset_result=PaperOrderResultCategory.PAPER_RESULT_UNKNOWN_SANITIZED
        )
        result = _run(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY, settlement=settlement
        )
        assert result.status is (
            GmoPaperAutoCycleStatus.PAPER_CYCLE_STOPPED_SETTLEMENT_NOT_ACCEPTED
        )
        assert settlement.call_count == 1
        assert result.paper_settlement_attempt_count == 1
        assert result.repost_performed is False

    def test_real_looking_transport_is_refused(self) -> None:
        real_like = _CountingFakeTransport()
        real_like.is_real_transport = True
        with pytest.raises(GmoPaperAutoCycleRunnerError):
            _run(AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY, entry=real_like)
        assert real_like.call_count == 0

    def test_unmarked_transport_is_refused(self) -> None:
        class _Unmarked:
            def send_paper_order_sanitized(self):
                return PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED

        with pytest.raises(GmoPaperAutoCycleRunnerError):
            run_gmo_paper_auto_cycle_once(
                auto_preview_signal=AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
                scenario=build_all_safe_paper_scenario_input(),
                entry_transport=_Unmarked(),
                settlement_transport=_CountingFakeTransport(),
            )

    @pytest.mark.parametrize("operator_label", ["ENTRY_BUY", "ENTRY_SELL", "HOLD"])
    def test_operator_signal_labels_are_rejected(self, operator_label) -> None:
        with pytest.raises(GmoPaperAutoCycleRunnerError):
            _run(operator_label)

    def test_unrecognized_string_signal_degrades_to_unknown_blocked(self) -> None:
        result = _run("SOMETHING_ELSE")
        assert result.status is (
            GmoPaperAutoCycleStatus.PAPER_CYCLE_BLOCKED_SIGNAL_UNKNOWN
        )


class TestResultSafety:
    def test_result_flags_are_fixed_false_and_never_truthy(self) -> None:
        result = _run(AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY)
        assert result.actual_entry_POST_allowed is False
        assert result.actual_settlement_POST_allowed is False
        assert result.broker_write_performed is False
        assert result.real_http_performed is False
        assert result.runtime_private_get_performed is False
        assert result.credential_value_read is False
        assert result.env_read_performed is False
        assert result.raw_id_value_exposure is False
        assert result.operator_confirmation_banked is False
        assert result.operator_confirmation_substituted is False
        assert result.real_post_count == 0
        assert not result

    def test_named_scenario_runner_is_deterministic(self) -> None:
        scenario = PaperAutoCycleScenario(
            scenario_name_safe_label="PAPER_SCENARIO_BUY_ALL_GREEN",
            auto_preview_signal=AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
            scenario=build_all_safe_paper_scenario_input(),
        )
        first = run_paper_auto_cycle_scenario(scenario)
        second = run_paper_auto_cycle_scenario(scenario)
        assert first == second
        assert first.status is GmoPaperAutoCycleStatus.PAPER_CYCLE_COMPLETE

    def test_event_log_contains_safe_labels_only(self) -> None:
        result = _run(AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY)
        for event in result.event_log_safe_labels:
            assert event.startswith("PAPER_EVENT_")


class TestFakePaperTransport:
    def test_default_fake_transport_is_marked_fake(self) -> None:
        assert FakePaperCycleTransport().is_real_transport is False


class TestModuleIsolation:
    def test_module_has_no_real_broker_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "build_auth_headers" not in source
        assert "closeOrder" not in source
        assert "/private/v1" not in source
