from __future__ import annotations

import json
import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    render_v4_gmo_unattended_scheduler_launchagent,
)
from app.services.h11_v4_g064_position_reconciliation_no_post import (
    load_g064_position_reconciliation_no_post,
    write_g064_position_reconciliation_no_post,
)
from app.services.h11_v4_g064_unattended_activation import (
    G064_GENERATION_LABEL,
    V4G064ActivationError,
    g064_worker_lease_alive,
    verify_g064_generation_activation,
    write_g064_runtime_evidence_no_post,
    write_g064_scheduler_service_evidence,
    write_g064_worker_lease,
)
from app.services.h11_v4_unattended_runtime_no_post import (
    V4UnattendedRuntimeEvidence,
    V4UnattendedRuntimeState,
    entry_evaluation_allowed,
    load_unattended_runtime_evidence_no_post,
    project_unattended_runtime_state,
)

NOW = datetime(2026, 8, 1, 1, 0, tzinfo=UTC)
GENERATION = "sha256:" + "a" * 64
REVIEWED = "sha256:" + "b" * 64


def _evidence(*, armed: bool, position: bool, process_lock: bool = True):
    return V4UnattendedRuntimeEvidence(
        arm_armed=armed,
        position_open=position,
        protection_confirmed=not position or True,
        ownership_exact=not position or True,
        quantity_matches=not position or True,
        runtime_clear=True,
        generation_matches=True,
        pending_transport=False,
        unknown_halt=False,
        heartbeat_alive=True,
        process_lock_clear=process_lock,
        dead_man_alive=True,
        entry_gate_open=armed and not position,
    )


def test_switch_only_state_machine_keeps_exit_management_after_off() -> None:
    off = project_unattended_runtime_state(_evidence(armed=False, position=False))
    waiting = project_unattended_runtime_state(_evidence(armed=True, position=False))
    exit_only = project_unattended_runtime_state(_evidence(armed=False, position=True))
    on_exit = project_unattended_runtime_state(_evidence(armed=True, position=True))

    assert off is V4UnattendedRuntimeState.OFF
    assert waiting is V4UnattendedRuntimeState.ON_WAITING
    assert exit_only is V4UnattendedRuntimeState.EXIT_ONLY
    assert on_exit is V4UnattendedRuntimeState.ON_EXIT_ONLY
    assert entry_evaluation_allowed(
        evidence=_evidence(armed=True, position=False), state=waiting
    )
    assert not entry_evaluation_allowed(
        evidence=_evidence(armed=True, position=True), state=on_exit
    )


def test_process_lock_is_not_derived_from_generation_binding() -> None:
    state = project_unattended_runtime_state(
        _evidence(armed=True, position=False, process_lock=False)
    )
    assert state is V4UnattendedRuntimeState.HALTED


def test_missing_position_proof_cannot_project_on_exit_only() -> None:
    evidence = _evidence(armed=True, position=True)
    evidence = V4UnattendedRuntimeEvidence(
        **{
            **evidence.__dict__,
            "protection_confirmed": False,
            "ownership_exact": False,
            "quantity_matches": False,
        }
    )
    assert project_unattended_runtime_state(evidence) is V4UnattendedRuntimeState.HALTED


def test_heartbeat_requires_explicit_process_lock_field(tmp_path: Path) -> None:
    path = tmp_path / "supervisor-heartbeat.json"
    payload = {
        "generation_digest": GENERATION,
        "observed_at_utc": NOW.isoformat(),
        "runtime_risk_ready": True,
        "dead_man_alive": True,
        "heartbeat_chain_beat": True,
        "persistent_halt": False,
        "generation_bound": True,
        "cycle_present": False,
        "protection_confirmed": True,
        "ownership_exact": True,
        "quantity_matches": True,
        "pending_transport": False,
        "unknown_halt": False,
        "entry_gate_open": True,
        "process_lock_clear": False,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    evidence = load_unattended_runtime_evidence_no_post(
        state_root=tmp_path,
        generation_digest=GENERATION,
        arm_armed=True,
        now_utc=NOW,
    )
    assert project_unattended_runtime_state(evidence) is V4UnattendedRuntimeState.HALTED


def test_g064_position_evidence_is_generation_bound_and_explicit(tmp_path: Path) -> None:
    write_g064_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest=GENERATION,
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
        observed_at_utc=NOW,
    )
    assert (tmp_path / "position-reconciliation.json").is_file()


