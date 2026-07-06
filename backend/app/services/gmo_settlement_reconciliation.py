"""GMO FX official settlement reconciliation skeleton: no real read yet.

A sanitized "settlement accepted" result is never treated as "done" by
itself -- OANDA's own broker follows the same principle with
`close_unconfirmed` (see `app/brokers/oanda_broker.py`). This module
formalizes the equivalent rule for GMO: reconciliation only counts as
complete when a read-only safe status/count confirms `NO_POSITION`/`count=0`
after the settlement attempt. This Step does not perform any real read-only
API call -- callers supply the post-settlement safe status/count as a
synthetic fixture (or, in a later Step, from the real private read-only
client already audited in `app/private_api/`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoSettlementResultCategory(str, Enum):
    ACCEPTED_SANITIZED = "ACCEPTED_SANITIZED"
    REJECTED_SANITIZED = "REJECTED_SANITIZED"
    UNKNOWN_SANITIZED = "UNKNOWN_SANITIZED"


class GmoPostSettlementPositionStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS = "MULTIPLE_POSITIONS"


class GmoSettlementReconciliationStatus(str, Enum):
    RECONCILED_NO_POSITION = "RECONCILED_NO_POSITION"
    UNRECONCILED_POSITION_STILL_OPEN = "UNRECONCILED_POSITION_STILL_OPEN"
    BLOCKED_MULTIPLE_POSITIONS = "BLOCKED_MULTIPLE_POSITIONS"
    BLOCKED_SETTLEMENT_NOT_ACCEPTED = "BLOCKED_SETTLEMENT_NOT_ACCEPTED"
    UNKNOWN_SAFE_READ_UNAVAILABLE = "UNKNOWN_SAFE_READ_UNAVAILABLE"


@dataclass(frozen=True)
class GmoSettlementReconciliationInput:
    settlement_result_category: str
    post_settlement_position_status_safe: str | None = None
    post_settlement_position_count_safe: int | None = None


@dataclass(frozen=True)
class GmoSettlementReconciliationResult:
    status: GmoSettlementReconciliationStatus
    reconciled: bool
    retry_allowed: bool
    repost_allowed: bool
    safe_reason: str


def evaluate_gmo_settlement_reconciliation(
    reconciliation_input: GmoSettlementReconciliationInput,
) -> GmoSettlementReconciliationResult:
    """Reconcile a settlement attempt against a read-only safe position read.

    retry/repost are always false: a rejected, unknown, unreconciled, or
    ambiguous result stops here for manual operator resolution rather than
    ever being retried automatically.
    """
    if (
        reconciliation_input.settlement_result_category
        == GmoSettlementResultCategory.UNKNOWN_SANITIZED.value
    ):
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE,
            reconciled=False,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="settlement_result_unknown",
        )
    if (
        reconciliation_input.settlement_result_category
        != GmoSettlementResultCategory.ACCEPTED_SANITIZED.value
    ):
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.BLOCKED_SETTLEMENT_NOT_ACCEPTED,
            reconciled=False,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="settlement_rejected",
        )

    position_status = reconciliation_input.post_settlement_position_status_safe
    position_count = reconciliation_input.post_settlement_position_count_safe

    if position_status is None or position_count is None:
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE,
            reconciled=False,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="safe_read_unavailable",
        )
    if position_status == GmoPostSettlementPositionStatus.MULTIPLE_POSITIONS.value:
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.BLOCKED_MULTIPLE_POSITIONS,
            reconciled=False,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="multiple_positions_detected_after_settlement",
        )
    if (
        position_status == GmoPostSettlementPositionStatus.NO_POSITION.value
        and position_count == 0
    ):
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.RECONCILED_NO_POSITION,
            reconciled=True,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="reconciled",
        )
    if position_status == GmoPostSettlementPositionStatus.ONE_POSITION_OPEN.value:
        return GmoSettlementReconciliationResult(
            status=GmoSettlementReconciliationStatus.UNRECONCILED_POSITION_STILL_OPEN,
            reconciled=False,
            retry_allowed=False,
            repost_allowed=False,
            safe_reason="position_still_open",
        )
    return GmoSettlementReconciliationResult(
        status=GmoSettlementReconciliationStatus.UNKNOWN_SAFE_READ_UNAVAILABLE,
        reconciled=False,
        retry_allowed=False,
        repost_allowed=False,
        safe_reason="unrecognized_position_status",
    )
