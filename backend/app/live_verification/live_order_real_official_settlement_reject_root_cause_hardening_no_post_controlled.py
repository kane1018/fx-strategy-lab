"""Official settlement rejected root-cause hardening, no POST.

This module combines only already-safe labels from the official-settlement
route, target consistency, side provenance, real-network binding, and safe
rejection category capture layers. It never calls HTTP, reads env, accepts raw
broker response text, executes position-specific settlement, or exposes IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_real_network_client_binding_no_post_controlled import (  # noqa: E501
    build_official_settlement_real_network_client_binding_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_rejection_safe_category_reporting_handoff_no_post_controlled import (  # noqa: E501
    build_official_settlement_rejection_safe_category_reporting_handoff_no_post,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (  # noqa: E501
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    build_official_settlement_route_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_safe_rejection_category_no_post_controlled import (  # noqa: E501
    OPERATOR_UI_REJECTION_SAFE_REASON_ACTIVE_ORDER_CONFLICT,
    OPERATOR_UI_REJECTION_SAFE_REASON_MARKET_OR_SESSION,
    OPERATOR_UI_REJECTION_SAFE_REASON_NOT_DISPLAYED,
    OPERATOR_UI_REJECTION_SAFE_REASON_PERMISSION,
    OPERATOR_UI_REJECTION_SAFE_REASON_POSITION_NOT_FOUND,
    OPERATOR_UI_REJECTION_SAFE_REASON_RATE_LIMIT_OR_TEMPORARY,
    OPERATOR_UI_REJECTION_SAFE_REASON_SIZE_OR_TARGET,
    OPERATOR_UI_REJECTION_SAFE_REASON_UNKNOWN,
    SAFE_API_STATUS_NONZERO,
    SAFE_API_STATUS_REJECTED,
    SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT,
    SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED,
    SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND,
    SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT,
    SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT,
    SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH,
    SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH,
    SAFE_BROKER_ERROR_CODE_FAMILY_ACCOUNT_OR_PERMISSION_CONSTRAINT,
    SAFE_BROKER_ERROR_CODE_FAMILY_PARAMETER_OR_REQUEST_SHAPE,
    SAFE_BROKER_ERROR_CODE_FAMILY_POSITION_STATE_OR_TARGET_NOT_FOUND,
    SAFE_BROKER_ERROR_CODE_FAMILY_RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
    SAFE_BROKER_ERROR_CODE_FAMILY_SESSION_OR_MARKET_CONSTRAINT,
    SAFE_BROKER_ERROR_CODE_FAMILY_SIZE_OR_TARGET_MISMATCH,
    SAFE_HTTP_STATUS_CLIENT_ERROR,
    SAFE_HTTP_STATUS_RATE_LIMIT,
    SAFE_HTTP_STATUS_SERVER_ERROR,
)
from app.live_verification.live_order_real_official_settlement_side_provenance_gate_no_post_controlled import (  # noqa: E501
    build_official_settlement_side_provenance_gate_no_post_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

STEP_NAME = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECT-ROOT-CAUSE-"
    "HARDENING-NO-POST-C"
)

SAFE_ERROR_CODE_CAPTURE_READY = "SAFE_ERROR_CODE_CAPTURE_READY_ALLOWLIST_ONLY"
POSITION_SPECIFIC_SAFE_ID_STATUS = (
    "POSITION_SPECIFIC_SAFE_ID_DESIGNED_BUT_ACTUAL_PATH_BLOCKED_UNTIL_OPAQUE_HANDLE"
)
SIZE_BASED_TARGET_CONSISTENCY_READY = (
    "SIZE_BASED_TARGET_CONSISTENCY_READY_SAFE_LABEL_SCOPE"
)
OPERATOR_UI_SAFE_LABEL_COLLECTION_READY = (
    "OPERATOR_UI_SAFE_LABEL_COLLECTION_READY_NO_TEXT_NO_ID_VALUE"
)
FRESH_RETRY_READY_WITH_GATES = "READY_WITH_FRESH_GATES_REQUIRED"
FRESH_RETRY_BLOCKED_NO_POST = "BLOCKED_NO_POST"
NEXT_STEP_FRESH_ENTRY_SIGNAL = (
    "Step 6G-PC-OX-R-FRESH-ENTRY-SIGNAL-SAFE-LABEL-CONFIRMATION-NO-POST-C"
)
NEXT_STEP_FIX_HARDENING = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECT-ROOT-CAUSE-HARDENING-FIX-NO-POST-C"
)


class OfficialSettlementRejectRootCauseHardeningStatus(StrEnum):
    READY_NO_POST = "OFFICIAL_SETTLEMENT_REJECT_ROOT_CAUSE_HARDENING_READY_NO_POST"
    BLOCKED_NO_POST = "OFFICIAL_SETTLEMENT_REJECT_ROOT_CAUSE_HARDENING_BLOCKED_NO_POST"


@dataclass(frozen=True)
class OfficialSettlementRejectRootCauseHardeningInput:
    manual_intervention_performed: bool = True
    runtime_position_status_current: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.NO_POSITION
    )
    position_count_safe_current: int = 0
    active_order_count_safe_current: int = 0
    pending_order_count_safe_current: int = 0

    safe_error_code_allowlist_ready: bool = True
    safe_api_status_label_allowed: bool = True
    safe_broker_error_code_label_allowed: bool = True
    safe_broker_error_code_family_allowed: bool = True
    safe_http_status_label_allowed: bool = True
    operator_ui_safe_label_collection_ready: bool = True
    official_error_code_family_mapping_recorded: bool = True

    size_based_request_uses_size_only: bool = True
    size_based_request_includes_settle_position: bool = False
    size_and_settle_position_mutually_exclusive: bool = True
    request_target_consistency_safe_label_available: bool = True
    active_orders_plus_target_safe_check_available: bool = True

    position_specific_safe_identifier_handling_ready: bool = False
    position_specific_actual_path_allowed: bool = False
    position_specific_opaque_handle_design_recorded: bool = True
    position_specific_identifier_rendered: bool = False
    position_specific_identifier_persisted: bool = False

    actual_post_this_step: bool = False
    entry_post_this_step: bool = False
    settlement_post_this_step: bool = False
    retry_this_step: bool = False
    repost_this_step: bool = False
    second_post_this_step: bool = False
    generic_close_this_step: bool = False
    ledger_update: bool = False
    receipt_handoff: bool = False
    raw_id_value_exposure: bool = False
    env_read: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.runtime_position_status_current,
            PositionReadOnlyControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "runtime_position_status_current must be safe position enum",
            )
        _validate_non_negative_int(
            "position_count_safe_current",
            self.position_count_safe_current,
        )
        _validate_non_negative_int(
            "active_order_count_safe_current",
            self.active_order_count_safe_current,
        )
        _validate_non_negative_int(
            "pending_order_count_safe_current",
            self.pending_order_count_safe_current,
        )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRejectRootCauseHardeningResult:
    step_name: str
    status: OfficialSettlementRejectRootCauseHardeningStatus
    hardening_ready: bool
    no_post_blocker_found: bool
    fresh_retry_readiness: str
    recommended_next_step: str

    runtime_position_status_current: str
    position_count_safe_current: int
    active_order_count_safe_current: int
    pending_order_count_safe_current: int

    safe_error_code_capture_status: str
    safe_error_code_capture_ready: bool
    safe_http_status_label_allowed: bool
    safe_api_status_label_allowed: bool
    safe_broker_error_code_label_allowed: bool
    safe_broker_error_code_family_allowed: bool
    raw_response_required_for_exact_cause: bool
    official_error_code_family_mapping_recorded: bool
    allowed_safe_http_status_labels: tuple[str, ...]
    allowed_safe_api_status_labels: tuple[str, ...]
    allowed_safe_broker_error_code_labels: tuple[str, ...]
    allowed_safe_broker_error_code_families: tuple[str, ...]

    position_specific_safe_id_handling_status: str
    position_specific_safe_id_handling_required: bool
    position_specific_safe_identifier_handling_ready: bool
    position_specific_actual_path_allowed: bool
    position_specific_identifier_rendered: bool
    position_specific_identifier_persisted: bool

    size_based_target_consistency_status: str
    size_based_target_consistency_risk: str
    size_based_request_uses_size_only: bool
    size_based_request_includes_settle_position: bool
    size_and_settle_position_mutually_exclusive: bool
    request_target_consistency_safe_label_available: bool
    active_orders_plus_target_safe_check_available: bool

    operator_ui_safe_label_collection_status: str
    operator_ui_safe_label_collection_ready: bool
    allowed_operator_ui_safe_labels: tuple[str, ...]

    request_plan_shape_status: str
    side_provenance_status: str
    official_docs_comparison_status: str
    safe_rejection_category: str
    safe_rejection_kind: str
    safe_rejection_source: str
    safe_rejection_confidence: str

    actual_post_this_step: bool
    entry_post_this_step: bool
    settlement_post_this_step: bool
    retry_this_step: bool
    repost_this_step: bool
    second_post_this_step: bool
    generic_close_this_step: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_exposure: bool
    env_read: bool

    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            OfficialSettlementRejectRootCauseHardeningStatus,
        ):
            raise LiveVerificationValidationError("status must be hardening enum")
        for field_name in (
            "step_name",
            "fresh_retry_readiness",
            "recommended_next_step",
            "runtime_position_status_current",
            "safe_error_code_capture_status",
            "position_specific_safe_id_handling_status",
            "size_based_target_consistency_status",
            "size_based_target_consistency_risk",
            "operator_ui_safe_label_collection_status",
            "request_plan_shape_status",
            "side_provenance_status",
            "official_docs_comparison_status",
            "safe_rejection_category",
            "safe_rejection_kind",
            "safe_rejection_source",
            "safe_rejection_confidence",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int(
            "position_count_safe_current",
            self.position_count_safe_current,
        )
        _validate_non_negative_int(
            "active_order_count_safe_current",
            self.active_order_count_safe_current,
        )
        _validate_non_negative_int(
            "pending_order_count_safe_current",
            self.pending_order_count_safe_current,
        )
        for field_name in (
            "allowed_safe_http_status_labels",
            "allowed_safe_api_status_labels",
            "allowed_safe_broker_error_code_labels",
            "allowed_safe_broker_error_code_families",
            "allowed_operator_ui_safe_labels",
            "blocked_reasons",
        ):
            _validate_str_tuple(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)


def build_official_settlement_reject_root_cause_hardening_no_post_controlled(
    input_snapshot: OfficialSettlementRejectRootCauseHardeningInput | None = None,
) -> OfficialSettlementRejectRootCauseHardeningResult:
    snapshot = input_snapshot or OfficialSettlementRejectRootCauseHardeningInput()
    route_result = build_official_settlement_route_no_post_controlled()
    side_result = build_official_settlement_side_provenance_gate_no_post_controlled()
    client_result = build_official_settlement_real_network_client_binding_no_post_controlled()
    reporting_result = (
        build_official_settlement_rejection_safe_category_reporting_handoff_no_post()
    )

    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        route_ready=route_result.official_settlement_no_post_preview_ready,
        side_ready=side_result.settlement_side_provenance_mechanically_confirmed,
        client_ready=client_result.official_settlement_real_network_client_binding_confirmed,
        reporting_ready=reporting_result.safe_rejection_reporting_handoff_ready,
    )
    hardening_ready = not blocked_reasons
    no_post_blocker_found = not hardening_ready
    current_state_safe = (
        snapshot.runtime_position_status_current is PositionReadOnlyControlledStatus.NO_POSITION
        and snapshot.position_count_safe_current == 0
        and snapshot.active_order_count_safe_current == 0
        and snapshot.pending_order_count_safe_current == 0
    )
    fresh_retry_readiness = (
        FRESH_RETRY_READY_WITH_GATES
        if hardening_ready and current_state_safe
        else FRESH_RETRY_BLOCKED_NO_POST
    )

    return OfficialSettlementRejectRootCauseHardeningResult(
        step_name=STEP_NAME,
        status=(
            OfficialSettlementRejectRootCauseHardeningStatus.READY_NO_POST
            if hardening_ready
            else OfficialSettlementRejectRootCauseHardeningStatus.BLOCKED_NO_POST
        ),
        hardening_ready=hardening_ready,
        no_post_blocker_found=no_post_blocker_found,
        fresh_retry_readiness=fresh_retry_readiness,
        recommended_next_step=(
            NEXT_STEP_FRESH_ENTRY_SIGNAL
            if fresh_retry_readiness == FRESH_RETRY_READY_WITH_GATES
            else NEXT_STEP_FIX_HARDENING
        ),
        runtime_position_status_current=snapshot.runtime_position_status_current.value,
        position_count_safe_current=snapshot.position_count_safe_current,
        active_order_count_safe_current=snapshot.active_order_count_safe_current,
        pending_order_count_safe_current=snapshot.pending_order_count_safe_current,
        safe_error_code_capture_status=SAFE_ERROR_CODE_CAPTURE_READY,
        safe_error_code_capture_ready=snapshot.safe_error_code_allowlist_ready,
        safe_http_status_label_allowed=snapshot.safe_http_status_label_allowed,
        safe_api_status_label_allowed=snapshot.safe_api_status_label_allowed,
        safe_broker_error_code_label_allowed=(
            snapshot.safe_broker_error_code_label_allowed
        ),
        safe_broker_error_code_family_allowed=(
            snapshot.safe_broker_error_code_family_allowed
        ),
        raw_response_required_for_exact_cause=True,
        official_error_code_family_mapping_recorded=(
            snapshot.official_error_code_family_mapping_recorded
        ),
        allowed_safe_http_status_labels=ALLOWED_SAFE_HTTP_STATUS_LABELS,
        allowed_safe_api_status_labels=ALLOWED_SAFE_API_STATUS_LABELS,
        allowed_safe_broker_error_code_labels=ALLOWED_SAFE_BROKER_ERROR_CODE_LABELS,
        allowed_safe_broker_error_code_families=(
            ALLOWED_SAFE_BROKER_ERROR_CODE_FAMILIES
        ),
        position_specific_safe_id_handling_status=POSITION_SPECIFIC_SAFE_ID_STATUS,
        position_specific_safe_id_handling_required=False,
        position_specific_safe_identifier_handling_ready=(
            snapshot.position_specific_safe_identifier_handling_ready
        ),
        position_specific_actual_path_allowed=snapshot.position_specific_actual_path_allowed,
        position_specific_identifier_rendered=False,
        position_specific_identifier_persisted=False,
        size_based_target_consistency_status=SIZE_BASED_TARGET_CONSISTENCY_READY,
        size_based_target_consistency_risk="LOW_WITH_FRESH_POSITION_GATE_REQUIRED",
        size_based_request_uses_size_only=snapshot.size_based_request_uses_size_only,
        size_based_request_includes_settle_position=(
            snapshot.size_based_request_includes_settle_position
        ),
        size_and_settle_position_mutually_exclusive=(
            snapshot.size_and_settle_position_mutually_exclusive
        ),
        request_target_consistency_safe_label_available=(
            snapshot.request_target_consistency_safe_label_available
        ),
        active_orders_plus_target_safe_check_available=(
            snapshot.active_orders_plus_target_safe_check_available
        ),
        operator_ui_safe_label_collection_status=OPERATOR_UI_SAFE_LABEL_COLLECTION_READY,
        operator_ui_safe_label_collection_ready=(
            snapshot.operator_ui_safe_label_collection_ready
        ),
        allowed_operator_ui_safe_labels=ALLOWED_OPERATOR_UI_SAFE_LABELS,
        request_plan_shape_status=(
            "OFFICIAL_SIZE_BASED_SETTLEMENT_SIZE_ONLY_NO_SETTLE_POSITION"
            if route_result.preview.settlement_route_kind
            == SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
            else "REQUEST_PLAN_SHAPE_BLOCKED"
        ),
        side_provenance_status=(
            "SIDE_PROVENANCE_MECHANICALLY_CONFIRMED"
            if side_result.settlement_side_provenance_mechanically_confirmed
            else "SIDE_PROVENANCE_BLOCKED"
        ),
        official_docs_comparison_status=(
            "OFFICIAL_DOCS_COMPARISON_SAFE_LABEL_SCOPE_CONFIRMED"
            if route_result.official_settlement_no_post_preview_ready
            else "OFFICIAL_DOCS_COMPARISON_BLOCKED"
        ),
        safe_rejection_category=reporting_result.safe_rejection_category,
        safe_rejection_kind=reporting_result.safe_rejection_kind,
        safe_rejection_source=reporting_result.safe_rejection_source,
        safe_rejection_confidence=reporting_result.safe_rejection_confidence,
        actual_post_this_step=False,
        entry_post_this_step=False,
        settlement_post_this_step=False,
        retry_this_step=False,
        repost_this_step=False,
        second_post_this_step=False,
        generic_close_this_step=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_exposure=False,
        env_read=False,
        blocked_reasons=blocked_reasons,
    )


def _blocked_reasons(
    *,
    snapshot: OfficialSettlementRejectRootCauseHardeningInput,
    route_ready: bool,
    side_ready: bool,
    client_ready: bool,
    reporting_ready: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _execution_or_exposure_attempted(snapshot):
        reasons.append("execution_or_exposure_attempt_blocked")
    if not snapshot.manual_intervention_performed:
        reasons.append("manual_intervention_not_confirmed")
    if not route_ready:
        reasons.append("official_settlement_route_blocked")
    if not side_ready:
        reasons.append("side_provenance_blocked")
    if not client_ready:
        reasons.append("real_network_client_binding_blocked")
    if not reporting_ready:
        reasons.append("safe_rejection_reporting_blocked")
    if not snapshot.safe_error_code_allowlist_ready:
        reasons.append("safe_error_code_allowlist_not_ready")
    if not snapshot.official_error_code_family_mapping_recorded:
        reasons.append("official_error_code_family_mapping_not_recorded")
    if not snapshot.operator_ui_safe_label_collection_ready:
        reasons.append("operator_ui_safe_label_collection_not_ready")
    if not snapshot.size_based_request_uses_size_only:
        reasons.append("size_based_request_not_size_only")
    if snapshot.size_based_request_includes_settle_position:
        reasons.append("size_based_request_includes_settle_position")
    if not snapshot.size_and_settle_position_mutually_exclusive:
        reasons.append("size_settle_position_exclusive_not_confirmed")
    if not snapshot.request_target_consistency_safe_label_available:
        reasons.append("target_consistency_safe_label_not_available")
    if snapshot.position_specific_actual_path_allowed:
        reasons.append("position_specific_actual_path_not_allowed_in_no_post")
    if snapshot.position_specific_identifier_rendered:
        reasons.append("position_specific_identifier_rendered_blocked")
    if snapshot.position_specific_identifier_persisted:
        reasons.append("position_specific_identifier_persisted_blocked")
    return tuple(dict.fromkeys(reasons))


def _execution_or_exposure_attempted(
    snapshot: OfficialSettlementRejectRootCauseHardeningInput,
) -> bool:
    return any(
        (
            snapshot.actual_post_this_step,
            snapshot.entry_post_this_step,
            snapshot.settlement_post_this_step,
            snapshot.retry_this_step,
            snapshot.repost_this_step,
            snapshot.second_post_this_step,
            snapshot.generic_close_this_step,
            snapshot.ledger_update,
            snapshot.receipt_handoff,
            snapshot.raw_id_value_exposure,
            snapshot.env_read,
        ),
    )


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_str_tuple(field_name: str, value: tuple[str, ...]) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
        raise LiveVerificationValidationError(f"{field_name} must be tuple[str, ...]")


def _validate_bool_fields(obj: object, bool_fields: frozenset[str]) -> None:
    for item in fields(obj):
        if item.name in bool_fields and type(getattr(obj, item.name)) is not bool:
            raise LiveVerificationValidationError(f"{item.name} must be bool")


ALLOWED_SAFE_HTTP_STATUS_LABELS = (
    SAFE_HTTP_STATUS_CLIENT_ERROR,
    SAFE_HTTP_STATUS_RATE_LIMIT,
    SAFE_HTTP_STATUS_SERVER_ERROR,
)
ALLOWED_SAFE_API_STATUS_LABELS = (
    SAFE_API_STATUS_NONZERO,
    SAFE_API_STATUS_REJECTED,
)
ALLOWED_SAFE_BROKER_ERROR_CODE_LABELS = (
    SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED,
    SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH,
    SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH,
    SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND,
    SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT,
    SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT,
    SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT,
)
ALLOWED_SAFE_BROKER_ERROR_CODE_FAMILIES = (
    SAFE_BROKER_ERROR_CODE_FAMILY_PARAMETER_OR_REQUEST_SHAPE,
    SAFE_BROKER_ERROR_CODE_FAMILY_SIZE_OR_TARGET_MISMATCH,
    SAFE_BROKER_ERROR_CODE_FAMILY_POSITION_STATE_OR_TARGET_NOT_FOUND,
    SAFE_BROKER_ERROR_CODE_FAMILY_SESSION_OR_MARKET_CONSTRAINT,
    SAFE_BROKER_ERROR_CODE_FAMILY_ACCOUNT_OR_PERMISSION_CONSTRAINT,
    SAFE_BROKER_ERROR_CODE_FAMILY_RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
)
ALLOWED_OPERATOR_UI_SAFE_LABELS = (
    OPERATOR_UI_REJECTION_SAFE_REASON_PERMISSION,
    OPERATOR_UI_REJECTION_SAFE_REASON_SIZE_OR_TARGET,
    OPERATOR_UI_REJECTION_SAFE_REASON_POSITION_NOT_FOUND,
    OPERATOR_UI_REJECTION_SAFE_REASON_ACTIVE_ORDER_CONFLICT,
    OPERATOR_UI_REJECTION_SAFE_REASON_MARKET_OR_SESSION,
    OPERATOR_UI_REJECTION_SAFE_REASON_RATE_LIMIT_OR_TEMPORARY,
    OPERATOR_UI_REJECTION_SAFE_REASON_UNKNOWN,
    OPERATOR_UI_REJECTION_SAFE_REASON_NOT_DISPLAYED,
)


_INPUT_BOOL_FIELDS = frozenset(
    {
        "manual_intervention_performed",
        "safe_error_code_allowlist_ready",
        "safe_api_status_label_allowed",
        "safe_broker_error_code_label_allowed",
        "safe_broker_error_code_family_allowed",
        "safe_http_status_label_allowed",
        "operator_ui_safe_label_collection_ready",
        "official_error_code_family_mapping_recorded",
        "size_based_request_uses_size_only",
        "size_based_request_includes_settle_position",
        "size_and_settle_position_mutually_exclusive",
        "request_target_consistency_safe_label_available",
        "active_orders_plus_target_safe_check_available",
        "position_specific_safe_identifier_handling_ready",
        "position_specific_actual_path_allowed",
        "position_specific_opaque_handle_design_recorded",
        "position_specific_identifier_rendered",
        "position_specific_identifier_persisted",
        "actual_post_this_step",
        "entry_post_this_step",
        "settlement_post_this_step",
        "retry_this_step",
        "repost_this_step",
        "second_post_this_step",
        "generic_close_this_step",
        "ledger_update",
        "receipt_handoff",
        "raw_id_value_exposure",
        "env_read",
    },
)

_RESULT_BOOL_FIELDS = frozenset(
    {
        "hardening_ready",
        "no_post_blocker_found",
        "safe_error_code_capture_ready",
        "safe_http_status_label_allowed",
        "safe_api_status_label_allowed",
        "safe_broker_error_code_label_allowed",
        "safe_broker_error_code_family_allowed",
        "raw_response_required_for_exact_cause",
        "official_error_code_family_mapping_recorded",
        "position_specific_safe_id_handling_required",
        "position_specific_safe_identifier_handling_ready",
        "position_specific_actual_path_allowed",
        "position_specific_identifier_rendered",
        "position_specific_identifier_persisted",
        "size_based_request_uses_size_only",
        "size_based_request_includes_settle_position",
        "size_and_settle_position_mutually_exclusive",
        "request_target_consistency_safe_label_available",
        "active_orders_plus_target_safe_check_available",
        "operator_ui_safe_label_collection_ready",
        "actual_post_this_step",
        "entry_post_this_step",
        "settlement_post_this_step",
        "retry_this_step",
        "repost_this_step",
        "second_post_this_step",
        "generic_close_this_step",
        "ledger_update",
        "receipt_handoff",
        "raw_id_value_exposure",
        "env_read",
    },
)
