from __future__ import annotations

import pytest

from app.services.h11_v4_unattended_runtime_no_post import (
    V4UnattendedRuntimeEvidence,
    V4UnattendedRuntimeProjectionError,
    V4UnattendedRuntimeState,
    entry_evaluation_allowed,
    exit_management_required,
    project_unattended_runtime_state,
)


def _evidence(**overrides: bool) -> V4UnattendedRuntimeEvidence:
    values = {
        "arm_armed": True,
        "position_open": False,
        "protection_confirmed": False,
        "ownership_exact": False,
        "quantity_matches": False,
        "runtime_clear": True,
        "generation_matches": True,
        "pending_transport": False,
        "unknown_halt": False,
        "heartbeat_alive": True,
        "process_lock_clear": True,
        "dead_man_alive": True,
        "entry_gate_open": True,
    }
    values.update(overrides)
    return V4UnattendedRuntimeEvidence(**values)


def test_arm_on_flat_projects_to_waiting_and_allows_entry_evaluation() -> None:
    evidence = _evidence()
    state = project_unattended_runtime_state(evidence)
    assert state is V4UnattendedRuntimeState.ON_WAITING
    assert entry_evaluation_allowed(evidence=evidence, state=state) is True
    assert exit_management_required(evidence=evidence, state=state) is False


def test_arm_on_protected_position_projects_to_exit_only() -> None:
    evidence = _evidence(
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
    )
    state = project_unattended_runtime_state(evidence)
    assert state is V4UnattendedRuntimeState.ON_EXIT_ONLY
    assert entry_evaluation_allowed(evidence=evidence, state=state) is False
    assert exit_management_required(evidence=evidence, state=state) is True


def test_arm_off_keeps_exit_management_for_protected_position() -> None:
    evidence = _evidence(
        arm_armed=False,
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        entry_gate_open=False,
    )
    state = project_unattended_runtime_state(evidence)
    assert state is V4UnattendedRuntimeState.EXIT_ONLY
    assert entry_evaluation_allowed(evidence=evidence, state=state) is False
    assert exit_management_required(evidence=evidence, state=state) is True


@pytest.mark.parametrize(
    "overrides",
    (
        {"protection_confirmed": False},
        {"ownership_exact": False},
        {"quantity_matches": False},
        {"pending_transport": True},
        {"unknown_halt": True},
        {"heartbeat_alive": False},
        {"process_lock_clear": False},
        {"dead_man_alive": False},
        {"generation_matches": False},
    ),
)
def test_unsafe_position_or_runtime_projects_to_halted(overrides: dict[str, bool]) -> None:
    evidence = _evidence(position_open=True, **overrides)
    assert project_unattended_runtime_state(evidence) is V4UnattendedRuntimeState.HALTED


def test_invalid_evidence_type_fails_closed() -> None:
    with pytest.raises(
        V4UnattendedRuntimeProjectionError, match="RUNTIME_EVIDENCE_TYPE_INVALID"
    ):
        project_unattended_runtime_state(object())  # type: ignore[arg-type]