def test_g064_position_evidence_rejects_nonzero_post_count(tmp_path: Path) -> None:
    write_g064_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest=GENERATION,
        position_open=False,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        generation_bound=True,
        observed_at_utc=NOW,
    )
    path = tmp_path / "position-reconciliation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["broker_post_count"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    evidence = load_g064_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest=GENERATION,
        now_utc=NOW,
    )
    assert evidence.evidence_available is False


def test_worker_lease_is_fresh_only_for_live_generation(tmp_path: Path) -> None:
    write_g064_worker_lease(
        state_root=tmp_path,
        generation_digest=GENERATION,
        reviewed_files_digest=REVIEWED,
        now_utc=NOW,
    )
    lock = H11AutoProcessLock(tmp_path / "process.lock")
    assert lock.acquire()
    try:
        assert g064_worker_lease_alive(
            state_root=tmp_path,
            generation_digest=GENERATION,
            reviewed_files_digest=REVIEWED,
            now_utc=NOW + timedelta(seconds=15),
        )
        assert not g064_worker_lease_alive(
            state_root=tmp_path,
            generation_digest=GENERATION,
            reviewed_files_digest=REVIEWED,
            now_utc=NOW + timedelta(seconds=61),
        )
    finally:
        lock.release()


def test_g064_scheduler_is_single_run_resident_without_restart() -> None:
    repository = Path(__file__).resolve().parents[4]
    generation = SimpleNamespace(
        generation_label=G064_GENERATION_LABEL,
        implementation_digest=REVIEWED,
        digest=GENERATION,
    )
    payload = plistlib.loads(
        render_v4_gmo_unattended_scheduler_launchagent(
            repository=repository,
            generation=generation,
            python_executable=Path("/usr/bin/python3"),
        )
    )
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is False
    assert "StartInterval" not in payload
    assert "ThrottleInterval" not in payload


def test_g064_activation_requires_commissioning_evidence(tmp_path: Path) -> None:
    generation = SimpleNamespace(
        generation_label=G064_GENERATION_LABEL,
        status="UNATTENDED_LIVE_COMMISSIONED",
        live_ready=True,
        unattended_live_supported=True,
        actual_post_authorized=False,
        activation_source_generation_digest=GENERATION,
        successful_canary_evidence_digest=None,
        runtime_commissioning_evidence_digest=GENERATION,
        successor_halt_release_digest=GENERATION,
        reconciliation_contract_digest=GENERATION,
        digest=GENERATION,
        implementation_digest=REVIEWED,
    )
    try:
        verify_g064_generation_activation(generation=generation, state_root=tmp_path)
    except V4G064ActivationError as error:
        assert str(error) == "G064_G063_BASELINE_DIGEST_MISMATCH"
    else:
        raise AssertionError("missing commissioning evidence must fail closed")


def test_g064_runtime_evidence_is_fresh_and_generation_bound(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[4]
    payload = json.loads(
        (repository / "docs/templates/h11_v4_g064_frozen_generation.json").read_text(
            encoding="utf-8"
        )
    )
    payload["blocked_hours_jst"] = tuple(payload["blocked_hours_jst"])
    payload["weekend_days_jst"] = tuple(payload["weekend_days_jst"])
    generation = V4GmoFrozenGeneration(**payload)
    write_g064_runtime_evidence_no_post(
        state_root=tmp_path,
        generation=generation,
        observed_at_utc=datetime.now(UTC),
    )
    verify_g064_generation_activation(
        generation=generation,
        state_root=tmp_path,
    )


def test_g064_scheduler_service_evidence_is_safe_and_generation_bound(
    tmp_path: Path,
) -> None:
    write_g064_scheduler_service_evidence(
        state_root=tmp_path,
        generation_digest=GENERATION,
        reviewed_files_digest=REVIEWED,
        observed_at_utc=NOW,
    )
    payload = json.loads(
        (tmp_path / "scheduler-service-state.json").read_text(encoding="utf-8")
    )
    assert payload["loaded"] is True
    assert payload["broker_write"] is False
    assert payload["actual_post_count"] == 0
