"""Read-only runtime safety confirmation gate design primitives (no-POST).

This module defines a fail-closed gate model for a future step that will
execute read-only private runtime checks. It is intentionally disconnected from
network, credentials, and raw payload handling:

- default denial (`__bool__` always False)
- no raw IDs, values, or payload fields
- fixed no-POST posture
- explicit operator current-turn confirmation requirements
- explicit anomaly/non-synthetic criteria hooks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSafeReadSnapshot,
)


class GmoReadOnlyRuntimePositionSafeStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS_OPEN = "MULTIPLE_POSITIONS_OPEN"
    UNKNOWN = "UNKNOWN"


class GmoReadOnlyRuntimeCountSafeStatus(str, Enum):
    COUNT_ZERO = "COUNT_ZERO"
    COUNT_ONE = "COUNT_ONE"
    COUNT_MULTIPLE = "COUNT_MULTIPLE"
    COUNT_NONZERO = "COUNT_NONZERO"
    COUNT_UNKNOWN = "COUNT_UNKNOWN"


class GmoReadOnlyActivePendingSafeStatus(str, Enum):
    NO_ACTIVE_PENDING_ORDERS = "NO_ACTIVE_PENDING_ORDERS"
    ACTIVE_OR_PENDING_ORDERS_PRESENT = "ACTIVE_OR_PENDING_ORDERS_PRESENT"
    UNKNOWN = "UNKNOWN"


class GmoReadOnlyRuntimeReadResultCategory(str, Enum):
    READ_CONFIRMED_SAFE = "READ_CONFIRMED_SAFE"
    READ_FAILED_SAFE = "READ_FAILED_SAFE"
    READ_TIMEOUT_SAFE = "READ_TIMEOUT_SAFE"
    READ_UNKNOWN_SAFE = "READ_UNKNOWN_SAFE"
    READ_REJECTED_SAFE = "READ_REJECTED_SAFE"


class GmoReadOnlyRuntimeSafeConfirmationStatus(str, Enum):
    READY = "RUNTIME_SAFE_CONFIRMATION_READY_FOR_FUTURE_STEP"
    BLOCKED = "RUNTIME_SAFE_CONFIRMATION_BLOCKED"


def _classify_position_count(count: int | None) -> GmoReadOnlyRuntimeCountSafeStatus:
    if count is None:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_UNKNOWN
    if count == 0:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_ZERO
    if count == 1:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_ONE
    if count > 1:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_MULTIPLE
    return GmoReadOnlyRuntimeCountSafeStatus.COUNT_UNKNOWN


def _classify_active_pending_count(
    count: int | None,
) -> GmoReadOnlyRuntimeCountSafeStatus:
    if count is None:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_UNKNOWN
    if count == 0:
        return GmoReadOnlyRuntimeCountSafeStatus.COUNT_ZERO
    return GmoReadOnlyRuntimeCountSafeStatus.COUNT_NONZERO


def _classify_position_status(
    status: GmoRuntimePositionSafeStatus,
) -> GmoReadOnlyRuntimePositionSafeStatus:
    if status is GmoRuntimePositionSafeStatus.NO_POSITION:
        return GmoReadOnlyRuntimePositionSafeStatus.NO_POSITION
    if status is GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN:
        return GmoReadOnlyRuntimePositionSafeStatus.ONE_POSITION_OPEN
    if status is GmoRuntimePositionSafeStatus.MULTIPLE_POSITIONS:
        return GmoReadOnlyRuntimePositionSafeStatus.MULTIPLE_POSITIONS_OPEN
    return GmoReadOnlyRuntimePositionSafeStatus.UNKNOWN


def _classify_active_pending_status(
    status: GmoRuntimeActivePendingSafeStatus,
) -> GmoReadOnlyActivePendingSafeStatus:
    if status is GmoRuntimeActivePendingSafeStatus.CLEAR:
        return GmoReadOnlyActivePendingSafeStatus.NO_ACTIVE_PENDING_ORDERS
    if status is GmoRuntimeActivePendingSafeStatus.CONFLICT:
        return GmoReadOnlyActivePendingSafeStatus.ACTIVE_OR_PENDING_ORDERS_PRESENT
    return GmoReadOnlyActivePendingSafeStatus.UNKNOWN


def _classify_runtime_read_category(
    snapshot: GmoRuntimeSafeReadSnapshot,
    override: GmoReadOnlyRuntimeReadResultCategory | None = None,
) -> GmoReadOnlyRuntimeReadResultCategory:
    if override is not None:
        return override
    if not snapshot.performed:
        return GmoReadOnlyRuntimeReadResultCategory.READ_FAILED_SAFE
    if not snapshot.fresh:
        return GmoReadOnlyRuntimeReadResultCategory.READ_TIMEOUT_SAFE
    if (
        snapshot.position_status is GmoRuntimePositionSafeStatus.UNKNOWN
        or snapshot.active_pending_status is GmoRuntimeActivePendingSafeStatus.UNKNOWN
    ):
        return GmoReadOnlyRuntimeReadResultCategory.READ_UNKNOWN_SAFE
    return GmoReadOnlyRuntimeReadResultCategory.READ_CONFIRMED_SAFE


@dataclass(frozen=True)
class GmoReadOnlyRuntimeSafeConfirmationSnapshot:
    """Safe outputs only."""

    runtime_position_safe_status: GmoReadOnlyRuntimePositionSafeStatus
    position_count_safe_status: GmoReadOnlyRuntimeCountSafeStatus
    active_pending_order_safe_status: GmoReadOnlyActivePendingSafeStatus
    active_pending_order_count_safe_status: GmoReadOnlyRuntimeCountSafeStatus
    runtime_read_result_category: GmoReadOnlyRuntimeReadResultCategory


@dataclass(frozen=True)
class GmoReadOnlyRuntimeSafeConfirmationInput:
    snapshot: GmoRuntimeSafeReadSnapshot = field(
        default_factory=GmoRuntimeSafeReadSnapshot
    )
    # repository gate
    branch_is_main: bool = False
    head_equals_origin_main_safe: bool = False
    working_tree_clean_safe: bool = True
    ahead_behind_zero: bool = True
    merge_not_in_progress: bool = True
    rebase_not_in_progress: bool = True

    # operator current-turn gate
    operator_runtime_readiness: bool = False
    operator_current_turn_exact_confirmation: bool = False
    operator_ack_private_read_risk: bool = False
    operator_ack_no_post: bool = False
    operator_ack_not_actual_post_permission: bool = False

    # credential handling
    credential_presence_safe_boolean: bool = False
    credential_source_safe_label: str = "NOT_PROVIDED"
    credential_value_exposed: bool = False
    credential_length_exposed: bool = False
    credential_hash_exposed: bool = False
    credential_fingerprint_exposed: bool = False
    credential_prefix_suffix_exposed: bool = False
    env_value_exposed: bool = False

    # anomaly / evidence readiness
    anomaly_evidence_not_synthetic_ready: bool = False
    raw_response_exposed: bool = False
    raw_ids_exposed: bool = False
    raw_price_or_size_values_exposed: bool = False

    # execution safety
    retry_requested: bool = False
    repost_requested: bool = False
    second_post_requested: bool = False
    settlement_post_requested: bool = False
    generic_close_requested: bool = False
    runtime_read_unknown_rejected_or_timeout_required_to_block: bool = True

    # design-time explicit outputs
    runtime_private_GET_executed: bool = False
    runtime_private_GET_required: bool = True
    actual_post_permission_implied: bool = False
    future_private_read_step_required: bool = True
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    override_runtime_read_result_category: GmoReadOnlyRuntimeReadResultCategory | None = None


GmoReadOnlyRuntimeConfirmationInput = GmoReadOnlyRuntimeSafeConfirmationInput


@dataclass(frozen=True)
class GmoReadOnlyRuntimeSafeConfirmationResult:
    ready: bool
    status: GmoReadOnlyRuntimeSafeConfirmationStatus
    blocked_reasons: tuple[str, ...]
    snapshot: GmoReadOnlyRuntimeSafeConfirmationSnapshot
    future_operator_confirmation_required: bool = True
    future_private_read_step_required: bool = True
    actual_post_permission: bool = False
    entry_post_permission: bool = False
    settlement_post_permission: bool = False
    runtime_private_GET_executed: bool = False
    runtime_position_status_safe_label: str = ""
    position_count_safe_label: str = ""
    active_pending_order_status_safe_label: str = ""
    active_pending_order_count_safe_label: str = ""
    actual_post_permission_implied: bool = False

    def __bool__(self) -> bool:
        return False


def build_runtime_confirmation_snapshot(
    snapshot: GmoRuntimeSafeReadSnapshot,
    override_runtime_read_result_category: GmoReadOnlyRuntimeReadResultCategory | None = None,
) -> GmoReadOnlyRuntimeSafeConfirmationSnapshot:
    return GmoReadOnlyRuntimeSafeConfirmationSnapshot(
        runtime_position_safe_status=_classify_position_status(snapshot.position_status),
        position_count_safe_status=_classify_position_count(snapshot.position_count_safe),
        active_pending_order_safe_status=_classify_active_pending_status(
            snapshot.active_pending_status
        ),
        active_pending_order_count_safe_status=_classify_active_pending_count(
            snapshot.active_order_count_safe
        ),
        runtime_read_result_category=_classify_runtime_read_category(
            snapshot,
            override=override_runtime_read_result_category,
        ),
    )


def evaluate_gmo_read_only_runtime_safe_confirmation_gate(
    gate_input: GmoReadOnlyRuntimeSafeConfirmationInput,
) -> GmoReadOnlyRuntimeSafeConfirmationResult:
    blockers: list[str] = []

    if gate_input.override_runtime_read_result_category is None:
        read_result_category = _classify_runtime_read_category(
            gate_input.snapshot, override=None
        )
    else:
        read_result_category = gate_input.override_runtime_read_result_category

    if not gate_input.branch_is_main or not gate_input.head_equals_origin_main_safe:
        blockers.append("REPOSITORY_HEAD_NOT_MAIN")
    if not gate_input.working_tree_clean_safe:
        blockers.append("REPOSITORY_WORKING_TREE_NOT_CLEAN")
    if not gate_input.ahead_behind_zero:
        blockers.append("REPOSITORY_AHEAD_BEHIND_NOT_ZERO")
    if not gate_input.merge_not_in_progress:
        blockers.append("REPOSITORY_MERGE_IN_PROGRESS")
    if not gate_input.rebase_not_in_progress:
        blockers.append("REPOSITORY_REBASE_IN_PROGRESS")

    if not gate_input.operator_runtime_readiness:
        blockers.append("OPERATOR_RUNTIME_READINESS_NOT_CONFIRMED")
    if not gate_input.operator_current_turn_exact_confirmation:
        blockers.append(
            "OPERATOR_CURRENT_TURN_CONFIRMATION_NOT_PROVIDED"
        )
    if not gate_input.operator_ack_private_read_risk:
        blockers.append("OPERATOR_PRIVATE_READ_RISK_NOT_ACKNOWLEDGED")
    if not gate_input.operator_ack_no_post:
        blockers.append("OPERATOR_NO_POST_ACKNOWLEDGMENT_MISSING")
    if not gate_input.operator_ack_not_actual_post_permission:
        blockers.append("OPERATOR_NOT_ACTUAL_POST_PERMISSION_ACK_MISSING")

    if not gate_input.credential_presence_safe_boolean:
        blockers.append("CREDENTIAL_PRESENCE_NOT_CONFIRMED")
    if gate_input.credential_source_safe_label in ("", "NOT_PROVIDED"):
        blockers.append("CREDENTIAL_SOURCE_SAFE_LABEL_MISSING")
    if gate_input.credential_value_exposed:
        blockers.append("CREDENTIAL_VALUE_EXPOSED")
    if gate_input.credential_length_exposed:
        blockers.append("CREDENTIAL_LENGTH_EXPOSED")
    if gate_input.credential_hash_exposed:
        blockers.append("CREDENTIAL_HASH_EXPOSED")
    if gate_input.credential_fingerprint_exposed:
        blockers.append("CREDENTIAL_FINGERPRINT_EXPOSED")
    if gate_input.credential_prefix_suffix_exposed:
        blockers.append("CREDENTIAL_PREFIX_SUFFIX_EXPOSED")
    if gate_input.env_value_exposed:
        blockers.append("ENV_VALUE_EXPOSED")

    safe_snapshot = build_runtime_confirmation_snapshot(
        gate_input.snapshot,
        gate_input.override_runtime_read_result_category,
    )
    if read_result_category is GmoReadOnlyRuntimeReadResultCategory.READ_FAILED_SAFE:
        blockers.append("RUNTIME_READ_FAILED")
    elif read_result_category is GmoReadOnlyRuntimeReadResultCategory.READ_TIMEOUT_SAFE:
        blockers.append("RUNTIME_READ_TIMEOUT")
    elif read_result_category is GmoReadOnlyRuntimeReadResultCategory.READ_UNKNOWN_SAFE:
        blockers.append("RUNTIME_READ_UNKNOWN")
    elif read_result_category is GmoReadOnlyRuntimeReadResultCategory.READ_REJECTED_SAFE:
        blockers.append("RUNTIME_READ_REJECTED")

    if (
        safe_snapshot.runtime_position_safe_status
        is not GmoReadOnlyRuntimePositionSafeStatus.NO_POSITION
    ):
        blockers.append("RUNTIME_POSITION_SAFE_STATUS_NOT_NO_POSITION")
    if (
        safe_snapshot.position_count_safe_status
        is not GmoReadOnlyRuntimeCountSafeStatus.COUNT_ZERO
    ):
        blockers.append("RUNTIME_POSITION_COUNT_NOT_ZERO")
    if (
        safe_snapshot.active_pending_order_safe_status
        is not GmoReadOnlyActivePendingSafeStatus.NO_ACTIVE_PENDING_ORDERS
    ):
        blockers.append("ACTIVE_PENDING_ORDER_STATUS_CONFLICT")
    if (
        safe_snapshot.active_pending_order_count_safe_status
        is not GmoReadOnlyRuntimeCountSafeStatus.COUNT_ZERO
    ):
        blockers.append("ACTIVE_PENDING_ORDER_COUNT_NOT_ZERO")

    if gate_input.retry_requested:
        blockers.append("RETRY_REQUESTED_BLOCKED")
    if gate_input.repost_requested:
        blockers.append("REPOST_REQUESTED_BLOCKED")
    if gate_input.second_post_requested:
        blockers.append("SECOND_POST_REQUESTED_BLOCKED")
    if gate_input.settlement_post_requested:
        blockers.append("SETTLEMENT_POST_REQUESTED_BLOCKED")
    if gate_input.generic_close_requested:
        blockers.append("GENERIC_CLOSE_REQUESTED_BLOCKED")

    if not gate_input.anomaly_evidence_not_synthetic_ready:
        blockers.append("ANOMALY_EVIDENCE_NON_SYNTHETIC_NOT_READY")

    if not gate_input.runtime_private_GET_required:
        blockers.append("RUNTIME_PRIVATE_GET_NOT_REQUIRED")
    if gate_input.runtime_private_GET_executed:
        blockers.append("RUNTIME_PRIVATE_GET_EXECUTED_OUTSIDE_DESIGN")

    if (
        gate_input.runtime_read_unknown_rejected_or_timeout_required_to_block
        and read_result_category
        in (
            GmoReadOnlyRuntimeReadResultCategory.READ_UNKNOWN_SAFE,
            GmoReadOnlyRuntimeReadResultCategory.READ_REJECTED_SAFE,
            GmoReadOnlyRuntimeReadResultCategory.READ_TIMEOUT_SAFE,
        )
    ):
        blockers.append("RUNTIME_RUNTIME_BLOCKED_FOR_UNKNOWN_OR_TIMEOUT_OR_REJECTED")

    if gate_input.raw_response_exposed:
        blockers.append("RAW_RESPONSE_EXPOSED")
    if gate_input.raw_ids_exposed:
        blockers.append("RAW_IDS_EXPOSED")
    if gate_input.raw_price_or_size_values_exposed:
        blockers.append("RAW_PRICE_OR_SIZE_VALUES_EXPOSED")

    if gate_input.actual_post_permission_implied:
        blockers.append("ACTUAL_POST_PERMISSION_IMPLIED")

    ready = not blockers
    status = (
        GmoReadOnlyRuntimeSafeConfirmationStatus.READY
        if ready
        else GmoReadOnlyRuntimeSafeConfirmationStatus.BLOCKED
    )

    return GmoReadOnlyRuntimeSafeConfirmationResult(
        ready=ready,
        status=status,
        blocked_reasons=tuple(blockers),
        snapshot=safe_snapshot,
        future_operator_confirmation_required=True,
        future_private_read_step_required=True,
        actual_post_permission=False,
        entry_post_permission=False,
        settlement_post_permission=False,
        runtime_private_GET_executed=False,
        runtime_position_status_safe_label=safe_snapshot.runtime_position_safe_status.value,
        position_count_safe_label=safe_snapshot.position_count_safe_status.value,
        active_pending_order_status_safe_label=safe_snapshot.active_pending_order_safe_status.value,
        active_pending_order_count_safe_label=(
            safe_snapshot.active_pending_order_count_safe_status.value
        ),
        actual_post_permission_implied=False,
    )
