"""No-POST runtime state projection for persistent ARM operation.

ARM is operator intent. Entry eligibility is a separate runtime decision. This
module only projects safe local evidence into a state and never reads a
credential, calls a broker, sends a notification, or issues a permit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class V4UnattendedRuntimeState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


class V4UnattendedRuntimeProjectionError(RuntimeError):
    """Fail-closed state projection error containing safe labels only."""


@dataclass(frozen=True)
class V4UnattendedRuntimeEvidence:
    arm_armed: bool
    position_open: bool
    protection_confirmed: bool
    ownership_exact: bool
    quantity_matches: bool
    runtime_clear: bool
    generation_matches: bool
    pending_transport: bool
    unknown_halt: bool
    heartbeat_alive: bool
    process_lock_clear: bool
    dead_man_alive: bool
    entry_gate_open: bool

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in self.__dict__.values()):
            raise V4UnattendedRuntimeProjectionError(
                "RUNTIME_EVIDENCE_BOOLEAN_INVALID"
            )

    def __bool__(self) -> bool:
        return False


def project_unattended_runtime_state(
    evidence: V4UnattendedRuntimeEvidence,
) -> V4UnattendedRuntimeState:
    """Project local evidence without turning any result into broker authority."""

    if type(evidence) is not V4UnattendedRuntimeEvidence:
        raise V4UnattendedRuntimeProjectionError("RUNTIME_EVIDENCE_TYPE_INVALID")
    if evidence.pending_transport or evidence.unknown_halt:
        return V4UnattendedRuntimeState.HALTED
    if not (
        evidence.generation_matches
        and evidence.heartbeat_alive
        and evidence.process_lock_clear
        and evidence.dead_man_alive
        and evidence.runtime_clear
    ):
        return V4UnattendedRuntimeState.HALTED
    if evidence.position_open:
        if not (
            evidence.protection_confirmed
            and evidence.ownership_exact
            and evidence.quantity_matches
        ):
            return V4UnattendedRuntimeState.HALTED
        return (
            V4UnattendedRuntimeState.ON_EXIT_ONLY
            if evidence.arm_armed
            else V4UnattendedRuntimeState.EXIT_ONLY
        )
    if not evidence.arm_armed:
        return V4UnattendedRuntimeState.OFF
    return V4UnattendedRuntimeState.ON_WAITING


def entry_evaluation_allowed(
    *,
    evidence: V4UnattendedRuntimeEvidence,
    state: V4UnattendedRuntimeState,
) -> bool:
    """Return whether a fresh signal may be evaluated for a new entry."""

    if type(state) is not V4UnattendedRuntimeState:
        raise V4UnattendedRuntimeProjectionError("RUNTIME_STATE_INVALID")
    return (
        state is V4UnattendedRuntimeState.ON_WAITING
        and evidence.arm_armed
        and evidence.entry_gate_open
    )


def exit_management_required(
    *,
    evidence: V4UnattendedRuntimeEvidence,
    state: V4UnattendedRuntimeState,
) -> bool:
    """Keep position management active independently of the ARM switch."""

    if type(state) is not V4UnattendedRuntimeState:
        raise V4UnattendedRuntimeProjectionError("RUNTIME_STATE_INVALID")
    return evidence.position_open
