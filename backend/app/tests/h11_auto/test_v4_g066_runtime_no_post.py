from __future__ import annotations

from app.services.h11_v4_g066_runtime_projection_no_post import (
    G066PositionEvidence,
    project_g066_runtime_state,
)
from app.services.h11_v4_g066_runtime_result_no_post import (
    begin_g066_operation_60_no_post,
    load_g066_operation_60_outcome_no_post,
    record_g066_operation_60_outcome_no_post,
)


def test_arm_on_flat_is_waiting_and_entry_gate_is_separate() -> None:
    result = project_g066_runtime_state(
        arm_state="ON",
        position=G066PositionEvidence(open_position_count=0, active_order_count=0),
    )
    assert result["arm_state"] == "ON"
    assert result["effective_state"] == "ON_WAITING"
    assert result["entry_gate_open"] is True
    assert result["broker_write"] is False
    assert result["actual_post_authorized"] is False


def test_protected_position_is_exit_only_and_never_entry_ready() -> None:
    result = project_g066_runtime_state(
        arm_state="ON",
        position=G066PositionEvidence(
            open_position_count=1,
            active_order_count=1,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        ),
    )
    assert result["effective_state"] == "ON_EXIT_ONLY"
    assert result["entry_gate_open"] is False
    assert result["entry_state"] == "EXIT_ONLY"


def test_unconfirmed_position_is_halted() -> None:
    result = project_g066_runtime_state(
        arm_state="ON",
        position={"open_position_count": 1, "active_order_count": 0},
    )
    assert result["effective_state"] == "HALTED"
    assert result["entry_gate_open"] is False


def test_arm_off_does_not_stop_exit_management() -> None:
    result = project_g066_runtime_state(
        arm_state="OFF",
        position=G066PositionEvidence(
            open_position_count=1,
            active_order_count=1,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        ),
    )
    assert result["effective_state"] == "EXIT_ONLY"
    assert result["entry_gate_open"] is False


def test_pending_and_unknown_fail_closed() -> None:
    for evidence in (
        {"open_position_count": 0, "active_order_count": 0, "pending": True},
        {"open_position_count": 0, "active_order_count": 0, "unknown": True},
    ):
        result = project_g066_runtime_state(arm_state="ON", position=evidence)
        assert result["effective_state"] == "HALTED"
        assert result["entry_gate_open"] is False


def test_operation_60_marker_is_one_use_and_no_post(tmp_path) -> None:
    generation_digest = "sha256:" + "1" * 64
    reviewed_digest = "sha256:" + "2" * 64
    begin_g066_operation_60_no_post(
        state_root=tmp_path,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_digest,
    )
    record_g066_operation_60_outcome_no_post(
        state_root=tmp_path,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_digest,
        outcome="PASSED",
    )
    assert load_g066_operation_60_outcome_no_post(
        state_root=tmp_path,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_digest,
    ) == "PASSED"
