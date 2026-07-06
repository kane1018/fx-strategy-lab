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
