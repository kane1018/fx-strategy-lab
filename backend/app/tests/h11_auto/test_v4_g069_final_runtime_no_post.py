from __future__ import annotations

import json
import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g069_position_reconciliation_no_post import (
    load_g069_position_reconciliation_no_post,
    write_g069_position_protection_evidence_no_post,
)
from app.services.h11_v4_g069_unattended_activation_no_post import (
    G069OwnerLock,
    G069RuntimeState,
    V4G069ActivationError,
    begin_g069_one_use_marker,
    project_g069_runtime_state,
    record_g069_one_use_outcome,
    require_g069_operation_60_passed,
    require_g069_persistent_halt_absent,
    verify_g069_arm_readiness_no_post,
    verify_g069_scheduler_binding,
    write_g069_health_no_post,
)
from scripts.h11_auto_v4_g069_operation_60_no_post import (
    _wait_for_g069_scheduler_readiness,
)


def test_flat_arm_on_is_waiting_and_entry_is_separate() -> None:
    projection = project_g069_runtime_state(
        arm_state="ON",
        position={
            "open_position_count": 0,
            "active_order_count": 0,
            "account_flat": True,
            "active_orders_zero": True,
        },
    )
    assert projection.effective_state is G069RuntimeState.ON_WAITING
    assert projection.entry_gate_open is True
    assert projection.to_safe_dict()["actual_post_authorized"] is False
    assert projection.ownership_exact is False


def test_g069_position_bridge_preserves_explicit_flat_and_zero_active(
    monkeypatch, tmp_path
) -> None:
    import app.services.h11_v4_g069_position_reconciliation_no_post as bridge

    snapshot = SimpleNamespace(
        open_positions_count=0,
        active_orders_count=0,
        cycle_binding_digest="sha256:" + "c" * 64,
        account_flat=True,
        active_orders_zero=True,
        broker_get_count=3,
        broker_write=False,
        broker_post_count=0,
    )
    monkeypatch.setattr(
        bridge.V4AccountSnapshotStoreNoPost,
        "load_completed",
        lambda self, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        bridge,
        "validate_bound_account_snapshot_evidence_no_post",
        lambda *_args, **_kwargs: None,
    )
    evidence = load_g069_position_reconciliation_no_post(
        reviewed_files_digest="sha256:" + "a" * 64,
        generation_digest="sha256:" + "b" * 64,
        snapshot_state_root=tmp_path,
        now_utc=datetime.now(UTC),
    )
    assert evidence.evidence_available is True
    assert evidence.account_flat is True
    assert evidence.active_orders_zero is True
    assert evidence.open_positions_count == 0
    assert evidence.active_orders_count == 0


def test_g069_position_bridge_rejects_inconsistent_zero_active_claim(
    monkeypatch, tmp_path
) -> None:
    import app.services.h11_v4_g069_position_reconciliation_no_post as bridge

    snapshot = SimpleNamespace(
        open_positions_count=0,
        active_orders_count=1,
        cycle_binding_digest="sha256:" + "c" * 64,
        account_flat=True,
        active_orders_zero=True,
        broker_get_count=3,
        broker_write=False,
        broker_post_count=0,
    )
    monkeypatch.setattr(
        bridge.V4AccountSnapshotStoreNoPost,
        "load_completed",
        lambda self, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        bridge,
        "validate_bound_account_snapshot_evidence_no_post",
        lambda *_args, **_kwargs: None,
    )
    evidence = load_g069_position_reconciliation_no_post(
        reviewed_files_digest="sha256:" + "a" * 64,
        generation_digest="sha256:" + "b" * 64,
        snapshot_state_root=tmp_path,
        now_utc=datetime.now(UTC),
    )
    assert evidence.evidence_available is False
    assert evidence.account_flat is False
    assert evidence.active_orders_zero is False


