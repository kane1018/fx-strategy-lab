"""Paper auto cycle runner (fake transport only, no-POST, fail-closed).

Runs the full automation-shaped cycle -- auto preview signal in, paper entry,
paper one-position confirmation, paper settlement, paper no-position
confirmation -- WITHOUT any real broker surface:

- Fake/paper transports only: a transport whose ``is_real_transport`` is
  true is refused before anything else. No HTTP, no private GET, no
  credential, no ``.env``, no local sealed value file read exist here.
- The input signal is an AUTO preview label (``AUTO_PREVIEW_SIGNAL_BUY`` /
  ``_SELL`` / ``_HOLD`` / ``_UNKNOWN_BLOCKED``). It is NEVER the operator
  safe label (ENTRY_BUY / ENTRY_SELL / HOLD), never becomes one, and never
  substitutes an operator current-turn confirmation.
- One paper entry maximum and one paper settlement maximum per run. There
  is no retry, repost, or second-attempt branch in this module at all;
  any non-accepted paper outcome ends the cycle in a safe stop state.
- Every result field is a safe label, safe count, or fixed-false flag.
  ``actual_entry_POST_allowed`` / ``actual_settlement_POST_allowed`` are
  hardcoded false and results are never truthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class GmoPaperAutoCycleRunnerError(RuntimeError):
    """Raised for fail-closed violations. Never carries a raw value."""


class AutoPreviewSignal(str, Enum):
    """Automation preview labels. NEVER an operator signal safe label."""

    AUTO_PREVIEW_SIGNAL_BUY = "AUTO_PREVIEW_SIGNAL_BUY"
    AUTO_PREVIEW_SIGNAL_SELL = "AUTO_PREVIEW_SIGNAL_SELL"
    AUTO_PREVIEW_SIGNAL_HOLD = "AUTO_PREVIEW_SIGNAL_HOLD"
    AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED = "AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED"


# Operator safe labels, listed only to reject them: an auto runner must never
# accept an operator label in place of an auto preview label.
_OPERATOR_SIGNAL_SAFE_LABELS = frozenset({"ENTRY_BUY", "ENTRY_SELL", "HOLD"})


class PaperOrderResultCategory(str, Enum):
    """Sanitized paper outcomes only. Never raw/ID/value."""

    PAPER_RESULT_ACCEPTED_SANITIZED = "PAPER_RESULT_ACCEPTED_SANITIZED"
    PAPER_RESULT_REJECTED_SANITIZED = "PAPER_RESULT_REJECTED_SANITIZED"
    PAPER_RESULT_UNKNOWN_SANITIZED = "PAPER_RESULT_UNKNOWN_SANITIZED"


@runtime_checkable
class PaperCycleTransport(Protocol):
    """Paper-only transport. Returns a sanitized paper category only."""

    def send_paper_order_sanitized(self) -> PaperOrderResultCategory:
        """Simulate exactly one paper order; return a sanitized category."""


@dataclass(frozen=True)
class FakePaperCycleTransport:
    """Deterministic paper transport for tests and scenarios. No network."""

    preset_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )
    is_real_transport: bool = False

    def send_paper_order_sanitized(self) -> PaperOrderResultCategory:
        return self.preset_result


@dataclass(frozen=True)
class PaperMarketScenarioSafeInput:
    """Synthetic scenario expressed as safe booleans only. Default-deny."""

    market_open_safe: bool = False
    ticker_fresh_safe: bool = False
    spread_within_limit_safe: bool = False
    paper_position_flat_safe: bool = False
    active_pending_clear_safe: bool = False


class GmoPaperAutoCycleStatus(str, Enum):
    PAPER_CYCLE_COMPLETE = "PAPER_CYCLE_COMPLETE"
    PAPER_CYCLE_HOLD_NO_ORDER = "PAPER_CYCLE_HOLD_NO_ORDER"
    PAPER_CYCLE_BLOCKED_SIGNAL_UNKNOWN = "PAPER_CYCLE_BLOCKED_SIGNAL_UNKNOWN"
    PAPER_CYCLE_BLOCKED_SCENARIO_GATE = "PAPER_CYCLE_BLOCKED_SCENARIO_GATE"
    PAPER_CYCLE_STOPPED_ENTRY_NOT_ACCEPTED = (
        "PAPER_CYCLE_STOPPED_ENTRY_NOT_ACCEPTED"
    )
    PAPER_CYCLE_STOPPED_SETTLEMENT_NOT_ACCEPTED = (
        "PAPER_CYCLE_STOPPED_SETTLEMENT_NOT_ACCEPTED"
    )


@dataclass(frozen=True)
class GmoPaperAutoCycleResult:
    """Safe labels / counts / fixed-false flags only. Never truthy."""

    status: GmoPaperAutoCycleStatus
    auto_preview_signal: AutoPreviewSignal
    paper_entry_order_kind_safe_label: str
    paper_settlement_side_safe_label: str
    paper_entry_attempt_count: int
    paper_settlement_attempt_count: int
    paper_entry_result: PaperOrderResultCategory | None
    paper_settlement_result: PaperOrderResultCategory | None
    paper_position_states_safe: tuple[str, ...]
    event_log_safe_labels: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
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
    operator_confirmation_banked: bool = False
    operator_confirmation_substituted: bool = False

    def __bool__(self) -> bool:
        return False


# Mechanical mapping from auto preview labels to PAPER-only order labels.
# These labels are paper-scoped on purpose so they can never be mistaken for
# the live gate's ENTRY_OPEN_* / SETTLEMENT_* labels.
_AUTO_SIGNAL_TO_PAPER_ORDER = {
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY: (
        "PAPER_ENTRY_OPEN_BUY",
        "PAPER_SETTLEMENT_SELL",
    ),
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL: (
        "PAPER_ENTRY_OPEN_SELL",
        "PAPER_SETTLEMENT_BUY",
    ),
}

_SCENARIO_GATE_REASONS: tuple[tuple[str, str], ...] = (
    ("market_open_safe", "PAPER_MARKET_NOT_OPEN_BLOCKED"),
    ("ticker_fresh_safe", "PAPER_TICKER_NOT_FRESH_BLOCKED"),
    ("spread_within_limit_safe", "PAPER_SPREAD_NOT_WITHIN_LIMIT_BLOCKED"),
    ("paper_position_flat_safe", "PAPER_POSITION_NOT_FLAT_BLOCKED"),
    ("active_pending_clear_safe", "PAPER_ACTIVE_PENDING_NOT_CLEAR_BLOCKED"),
)


def _assert_paper_transport(transport: PaperCycleTransport, role: str) -> None:
    if getattr(transport, "is_real_transport", True):
        raise GmoPaperAutoCycleRunnerError(
            f"paper auto cycle runner accepts fake/paper transports only "
            f"({role} transport looks real or unmarked)"
        )


def _stopped(
    *,
    status: GmoPaperAutoCycleStatus,
    signal: AutoPreviewSignal,
    entry_kind: str = "",
    settlement_side: str = "",
    entry_attempts: int = 0,
    settlement_attempts: int = 0,
    entry_result: PaperOrderResultCategory | None = None,
    settlement_result: PaperOrderResultCategory | None = None,
    positions: tuple[str, ...] = (),
    events: tuple[str, ...] = (),
    reasons: tuple[str, ...] = (),
) -> GmoPaperAutoCycleResult:
    return GmoPaperAutoCycleResult(
        status=status,
        auto_preview_signal=signal,
        paper_entry_order_kind_safe_label=entry_kind,
        paper_settlement_side_safe_label=settlement_side,
        paper_entry_attempt_count=entry_attempts,
        paper_settlement_attempt_count=settlement_attempts,
        paper_entry_result=entry_result,
        paper_settlement_result=settlement_result,
        paper_position_states_safe=positions,
        event_log_safe_labels=events,
        blocked_reasons=reasons,
    )


def run_gmo_paper_auto_cycle_once(
    *,
    auto_preview_signal: AutoPreviewSignal | str,
    scenario: PaperMarketScenarioSafeInput,
    entry_transport: PaperCycleTransport,
    settlement_transport: PaperCycleTransport,
) -> GmoPaperAutoCycleResult:
    """Run at most one full PAPER cycle and never resend on any outcome.

    Fail-closed order of checks: transports must be paper-only, the signal
    must be an auto preview label (an operator safe label is rejected with an
    exception so it can never silently drive an auto path), HOLD makes no
    paper order, UNKNOWN blocks, and every scenario gate must be safe before
    the single paper entry. A non-accepted paper entry or settlement stops
    the cycle immediately -- there is no retry branch in this function.
    """

    _assert_paper_transport(entry_transport, "entry")
    _assert_paper_transport(settlement_transport, "settlement")

    if isinstance(auto_preview_signal, str) and not isinstance(
        auto_preview_signal, AutoPreviewSignal
    ):
        if auto_preview_signal in _OPERATOR_SIGNAL_SAFE_LABELS:
            raise GmoPaperAutoCycleRunnerError(
                "operator signal safe labels are rejected here: the paper "
                "auto runner accepts AUTO_PREVIEW_SIGNAL_* labels only"
            )
        try:
            auto_preview_signal = AutoPreviewSignal(auto_preview_signal)
        except ValueError:
            auto_preview_signal = (
                AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
            )

    signal = auto_preview_signal
    if signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED:
        return _stopped(
            status=GmoPaperAutoCycleStatus.PAPER_CYCLE_BLOCKED_SIGNAL_UNKNOWN,
            signal=signal,
            events=("PAPER_EVENT_SIGNAL_UNKNOWN_HARD_STOP",),
            reasons=("AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED",),
        )
    if signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD:
        return _stopped(
            status=GmoPaperAutoCycleStatus.PAPER_CYCLE_HOLD_NO_ORDER,
            signal=signal,
            events=("PAPER_EVENT_HOLD_NO_ORDER",),
        )

    gate_reasons = tuple(
        reason
        for field_name, reason in _SCENARIO_GATE_REASONS
        if not getattr(scenario, field_name)
    )
    if gate_reasons:
        return _stopped(
            status=GmoPaperAutoCycleStatus.PAPER_CYCLE_BLOCKED_SCENARIO_GATE,
            signal=signal,
            events=("PAPER_EVENT_SCENARIO_GATE_BLOCKED",),
            reasons=gate_reasons,
        )

    entry_kind, settlement_side = _AUTO_SIGNAL_TO_PAPER_ORDER[signal]
    events: list[str] = ["PAPER_EVENT_CYCLE_STARTED"]
    positions: list[str] = ["PAPER_NO_POSITION"]

    # Exactly one paper entry attempt.
    events.append("PAPER_EVENT_ENTRY_SENT_ONCE")
    entry_result = entry_transport.send_paper_order_sanitized()
    if entry_result is not PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED:
        events.append("PAPER_EVENT_ENTRY_NOT_ACCEPTED_HARD_STOP")
        return _stopped(
            status=(
                GmoPaperAutoCycleStatus.PAPER_CYCLE_STOPPED_ENTRY_NOT_ACCEPTED
            ),
            signal=signal,
            entry_kind=entry_kind,
            settlement_side=settlement_side,
            entry_attempts=1,
            entry_result=entry_result,
            positions=tuple(positions),
            events=tuple(events),
            reasons=(entry_result.value,),
        )

    positions.append("PAPER_ONE_POSITION_OPEN")
    events.append("PAPER_EVENT_ONE_POSITION_OPEN_CONFIRMED")

    # Exactly one paper settlement attempt.
    events.append("PAPER_EVENT_SETTLEMENT_SENT_ONCE")
    settlement_result = settlement_transport.send_paper_order_sanitized()
    if (
        settlement_result
        is not PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    ):
        events.append("PAPER_EVENT_SETTLEMENT_NOT_ACCEPTED_HARD_STOP")
        return _stopped(
            status=(
                GmoPaperAutoCycleStatus
                .PAPER_CYCLE_STOPPED_SETTLEMENT_NOT_ACCEPTED
            ),
            signal=signal,
            entry_kind=entry_kind,
            settlement_side=settlement_side,
            entry_attempts=1,
            settlement_attempts=1,
            entry_result=entry_result,
            settlement_result=settlement_result,
            positions=tuple(positions),
            events=tuple(events),
            reasons=(settlement_result.value,),
        )

    positions.append("PAPER_NO_POSITION")
    events.append("PAPER_EVENT_NO_POSITION_CONFIRMED")
    events.append("PAPER_EVENT_CYCLE_COMPLETE")
    return _stopped(
        status=GmoPaperAutoCycleStatus.PAPER_CYCLE_COMPLETE,
        signal=signal,
        entry_kind=entry_kind,
        settlement_side=settlement_side,
        entry_attempts=1,
        settlement_attempts=1,
        entry_result=entry_result,
        settlement_result=settlement_result,
        positions=tuple(positions),
        events=tuple(events),
    )


@dataclass(frozen=True)
class PaperAutoCycleScenario:
    """A named deterministic scenario for repeatable paper runs."""

    scenario_name_safe_label: str
    auto_preview_signal: AutoPreviewSignal
    scenario: PaperMarketScenarioSafeInput = field(
        default_factory=PaperMarketScenarioSafeInput
    )
    entry_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )
    settlement_result: PaperOrderResultCategory = (
        PaperOrderResultCategory.PAPER_RESULT_ACCEPTED_SANITIZED
    )


def run_paper_auto_cycle_scenario(
    scenario: PaperAutoCycleScenario,
) -> GmoPaperAutoCycleResult:
    """Run one named deterministic scenario with fake transports only."""

    return run_gmo_paper_auto_cycle_once(
        auto_preview_signal=scenario.auto_preview_signal,
        scenario=scenario.scenario,
        entry_transport=FakePaperCycleTransport(
            preset_result=scenario.entry_result
        ),
        settlement_transport=FakePaperCycleTransport(
            preset_result=scenario.settlement_result
        ),
    )


def build_all_safe_paper_scenario_input() -> PaperMarketScenarioSafeInput:
    """Convenience all-green scenario input for tests and demos."""

    return PaperMarketScenarioSafeInput(
        market_open_safe=True,
        ticker_fresh_safe=True,
        spread_within_limit_safe=True,
        paper_position_flat_safe=True,
        active_pending_clear_safe=True,
    )
