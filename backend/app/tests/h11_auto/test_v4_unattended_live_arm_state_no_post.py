from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.h11_v4_unattended_live_arm_state import (
    V4ArmDesiredState,
    V4UnattendedLiveArmStateError,
    V4UnattendedLiveArmStore,
)

_GENERATION = "sha256:" + "a" * 64
_REVIEWED = "sha256:" + "b" * 64
_NOW = datetime(2026, 7, 26, 1, 0, tzinfo=UTC)


def test_missing_state_is_disarmed_and_writes_no_broker_data(tmp_path) -> None:
    store = V4UnattendedLiveArmStore(tmp_path / "arm-state.json")
    check = store.check(
        expected_generation_digest=_GENERATION,
        expected_reviewed_files_digest=_REVIEWED,
    )
    assert check.armed is False
    assert check.revision == 0
    assert check.blocked_reasons == ("ARM_STATE_MISSING",)


def test_arm_then_disarm_is_revision_bound_and_persistent(tmp_path) -> None:
    store = V4UnattendedLiveArmStore(tmp_path / "arm-state.json")
    armed = store.set_desired_state(
        desired_state=V4ArmDesiredState.ARMED,
        expected_revision=0,
        generation_digest=_GENERATION,
        reviewed_files_digest=_REVIEWED,
        changed_at_utc=_NOW,
    )
    assert armed.armed is True
    assert armed.revision == 1
    restarted = V4UnattendedLiveArmStore(store.path).check(
        expected_generation_digest=_GENERATION,
        expected_reviewed_files_digest=_REVIEWED,
    )
    assert restarted.armed is True
    disarmed = store.set_desired_state(
        desired_state=V4ArmDesiredState.DISARMED,
        expected_revision=1,
        generation_digest=_GENERATION,
        reviewed_files_digest=_REVIEWED,
        changed_at_utc=_NOW,
    )
    assert disarmed.armed is False
    assert disarmed.revision == 2
    assert disarmed.blocked_reasons == ("OPERATOR_DISARMED",)


def test_generation_or_reviewed_digest_change_fails_closed(tmp_path) -> None:
    store = V4UnattendedLiveArmStore(tmp_path / "arm-state.json")
    store.set_desired_state(
        desired_state=V4ArmDesiredState.ARMED,
        expected_revision=0,
        generation_digest=_GENERATION,
        reviewed_files_digest=_REVIEWED,
        changed_at_utc=_NOW,
    )
    generation_changed = store.check(
        expected_generation_digest="sha256:" + "c" * 64,
        expected_reviewed_files_digest=_REVIEWED,
    )
    reviewed_changed = store.check(
        expected_generation_digest=_GENERATION,
        expected_reviewed_files_digest="sha256:" + "d" * 64,
    )
    assert generation_changed.armed is False
    assert "ARM_STATE_GENERATION_MISMATCH" in generation_changed.blocked_reasons
    assert reviewed_changed.armed is False
    assert "ARM_STATE_REVIEWED_FILES_MISMATCH" in reviewed_changed.blocked_reasons


def test_stale_revision_and_symlink_are_refused(tmp_path) -> None:
    store = V4UnattendedLiveArmStore(tmp_path / "arm-state.json")
    store.set_desired_state(
        desired_state=V4ArmDesiredState.ARMED,
        expected_revision=0,
        generation_digest=_GENERATION,
        reviewed_files_digest=_REVIEWED,
        changed_at_utc=_NOW,
    )
    with pytest.raises(V4UnattendedLiveArmStateError, match="REVISION_CONFLICT"):
        store.set_desired_state(
            desired_state=V4ArmDesiredState.DISARMED,
            expected_revision=0,
            generation_digest=_GENERATION,
            reviewed_files_digest=_REVIEWED,
            changed_at_utc=_NOW,
        )
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    store.path.unlink()
    store.path.symlink_to(real)
    assert (
        store.check(
            expected_generation_digest=_GENERATION,
            expected_reviewed_files_digest=_REVIEWED,
        ).blocked_reasons
        == ("ARM_STATE_SYMLINK_REFUSED",)
    )
