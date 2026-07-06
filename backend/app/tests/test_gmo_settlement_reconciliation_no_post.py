"""No-POST tests for the GMO official settlement reconciliation skeleton.

Pure logic over synthetic safe-status/safe-count fixtures. No real read-only
API call is performed in this Step.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_settlement_reconciliation import (
    GmoSettlementReconciliationInput,
    GmoSettlementReconciliationStatus,
    GmoSettlementSafeReadSnapshot,
    build_gmo_settlement_reconciliation_input_from_safe_snapshot,
    build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result,
    evaluate_gmo_settlement_reconciliation,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_settlement_reconciliation.py"
)


def test_no_position_count_zero_is_reconciled() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe="NO_POSITION",
            post_settlement_position_count_safe=0,
        )
    )
    assert result.reconciled is True
    assert result.status is GmoSettlementReconciliationStatus.RECONCILED_NO_POSITION
    assert result.retry_allowed is False
    assert result.repost_allowed is False


def test_one_position_open_is_unreconciled() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe="ONE_POSITION_OPEN",
            post_settlement_position_count_safe=1,
        )
    )
    assert result.reconciled is False
    assert result.status is GmoSettlementReconciliationStatus.UNRECONCILED_POSITION_STILL_OPEN
    assert result.retry_allowed is False
    assert result.repost_allowed is False


def test_multiple_positions_is_blocked_dangerous() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe="MULTIPLE_POSITIONS",
            post_settlement_position_count_safe=2,
        )
    )
    assert result.reconciled is False
    assert result.status is GmoSettlementReconciliationStatus.BLOCKED_MULTIPLE_POSITIONS


def test_missing_safe_read_is_unknown() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe=None,
            post_settlement_position_count_safe=None,
        )
    )
    assert result.reconciled is False
    assert result.status is GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE


@pytest.mark.parametrize(
    "category",
    ["REJECTED_SANITIZED", "UNKNOWN_SANITIZED"],
)
def test_settlement_not_accepted_never_reconciles_and_never_retries(category: str) -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category=category)
    )
    assert result.reconciled is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False


def test_rejected_status_is_distinguished_from_unknown() -> None:
    rejected = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="REJECTED_SANITIZED")
    )
    unknown = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="UNKNOWN_SANITIZED")
    )
    assert rejected.status is GmoSettlementReconciliationStatus.BLOCKED_SETTLEMENT_NOT_ACCEPTED
    assert unknown.status is GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE


def test_active_or_pending_conflict_blocks_regardless_of_position_status() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe="NO_POSITION",
            post_settlement_position_count_safe=0,
            active_or_pending_order_conflict_detected=True,
        )
    )
    assert result.reconciled is False
    assert (
        result.status
        is GmoSettlementReconciliationStatus.BLOCKED_ACTIVE_OR_PENDING_ORDER_CONFLICT
    )


def test_safe_snapshot_adapter_maps_successful_read_through() -> None:
    reconciliation_input = build_gmo_settlement_reconciliation_input_from_safe_snapshot(
        settlement_result_category="ACCEPTED_SANITIZED",
        snapshot=GmoSettlementSafeReadSnapshot(
            safe_read_succeeded=True,
            position_status_safe="NO_POSITION",
            position_count_safe=0,
        ),
    )
    result = evaluate_gmo_settlement_reconciliation(reconciliation_input)
    assert result.reconciled is True
    assert result.status is GmoSettlementReconciliationStatus.RECONCILED_NO_POSITION


def test_safe_snapshot_adapter_maps_failed_read_to_unavailable() -> None:
    reconciliation_input = build_gmo_settlement_reconciliation_input_from_safe_snapshot(
        settlement_result_category="ACCEPTED_SANITIZED",
        snapshot=GmoSettlementSafeReadSnapshot(safe_read_succeeded=False),
    )
    result = evaluate_gmo_settlement_reconciliation(reconciliation_input)
    assert result.reconciled is False
    assert result.status is GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE


def test_safe_snapshot_adapter_propagates_active_or_pending_conflict() -> None:
    reconciliation_input = build_gmo_settlement_reconciliation_input_from_safe_snapshot(
        settlement_result_category="ACCEPTED_SANITIZED",
        snapshot=GmoSettlementSafeReadSnapshot(
            safe_read_succeeded=True,
            position_status_safe="NO_POSITION",
            position_count_safe=0,
            active_or_pending_order_conflict_detected=True,
        ),
    )
    result = evaluate_gmo_settlement_reconciliation(reconciliation_input)
    assert result.reconciled is False
    assert (
        result.status
        is GmoSettlementReconciliationStatus.BLOCKED_ACTIVE_OR_PENDING_ORDER_CONFLICT
    )


def test_safe_snapshot_from_counts_zero_positions_is_no_position() -> None:
    snapshot = build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
        open_positions_count=0, active_orders_count=0,
    )
    assert snapshot.safe_read_succeeded is True
    assert snapshot.position_status_safe == "NO_POSITION"
    assert snapshot.position_count_safe == 0
    assert snapshot.active_or_pending_order_conflict_detected is False


def test_safe_snapshot_from_counts_one_position_is_one_open() -> None:
    snapshot = build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
        open_positions_count=1, active_orders_count=0,
    )
    assert snapshot.position_status_safe == "ONE_POSITION_OPEN"


def test_safe_snapshot_from_counts_multiple_positions() -> None:
    snapshot = build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
        open_positions_count=3, active_orders_count=0,
    )
    assert snapshot.position_status_safe == "MULTIPLE_POSITIONS"


def test_safe_snapshot_from_counts_active_orders_flag_conflict() -> None:
    snapshot = build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
        open_positions_count=0, active_orders_count=2,
    )
    assert snapshot.active_or_pending_order_conflict_detected is True


def test_safe_snapshot_from_counts_read_failure_is_unavailable() -> None:
    snapshot = build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
        open_positions_count=0, active_orders_count=0, read_succeeded=False,
    )
    assert snapshot.safe_read_succeeded is False
    assert snapshot.position_status_safe is None
    assert snapshot.position_count_safe is None


def test_safe_snapshot_from_counts_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result(
            open_positions_count=-1, active_orders_count=0,
        )


def test_safe_snapshot_from_counts_signature_only_accepts_ints_and_bool() -> None:
    """Structural guarantee: the function cannot receive raw responses, IDs,
    quantities, or prices -- its parameters are only integers and a bool.
    """
    import inspect

    signature = inspect.signature(
        build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result
    )
    for name, parameter in signature.parameters.items():
        assert parameter.annotation in ("int", "bool", int, bool), (
            f"parameter {name} must be int or bool, got {parameter.annotation}"
        )


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_call_http_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text
