from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from app.services.h11_v4_g028_unattended_runtime_no_post import (
    V4G028ArmProjectionNoPost,
    V4G028FakeSnapshotNoPost,
    V4G028ProtectedCycleNoPost,
    V4G028ResidentSupervisorNoPost,
    V4G028RuntimeNoPostError,
    consume_external_approval_for_fake_snapshot_no_post,
    dispatch_30m_exit_fake_no_post,
    record_fake_protected_cycle_once_no_post,
    validate_g028_entry_halt_no_post,
)

_REVIEWED = "sha256:" + "a" * 64
_GENERATION = "sha256:" + "b" * 64
_CYCLE = "sha256:" + "d" * 64
_NOW = datetime(2026, 7, 29, 1, 0, tzinfo=UTC)
_ARMED = V4G028ArmProjectionNoPost(_REVIEWED, _GENERATION, "ARMED")
_DISARMED = V4G028ArmProjectionNoPost(_REVIEWED, _GENERATION, "DISARMED")


def _digest(payload: dict) -> str:
    canonical = {key: value for key, value in payload.items() if key != "artifact_digest"}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _receipt(tmp_path, anchor):
    anchor_stat = anchor.stat()
    payload = {
        "schema": "H11_V4_G028_EXTERNAL_APPROVAL_RECEIPT_V1",
        "reviewed_files_digest": _REVIEWED,
        "generation_digest": _GENERATION,
        "scope": "FAKE_SNAPSHOT_TRANSACTION_ONLY",
        "anchor_device": anchor_stat.st_dev,
        "anchor_inode": anchor_stat.st_ino,
        "valid_until_utc": (_NOW + timedelta(minutes=5)).isoformat(),
        "private_api_authorized": False,
        "broker_post_authorized": False,
    }
    payload["artifact_digest"] = _digest(payload)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _cycle() -> V4G028ProtectedCycleNoPost:
    return V4G028ProtectedCycleNoPost(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        cycle_binding_digest=_CYCLE,
        entry_filled_at_utc=_NOW.isoformat(),
        exact_protection_confirmed=True,
    )


def test_anchor_fd_transaction_is_one_use_and_has_no_external_action(tmp_path) -> None:
    anchor = tmp_path / "anchor"
    anchor.mkdir()
    receipt = _receipt(tmp_path, anchor)
    anchor_fd = os.open(anchor, os.O_RDONLY)
    receipt_fd = os.open(receipt, os.O_RDONLY)
    try:
        result = consume_external_approval_for_fake_snapshot_no_post(
            anchor_directory_fd=anchor_fd,
            approval_receipt_fd=receipt_fd,
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            snapshot=V4G028FakeSnapshotNoPost(0, 0, 0),
            observed_at_utc=_NOW,
        )
        assert result.private_api_read is False
        assert result.credential_read is False
        assert result.broker_get_count == 0
        assert result.modeled_private_get_count == 3
        anchor.rename(tmp_path / "renamed-anchor")
        (tmp_path / "anchor").mkdir()
        with pytest.raises(V4G028RuntimeNoPostError, match="ALREADY_ATTEMPTED"):
            consume_external_approval_for_fake_snapshot_no_post(
                anchor_directory_fd=anchor_fd,
                approval_receipt_fd=receipt_fd,
                reviewed_files_digest=_REVIEWED,
                generation_digest=_GENERATION,
                snapshot=V4G028FakeSnapshotNoPost(0, 0, 0),
                observed_at_utc=_NOW,
            )
    finally:
        os.close(receipt_fd)
        os.close(anchor_fd)


def test_invalid_receipt_stops_before_started_marker(tmp_path) -> None:
    anchor = tmp_path / "anchor"
    anchor.mkdir()
    receipt = _receipt(tmp_path, anchor)
    receipt.chmod(0o644)
    anchor_fd = os.open(anchor, os.O_RDONLY)
    receipt_fd = os.open(receipt, os.O_RDONLY)
    try:
        with pytest.raises(V4G028RuntimeNoPostError, match="RECEIPT_FD_INVALID"):
            consume_external_approval_for_fake_snapshot_no_post(
                anchor_directory_fd=anchor_fd,
                approval_receipt_fd=receipt_fd,
                reviewed_files_digest=_REVIEWED,
                generation_digest=_GENERATION,
                snapshot=V4G028FakeSnapshotNoPost(0, 0, 0),
                observed_at_utc=_NOW,
            )
        assert not (anchor / "g028-private-snapshot.started.json").exists()
    finally:
        os.close(receipt_fd)
        os.close(anchor_fd)