def test_g069_position_bridge_accepts_fresh_explicit_protection_proof(
    monkeypatch, tmp_path
) -> None:
    import app.services.h11_v4_g069_position_reconciliation_no_post as bridge

    snapshot = SimpleNamespace(
        open_positions_count=1,
        active_orders_count=1,
        cycle_binding_digest="sha256:" + "c" * 64,
        account_flat=False,
        active_orders_zero=False,
        broker_get_count=3,
        broker_write=False,
        broker_post_count=0,
        artifact_digest="sha256:" + "d" * 64,
    )
    monkeypatch.setattr(
        bridge.V4AccountSnapshotStoreNoPost,
        "load_completed",
        lambda self, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        bridge,
        "validate_bound_account_snapshot_evidence_no_post",
        lambda *_args, **_kwargs: None,
    )
    now = datetime.now(UTC)
    write_g069_position_protection_evidence_no_post(
        snapshot_state_root=tmp_path,
        reviewed_files_digest="sha256:" + "a" * 64,
        generation_digest="sha256:" + "b" * 64,
        account_snapshot_artifact_digest=snapshot.artifact_digest,
        observed_at_utc=now,
        valid_until_utc=now + timedelta(seconds=30),
        ownership_exact=True,
        quantity_matches=True,
        protection_confirmed=True,
    )
    evidence = load_g069_position_reconciliation_no_post(
        reviewed_files_digest="sha256:" + "a" * 64,
        generation_digest="sha256:" + "b" * 64,
        snapshot_state_root=tmp_path,
        now_utc=now,
    )
    assert evidence.position_open is True
    assert evidence.ownership_exact is True
    assert evidence.quantity_matches is True
    assert evidence.protection_confirmed is True


def test_open_position_with_zero_active_orders_is_not_protected() -> None:
    projection = project_g069_runtime_state(
        arm_state="ON",
        position={
            "open_position_count": 1,
            "active_order_count": 0,
            "account_flat": False,
            "active_orders_zero": True,
            "ownership_exact": True,
            "quantity_matches": True,
            "protection_confirmed": True,
        },
    )
    assert projection.effective_state is G069RuntimeState.HALTED
    assert projection.entry_gate_open is False


def test_arm_readiness_rejects_control_plane_only_readiness() -> None:
    with pytest.raises(V4G069ActivationError, match="G069_ARM_POSITION_EVIDENCE_REQUIRED"):
        verify_g069_arm_readiness_no_post(
            scheduler_ready=True,
            position_evidence_available=False,
        position_evidence_fresh=False,
        position_generation_bound=False,
        position_open=False,
        account_flat=False,
        active_orders_zero=False,
        ownership_exact=False,
            quantity_matches=False,
            protection_confirmed=False,
        )


def test_arm_readiness_accepts_fresh_flat_evidence() -> None:
    verify_g069_arm_readiness_no_post(
        scheduler_ready=True,
        position_evidence_available=True,
        position_evidence_fresh=True,
        position_generation_bound=True,
        position_open=False,
        account_flat=True,
        active_orders_zero=True,
        ownership_exact=False,
        quantity_matches=False,
        protection_confirmed=False,
    )


def test_arm_readiness_accepts_explicitly_protected_position() -> None:
    verify_g069_arm_readiness_no_post(
        scheduler_ready=True,
        position_evidence_available=True,
        position_evidence_fresh=True,
        position_generation_bound=True,
        position_open=True,
        account_flat=False,
        active_orders_zero=False,
        ownership_exact=True,
        quantity_matches=True,
        protection_confirmed=True,
    )


def test_arm_readiness_rejects_unconfirmed_position() -> None:
    with pytest.raises(V4G069ActivationError, match="G069_ARM_PROTECTION_UNCONFIRMED"):
        verify_g069_arm_readiness_no_post(
            scheduler_ready=True,
            position_evidence_available=True,
            position_evidence_fresh=True,
            position_generation_bound=True,
            position_open=True,
            account_flat=False,
            active_orders_zero=False,
            ownership_exact=False,
            quantity_matches=True,
            protection_confirmed=True,
        )


