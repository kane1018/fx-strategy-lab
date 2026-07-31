"""No-POST runtime state projection for persistent ARM operation.

ARM is operator intent. Entry eligibility is a separate runtime decision. This
module only projects safe local evidence into a state and never reads a
credential, calls a broker, sends a notification, or issues a permit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class V4UnattendedRuntimeState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


class V4UnattendedRuntimeProjectionError(RuntimeError):
    """Fail-closed state projection error containing safe labels only."""


_SUPERVISOR_HEARTBEAT_FILENAME = "supervisor-heartbeat.json"
_HEARTBEAT_BOOLEAN_FIELDS = (
    "runtime_risk_ready",
    "dead_man_alive",
    "heartbeat_chain_beat",
    "persistent_halt",
    "generation_bound",
    "cycle_present",
    "protection_confirmed",
    "ownership_exact",
    "quantity_matches",
    "pending_transport",
    "unknown_halt",
    "entry_gate_open",
)


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


def _halted_evidence(*, arm_armed: bool) -> V4UnattendedRuntimeEvidence:
    return V4UnattendedRuntimeEvidence(
        arm_armed=arm_armed,
        position_open=False,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        runtime_clear=False,
        generation_matches=False,
        pending_transport=False,
        unknown_halt=True,
        heartbeat_alive=False,
        process_lock_clear=False,
        dead_man_alive=False,
        entry_gate_open=False,
    )


def load_unattended_runtime_evidence_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    arm_armed: bool,
    now_utc: datetime | None = None,
    maximum_age_seconds: int = 60,
) -> V4UnattendedRuntimeEvidence:
    """Read only the supervisor's safe heartbeat aggregate."""

    if type(arm_armed) is not bool or type(maximum_age_seconds) is not int:
        raise V4UnattendedRuntimeProjectionError("RUNTIME_EVIDENCE_INPUT_INVALID")
    if maximum_age_seconds <= 0:
        raise V4UnattendedRuntimeProjectionError("RUNTIME_EVIDENCE_AGE_INVALID")
    path = state_root / _SUPERVISOR_HEARTBEAT_FILENAME
    if path.is_symlink() or not path.is_file():
        return _halted_evidence(arm_armed=arm_armed)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _halted_evidence(arm_armed=arm_armed)
    if not isinstance(payload, dict):
        return _halted_evidence(arm_armed=arm_armed)
    if payload.get("generation_digest") != generation_digest:
        return _halted_evidence(arm_armed=arm_armed)
    observed_raw = payload.get("observed_at_utc")
    if not isinstance(observed_raw, str):
        return _halted_evidence(arm_armed=arm_armed)
    try:
        observed_at = datetime.fromisoformat(observed_raw).astimezone(UTC)
    except ValueError:
        return _halted_evidence(arm_armed=arm_armed)
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    age = (now - observed_at).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        return _halted_evidence(arm_armed=arm_armed)
    if any(type(payload.get(field)) is not bool for field in _HEARTBEAT_BOOLEAN_FIELDS):
        return _halted_evidence(arm_armed=arm_armed)
    position_open = payload["cycle_present"]
    persistent_halt = payload["persistent_halt"]
    return V4UnattendedRuntimeEvidence(
        arm_armed=arm_armed,
        position_open=position_open,
        protection_confirmed=(
            payload["protection_confirmed"] if position_open else True
        ),
        ownership_exact=(payload["ownership_exact"] if position_open else True),
        quantity_matches=(payload["quantity_matches"] if position_open else True),
        runtime_clear=payload["runtime_risk_ready"] and not persistent_halt,
        generation_matches=payload["generation_bound"],
        pending_transport=payload["pending_transport"],
        unknown_halt=payload["unknown_halt"] or persistent_halt,
        heartbeat_alive=payload["heartbeat_chain_beat"],
        process_lock_clear=payload["generation_bound"],
        dead_man_alive=payload["dead_man_alive"],
        entry_gate_open=payload["entry_gate_open"],
    )


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
