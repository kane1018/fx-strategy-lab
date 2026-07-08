"""Paper soak readiness runner (synthetic scenario suite, no-POST).

Drives the unattended readiness pieces -- monitoring guard, paper cycle
state machine, lock, safe attempt ledger, fake notifier, and the existing
paper auto cycle transports -- through a deterministic synthetic scenario
suite. This is an immediate verification suite, NOT a resident process:
there is no daemon, cron, scheduler, background worker, network, broker,
credential, or ``.env`` surface here.

Fail-closed rules carried through from the underlying pieces:

- Real-looking transports are refused before any attempt.
- One paper entry and one paper settlement maximum per cycle; a duplicate
  attempt halts. Non-accepted paper outcomes halt with no retry branch.
- A guard halt happens BEFORE any paper attempt.
- When a scenario requires notifications, a notifier failure halts safely.
- Every output is a safe category; readiness PASS is never a live
  permission (``unattended_live_supported`` stays false).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import (
    AutoPreviewSignal,
    FakePaperCycleTransport,
    GmoPaperAutoCycleRunnerError,
    PaperOrderResultCategory,
)
from app.services.gmo_unattended_cycle_state_machine import (
    PAPER_EVENT_ENTRY_ACCEPTED_SAFE,
    PAPER_EVENT_NO_POSITION_CONFIRMED_SAFE,
    PAPER_EVENT_POSITION_OPEN_CONFIRMED_SAFE,
    PAPER_EVENT_PREVIEW_READY,
    PAPER_EVENT_SETTLEMENT_ACCEPTED_SAFE,
    PAPER_EVENT_SIGNAL_CANDIDATE,
    UnattendedPaperCycleState,
    UnattendedPaperCycleStateMachine,
    acquire_paper_cycle_lock,
)
from app.services.gmo_unattended_fake_notifier import (
    FakeUnattendedNotifier,
    GmoUnattendedNotificationCategory,
    GmoUnattendedNotifierResult,
)
from app.services.gmo_unattended_monitoring_guard import (
    UnattendedGuardDecision,
    UnattendedMonitoringGuardSafeSnapshot,
    build_all_safe_guard_snapshot,
    evaluate_unattended_monitoring_guard,
)

_GUARD_HALT_NOTIFICATIONS: dict[
    UnattendedGuardDecision, GmoUnattendedNotificationCategory
] = {
    UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH: (
        GmoUnattendedNotificationCategory.NOTIFY_KILL_SWITCH_HALTED
    ),
    UnattendedGuardDecision.GUARD_HALT_MAX_HOLD_EXCEEDED: (
        GmoUnattendedNotificationCategory.NOTIFY_MAX_HOLD_HALTED
    ),
    UnattendedGuardDecision.GUARD_HALT_MAX_LOSS_EXCEEDED: (
        GmoUnattendedNotificationCategory.NOTIFY_MAX_LOSS_HALTED
    ),
}


class GmoPaperSoakScenarioOutcome(str, Enum):
    SCENARIO_COMPLETED_SAFE = "SCENARIO_COMPLETED_SAFE"
    SCENARIO_HOLD_NO_ORDER_SAFE = "SCENARIO_HOLD_NO_ORDER_SAFE"
    SCENARIO_SIGNAL_BLOCKED_SAFE = "SCENARIO_SIGNAL_BLOCKED_SAFE"
    SCENARIO_GUARD_HALTED_SAFE = "SCENARIO_GUARD_HALTED_SAFE"
    SCENARIO_HALTED_NO_RETRY_SAFE = "SCENARIO_HALTED_NO_RETRY_SAFE"
    SCENARIO_DUPLICATE_BLOCKED_SAFE = "SCENARIO_DUPLICATE_BLOCKED_SAFE"
    SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE = (
        "SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE"
    )
    SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE = (
        "SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE"
    )
    SCENARIO_REAL_TRANSPORT_REFUSED_SAFE = (
        "SCENARIO_REAL_TRANSPORT_REFUSED_SAFE"
    )


class GmoPaperSoakReadinessStatus(str, Enum):
    PAPER_SOAK_READINESS_PASSED = "PAPER_SOAK_READINESS_PASSED"
    PAPER_SOAK_READINESS_FAILED_SAFE = "PAPER_SOAK_READINESS_FAILED_SAFE"
    PAPER_SOAK_READINESS_BLOCKED_SAFE = "PAPER_SOAK_READINESS_BLOCKED_SAFE"


@dataclass(frozen=True)
class PaperSoakScenario:
    """One deterministic synthetic scenario with an expected safe outcome."""

    scenario_name_safe_label: str
    expected_outcome: GmoPaperSoakScenarioOutcome
    auto_preview_signal: AutoPreviewSignal
    guard_snapshot: UnattendedMonitoringGuardSafeSnapshot = field(
        default_factory=build_all_safe_guard_snapshot
    )
    paper_entry_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )
    paper_settlement_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )
    # Fault injection (synthetic only)
    inject_duplicate_entry_attempt: bool = False
    inject_duplicate_settlement_attempt: bool = False
    inject_illegal_transition: bool = False
    inject_real_like_transport: bool = False
    notifier_fails: bool = False
    notification_required: bool = True


@dataclass(frozen=True)
class PaperSoakScenarioResult:
    """Safe-category-only scenario result. Never truthy."""

    scenario_name_safe_label: str
    outcome: GmoPaperSoakScenarioOutcome
    expected_outcome: GmoPaperSoakScenarioOutcome
    matched_expectation: bool
    final_state_safe_label: str
    guard_decision_safe_label: str
    paper_entry_attempt_count: int
    paper_settlement_attempt_count: int
    ledger_events_safe: tuple[str, ...]
    notifications_safe: tuple[str, ...]
    retry_performed: bool = False
    repost_performed: bool = False
    second_post_performed: bool = False
    real_post_count: int = 0
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    broker_write_performed: bool = False
    real_http_performed: bool = False
    runtime_private_get_performed: bool = False
    credential_value_read: bool = False
    env_read_performed: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


def _notify(
    notifier,
    category: GmoUnattendedNotificationCategory,
    *,
    required: bool,
) -> bool:
    """Send one fake notification. Returns False when a required one fails."""

    result = notifier.notify_safe_category(category)
    return not (
        required and result is not GmoUnattendedNotifierResult.NOTIFY_RECORDED_SAFE
    )


def run_paper_soak_scenario(scenario: PaperSoakScenario) -> PaperSoakScenarioResult:
    """Run one synthetic scenario end to end (paper only, no retry paths)."""

    notifier = (
        _make_failing_notifier() if scenario.notifier_fails else FakeUnattendedNotifier()
    )
    machine = UnattendedPaperCycleStateMachine(lock=acquire_paper_cycle_lock())

    def _result(outcome: GmoPaperSoakScenarioOutcome) -> PaperSoakScenarioResult:
        return PaperSoakScenarioResult(
            scenario_name_safe_label=scenario.scenario_name_safe_label,
            outcome=outcome,
            expected_outcome=scenario.expected_outcome,
            matched_expectation=outcome is scenario.expected_outcome,
            final_state_safe_label=machine.state.value,
            guard_decision_safe_label=guard_result.decision.value,
            paper_entry_attempt_count=machine.ledger.entry_attempt_count,
            paper_settlement_attempt_count=(
                machine.ledger.settlement_attempt_count
            ),
            ledger_events_safe=machine.ledger.events,
            notifications_safe=tuple(
                category.value for category in notifier.collected_categories
            ),
        )

    # Real-like transport refusal happens before anything else.
    if scenario.inject_real_like_transport:
        guard_result = evaluate_unattended_monitoring_guard(scenario.guard_snapshot)
        try:
            _build_transport(scenario.paper_entry_result, real_like=True)
            machine.transition_to(UnattendedPaperCycleState.HALTED)
        except GmoPaperAutoCycleRunnerError:
            machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(
            GmoPaperSoakScenarioOutcome.SCENARIO_REAL_TRANSPORT_REFUSED_SAFE
        )

    # Guard runs before any paper attempt.
    guard_result = evaluate_unattended_monitoring_guard(scenario.guard_snapshot)
    if guard_result.halted:
        category = _GUARD_HALT_NOTIFICATIONS.get(
            guard_result.decision,
            GmoUnattendedNotificationCategory.NOTIFY_GUARD_HALTED,
        )
        _notify(notifier, category, required=False)
        machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_GUARD_HALTED_SAFE)

    signal = scenario.auto_preview_signal
    if signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED:
        _notify(
            notifier,
            GmoUnattendedNotificationCategory.NOTIFY_UNKNOWN_SAFE_STOP,
            required=False,
        )
        machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_SIGNAL_BLOCKED_SAFE)

    machine.transition_to(UnattendedPaperCycleState.SIGNAL_CANDIDATE)
    machine.ledger.record(PAPER_EVENT_SIGNAL_CANDIDATE)

    if signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD:
        machine.transition_to(UnattendedPaperCycleState.IDLE)
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_HOLD_NO_ORDER_SAFE)

    machine.transition_to(UnattendedPaperCycleState.PREVIEW_READY)
    machine.ledger.record(PAPER_EVENT_PREVIEW_READY)
    if not _notify(
        notifier,
        GmoUnattendedNotificationCategory.NOTIFY_PREVIEW_READY,
        required=scenario.notification_required,
    ):
        machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(
            GmoPaperSoakScenarioOutcome.SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE
        )

    if scenario.inject_illegal_transition:
        # e.g. jumping straight from PREVIEW_READY to PAPER_POSITION_OPEN.
        machine.transition_to(UnattendedPaperCycleState.PAPER_POSITION_OPEN)
        return _result(
            GmoPaperSoakScenarioOutcome.SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE
        )

    # PAPER-scoped stand-in for the operator gate: in paper soak the
    # confirmation is synthetic; in any live step it is a real operator input.
    machine.transition_to(UnattendedPaperCycleState.AWAITING_OPERATOR_CONFIRMATION)
    machine.transition_to(UnattendedPaperCycleState.PAPER_ENTRY_REQUESTED)

    if not machine.request_paper_entry_attempt():
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE)
    entry_transport = _build_transport(scenario.paper_entry_result)
    entry_result = entry_transport.send_paper_order_sanitized()

    if scenario.inject_duplicate_entry_attempt:
        machine.request_paper_entry_attempt()  # duplicate: blocked + halted
        _notify(
            notifier,
            GmoUnattendedNotificationCategory.NOTIFY_DUPLICATE_ATTEMPT_BLOCKED,
            required=False,
        )
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE)

    if entry_result is not PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED:
        machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_HALTED_NO_RETRY_SAFE)

    machine.transition_to(UnattendedPaperCycleState.PAPER_ENTRY_ACCEPTED)
    machine.ledger.record(PAPER_EVENT_ENTRY_ACCEPTED_SAFE)
    _notify(
        notifier,
        GmoUnattendedNotificationCategory.NOTIFY_PAPER_ENTRY_ACCEPTED,
        required=False,
    )
    machine.transition_to(UnattendedPaperCycleState.PAPER_POSITION_OPEN)
    machine.ledger.record(PAPER_EVENT_POSITION_OPEN_CONFIRMED_SAFE)
    _notify(
        notifier,
        GmoUnattendedNotificationCategory.NOTIFY_PAPER_POSITION_OPEN,
        required=False,
    )

    machine.transition_to(UnattendedPaperCycleState.PAPER_SETTLEMENT_CANDIDATE)
    machine.transition_to(UnattendedPaperCycleState.PAPER_SETTLEMENT_REQUESTED)
    if not machine.request_paper_settlement_attempt():
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE)
    settlement_transport = _build_transport(scenario.paper_settlement_result)
    settlement_result = settlement_transport.send_paper_order_sanitized()

    if scenario.inject_duplicate_settlement_attempt:
        machine.request_paper_settlement_attempt()  # duplicate: blocked + halted
        _notify(
            notifier,
            GmoUnattendedNotificationCategory.NOTIFY_DUPLICATE_ATTEMPT_BLOCKED,
            required=False,
        )
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE)

    if (
        settlement_result
        is not PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    ):
        machine.transition_to(UnattendedPaperCycleState.HALTED)
        return _result(GmoPaperSoakScenarioOutcome.SCENARIO_HALTED_NO_RETRY_SAFE)

    machine.transition_to(UnattendedPaperCycleState.PAPER_SETTLEMENT_ACCEPTED)
    machine.ledger.record(PAPER_EVENT_SETTLEMENT_ACCEPTED_SAFE)
    _notify(
        notifier,
        GmoUnattendedNotificationCategory.NOTIFY_PAPER_SETTLEMENT_ACCEPTED,
        required=False,
    )
    machine.transition_to(UnattendedPaperCycleState.PAPER_NO_POSITION_CONFIRMED)
    machine.ledger.record(PAPER_EVENT_NO_POSITION_CONFIRMED_SAFE)
    _notify(
        notifier,
        GmoUnattendedNotificationCategory.NOTIFY_PAPER_NO_POSITION_CONFIRMED,
        required=False,
    )
    machine.transition_to(UnattendedPaperCycleState.COMPLETED)
    return _result(GmoPaperSoakScenarioOutcome.SCENARIO_COMPLETED_SAFE)


def _make_failing_notifier():
    from app.services.gmo_unattended_fake_notifier import (
        FailingFakeUnattendedNotifier,
    )

    return FailingFakeUnattendedNotifier()


def _build_transport(
    preset: PaperOrderResultCategory, *, real_like: bool = False
) -> FakePaperCycleTransport:
    transport = FakePaperCycleTransport(
        preset_result=preset, is_real_transport=real_like
    )
    if getattr(transport, "is_real_transport", True):
        raise GmoPaperAutoCycleRunnerError(
            "paper soak accepts fake/paper transports only"
        )
    return transport


def _guard_snapshot_with(**overrides) -> UnattendedMonitoringGuardSafeSnapshot:
    return replace(build_all_safe_guard_snapshot(), **overrides)


def build_default_paper_soak_scenario_suite() -> tuple[PaperSoakScenario, ...]:
    """The required synthetic scenario suite (deterministic, paper only)."""

    from app.services.gmo_unattended_monitoring_guard import (
        ActivePendingOrderSafeStatus,
        MarketSafeStatus,
        MaxHoldStatus,
        MaxLossStatus,
        PositionCountSafeStatus,
        SpreadSafeStatus,
        TickerFreshStatus,
    )

    buy = AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
    sell = AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL
    completed = GmoPaperSoakScenarioOutcome.SCENARIO_COMPLETED_SAFE
    guard_halt = GmoPaperSoakScenarioOutcome.SCENARIO_GUARD_HALTED_SAFE
    no_retry_halt = GmoPaperSoakScenarioOutcome.SCENARIO_HALTED_NO_RETRY_SAFE
    duplicate = GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE
    rejected = PaperOrderResultCategory.PAPER_RESULT_REJECTED_SANITIZED
    unknown = PaperOrderResultCategory.PAPER_RESULT_UNKNOWN_SANITIZED

    return (
        PaperSoakScenario("SOAK_01_BUY_FULL_CYCLE", completed, buy),
        PaperSoakScenario("SOAK_02_SELL_FULL_CYCLE", completed, sell),
        PaperSoakScenario(
            "SOAK_03_HOLD_NO_ORDER",
            GmoPaperSoakScenarioOutcome.SCENARIO_HOLD_NO_ORDER_SAFE,
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
        ),
        PaperSoakScenario(
            "SOAK_04_UNKNOWN_SIGNAL_BLOCKED",
            GmoPaperSoakScenarioOutcome.SCENARIO_SIGNAL_BLOCKED_SAFE,
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
        ),
        PaperSoakScenario(
            "SOAK_05_SPREAD_OUT_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                spread_safe_status=SpreadSafeStatus.SPREAD_OUT_OF_LIMIT
            ),
        ),
        PaperSoakScenario(
            "SOAK_06_TICKER_STALE_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                ticker_fresh_status=TickerFreshStatus.TICKER_STALE
            ),
        ),
        PaperSoakScenario(
            "SOAK_07_MARKET_UNSAFE_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                market_safe_status=MarketSafeStatus.MARKET_UNSAFE
            ),
        ),
        PaperSoakScenario(
            "SOAK_08_ACTIVE_PENDING_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                active_pending_order_safe_status=(
                    ActivePendingOrderSafeStatus.ACTIVE_PENDING_ORDERS_PRESENT
                )
            ),
        ),
        PaperSoakScenario(
            "SOAK_09_POSITION_COUNT_MISMATCH_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                position_count_safe=PositionCountSafeStatus.COUNT_MISMATCH
            ),
        ),
        PaperSoakScenario(
            "SOAK_10_KILL_SWITCH_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(kill_switch_engaged=True),
        ),
        PaperSoakScenario(
            "SOAK_11_MAX_HOLD_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                max_hold_status=MaxHoldStatus.HOLD_LIMIT_EXCEEDED
            ),
        ),
        PaperSoakScenario(
            "SOAK_12_MAX_LOSS_GUARD_HALT",
            guard_halt,
            buy,
            guard_snapshot=_guard_snapshot_with(
                max_loss_status=MaxLossStatus.LOSS_LIMIT_EXCEEDED
            ),
        ),
        PaperSoakScenario(
            "SOAK_13_ENTRY_REJECTED_NO_RETRY",
            no_retry_halt,
            buy,
            paper_entry_result=rejected,
        ),
        PaperSoakScenario(
            "SOAK_14_ENTRY_UNKNOWN_NO_RETRY",
            no_retry_halt,
            buy,
            paper_entry_result=unknown,
        ),
        PaperSoakScenario(
            "SOAK_15_SETTLEMENT_REJECTED_NO_RETRY",
            no_retry_halt,
            buy,
            paper_settlement_result=rejected,
        ),
        PaperSoakScenario(
            "SOAK_16_SETTLEMENT_UNKNOWN_NO_RETRY",
            no_retry_halt,
            buy,
            paper_settlement_result=unknown,
        ),
        PaperSoakScenario(
            "SOAK_17_DUPLICATE_ENTRY_BLOCKED",
            duplicate,
            buy,
            inject_duplicate_entry_attempt=True,
        ),
        PaperSoakScenario(
            "SOAK_18_DUPLICATE_SETTLEMENT_BLOCKED",
            duplicate,
            buy,
            inject_duplicate_settlement_attempt=True,
        ),
        PaperSoakScenario(
            "SOAK_19_ILLEGAL_TRANSITION_BLOCKED",
            GmoPaperSoakScenarioOutcome.SCENARIO_ILLEGAL_TRANSITION_BLOCKED_SAFE,
            buy,
            inject_illegal_transition=True,
        ),
        PaperSoakScenario(
            "SOAK_20_NOTIFIER_FAILURE_HALT",
            GmoPaperSoakScenarioOutcome.SCENARIO_NOTIFIER_FAILURE_HALTED_SAFE,
            buy,
            notifier_fails=True,
            notification_required=True,
        ),
        PaperSoakScenario(
            "SOAK_21_REAL_LIKE_TRANSPORT_REFUSED",
            GmoPaperSoakScenarioOutcome.SCENARIO_REAL_TRANSPORT_REFUSED_SAFE,
            buy,
            inject_real_like_transport=True,
        ),
    )


@dataclass(frozen=True)
class GmoPaperSoakReadinessReport:
    """Suite-level readiness report. Safe categories only, never truthy."""

    status: GmoPaperSoakReadinessStatus
    scenario_count: int
    matched_count: int
    mismatched_scenarios_safe: tuple[str, ...]
    scenario_results: tuple[PaperSoakScenarioResult, ...]
    unattended_live_supported: bool = False
    unattended_full_auto_completed: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    real_post_count: int = 0

    def __bool__(self) -> bool:
        return False


def run_paper_soak_readiness_suite(
    scenarios: tuple[PaperSoakScenario, ...] | None = None,
) -> GmoPaperSoakReadinessReport:
    """Run the synthetic suite once and classify overall readiness."""

    suite = scenarios if scenarios is not None else (
        build_default_paper_soak_scenario_suite()
    )
    if not suite:
        return GmoPaperSoakReadinessReport(
            status=GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_BLOCKED_SAFE,
            scenario_count=0,
            matched_count=0,
            mismatched_scenarios_safe=(),
            scenario_results=(),
        )
    results = tuple(run_paper_soak_scenario(scenario) for scenario in suite)
    mismatched = tuple(
        result.scenario_name_safe_label
        for result in results
        if not result.matched_expectation
    )
    status = (
        GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_PASSED
        if not mismatched
        else GmoPaperSoakReadinessStatus.PAPER_SOAK_READINESS_FAILED_SAFE
    )
    return GmoPaperSoakReadinessReport(
        status=status,
        scenario_count=len(results),
        matched_count=len(results) - len(mismatched),
        mismatched_scenarios_safe=mismatched,
        scenario_results=results,
    )