def test_protected_position_is_exit_only() -> None:
    projection = project_g069_runtime_state(
        arm_state="ON",
        position={
            "open_position_count": 1,
            "active_order_count": 1,
            "account_flat": False,
            "active_orders_zero": False,
            "ownership_exact": True,
            "quantity_matches": True,
            "protection_confirmed": True,
        },
    )
    assert projection.effective_state is G069RuntimeState.ON_EXIT_ONLY
    assert projection.entry_gate_open is False


def test_unknown_position_is_halted_and_all_protection_flags_are_false() -> None:
    projection = project_g069_runtime_state(
        arm_state="ON",
        position={
            "open_position_count": 1,
            "active_order_count": 1,
            "account_flat": False,
            "active_orders_zero": False,
        },
    )
    assert projection.effective_state is G069RuntimeState.HALTED
    assert projection.entry_gate_open is False
    assert projection.ownership_exact is False
    assert projection.quantity_matches is False
    assert projection.protection_confirmed is False


def test_arm_off_keeps_exit_only() -> None:
    projection = project_g069_runtime_state(
        arm_state="OFF",
        position={
            "open_position_count": 1,
            "active_order_count": 1,
            "account_flat": False,
            "active_orders_zero": False,
            "ownership_exact": True,
            "quantity_matches": True,
            "protection_confirmed": True,
        },
    )
    assert projection.effective_state is G069RuntimeState.EXIT_ONLY
    assert projection.entry_gate_open is False


def test_owner_lock_rejects_live_owner(tmp_path) -> None:
    digest = "sha256:" + "a" * 64
    first = G069OwnerLock(tmp_path / "process.lock", generation_digest=digest)
    first.acquire()
    try:
        second = G069OwnerLock(tmp_path / "process.lock", generation_digest=digest)
        with pytest.raises(V4G069ActivationError, match="PROCESS_LOCK_CONFLICT"):
            second.acquire()
    finally:
        first.release()


def test_owner_lock_recovers_dead_owner(tmp_path) -> None:
    digest = "sha256:" + "a" * 64
    (tmp_path / "process.lock").write_text(
        json.dumps({"pid": 999999, "generation_digest": digest}), encoding="utf-8"
    )
    lock = G069OwnerLock(tmp_path / "process.lock", generation_digest=digest)
    lock.acquire()
    lock.release()


def test_health_chain_is_generation_bound_and_no_post(tmp_path) -> None:
    write_g069_health_no_post(
        state_root=tmp_path,
        generation_digest="sha256:" + "a" * 64,
        reviewed_files_digest="sha256:" + "b" * 64,
        now_utc=datetime.now(UTC),
        chain_index=1,
    )
    heartbeat = json.loads((tmp_path / "heartbeat.json").read_text())
    assert heartbeat["generation_label"].endswith("G069")
    assert heartbeat["broker_write"] is False
    assert heartbeat["private_api_read"] is False


def test_release_marker_is_one_use(tmp_path) -> None:
    begin_g069_one_use_marker(
        state_root=tmp_path,
        filename="release-activation.started.json",
        payload={"generation_label": "H11_AUTO_30M_20260802_G069"},
    )
    with pytest.raises(V4G069ActivationError, match="MARKER_ALREADY_EXISTS"):
        begin_g069_one_use_marker(
            state_root=tmp_path,
            filename="release-activation.started.json",
            payload={},
        )
    record_g069_one_use_outcome(
        state_root=tmp_path,
        filename="release-activation.outcome.json",
        payload={"broker_write": False, "broker_post_count": 0},
        outcome="PASSED",
    )


def test_operation_60_source_requires_install_and_runtime_verification() -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "scripts/h11_auto_v4_g069_operation_60_no_post.py"
    ).read_text(encoding="utf-8")
    assert "h11_auto_v4_install_unattended_live_scheduler_launchagent" in source
    assert "verify_g069_scheduler_binding" in source
    assert "installer_timeout_seconds" in source
    assert "readiness_timeout_seconds" in source
    assert "_wait_for_g069_scheduler_readiness" in source
    assert "require_operation_60_passed=False" in source


def test_g069_state_root_is_distinct_from_g068_incident_root(tmp_path) -> None:
    g068 = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest="sha256:" + "6" * 64,
    )
    g069 = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest="sha256:" + "9" * 64,
    )
    assert g069 != g068
    assert not g069.exists()
    assert not g068.exists()


