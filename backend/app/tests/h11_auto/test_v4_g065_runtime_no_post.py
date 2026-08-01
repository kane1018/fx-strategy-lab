"""Focused fake-only invariants for the G065 corrective runtime."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    render_v4_gmo_unattended_scheduler_launchagent,
)
from app.services.h11_v4_g065_position_reconciliation_no_post import (
    load_g065_position_reconciliation_no_post,
    write_g065_position_reconciliation_no_post,
)
from app.services.h11_v4_g065_unattended_activation import (
    G065_G064_BASELINE_DIGEST,
    _review_report_digest,
    _stable_artifact_digest,
    verify_g065_generation_contract,
)
from app.services.h11_v4_unattended_runtime_no_post import (
    V4UnattendedRuntimeEvidence,
    V4UnattendedRuntimeState,
    project_unattended_runtime_state,
)


def _generation():
    selected = V4ApprovedOperatorSelections()
    policy = V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260801_G065",
        implementation_digest="sha256:" + "d" * 64,
        policy=policy,
    )


def _runtime_evidence(*, position_open: bool, **overrides):
    values = dict(
        arm_armed=True,
        position_open=position_open,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        runtime_clear=True,
        generation_matches=True,
        pending_transport=False,
        unknown_halt=False,
        heartbeat_alive=True,
        process_lock_clear=True,
        dead_man_alive=True,
        entry_gate_open=not position_open,
    )
    values.update(overrides)
    return V4UnattendedRuntimeEvidence(**values)


def test_g065_missing_position_evidence_is_unknown(tmp_path: Path) -> None:
    evidence = load_g065_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:" + "a" * 64,
        now_utc=datetime.now(UTC),
    )
    assert evidence.evidence_available is False
    assert evidence.protection_confirmed is False
    assert evidence.ownership_exact is False
    assert evidence.quantity_matches is False


def test_g065_open_position_without_proof_is_halted(tmp_path: Path) -> None:
    digest = "sha256:" + "a" * 64
    write_g065_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest=digest,
        position_open=True,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        generation_bound=True,
        observed_at_utc=datetime.now(UTC),
    )
    evidence = load_g065_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest=digest,
        now_utc=datetime.now(UTC),
    )
    assert (
        project_unattended_runtime_state(
            _runtime_evidence(
                position_open=True,
                protection_confirmed=evidence.protection_confirmed,
                ownership_exact=evidence.ownership_exact,
                quantity_matches=evidence.quantity_matches,
            )
        )
        is V4UnattendedRuntimeState.HALTED
    )


def test_g065_flat_arm_on_projects_to_waiting_without_entry_proof() -> None:
    evidence = _runtime_evidence(position_open=False)
    assert project_unattended_runtime_state(evidence) is V4UnattendedRuntimeState.ON_WAITING


def test_g065_arm_off_with_position_keeps_exit_only() -> None:
    evidence = _runtime_evidence(
        position_open=True,
        arm_armed=False,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        entry_gate_open=False,
    )
    assert project_unattended_runtime_state(evidence) is V4UnattendedRuntimeState.EXIT_ONLY


def test_g065_resident_scheduler_render_has_no_periodic_restart(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    launcher = repository / "backend/scripts/h11_auto_v4_unattended_live_scheduled_launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# synthetic launcher\n", encoding="utf-8")
    payload = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=_generation(),
        python_executable=Path("/usr/bin/python3"),
    )
    assert b"StartInterval" not in payload
    assert b"KeepAlive" in payload


def test_g065_commissioned_contract_uses_frozen_g064_baseline(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    templates = repository / "docs/templates"
    templates.mkdir(parents=True)
    source_repository = Path(__file__).resolve().parents[4]
    frozen_g064 = json.loads(
        (source_repository / "docs/templates/h11_v4_g064_frozen_generation.json").read_text(
            encoding="utf-8"
        )
    )
    (templates / "h11_v4_g064_frozen_generation.json").write_text(
        json.dumps(frozen_g064), encoding="utf-8"
    )

    reviewed_digest = "sha256:" + "d" * 64
    generation_digest = "sha256:" + "e" * 64
    commit = "a" * 40
    provenance = {}
    for name, role in (
        ("architecture", "independent_architecture"),
        ("safety", "independent_safety"),
        ("operations", "independent_operations"),
    ):
        entry = {
            "broker_post_count": 0,
            "broker_read_count": 0,
            "credential_read_count": 0,
            "launchagent_executed": False,
            "notification_attempt_count": 0,
            "private_api_read_count": 0,
            "review_scope": "READ_ONLY_NO_POST",
            "reviewed_at_utc": "2026-08-01T00:00:00+00:00",
            "reviewed_branch": "main",
            "reviewed_commit": commit,
            "reviewer_role": role,
            "status": "CLEAR",
        }
        entry["report_digest"] = _review_report_digest(entry)
        provenance[name] = entry

    attestation = {
        "architecture_status": "CLEAR",
        "generation_digest": generation_digest,
        "operations_status": "CLEAR",
        "review_evidence": {
            "architecture": "CLEAR",
            "operations": "CLEAR",
            "safety": "CLEAR",
        },
        "review_method": "INDEPENDENT_A_S_O_REVIEW",
        "review_provenance": provenance,
        "review_scope": "READ_ONLY_NO_POST",
        "reviewed_at_utc": "2026-08-01T00:00:00+00:00",
        "reviewed_branch": "main",
        "reviewed_commit": commit,
        "reviewed_files_digest": reviewed_digest,
        "safety_status": "CLEAR",
    }
    attestation["artifact_digest"] = _stable_artifact_digest(attestation)
    evidence = {
        "actual_post_authorized": False,
        "actual_post_count": 0,
        "architecture_review_clear": True,
        "broker_post_authorized": False,
        "broker_post_count": 0,
        "broker_write": False,
        "credential_read_count": 0,
        "danger_scan_clear": True,
        "diff_check_clear": True,
        "focused_tests_clear": True,
        "generation_digest": generation_digest,
        "independent_review_attestation_digest": attestation["artifact_digest"],
        "launchagent_executed": False,
        "notification_attempt_count": 0,
        "operations_review_clear": True,
        "private_api_read_count": 0,
        "related_tests_clear": True,
        "reviewed_files_digest": reviewed_digest,
        "ruff_clear": True,
        "safety_review_clear": True,
        "status": "G065_RUNTIME_COMMISSIONED_NO_POST",
    }
    evidence["artifact_digest"] = _stable_artifact_digest(evidence)
    (templates / "h11_v4_g065_independent_review_attestation.json").write_text(
        json.dumps(attestation), encoding="utf-8"
    )
    (templates / "h11_v4_g065_runtime_commissioning_evidence.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260801_G065",
        status="UNATTENDED_LIVE_COMMISSIONED",
        live_ready=True,
        unattended_live_supported=True,
        actual_post_authorized=False,
        activation_source_generation_digest=G065_G064_BASELINE_DIGEST,
        successful_canary_evidence_digest=None,
        runtime_commissioning_evidence_digest=evidence["artifact_digest"],
        successor_halt_release_digest=attestation["artifact_digest"],
        reconciliation_contract_digest="sha256:" + "f" * 64,
        digest=generation_digest,
        implementation_digest=reviewed_digest,
    )

    verify_g065_generation_contract(generation=generation, repository=repository)
