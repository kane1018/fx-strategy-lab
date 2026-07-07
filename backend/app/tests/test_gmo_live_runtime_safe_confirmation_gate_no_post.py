"""No-POST design tests for read-only runtime confirmation gate."""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_live_runtime_safe_confirmation_gate import (
    GmoReadOnlyRuntimeConfirmationInput,
    GmoReadOnlyRuntimeReadResultCategory,
    GmoReadOnlyRuntimeSafeConfirmationStatus,
    build_runtime_confirmation_snapshot,
    evaluate_gmo_read_only_runtime_safe_confirmation_gate,
)
from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSafeReadSnapshot,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_runtime_safe_confirmation_gate.py"
)


def _ready_input(**overrides) -> GmoReadOnlyRuntimeConfirmationInput:
    default = GmoReadOnlyRuntimeConfirmationInput(
        snapshot=GmoRuntimeSafeReadSnapshot(
            performed=True,
            fresh=True,
            position_status=GmoRuntimePositionSafeStatus.NO_POSITION,
            position_count_safe=0,
            active_pending_status=GmoRuntimeActivePendingSafeStatus.CLEAR,
            active_order_count_safe=0,
        ),
        branch_is_main=True,
        head_equals_origin_main_safe=True,
        working_tree_clean_safe=True,
        ahead_behind_zero=True,
        merge_not_in_progress=True,
        rebase_not_in_progress=True,
        operator_runtime_readiness=True,
        operator_current_turn_exact_confirmation=True,
        operator_ack_private_read_risk=True,
        operator_ack_no_post=True,
        operator_ack_not_actual_post_permission=True,
        credential_presence_safe_boolean=True,
        credential_source_safe_label="TEST_SOURCE",
        anomaly_evidence_not_synthetic_ready=True,
    )
    return GmoReadOnlyRuntimeConfirmationInput(**{**default.__dict__, **overrides})


def test_default_gate_is_fail_closed_and_falsey() -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        GmoReadOnlyRuntimeConfirmationInput()
    )
    assert result.ready is False
    assert result.status is GmoReadOnlyRuntimeSafeConfirmationStatus.BLOCKED
    assert bool(result) is False
    assert result.actual_post_permission is False
    assert result.entry_post_permission is False
    assert result.settlement_post_permission is False
    assert result.runtime_private_GET_executed is False


def test_ready_input_is_still_design_only() -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(_ready_input())
    assert result.ready is True
    assert result.status is GmoReadOnlyRuntimeSafeConfirmationStatus.READY
    assert result.snapshot.runtime_read_result_category.value == (
        GmoReadOnlyRuntimeReadResultCategory.READ_CONFIRMED_SAFE
    )
    assert result.runtime_position_status_safe_label == "NO_POSITION"
    assert result.position_count_safe_label == "COUNT_ZERO"
    assert result.active_pending_order_status_safe_label == "NO_ACTIVE_PENDING_ORDERS"
    assert result.active_pending_order_count_safe_label == "COUNT_ZERO"
    assert result.runtime_private_GET_executed is False
    assert result.future_operator_confirmation_required is True
    assert result.future_private_read_step_required is True
    assert bool(result) is False


@pytest.mark.parametrize(
    (
        "override,expected"
    ),
    [
        ({"head_equals_origin_main_safe": False}, "REPOSITORY_HEAD_NOT_MAIN"),
        ({"branch_is_main": False}, "REPOSITORY_HEAD_NOT_MAIN"),
        ({"working_tree_clean_safe": False}, "REPOSITORY_WORKING_TREE_NOT_CLEAN"),
    ],
)
def test_repository_gate_blocks_ready(override: dict, expected: str) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(_ready_input(**override))
    assert result.ready is False
    assert expected in result.blocked_reasons


@pytest.mark.parametrize(
    (
        "override,expected"
    ),
    [
        ({"operator_runtime_readiness": False}, "OPERATOR_RUNTIME_READINESS_NOT_CONFIRMED"),
        (
            {"operator_current_turn_exact_confirmation": False},
            "OPERATOR_CURRENT_TURN_CONFIRMATION_NOT_PROVIDED",
        ),
        (
            {"operator_ack_private_read_risk": False},
            "OPERATOR_PRIVATE_READ_RISK_NOT_ACKNOWLEDGED",
        ),
        ({"operator_ack_no_post": False}, "OPERATOR_NO_POST_ACKNOWLEDGMENT_MISSING"),
        (
            {"operator_ack_not_actual_post_permission": False},
            "OPERATOR_NOT_ACTUAL_POST_PERMISSION_ACK_MISSING",
        ),
    ],
)
def test_operator_gate_blocks(override: dict, expected: str) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(**override)
    )
    assert result.ready is False
    assert expected in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"credential_presence_safe_boolean": False}, "CREDENTIAL_PRESENCE_NOT_CONFIRMED"),
        ({"credential_source_safe_label": "NOT_PROVIDED"}, "CREDENTIAL_SOURCE_SAFE_LABEL_MISSING"),
        ({"credential_value_exposed": True}, "CREDENTIAL_VALUE_EXPOSED"),
        ({"credential_length_exposed": True}, "CREDENTIAL_LENGTH_EXPOSED"),
        ({"credential_hash_exposed": True}, "CREDENTIAL_HASH_EXPOSED"),
    ],
)
def test_credential_gate_blocks(override: dict, expected: str) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(**override)
    )
    assert result.ready is False
    assert expected in result.blocked_reasons