def test_g069_evidence_scopes_predecessor_immutability_to_state_root() -> None:
    evidence_path = (
        Path(__file__).resolve().parents[4]
        / "docs/templates/h11_v4_g069_runtime_commissioning_evidence.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["predecessor_operation_60_unknown"] is True
    assert evidence["predecessor_authorization_reused"] is False
    assert evidence["predecessor_marker_halt_state_copied"] is False
    assert evidence["predecessor_runtime_state_root_immutable"] is True
    assert evidence["predecessor_scheduler_service_reused"] is False
    assert evidence["predecessor_scheduler_service_replacement_authorized"] is True
    assert evidence["live_ready"] is False
    assert evidence["unattended_live_supported"] is False
    assert evidence["launchagent_executed"] is False
    assert evidence["operation_60_passed"] is False
    assert evidence["effective_live_ready_requires_operation_60_marker"] is True


class _FakeClock:
    def __init__(self, initial: float) -> None:
        self.value = initial

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_readiness_gets_fresh_window_after_delayed_installer() -> None:
    clock = _FakeClock(89.0)
    calls = 0

    def verifier() -> None:
        nonlocal calls
        calls += 1
        if calls < 31:
            raise V4G069ActivationError("NOT_READY")

    _wait_for_g069_scheduler_readiness(
        verifier=verifier,
        readiness_timeout_seconds=60,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert clock.value == 119.0


def test_readiness_timeout_is_unknown_boundary() -> None:
    clock = _FakeClock(40.0)

    with pytest.raises(V4G069ActivationError, match="READINESS_TIMEOUT"):
        _wait_for_g069_scheduler_readiness(
            verifier=lambda: (_ for _ in ()).throw(V4G069ActivationError("NOT_READY")),
            readiness_timeout_seconds=3,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )


@pytest.mark.parametrize("halt_kind", ["file", "malformed", "symlink"])
def test_scheduler_binding_rejects_every_persistent_halt_shape(tmp_path, halt_kind) -> None:
    halt = tmp_path / "g069-runtime-halt.json"
    if halt_kind == "file":
        halt.write_text('{"status":"HALTED"}', encoding="utf-8")
    elif halt_kind == "malformed":
        halt.write_text("not-json", encoding="utf-8")
    else:
        target = tmp_path / "halt-target"
        target.write_text("halted", encoding="utf-8")
        halt.symlink_to(target)
    with pytest.raises(V4G069ActivationError, match="PERSISTENT_HALT_PRESENT"):
        require_g069_persistent_halt_absent(state_root=tmp_path)


def test_scheduler_binding_passes_only_fresh_health_without_halt(tmp_path, monkeypatch) -> None:
    import app.services.h11_v4_g069_unattended_activation_no_post as service

    digest = "sha256:" + "a" * 64
    reviewed = "sha256:" + "b" * 64
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260802_G069",
        digest=digest,
        implementation_digest=reviewed,
    )
    monkeypatch.setattr(service, "_DEFAULT_REPOSITORY", tmp_path)
    monkeypatch.setattr(service, "verify_g069_generation_contract", lambda **_: None)
    plist = tmp_path / "scheduler.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    "/python",
                    str(tmp_path / "backend/scripts/h11_auto_v4_g069_runtime_bootstrap_no_post.py"),
                    "--repository",
                    str(tmp_path),
                    "--expected-reviewed-files-digest",
                    reviewed,
                    "--expected-generation-digest",
                    digest,
                ],
                "WorkingDirectory": str(tmp_path / "backend"),
                "RunAtLoad": True,
                "KeepAlive": False,
            }
        )
    )
    write_g069_health_no_post(
        state_root=tmp_path,
        generation_digest=digest,
        reviewed_files_digest=reviewed,
        now_utc=datetime.now(UTC),
        chain_index=1,
    )
    (tmp_path / "process.lock").write_text(
        json.dumps({"pid": 1, "generation_digest": digest, "owner_token": "owner"}),
        encoding="utf-8",
    )
    (tmp_path / "runtime-projection.json").write_text(
        json.dumps({"actual_post_authorized": False, "broker_write": False}),
        encoding="utf-8",
    )
    (tmp_path / "operation-60-result.outcome.json").write_text(
        json.dumps(
            {
                "schema": "H11_V4_G069_OPERATION_60_RESULT_V1",
                "generation_label": "H11_AUTO_30M_20260802_G069",
                "generation_digest": digest,
                "reviewed_files_digest": reviewed,
                "status": "PASSED",
                "broker_write": False,
                "broker_post_count": 0,
                "private_api_read_count": 0,
                "credential_read_count": 0,
            }
        ),
        encoding="utf-8",
    )
    verify_g069_scheduler_binding(
        generation=generation,
        plist_path=plist,
        state_root=tmp_path,
        now_utc=datetime.now(UTC),
    )


