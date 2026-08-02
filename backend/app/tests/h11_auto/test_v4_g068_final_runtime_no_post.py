from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g068_unattended_activation_no_post import (
    G068OwnerLock,
    G068RuntimeState,
    V4G068ActivationError,
    begin_g068_one_use_marker,
    project_g068_runtime_state,
    record_g068_one_use_outcome,
    write_g068_health_no_post,
)


def test_flat_arm_on_is_waiting_and_entry_is_separate() -> None:
    projection = project_g068_runtime_state(
        arm_state="ON",
        position={"open_position_count": 0, "active_order_count": 0},
    )
    assert projection.effective_state is G068RuntimeState.ON_WAITING
    assert projection.entry_gate_open is True
    assert projection.to_safe_dict()["actual_post_authorized"] is False
    assert projection.ownership_exact is False


def test_protected_position_is_exit_only() -> None:
    projection = project_g068_runtime_state(
        arm_state="ON",
        position={
            "open_position_count": 1,
            "active_order_count": 1,
            "ownership_exact": True,
            "quantity_matches": True,
            "protection_confirmed": True,
        },
    )
    assert projection.effective_state is G068RuntimeState.ON_EXIT_ONLY
    assert projection.entry_gate_open is False


def test_unknown_position_is_halted_and_all_protection_flags_are_false() -> None:
    projection = project_g068_runtime_state(
        arm_state="ON",
        position={"open_position_count": 1, "active_order_count": 1},
    )
    assert projection.effective_state is G068RuntimeState.HALTED
    assert projection.entry_gate_open is False
    assert projection.ownership_exact is False
    assert projection.quantity_matches is False
    assert projection.protection_confirmed is False


def test_arm_off_keeps_exit_only() -> None:
    projection = project_g068_runtime_state(
        arm_state="OFF",
        position={
            "open_position_count": 1,
            "active_order_count": 1,
            "ownership_exact": True,
            "quantity_matches": True,
            "protection_confirmed": True,
        },
    )
    assert projection.effective_state is G068RuntimeState.EXIT_ONLY
    assert projection.entry_gate_open is False


def test_owner_lock_rejects_live_owner(tmp_path) -> None:
    digest = "sha256:" + "a" * 64
    first = G068OwnerLock(tmp_path / "process.lock", generation_digest=digest)
    first.acquire()
    try:
        second = G068OwnerLock(tmp_path / "process.lock", generation_digest=digest)
        with pytest.raises(V4G068ActivationError, match="PROCESS_LOCK_CONFLICT"):
            second.acquire()
    finally:
        first.release()


def test_owner_lock_recovers_dead_owner(tmp_path) -> None:
    digest = "sha256:" + "a" * 64
    (tmp_path / "process.lock").write_text(
        json.dumps({"pid": 999999, "generation_digest": digest}), encoding="utf-8"
    )
    lock = G068OwnerLock(tmp_path / "process.lock", generation_digest=digest)
    lock.acquire()
    lock.release()


def test_health_chain_is_generation_bound_and_no_post(tmp_path) -> None:
    write_g068_health_no_post(
        state_root=tmp_path,
        generation_digest="sha256:" + "a" * 64,
        reviewed_files_digest="sha256:" + "b" * 64,
        now_utc=datetime.now(UTC),
        chain_index=1,
    )
    heartbeat = json.loads((tmp_path / "heartbeat.json").read_text())
    assert heartbeat["generation_label"].endswith("G068")
    assert heartbeat["broker_write"] is False
    assert heartbeat["private_api_read"] is False


def test_release_marker_is_one_use(tmp_path) -> None:
    begin_g068_one_use_marker(
        state_root=tmp_path,
        filename="release-activation.started.json",
        payload={"generation_label": "H11_AUTO_30M_20260802_G068"},
    )
    with pytest.raises(V4G068ActivationError, match="MARKER_ALREADY_EXISTS"):
        begin_g068_one_use_marker(
            state_root=tmp_path,
            filename="release-activation.started.json",
            payload={},
        )
    record_g068_one_use_outcome(
        state_root=tmp_path,
        filename="release-activation.outcome.json",
        payload={"broker_write": False, "broker_post_count": 0},
        outcome="PASSED",
    )


def test_operation_60_source_requires_install_and_runtime_verification() -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "scripts/h11_auto_v4_g068_operation_60_no_post.py"
    ).read_text(encoding="utf-8")
    assert "h11_auto_v4_install_unattended_live_scheduler_launchagent" in source
    assert "verify_g068_scheduler_binding" in source
    assert "G068_OPERATION_60_HEALTH_TIMEOUT" in source