def test_receipt_cannot_be_reused_with_another_anchor(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    receipt = _receipt(tmp_path, first)
    receipt_fd = os.open(receipt, os.O_RDONLY)
    second_fd = os.open(second, os.O_RDONLY)
    try:
        with pytest.raises(V4G028RuntimeNoPostError, match="RECEIPT_INVALID"):
            consume_external_approval_for_fake_snapshot_no_post(
                anchor_directory_fd=second_fd,
                approval_receipt_fd=receipt_fd,
                reviewed_files_digest=_REVIEWED,
                generation_digest=_GENERATION,
                snapshot=V4G028FakeSnapshotNoPost(0, 0, 0),
                observed_at_utc=_NOW,
            )
    finally:
        os.close(second_fd)
        os.close(receipt_fd)


def test_supervisor_updates_lock_deadman_heartbeat_and_arm_off(tmp_path) -> None:
    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    started = supervisor.start(now_utc=_NOW, arm=_ARMED)
    assert started.process_lock_held and started.entry_halted
    first = json.loads((tmp_path / "g028-supervisor-heartbeat.json").read_text())
    tick = supervisor.tick(now_utc=_NOW + timedelta(seconds=15), arm=_DISARMED)
    second = json.loads((tmp_path / "g028-supervisor-heartbeat.json").read_text())
    assert tick.status == "G028_SUPERVISOR_ARM_OFF_ENTRY_DISABLED_NO_POST"
    assert second["previous_artifact_digest"] == first["artifact_digest"]
    stopped = supervisor.stop(
        now_utc=_NOW + timedelta(seconds=16), reason="ARM_OFF"
    )
    assert stopped.process_lock_held is False


def test_sleep_restart_recovers_protected_cycle_and_dispatches_once(tmp_path) -> None:
    record_fake_protected_cycle_once_no_post(
        state_directory=tmp_path, cycle=_cycle()
    )
    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    assert supervisor.start(
        now_utc=_NOW + timedelta(seconds=120), arm=_ARMED
    ).settlement_monitor_required
    due = supervisor.tick(
        now_utc=_NOW + timedelta(seconds=1_800), arm=_ARMED
    )
    assert due.status == "G028_30M_EXIT_DUE_REVIEW_REQUIRED_NO_POST"
    repeated = supervisor.tick(
        now_utc=_NOW + timedelta(seconds=1_815), arm=_ARMED
    )
    assert repeated.status == "G028_30M_EXIT_ALREADY_DISPATCHED_NO_POST"
    supervisor.stop(
        now_utc=_NOW + timedelta(seconds=1_816), reason="HOST_SHUTDOWN"
    )


def test_sleep_without_cycle_latches_unknown_across_ctrl_c_restart(tmp_path) -> None:
    first = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    first.start(now_utc=_NOW, arm=_ARMED)
    halted = first.tick(now_utc=_NOW + timedelta(seconds=120), arm=_ARMED)
    assert halted.persistent_halt
    first.stop(now_utc=_NOW + timedelta(seconds=121), reason="CTRL_C")
    second = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    restarted = second.start(now_utc=_NOW + timedelta(seconds=130), arm=_ARMED)
    assert restarted.persistent_halt
    second.stop(now_utc=_NOW + timedelta(seconds=131), reason="PROCESS_EXIT")


def test_partial_heartbeat_startup_and_failed_stop_latch_unknown(
    tmp_path, monkeypatch
) -> None:
    partial = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    partial.dead_man.heartbeat(heartbeat_utc=_NOW)
    result = partial.start(now_utc=_NOW + timedelta(seconds=1), arm=_ARMED)
    assert result.persistent_halt
    partial.stop(now_utc=_NOW + timedelta(seconds=2), reason="PROCESS_EXIT")

    other_root = tmp_path / "stop-failure"
    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=other_root,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    supervisor.start(now_utc=_NOW, arm=_ARMED)
    monkeypatch.setattr(
        supervisor,
        "_write_entry_halt",
        lambda *_args: (_ for _ in ()).throw(OSError("synthetic failure")),
    )
    with pytest.raises(OSError):
        supervisor.stop(now_utc=_NOW + timedelta(seconds=1), reason="CTRL_C")
    assert not supervisor.process_lock.held
    assert (other_root / "g028-unknown-halt.json").is_file()


def test_rapid_unclean_restart_without_cycle_latches_unknown(tmp_path) -> None:
    first = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    first.start(now_utc=_NOW, arm=_ARMED)
    first.process_lock.release()
    restarted = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    result = restarted.start(now_utc=_NOW + timedelta(seconds=10), arm=_ARMED)
    assert result.persistent_halt
    restarted.stop(now_utc=_NOW + timedelta(seconds=11), reason="PROCESS_EXIT")


def test_corrupt_shutdown_cannot_suppress_unclean_restart(tmp_path) -> None:
    first = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    first.start(now_utc=_NOW, arm=_ARMED)
    first.stop(now_utc=_NOW + timedelta(seconds=1), reason="PROCESS_EXIT")
    shutdown = tmp_path / "g028-supervisor-shutdown.json"
    payload = json.loads(shutdown.read_text())
    payload["heartbeat_sequence"] += 1
    payload["artifact_digest"] = _digest(payload)
    shutdown.write_text(json.dumps(payload))

    restarted = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    result = restarted.start(now_utc=_NOW + timedelta(seconds=2), arm=_ARMED)
    assert result.persistent_halt
    restarted.stop(now_utc=_NOW + timedelta(seconds=3), reason="PROCESS_EXIT")


def test_invalid_cycle_persists_unknown_halt(tmp_path) -> None:
    record_fake_protected_cycle_once_no_post(
        state_directory=tmp_path, cycle=_cycle()
    )
    lifecycle = tmp_path / "g028-protected-cycle.fake.json"
    payload = json.loads(lifecycle.read_text())
    payload["artifact_digest"] = "sha256:" + "0" * 64
    lifecycle.write_text(json.dumps(payload))
    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    result = supervisor.start(now_utc=_NOW, arm=_ARMED)
    assert result.persistent_halt
    assert (tmp_path / "g028-unknown-halt.json").is_file()
    supervisor.stop(now_utc=_NOW + timedelta(seconds=1), reason="PROCESS_EXIT")


def test_entry_halt_is_self_digested_and_stop_requires_lock(tmp_path) -> None:
    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=tmp_path,
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
    )
    supervisor.start(now_utc=_NOW, arm=_ARMED)
    halt = tmp_path / "g028-entry-halt.json"
    assert validate_g028_entry_halt_no_post(
        path=halt,
        expected_reviewed_files_digest=_REVIEWED,
        expected_generation_digest=_GENERATION,
    )
    supervisor.stop(now_utc=_NOW + timedelta(seconds=1), reason="PROCESS_EXIT")
    with pytest.raises(V4G028RuntimeNoPostError, match="PROCESS_LOCK_REQUIRED"):
        supervisor.stop(
            now_utc=_NOW + timedelta(seconds=2),
            reason="PROCESS_EXIT",
        )