def test_effective_readiness_rejects_missing_or_malformed_operation_60(tmp_path) -> None:
    digest = "sha256:" + "a" * 64
    reviewed = "sha256:" + "b" * 64
    with pytest.raises(V4G069ActivationError, match="PASSED_EVIDENCE_MISSING"):
        require_g069_operation_60_passed(
            state_root=tmp_path,
            generation_digest=digest,
            reviewed_files_digest=reviewed,
        )


@pytest.mark.parametrize(
    ("filename", "field", "value"),
    [
        ("heartbeat.json", "broker_read", True),
        ("dead-man.json", "generation_digest", "sha256:" + "c" * 64),
        ("dead-man.json", "actual_post_count", 1),
        ("heartbeat-chain.json", "reviewed_files_digest", "sha256:" + "c" * 64),
        ("heartbeat-chain.json", "private_api_read", True),
    ],
)
def test_scheduler_binding_rejects_foreign_or_nonzero_runtime_health(
    tmp_path, monkeypatch, filename, field, value
) -> None:
    import app.services.h11_v4_g069_unattended_activation_no_post as service

    digest = "sha256:" + "a" * 64
    reviewed = "sha256:" + "b" * 64
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260802_G069",
        digest=digest,
        implementation_digest=reviewed,
    )
    monkeypatch.setattr(service, "_DEFAULT_REPOSITORY", tmp_path)
    monkeypatch.setattr(service, "verify_g069_generation_contract", lambda **_: None)
    plist = tmp_path / "scheduler.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    "/python",
                    str(tmp_path / "backend/scripts/h11_auto_v4_g069_runtime_bootstrap_no_post.py"),
                    "--repository",
                    str(tmp_path),
                    "--expected-reviewed-files-digest",
                    reviewed,
                    "--expected-generation-digest",
                    digest,
                ],
                "WorkingDirectory": str(tmp_path / "backend"),
                "RunAtLoad": True,
                "KeepAlive": False,
            }
        )
    )
    write_g069_health_no_post(
        state_root=tmp_path,
        generation_digest=digest,
        reviewed_files_digest=reviewed,
        now_utc=datetime.now(UTC),
        chain_index=1,
    )
    health_path = tmp_path / filename
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health[field] = value
    health_path.write_text(json.dumps(health), encoding="utf-8")
    (tmp_path / "process.lock").write_text(
        json.dumps({"pid": 1, "generation_digest": digest, "owner_token": "owner"}),
        encoding="utf-8",
    )
    (tmp_path / "runtime-projection.json").write_text(
        json.dumps({"actual_post_authorized": False, "broker_write": False}),
        encoding="utf-8",
    )
    with pytest.raises(V4G069ActivationError, match="RUNTIME_NOT_CLEAR"):
        verify_g069_scheduler_binding(
            generation=generation,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=datetime.now(UTC),
            require_operation_60_passed=False,
        )
    (tmp_path / "operation-60-result.outcome.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(V4G069ActivationError, match="PASSED_EVIDENCE_INVALID"):
        require_g069_operation_60_passed(
            state_root=tmp_path,
            generation_digest=digest,
            reviewed_files_digest=reviewed,
        )
