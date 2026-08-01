from pathlib import Path

from app.services.h11_v4_g064_unattended_activation import (
    _review_provenance_is_clear,
    _review_report_digest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LAUNCHER = (
    REPOSITORY_ROOT
    / "backend"
    / "scripts"
    / "h11_auto_v4_unattended_live_scheduled_launcher.py"
)
MONITOR = (
    REPOSITORY_ROOT
    / "backend"
    / "app"
    / "h11_auto"
    / "v4_gmo_monitor_supervisor.py"
)
RUNTIME_PROJECTION = (
    REPOSITORY_ROOT
    / "backend"
    / "app"
    / "services"
    / "h11_v4_unattended_runtime_no_post.py"
)


def test_g064_resident_worker_is_the_single_runtime_lock_owner():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "runtime_lock=preheld_process_lock" in source
    assert "resident_lock = H11AutoProcessLock" in source
    assert "preheld_process_lock is None" in source


def test_g064_partial_runtime_state_fails_closed_instead_of_regenerating_evidence():
    source = MONITOR.read_text(encoding="utf-8")

    assert "scheduler-service-state.json" in source
    assert "runtime_files_incomplete = any" in source
    assert "if service_state.is_file() and runtime_files_incomplete" in source
    assert "V4_SUPERVISOR_G064_RUNTIME_FILES_INCOMPLETE" in source
    assert "V4_SUPERVISOR_G064_RUNTIME_BOOTSTRAP_INCOMPLETE" in source


def test_g064_unknown_position_evidence_cannot_be_flat_or_exit_only():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "not position.evidence_available" in source
    assert "not position.generation_bound" in source


def test_g064_runtime_projection_binds_reviewed_files_digest():
    source = RUNTIME_PROJECTION.read_text(encoding="utf-8")

    assert "reviewed_files_digest: str | None = None" in source
    assert "payload.get(\"reviewed_files_digest\") != reviewed_files_digest" in source


def test_g064_service_evidence_records_the_resident_worker_pid():
    source = MONITOR.read_text(encoding="utf-8")

    assert "service_pid=os.getpid()" in source


def test_g064_review_provenance_is_complete_and_tamper_evident():
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
        "review_provenance": provenance,
        "reviewed_at_utc": "2026-08-01T00:00:00+00:00",
        "reviewed_branch": "main",
        "reviewed_commit": commit,
    }

    assert _review_provenance_is_clear(attestation)
    provenance["safety"]["status"] = "VETO"
    assert not _review_provenance_is_clear(attestation)


def test_g064_arm_off_handoff_is_exit_only_and_no_post():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "write_g064_exit_only_dispatch_no_post" in source
    assert "run_g064_exit_only_dispatch_no_post" in source
    assert "G064_ARM_OFF_EXIT_ONLY_MONITORING_NO_POST" in source
    assert "entry_gate_open=false" in source
    assert "execute_one_shot_live_order" not in source


def test_g064_runtime_keeps_safety_counters_zero():
    source = MONITOR.read_text(encoding="utf-8")

    for field in (
        "broker_read: bool = False",
        "broker_post_authorized: bool = False",
        "broker_write: bool = False",
        "actual_post_count: int = 0",
        "private_api_read_count: int = 0",
        "credential_read_count: int = 0",
        "notification_attempt_count: int = 0",
    ):
        assert field in source