def test_entrypoint_loop_rechecks_stop_after_sleep_and_latches_exception() -> None:
    from scripts.h11_auto_v4_g028_supervisor_no_post import (
        run_resident_loop_no_post,
    )

    class FakeSupervisor:
        ticks = 0
        failed = False

        def tick(self, **_kwargs):
            self.ticks += 1

        def fail_closed(self, **_kwargs):
            self.failed = True

    supervisor = FakeSupervisor()
    stopping = False

    def sleep(_seconds):
        nonlocal stopping
        stopping = True

    assert run_resident_loop_no_post(
        supervisor=supervisor,
        arm_loader=lambda: _ARMED,
        sleep=sleep,
        now=lambda: _NOW,
        should_stop=lambda: stopping,
        interval_seconds=15,
        max_ticks=1,
    ) == 0
    assert supervisor.ticks == 0

    def failed_arm():
        raise RuntimeError("synthetic wrapper failure")

    with pytest.raises(RuntimeError):
        run_resident_loop_no_post(
            supervisor=supervisor,
            arm_loader=failed_arm,
            sleep=lambda _seconds: None,
            now=lambda: _NOW,
            should_stop=lambda: False,
            interval_seconds=15,
            max_ticks=1,
        )
    assert supervisor.failed


def test_dispatcher_rejects_unreviewed_lifecycle(tmp_path) -> None:
    record_fake_protected_cycle_once_no_post(
        state_directory=tmp_path, cycle=_cycle()
    )
    lifecycle = tmp_path / "g028-protected-cycle.fake.json"
    payload = json.loads(lifecycle.read_text())
    payload["entry_filled_at_utc"] = (
        _NOW - timedelta(days=1)
    ).isoformat()
    lifecycle.write_text(json.dumps(payload))
    with pytest.raises(V4G028RuntimeNoPostError, match="LIFECYCLE_INVALID"):
        dispatch_30m_exit_fake_no_post(
            state_directory=tmp_path,
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            observed_at_utc=_NOW + timedelta(seconds=1_800),
        )


def test_g028_source_has_no_external_adapter_or_authorization_path() -> None:
    import app.services.h11_v4_g028_unattended_runtime_no_post as subject

    source = open(subject.__file__, encoding="utf-8").read()
    for forbidden in (
        "import httpx", "import requests", ".post(", '"POST"', "Keychain",
        "closeOrder", "cancelOrders", "changeOrder", "set_desired_state",
        "ActualPushover", "ActualEmail", "assert_real_broker_post_allowed",
    ):
        assert forbidden not in source
