"""Fake, synthetic-fixture-only Level 5 full auto cycle simulation.

The production GMO order-write broker's entry and settlement methods
deliberately have no real transport implemented yet -- both always raise
after the shared hard guard, by design (see
docs/GMO_LIVE_AUTOMATION_RESUME_DESIGN.md). There is therefore no way to
drive an actual "successful" cycle through that broker itself in this Step,
fake or otherwise. This module instead simulates the cycle at the
state-machine level: it takes safe-label/safe-boolean inputs that represent
what a fresh entry gate, fresh position read, official settlement gate, and
fresh post-settlement read would have reported, and computes whether the
cycle counts as a completed Level 5 full auto cycle.

`level5_full_auto_cycle_completed` is true only when every step reports
success, no retry/repost/generic-close was attempted, no manual
intervention occurred, and the kill switch never tripped during the cycle.
Any rejection, unknown/timeout result, or manual step makes it false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoLevel5ResultCategory(str, Enum):
    ACCEPTED_SANITIZED = "ACCEPTED_SANITIZED"
    REJECTED_SANITIZED = "REJECTED_SANITIZED"
    UNKNOWN_SANITIZED = "UNKNOWN_SANITIZED"


class GmoLevel5PositionStatus(str, Enum):
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    NO_POSITION = "NO_POSITION"
    MULTIPLE_POSITIONS = "MULTIPLE_POSITIONS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GmoLevel5FakeCycleInput:
    entry_signal_safe_label_present: bool
    entry_result_category: str
    post_entry_position_status: str
    settlement_result_category: str
    post_settlement_position_status: str
    manual_intervention_performed: bool = False
    retry_attempted: bool = False
    repost_attempted: bool = False
    generic_close_attempted: bool = False
    kill_switch_triggered_during_cycle: bool = False


@dataclass(frozen=True)
class GmoLevel5FakeCycleResult:
    level5_full_auto_cycle_completed: bool
    blocked_reasons: tuple[str, ...]


def simulate_gmo_level5_fake_cycle(
    cycle_input: GmoLevel5FakeCycleInput,
) -> GmoLevel5FakeCycleResult:
    reasons: list[str] = []
    if not cycle_input.entry_signal_safe_label_present:
        reasons.append("entry_signal_missing")
    if cycle_input.entry_result_category != GmoLevel5ResultCategory.ACCEPTED_SANITIZED.value:
        reasons.append("entry_not_accepted")
    if cycle_input.post_entry_position_status != GmoLevel5PositionStatus.ONE_POSITION_OPEN.value:
        reasons.append("post_entry_position_not_confirmed")
    if (
        cycle_input.settlement_result_category
        != GmoLevel5ResultCategory.ACCEPTED_SANITIZED.value
    ):
        reasons.append("settlement_not_accepted")
    if (
        cycle_input.post_settlement_position_status
        != GmoLevel5PositionStatus.NO_POSITION.value
    ):
        reasons.append("post_settlement_position_not_confirmed")
    if cycle_input.manual_intervention_performed:
        reasons.append("manual_intervention_performed")
    if cycle_input.retry_attempted:
        reasons.append("retry_attempted")
    if cycle_input.repost_attempted:
        reasons.append("repost_attempted")
    if cycle_input.generic_close_attempted:
        reasons.append("generic_close_attempted")
    if cycle_input.kill_switch_triggered_during_cycle:
        reasons.append("kill_switch_triggered_during_cycle")
    return GmoLevel5FakeCycleResult(
        level5_full_auto_cycle_completed=not reasons,
        blocked_reasons=tuple(reasons),
    )