@pytest.mark.parametrize(
    (
        "override,expected"
    ),
    [
        (
            {
                "snapshot": GmoRuntimeSafeReadSnapshot(
                    performed=True,
                    fresh=True,
                    position_status=GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
                    position_count_safe=0,
                    active_pending_status=GmoRuntimeActivePendingSafeStatus.CLEAR,
                    active_order_count_safe=0,
                )
            },
        "RUNTIME_POSITION_SAFE_STATUS_NOT_NO_POSITION",
        ),
        (
            {
                "snapshot": GmoRuntimeSafeReadSnapshot(
                    performed=True,
                    fresh=True,
                    position_status=GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
                    position_count_safe=1,
                    active_pending_status=GmoRuntimeActivePendingSafeStatus.CLEAR,
                    active_order_count_safe=0,
                )
            },
            "RUNTIME_POSITION_COUNT_NOT_ZERO",
        ),
        (
            {
                "snapshot": GmoRuntimeSafeReadSnapshot(
                    performed=True,
                    fresh=True,
                    position_status=GmoRuntimePositionSafeStatus.NO_POSITION,
                    position_count_safe=0,
                    active_pending_status=GmoRuntimeActivePendingSafeStatus.CONFLICT,
                    active_order_count_safe=1,
                )
            },
            "ACTIVE_PENDING_ORDER_STATUS_CONFLICT",
        ),
    ],
)
def test_runtime_read_state_blocks(override: dict, expected: str) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(**override)
    )
    assert result.ready is False
    assert expected in result.blocked_reasons


@pytest.mark.parametrize(
    (
        "category,expected"
    ),
    [
        (GmoReadOnlyRuntimeReadResultCategory.READ_FAILED_SAFE, "RUNTIME_READ_FAILED"),
        (GmoReadOnlyRuntimeReadResultCategory.READ_TIMEOUT_SAFE, "RUNTIME_READ_TIMEOUT"),
        (GmoReadOnlyRuntimeReadResultCategory.READ_UNKNOWN_SAFE, "RUNTIME_READ_UNKNOWN"),
        (GmoReadOnlyRuntimeReadResultCategory.READ_REJECTED_SAFE, "RUNTIME_READ_REJECTED"),
    ],
)
def test_runtime_read_unknown_timeout_rejected_block(category, expected) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(override_runtime_read_result_category=category)
    )
    assert result.ready is False
    assert expected in result.blocked_reasons


def test_retry_repost_second_generic_settlement_requests_block() -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(
            retry_requested=True,
            repost_requested=True,
            second_post_requested=True,
            settlement_post_requested=True,
            generic_close_requested=True,
        )
    )
    assert result.ready is False
    assert "RETRY_REQUESTED_BLOCKED" in result.blocked_reasons
    assert "REPOST_REQUESTED_BLOCKED" in result.blocked_reasons
    assert "SECOND_POST_REQUESTED_BLOCKED" in result.blocked_reasons
    assert "SETTLEMENT_POST_REQUESTED_BLOCKED" in result.blocked_reasons
    assert "GENERIC_CLOSE_REQUESTED_BLOCKED" in result.blocked_reasons


def test_anomaly_non_synthetic_readiness_required() -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(anomaly_evidence_not_synthetic_ready=False)
    )
    assert result.ready is False
    assert "ANOMALY_EVIDENCE_NON_SYNTHETIC_NOT_READY" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"raw_response_exposed": True}, "RAW_RESPONSE_EXPOSED"),
        ({"raw_ids_exposed": True}, "RAW_IDS_EXPOSED"),
        ({"raw_price_or_size_values_exposed": True}, "RAW_PRICE_OR_SIZE_VALUES_EXPOSED"),
    ],
)
def test_raw_and_id_exposure_blocked(override: dict, expected: str) -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(_ready_input(**override))
    assert result.ready is False
    assert expected in result.blocked_reasons


def test_actual_post_implied_blocks() -> None:
    result = evaluate_gmo_read_only_runtime_safe_confirmation_gate(
        _ready_input(actual_post_permission_implied=True)
    )
    assert result.ready is False
    assert "ACTUAL_POST_PERMISSION_IMPLIED" in result.blocked_reasons
    assert result.entry_post_permission is False
    assert result.settlement_post_permission is False


def test_build_runtime_confirmation_snapshot_structural_shape() -> None:
    snapshot = build_runtime_confirmation_snapshot(
        GmoRuntimeSafeReadSnapshot(
            performed=True,
            fresh=True,
            position_status=GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
            position_count_safe=1,
            active_pending_status=GmoRuntimeActivePendingSafeStatus.CONFLICT,
            active_order_count_safe=1,
        )
    )
    assert snapshot.runtime_position_safe_status.value == "ONE_POSITION_OPEN"
    assert snapshot.position_count_safe_status.value == "COUNT_ONE"
    assert snapshot.active_pending_order_safe_status.value == "ACTIVE_OR_PENDING_ORDERS_PRESENT"
    assert snapshot.active_pending_order_count_safe_status.value == "COUNT_NONZERO"
    assert snapshot.runtime_read_result_category.value == (
        GmoReadOnlyRuntimeReadResultCategory.READ_CONFIRMED_SAFE
    )


def test_module_does_not_read_env_or_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text
    assert "load_dotenv" not in text
    assert "live_order_once" not in text
    assert "app.live_verification" not in text
