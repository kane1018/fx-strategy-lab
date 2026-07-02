"""Step 6G sealed request/body/result foundation.

This module builds only safe summaries for the future POST-only source path. It
does not hold raw request bodies, endpoint values, credential values, signature
values, header values, raw responses, or real IDs. It also does not import
HTTP clients, live_order_once, broker/private API clients, env readers, or
ledger writers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    SAFE_ENVIRONMENT_LABEL,
    SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
    SAFE_RISK_LABEL,
    SAFE_TIME_IN_FORCE_LABEL,
    LiveOrderRealExecutableOrderPreviewResult,
    LiveOrderRealOneShotPostTransportResultCategory,
    build_live_order_real_executable_order_preview,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SAFE_POST_RESULT_LABEL,
    SAFE_RECONCILIATION_LABEL,
    SafePostResultCategory,
    SafeReconciliationStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

SAFE_SEALED_REQUEST_RESULT_LABEL = "CONTROLLED_SEALED_REQUEST_RESULT_FOUNDATION"
SAFE_SEALED_REQUEST_LABEL = "SEALED_REQUEST_SAFE_SUMMARY_ONLY"
SAFE_SEALED_BODY_LABEL = "SEALED_BODY_SAFE_SUMMARY_ONLY"
SAFE_SEALED_ENDPOINT_LABEL = "SEALED_ENDPOINT_LABEL_ONLY"
SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL = (
    "SOURCE_OWNED_CLIENT_ORDER_ID_STRATEGY_SKELETON"
)
SEALED_REQUEST_RESULT_RECOMMENDED_NEXT_STEP = (
    "sealed_credential_signing_provider_no_post"
)
UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL = "UNSUPPORTED_REDACTED"

TransportResultCategory = LiveOrderRealOneShotPostTransportResultCategory


class LiveOrderRealOneShotPostSealedRequestResultControlledStatus(str, Enum):
    SEALED_REQUEST_RESULT_READY_NO_POST = "SEALED_REQUEST_RESULT_READY_NO_POST"
    SEALED_REQUEST_RESULT_BLOCKED_MISSING_CANDIDATE = (
        "SEALED_REQUEST_RESULT_BLOCKED_MISSING_CANDIDATE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_AMBIGUOUS_CANDIDATE = (
        "SEALED_REQUEST_RESULT_BLOCKED_AMBIGUOUS_CANDIDATE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SYMBOL = (
        "SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SYMBOL"
    )
    SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SIDE = (
        "SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SIDE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_ORDER_TYPE = (
        "SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_ORDER_TYPE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_INVALID_SIZE = (
        "SEALED_REQUEST_RESULT_BLOCKED_INVALID_SIZE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE = (
        "SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE = (
        "SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE = (
        "SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE"
    )
    SEALED_REQUEST_RESULT_BLOCKED_POST_OR_ORDER_EXECUTION = (
        "SEALED_REQUEST_RESULT_BLOCKED_POST_OR_ORDER_EXECUTION"
    )
    SEALED_REQUEST_RESULT_BLOCKED_LEDGER_RECEIPT_RETRY = (
        "SEALED_REQUEST_RESULT_BLOCKED_LEDGER_RECEIPT_RETRY"
    )


class LiveOrderRealSealedTransportSafeCategory(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class LiveOrderRealSealedResultMappingStatus(str, Enum):
    SEALED_RESULT_MAPPING_ACCEPTED = "SEALED_RESULT_MAPPING_ACCEPTED"
    SEALED_RESULT_MAPPING_REJECTED = "SEALED_RESULT_MAPPING_REJECTED"
    SEALED_RESULT_MAPPING_FAILED_FAIL_CLOSED = (
        "SEALED_RESULT_MAPPING_FAILED_FAIL_CLOSED"
    )
    SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED = (
        "SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED"
    )
    SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED = (
        "SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED"
    )
    SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED = (
        "SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED"
    )
    SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE = (
        "SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE"
    )
    SEALED_RESULT_MAPPING_BLOCKED_ID_EXPOSURE = (
        "SEALED_RESULT_MAPPING_BLOCKED_ID_EXPOSURE"
    )
    SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT = (
        "SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT"
    )


SealedRequestStatus = LiveOrderRealOneShotPostSealedRequestResultControlledStatus
SealedTransportSafeCategory = LiveOrderRealSealedTransportSafeCategory
SealedResultMappingStatus = LiveOrderRealSealedResultMappingStatus


@dataclass(frozen=True)
class LiveOrderRealOneShotPostSealedRequestResultControlledInput:
    sealed_request_result_label: str = SAFE_SEALED_REQUEST_RESULT_LABEL
    sealed_request_label: str = SAFE_SEALED_REQUEST_LABEL
    sealed_body_label: str = SAFE_SEALED_BODY_LABEL
    sealed_endpoint_label: str = SAFE_SEALED_ENDPOINT_LABEL
    source_owned_client_order_id_strategy_label: str = (
        SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL
    )
    safe_preview_label: str = SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL
    safe_order_candidate_available: bool = True
    order_ambiguity: bool = False
    symbol: str = SUPPORTED_SYMBOL
    side: str = LiveOrderCandidateSide.BUY.value
    order_type: str = LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
    size: int = LIVE_ORDER_CANDIDATE_SIZE
    time_in_force_label: str = SAFE_TIME_IN_FORCE_LABEL
    environment_label: str = SAFE_ENVIRONMENT_LABEL
    risk_label: str = SAFE_RISK_LABEL
    safe_order_source_label: str = "STEP6G_REPO_DEFINED_ORDER_INTENT"
    codex_inferred_symbol: bool = False
    codex_inferred_side: bool = False
    codex_inferred_size: bool = False
    codex_inferred_order_type: bool = False
    source_owned_client_order_id_strategy_required: bool = True
    source_owned_client_order_id_strategy_ready: bool = True
    client_order_id_strategy_non_ledger: bool = True
    client_order_id_actual_value_generated: bool = False
    client_order_id_actual_value_exposed: bool = False
    raw_body_exposure_attempted: bool = False
    endpoint_actual_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    id_exposure_attempted: bool = False
    actual_http_post_executed: bool = False
    order_endpoint_executed: bool = False
    live_order_once_executed: bool = False
    post_execution_count: int = 0
    second_post_attempted: bool = False
    retry_attempted: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persisted: bool = False
    receipt_handoff_attempted: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "sealed_request_result_label",
            "sealed_request_label",
            "sealed_body_label",
            "sealed_endpoint_label",
            "source_owned_client_order_id_strategy_label",
            "safe_preview_label",
            "symbol",
            "side",
            "order_type",
            "time_in_force_label",
            "environment_label",
            "risk_label",
            "safe_order_source_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("size", self.size)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _SEALED_REQUEST_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostSealedRequestResultControlledResult:
    status: LiveOrderRealOneShotPostSealedRequestResultControlledStatus
    sealed_request_model_ready: bool
    sealed_body_builder_ready: bool
    sealed_endpoint_label_ready: bool
    safe_result_mapper_ready: bool
    sealed_request_result_label: str
    sealed_request_status: str
    sealed_request_label: str
    sealed_body_label: str
    sealed_endpoint_label: str
    source_owned_client_order_id_strategy_required: bool
    source_owned_client_order_id_strategy_ready: bool
    source_owned_client_order_id_strategy_label: str
    client_order_id_strategy_non_ledger: bool
    client_order_id_actual_value_generated: bool
    client_order_id_actual_value_exposed: bool
    safe_order_candidate_available: bool
    order_ambiguity: bool
    safe_preview_label: str
    symbol: str
    side: str
    order_type: str
    size: int
    time_in_force_label: str
    environment_label: str
    risk_label: str
    safe_order_source_label: str
    codex_inferred_symbol: bool
    codex_inferred_side: bool
    codex_inferred_size: bool
    codex_inferred_order_type: bool
    raw_body_exposed: bool
    endpoint_actual_value_exposed: bool
    headers_value_exposed: bool
    signature_value_exposed: bool
    credential_value_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    id_exposed: bool
    real_account_order_transaction_id_exposed: bool
    actual_http_post_executed: bool
    order_endpoint_executed: bool
    live_order_once_executed: bool
    post_execution_count: int
    second_post_attempted: bool
    retry_attempted: bool
    ledger_updated: bool
    attempt_counter_persisted: bool
    actual_receipt_handoff_executed: bool
    approved_primitive_actual_source_available: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOneShotPostSealedRequestResultControlledStatus,
        ):
            raise LiveVerificationValidationError("status must be sealed status")
        for field_name in (
            "sealed_request_result_label",
            "sealed_request_status",
            "sealed_request_label",
            "sealed_body_label",
            "sealed_endpoint_label",
            "source_owned_client_order_id_strategy_label",
            "safe_preview_label",
            "symbol",
            "side",
            "order_type",
            "time_in_force_label",
            "environment_label",
            "risk_label",
            "safe_order_source_label",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("size", self.size)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _SEALED_REQUEST_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_sealed_request_result_safety(self)


@dataclass(frozen=True)
class LiveOrderRealSealedTransportResultMappingInput:
    transport_safe_category: str = SealedTransportSafeCategory.ACCEPTED.value
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    safe_reconciliation_label: str = SAFE_RECONCILIATION_LABEL
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    id_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    retry_attempted: bool = False
    ledger_update_attempted: bool = False
    receipt_handoff_attempted: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("transport_safe_category", self.transport_safe_category)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_reconciliation_label", self.safe_reconciliation_label)
        _validate_bool_fields(self, _SEALED_RESULT_MAPPING_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealSealedTransportResultMappingResult:
    status: LiveOrderRealSealedResultMappingStatus
    safe_result_mapper_ready: bool
    transport_safe_category: str
    safe_post_result_label: str
    sanitized_result_category: str
    safe_reconciliation_label: str
    safe_reconciliation_status: str
    accepted: bool
    rejected: bool
    failed: bool
    timeout: bool
    unknown: bool
    unavailable: bool
    retry_allowed: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    id_exposed: bool
    real_account_order_transaction_id_exposed: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealSealedResultMappingStatus):
            raise LiveVerificationValidationError("status must be result mapping status")
        for field_name in (
            "transport_safe_category",
            "safe_post_result_label",
            "sanitized_result_category",
            "safe_reconciliation_label",
            "safe_reconciliation_status",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _SEALED_RESULT_MAPPING_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_mapping_safety(self)


def build_live_order_real_one_shot_post_sealed_request_result_controlled(
    input_snapshot: (
        LiveOrderRealOneShotPostSealedRequestResultControlledInput | None
    ) = None,
    *,
    preview: LiveOrderRealExecutableOrderPreviewResult | None = None,
) -> LiveOrderRealOneShotPostSealedRequestResultControlledResult:
    """Build a sealed request/body foundation summary without raw values."""
    snapshot = input_snapshot or _sealed_request_input_from_preview(preview)
    status, reasons = _sealed_request_status(snapshot)
    ready = status is SealedRequestStatus.SEALED_REQUEST_RESULT_READY_NO_POST
    safe_candidate = ready and snapshot.safe_order_candidate_available
    return LiveOrderRealOneShotPostSealedRequestResultControlledResult(
        status=status,
        sealed_request_model_ready=ready,
        sealed_body_builder_ready=ready,
        sealed_endpoint_label_ready=ready,
        safe_result_mapper_ready=True,
        sealed_request_result_label=_safe_label(
            snapshot.sealed_request_result_label,
            SAFE_SEALED_REQUEST_RESULT_LABEL,
        ),
        sealed_request_status=status.value,
        sealed_request_label=_safe_label(
            snapshot.sealed_request_label,
            SAFE_SEALED_REQUEST_LABEL,
        ),
        sealed_body_label=_safe_label(
            snapshot.sealed_body_label,
            SAFE_SEALED_BODY_LABEL,
        ),
        sealed_endpoint_label=_safe_label(
            snapshot.sealed_endpoint_label,
            SAFE_SEALED_ENDPOINT_LABEL,
        ),
        source_owned_client_order_id_strategy_required=(
            snapshot.source_owned_client_order_id_strategy_required
        ),
        source_owned_client_order_id_strategy_ready=(
            snapshot.source_owned_client_order_id_strategy_ready and ready
        ),
        source_owned_client_order_id_strategy_label=_safe_label(
            snapshot.source_owned_client_order_id_strategy_label,
            SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL,
        ),
        client_order_id_strategy_non_ledger=(
            snapshot.client_order_id_strategy_non_ledger
        ),
        client_order_id_actual_value_generated=False,
        client_order_id_actual_value_exposed=False,
        safe_order_candidate_available=snapshot.safe_order_candidate_available,
        order_ambiguity=snapshot.order_ambiguity or not ready,
        safe_preview_label=_safe_label(
            snapshot.safe_preview_label,
            SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
        ),
        symbol=snapshot.symbol if safe_candidate else UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL,
        side=snapshot.side if safe_candidate else UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL,
        order_type=(
            snapshot.order_type
            if safe_candidate
            else UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL
        ),
        size=snapshot.size if safe_candidate else 0,
        time_in_force_label=_safe_text_label(snapshot.time_in_force_label),
        environment_label=_safe_text_label(snapshot.environment_label),
        risk_label=_safe_text_label(snapshot.risk_label),
        safe_order_source_label=_safe_text_label(snapshot.safe_order_source_label),
        codex_inferred_symbol=False,
        codex_inferred_side=False,
        codex_inferred_size=False,
        codex_inferred_order_type=False,
        raw_body_exposed=False,
        endpoint_actual_value_exposed=False,
        headers_value_exposed=False,
        signature_value_exposed=False,
        credential_value_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        id_exposed=False,
        real_account_order_transaction_id_exposed=False,
        actual_http_post_executed=False,
        order_endpoint_executed=False,
        live_order_once_executed=False,
        post_execution_count=0,
        second_post_attempted=False,
        retry_attempted=False,
        ledger_updated=False,
        attempt_counter_persisted=False,
        actual_receipt_handoff_executed=False,
        approved_primitive_actual_source_available=False,
        blocked_reasons=reasons,
        recommended_next_step=SEALED_REQUEST_RESULT_RECOMMENDED_NEXT_STEP,
    )


def map_live_order_real_one_shot_post_sealed_transport_result(
    input_snapshot: LiveOrderRealSealedTransportResultMappingInput | None = None,
) -> LiveOrderRealSealedTransportResultMappingResult:
    """Map a safe transport category into a sanitized result category."""
    snapshot = input_snapshot or LiveOrderRealSealedTransportResultMappingInput()
    status, reasons = _mapping_status(snapshot)
    category = _transport_safe_category(snapshot.transport_safe_category)
    sanitized_category = _sanitized_result_category(status)
    return LiveOrderRealSealedTransportResultMappingResult(
        status=status,
        safe_result_mapper_ready=not reasons,
        transport_safe_category=category.value,
        safe_post_result_label=_safe_label(
            snapshot.safe_post_result_label,
            SAFE_POST_RESULT_LABEL,
        ),
        sanitized_result_category=sanitized_category.value,
        safe_reconciliation_label=_safe_label(
            snapshot.safe_reconciliation_label,
            SAFE_RECONCILIATION_LABEL,
        ),
        safe_reconciliation_status=_safe_reconciliation_status(status).value,
        accepted=category is SealedTransportSafeCategory.ACCEPTED and not reasons,
        rejected=category is SealedTransportSafeCategory.REJECTED and not reasons,
        failed=category is SealedTransportSafeCategory.FAILED or (
            status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_FAILED_FAIL_CLOSED
        ),
        timeout=category is SealedTransportSafeCategory.TIMEOUT or (
            status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED
        ),
        unknown=category is SealedTransportSafeCategory.UNKNOWN or (
            status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED
        ),
        unavailable=category is SealedTransportSafeCategory.UNAVAILABLE or (
            status
            is SealedResultMappingStatus.SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED
        ),
        retry_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        id_exposed=False,
        real_account_order_transaction_id_exposed=False,
        blocked_reasons=reasons,
    )


def render_live_order_real_one_shot_post_sealed_request_result_markdown(
    result: LiveOrderRealOneShotPostSealedRequestResultControlledResult,
) -> str:
    """Render a safe sealed request/body/result foundation summary."""
    lines = [
        "# Step 6G Sealed Request Body Result Controlled",
        "",
        "This is a safe foundation summary only.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw bodies, endpoint values, raw responses,",
        "credential values, signature values, headers values, or IDs.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- sealed_request_model_ready: {_bool_text(result.sealed_request_model_ready)}",
        f"- sealed_body_builder_ready: {_bool_text(result.sealed_body_builder_ready)}",
        f"- safe_result_mapper_ready: {_bool_text(result.safe_result_mapper_ready)}",
        f"- sealed_request_label: {result.sealed_request_label}",
        f"- sealed_body_label: {result.sealed_body_label}",
        f"- sealed_endpoint_label: {result.sealed_endpoint_label}",
        "",
        "## Safe Candidate",
        (
            "- safe_order_candidate_available: "
            f"{_bool_text(result.safe_order_candidate_available)}"
        ),
        f"- order_ambiguity: {_bool_text(result.order_ambiguity)}",
        f"- symbol: {result.symbol}",
        f"- side: {result.side}",
        f"- order_type: {result.order_type}",
        f"- size: {result.size}",
        f"- time_in_force_label: {result.time_in_force_label}",
        f"- environment_label: {result.environment_label}",
        f"- risk_label: {result.risk_label}",
        (
            "- safe_order_source_label: "
            f"{result.safe_order_source_label}"
        ),
        "",
        "## Client Order Id Strategy",
        (
            "- source_owned_client_order_id_strategy_required: "
            f"{_bool_text(result.source_owned_client_order_id_strategy_required)}"
        ),
        (
            "- source_owned_client_order_id_strategy_ready: "
            f"{_bool_text(result.source_owned_client_order_id_strategy_ready)}"
        ),
        (
            "- source_owned_client_order_id_strategy_label: "
            f"{result.source_owned_client_order_id_strategy_label}"
        ),
        (
            "- client_order_id_strategy_non_ledger: "
            f"{_bool_text(result.client_order_id_strategy_non_ledger)}"
        ),
        (
            "- client_order_id_actual_value_generated: "
            f"{_bool_text(result.client_order_id_actual_value_generated)}"
        ),
        (
            "- client_order_id_actual_value_exposed: "
            f"{_bool_text(result.client_order_id_actual_value_exposed)}"
        ),
        "",
        "## Safety",
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
        f"- attempt_counter_persisted: {_bool_text(result.attempt_counter_persisted)}",
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- raw_body_exposed: {_bool_text(result.raw_body_exposed)}",
        (
            "- endpoint_actual_value_exposed: "
            f"{_bool_text(result.endpoint_actual_value_exposed)}"
        ),
        f"- headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"- signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        f"- credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        f"- raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        f"- id_exposed: {_bool_text(result.id_exposed)}",
        (
            "- approved_primitive_actual_source_available: "
            f"{_bool_text(result.approved_primitive_actual_source_available)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def render_live_order_real_one_shot_post_sealed_result_mapping_markdown(
    result: LiveOrderRealSealedTransportResultMappingResult,
) -> str:
    """Render a safe result mapper summary."""
    lines = [
        "# Step 6G Sealed Result Mapper",
        "",
        f"- status: {result.status.value}",
        f"- safe_result_mapper_ready: {_bool_text(result.safe_result_mapper_ready)}",
        f"- transport_safe_category: {result.transport_safe_category}",
        f"- sanitized_result_category: {result.sanitized_result_category}",
        f"- safe_reconciliation_status: {result.safe_reconciliation_status}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- ledger_update_allowed: {_bool_text(result.ledger_update_allowed)}",
        f"- receipt_handoff_allowed: {_bool_text(result.receipt_handoff_allowed)}",
        f"- raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        (
            "- broker_api_response_exposed: "
            f"{_bool_text(result.broker_api_response_exposed)}"
        ),
        f"- credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        f"- signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        f"- headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"- id_exposed: {_bool_text(result.id_exposed)}",
    ]
    return "\n".join(lines) + "\n"


def _sealed_request_input_from_preview(
    preview: LiveOrderRealExecutableOrderPreviewResult | None,
) -> LiveOrderRealOneShotPostSealedRequestResultControlledInput:
    preview_result = preview or build_live_order_real_executable_order_preview()
    return LiveOrderRealOneShotPostSealedRequestResultControlledInput(
        safe_preview_label=preview_result.safe_preview_label,
        safe_order_candidate_available=(
            preview_result.sanitized_order_preview_available
        ),
        order_ambiguity=preview_result.order_ambiguity,
        symbol=preview_result.symbol,
        side=preview_result.side,
        order_type=preview_result.order_type,
        size=preview_result.size,
        time_in_force_label=preview_result.time_in_force_label,
        environment_label=preview_result.environment_label,
        risk_label=preview_result.risk_label,
        safe_order_source_label=preview_result.safe_order_source_label,
        codex_inferred_symbol=preview_result.codex_inferred_symbol,
        codex_inferred_side=preview_result.codex_inferred_side,
        codex_inferred_size=preview_result.codex_inferred_size,
        codex_inferred_order_type=preview_result.codex_inferred_order_type,
    )


def _sealed_request_status(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[LiveOrderRealOneShotPostSealedRequestResultControlledStatus, tuple[str, ...]]:
    raw_reasons = _raw_exposure_reasons(snapshot)
    if raw_reasons:
        return SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE, raw_reasons
    id_reasons = _id_exposure_reasons(snapshot)
    if id_reasons:
        return SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE, id_reasons
    value_reasons = _value_exposure_reasons(snapshot)
    if value_reasons:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE,
            value_reasons,
        )
    execution_reasons = _execution_reasons(snapshot)
    if execution_reasons:
        return (
            SealedRequestStatus
            .SEALED_REQUEST_RESULT_BLOCKED_POST_OR_ORDER_EXECUTION,
            execution_reasons,
        )
    lifecycle_reasons = _lifecycle_reasons(snapshot)
    if lifecycle_reasons:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_LEDGER_RECEIPT_RETRY,
            lifecycle_reasons,
        )
    if not snapshot.safe_order_candidate_available:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_MISSING_CANDIDATE,
            ("safe_order_candidate_missing",),
        )
    ambiguity_reasons = _ambiguity_reasons(snapshot)
    if ambiguity_reasons:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_AMBIGUOUS_CANDIDATE,
            ambiguity_reasons,
        )
    if snapshot.symbol != SUPPORTED_SYMBOL:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SYMBOL,
            ("unsupported_symbol",),
        )
    if snapshot.side not in {side.value for side in LiveOrderCandidateSide}:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SIDE,
            ("unsupported_side",),
        )
    if snapshot.order_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_ORDER_TYPE,
            ("unsupported_order_type",),
        )
    if snapshot.size != LIVE_ORDER_CANDIDATE_SIZE:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_INVALID_SIZE,
            ("unsupported_size",),
        )
    if not snapshot.source_owned_client_order_id_strategy_ready:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE,
            ("client_order_id_strategy_not_ready",),
        )
    if not snapshot.client_order_id_strategy_non_ledger:
        return (
            SealedRequestStatus.SEALED_REQUEST_RESULT_BLOCKED_LEDGER_RECEIPT_RETRY,
            ("client_order_id_strategy_ledger_coupled",),
        )
    return SealedRequestStatus.SEALED_REQUEST_RESULT_READY_NO_POST, ()


def _mapping_status(
    snapshot: LiveOrderRealSealedTransportResultMappingInput,
) -> tuple[LiveOrderRealSealedResultMappingStatus, tuple[str, ...]]:
    raw_reasons = []
    if snapshot.raw_response_exposure_attempted:
        raw_reasons.append("raw_response_exposure_attempted")
    if snapshot.broker_api_response_exposure_attempted:
        raw_reasons.append("broker_api_response_exposure_attempted")
    if raw_reasons:
        return (
            SealedResultMappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            tuple(raw_reasons),
        )
    if snapshot.id_exposure_attempted:
        return (
            SealedResultMappingStatus.SEALED_RESULT_MAPPING_BLOCKED_ID_EXPOSURE,
            ("id_exposure_attempted",),
        )
    lifecycle_reasons = []
    if snapshot.retry_attempted:
        lifecycle_reasons.append("retry_attempted")
    if snapshot.ledger_update_attempted:
        lifecycle_reasons.append("ledger_update_attempted")
    if snapshot.receipt_handoff_attempted:
        lifecycle_reasons.append("receipt_handoff_attempted")
    if lifecycle_reasons:
        return (
            SealedResultMappingStatus
            .SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT,
            tuple(lifecycle_reasons),
        )
    if (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
    ):
        return (
            SealedResultMappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            ("credential_signature_headers_value_exposure_attempted",),
        )

    category = _transport_safe_category(snapshot.transport_safe_category)
    if category is SealedTransportSafeCategory.ACCEPTED:
        return SealedResultMappingStatus.SEALED_RESULT_MAPPING_ACCEPTED, ()
    if category is SealedTransportSafeCategory.REJECTED:
        return SealedResultMappingStatus.SEALED_RESULT_MAPPING_REJECTED, ()
    if category is SealedTransportSafeCategory.FAILED:
        return SealedResultMappingStatus.SEALED_RESULT_MAPPING_FAILED_FAIL_CLOSED, ()
    if category is SealedTransportSafeCategory.TIMEOUT:
        return SealedResultMappingStatus.SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED, ()
    if category is SealedTransportSafeCategory.UNAVAILABLE:
        return (
            SealedResultMappingStatus.SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED,
            (),
        )
    return SealedResultMappingStatus.SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED, ()


def _transport_safe_category(category: str) -> LiveOrderRealSealedTransportSafeCategory:
    try:
        return SealedTransportSafeCategory(category)
    except ValueError:
        return SealedTransportSafeCategory.UNKNOWN


def _sanitized_result_category(
    status: LiveOrderRealSealedResultMappingStatus,
) -> SafePostResultCategory:
    if status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_ACCEPTED:
        return SafePostResultCategory.RESULT_ACCEPTED_SANITIZED
    if status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_REJECTED:
        return SafePostResultCategory.RESULT_REJECTED_SANITIZED
    if status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED:
        return SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED
    if (
        status
        is SealedResultMappingStatus.SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED
    ):
        return SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED
    return SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED


def _safe_reconciliation_status(
    status: LiveOrderRealSealedResultMappingStatus,
) -> SafeReconciliationStatus:
    if status is SealedResultMappingStatus.SEALED_RESULT_MAPPING_ACCEPTED:
        return SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF
    return SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY


def _raw_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.raw_body_exposure_attempted:
        reasons.append("raw_body_exposure_attempted")
    if snapshot.raw_response_exposure_attempted:
        reasons.append("raw_response_exposure_attempted")
    if snapshot.broker_api_response_exposure_attempted:
        reasons.append("broker_api_response_exposure_attempted")
    if snapshot.endpoint_actual_value_exposure_attempted:
        reasons.append("endpoint_actual_value_exposure_attempted")
    return tuple(reasons)


def _id_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.id_exposure_attempted:
        reasons.append("id_exposure_attempted")
    if snapshot.client_order_id_actual_value_generated:
        reasons.append("client_order_id_actual_value_generated")
    if snapshot.client_order_id_actual_value_exposed:
        reasons.append("client_order_id_actual_value_exposed")
    return tuple(reasons)


def _value_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.credential_value_exposure_attempted:
        reasons.append("credential_value_exposure_attempted")
    if snapshot.signature_value_exposure_attempted:
        reasons.append("signature_value_exposure_attempted")
    if snapshot.headers_value_exposure_attempted:
        reasons.append("headers_value_exposure_attempted")
    return tuple(reasons)


def _execution_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.actual_http_post_executed:
        reasons.append("actual_http_post_executed")
    if snapshot.post_execution_count:
        reasons.append("post_execution_count_nonzero")
    if snapshot.order_endpoint_executed:
        reasons.append("order_endpoint_executed")
    if snapshot.live_order_once_executed:
        reasons.append("live_order_once_executed")
    return tuple(reasons)


def _lifecycle_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.retry_attempted:
        reasons.append("retry_attempted")
    if snapshot.second_post_attempted:
        reasons.append("second_post_attempted")
    if snapshot.ledger_update_attempted:
        reasons.append("ledger_update_attempted")
    if snapshot.attempt_counter_persisted:
        reasons.append("attempt_counter_persisted")
    if snapshot.receipt_handoff_attempted:
        reasons.append("receipt_handoff_attempted")
    return tuple(reasons)


def _ambiguity_reasons(
    snapshot: LiveOrderRealOneShotPostSealedRequestResultControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.order_ambiguity:
        reasons.append("order_ambiguity")
    if snapshot.codex_inferred_symbol:
        reasons.append("codex_inferred_symbol")
    if snapshot.codex_inferred_side:
        reasons.append("codex_inferred_side")
    if snapshot.codex_inferred_size:
        reasons.append("codex_inferred_size")
    if snapshot.codex_inferred_order_type:
        reasons.append("codex_inferred_order_type")
    return tuple(reasons)


def _validate_sealed_request_result_safety(
    result: LiveOrderRealOneShotPostSealedRequestResultControlledResult,
) -> None:
    if any((
        result.raw_body_exposed,
        result.endpoint_actual_value_exposed,
        result.headers_value_exposed,
        result.signature_value_exposed,
        result.credential_value_exposed,
        result.raw_response_exposed,
        result.broker_api_response_exposed,
        result.id_exposed,
        result.real_account_order_transaction_id_exposed,
    )):
        raise LiveVerificationValidationError("sealed request result exposed unsafe data")
    if any((
        result.actual_http_post_executed,
        result.order_endpoint_executed,
        result.live_order_once_executed,
        result.post_execution_count != 0,
        result.second_post_attempted,
        result.retry_attempted,
        result.ledger_updated,
        result.attempt_counter_persisted,
        result.actual_receipt_handoff_executed,
    )):
        raise LiveVerificationValidationError("sealed request result executed unsafe path")
    if result.approved_primitive_actual_source_available:
        raise LiveVerificationValidationError(
            "sealed foundation must not supply actual source",
        )


def _validate_result_mapping_safety(
    result: LiveOrderRealSealedTransportResultMappingResult,
) -> None:
    if any((
        result.retry_allowed,
        result.ledger_update_allowed,
        result.receipt_handoff_allowed,
        result.raw_response_exposed,
        result.broker_api_response_exposed,
        result.credential_value_exposed,
        result.signature_value_exposed,
        result.headers_value_exposed,
        result.id_exposed,
        result.real_account_order_transaction_id_exposed,
    )):
        raise LiveVerificationValidationError("sealed result mapper exposed unsafe data")


def _safe_label(value: str, expected: str) -> str:
    return value if value == expected else UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL


def _safe_text_label(value: str) -> str:
    if isinstance(value, str) and value in _ALLOWED_SAFE_TEXT_LABELS:
        return value
    return UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(object_: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(object_, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


_SEALED_REQUEST_INPUT_BOOL_FIELDS = (
    "safe_order_candidate_available",
    "order_ambiguity",
    "codex_inferred_symbol",
    "codex_inferred_side",
    "codex_inferred_size",
    "codex_inferred_order_type",
    "source_owned_client_order_id_strategy_required",
    "source_owned_client_order_id_strategy_ready",
    "client_order_id_strategy_non_ledger",
    "client_order_id_actual_value_generated",
    "client_order_id_actual_value_exposed",
    "raw_body_exposure_attempted",
    "endpoint_actual_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "credential_value_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "id_exposure_attempted",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "second_post_attempted",
    "retry_attempted",
    "ledger_update_attempted",
    "attempt_counter_persisted",
    "receipt_handoff_attempted",
)

_SEALED_REQUEST_RESULT_BOOL_FIELDS = (
    "sealed_request_model_ready",
    "sealed_body_builder_ready",
    "sealed_endpoint_label_ready",
    "safe_result_mapper_ready",
    "source_owned_client_order_id_strategy_required",
    "source_owned_client_order_id_strategy_ready",
    "client_order_id_strategy_non_ledger",
    "client_order_id_actual_value_generated",
    "client_order_id_actual_value_exposed",
    "safe_order_candidate_available",
    "order_ambiguity",
    "codex_inferred_symbol",
    "codex_inferred_side",
    "codex_inferred_size",
    "codex_inferred_order_type",
    "raw_body_exposed",
    "endpoint_actual_value_exposed",
    "headers_value_exposed",
    "signature_value_exposed",
    "credential_value_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "id_exposed",
    "real_account_order_transaction_id_exposed",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "second_post_attempted",
    "retry_attempted",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "approved_primitive_actual_source_available",
)

_SEALED_RESULT_MAPPING_INPUT_BOOL_FIELDS = (
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "id_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "retry_attempted",
    "ledger_update_attempted",
    "receipt_handoff_attempted",
)

_SEALED_RESULT_MAPPING_RESULT_BOOL_FIELDS = (
    "safe_result_mapper_ready",
    "accepted",
    "rejected",
    "failed",
    "timeout",
    "unknown",
    "unavailable",
    "retry_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "id_exposed",
    "real_account_order_transaction_id_exposed",
)

_ALLOWED_SAFE_TEXT_LABELS = frozenset(
    {
        SAFE_TIME_IN_FORCE_LABEL,
        SAFE_ENVIRONMENT_LABEL,
        SAFE_RISK_LABEL,
        "STEP6G_REPO_DEFINED_ORDER_INTENT",
        UNSUPPORTED_SEALED_REQUEST_RESULT_LABEL,
    },
)
