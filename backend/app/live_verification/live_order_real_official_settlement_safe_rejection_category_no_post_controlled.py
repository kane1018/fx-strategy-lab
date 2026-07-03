"""Safe official-settlement rejection category capture, no POST.

This module classifies only already-sanitized labels and synthetic test
fixtures. It never accepts raw broker responses, error message text, IDs,
quantity values, price values, credentials, headers, signatures, HTTP clients,
or execution callables.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import StrEnum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSafePostResultCategory,
    LiveOrderRealSanitizedPostResultResult,
)

STEP_NAME = (
    "Step 6G-PC-OX-R-SAFE-REJECTION-CATEGORY-CAPTURE-DESIGN-NO-POST-C"
)
SAFE_REJECTION_CAPTURE_LABEL = (
    "OFFICIAL_SETTLEMENT_SAFE_REJECTION_CATEGORY_CAPTURE_NO_POST"
)
UNAVAILABLE_SAFE_LABEL = "UNAVAILABLE"
UNSUPPORTED_SAFE_LABEL = "UNSUPPORTED_REDACTED"
NEXT_STEP_SAFE_REJECTION_CAPTURE_READY = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-"
    "CAPTURE-INTEGRATION-NO-POST-C"
)
NEXT_STEP_FIX_SAFE_REJECTION_CAPTURE = (
    "fix_safe_rejection_category_capture_no_post"
)

SAFE_HTTP_STATUS_CLIENT_ERROR = "SAFE_HTTP_STATUS_CLIENT_ERROR"
SAFE_HTTP_STATUS_RATE_LIMIT = "SAFE_HTTP_STATUS_RATE_LIMIT"
SAFE_HTTP_STATUS_SERVER_ERROR = "SAFE_HTTP_STATUS_SERVER_ERROR"

SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING = (
    "SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING"
)
SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED = (
    "SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED"
)
SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH = "SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH"
SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH = (
    "SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH"
)
SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND = (
    "SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND"
)
SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT = (
    "SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT"
)
SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT = (
    "SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT"
)
SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT = (
    "SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT"
)

OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED = (
    "OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED"
)
OPERATOR_UI_SAFE_LABEL_MARKET_OR_SESSION_BLOCKED = (
    "OPERATOR_UI_SAFE_LABEL_MARKET_OR_SESSION_BLOCKED"
)
OPERATOR_UI_SAFE_LABEL_PERMISSION_WARNING = "OPERATOR_UI_SAFE_LABEL_PERMISSION_WARNING"

OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE = (
    "OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE"
)
OFFICIAL_DOCS_SPEC_COMPARISON_SIZE_TARGET_MISMATCH_CANDIDATE = (
    "OFFICIAL_DOCS_SPEC_COMPARISON_SIZE_TARGET_MISMATCH_CANDIDATE"
)
OFFICIAL_DOCS_SPEC_COMPARISON_SIDE_SEMANTICS_MISMATCH_CANDIDATE = (
    "OFFICIAL_DOCS_SPEC_COMPARISON_SIDE_SEMANTICS_MISMATCH_CANDIDATE"
)
OFFICIAL_DOCS_SPEC_COMPARISON_POSITION_SPECIFIC_REQUIRED_CANDIDATE = (
    "OFFICIAL_DOCS_SPEC_COMPARISON_POSITION_SPECIFIC_REQUIRED_CANDIDATE"
)

SYNTHETIC_FIXTURE_PARAMETER_SHAPE_MISMATCH = (
    "SYNTHETIC_FIXTURE_PARAMETER_SHAPE_MISMATCH"
)
SYNTHETIC_FIXTURE_SIZE_TARGET_MISMATCH = (
    "SYNTHETIC_FIXTURE_SIZE_TARGET_MISMATCH"
)
SYNTHETIC_FIXTURE_SIDE_SEMANTICS_MISMATCH = (
    "SYNTHETIC_FIXTURE_SIDE_SEMANTICS_MISMATCH"
)
SYNTHETIC_FIXTURE_POSITION_TARGET_NOT_FOUND = (
    "SYNTHETIC_FIXTURE_POSITION_TARGET_NOT_FOUND"
)


class SafeRejectionCaptureStatus(StrEnum):
    READY_NO_POST = "SAFE_REJECTION_CATEGORY_CAPTURE_READY_NO_POST"
    BLOCKED_UNSAFE_INPUT = "SAFE_REJECTION_CATEGORY_CAPTURE_BLOCKED_UNSAFE_INPUT"
    BLOCKED_EXECUTION_ATTEMPT = (
        "SAFE_REJECTION_CATEGORY_CAPTURE_BLOCKED_EXECUTION_ATTEMPT"
    )


class SafeRejectionCategory(StrEnum):
    UNKNOWN = "SAFE_REJECTION_CATEGORY_UNKNOWN"
    PARAMETER_OR_REQUEST_SHAPE = (
        "SAFE_REJECTION_CATEGORY_PARAMETER_OR_REQUEST_SHAPE"
    )
    SIZE_OR_TARGET_MISMATCH = "SAFE_REJECTION_CATEGORY_SIZE_OR_TARGET_MISMATCH"
    SIDE_OR_SETTLEMENT_SEMANTICS = (
        "SAFE_REJECTION_CATEGORY_SIDE_OR_SETTLEMENT_SEMANTICS"
    )
    POSITION_STATE_OR_TARGET_NOT_FOUND = (
        "SAFE_REJECTION_CATEGORY_POSITION_STATE_OR_TARGET_NOT_FOUND"
    )
    SESSION_OR_MARKET_CONSTRAINT = (
        "SAFE_REJECTION_CATEGORY_SESSION_OR_MARKET_CONSTRAINT"
    )
    ACCOUNT_OR_PERMISSION_CONSTRAINT = (
        "SAFE_REJECTION_CATEGORY_ACCOUNT_OR_PERMISSION_CONSTRAINT"
    )
    RATE_LIMIT_OR_TEMPORARY_CONSTRAINT = (
        "SAFE_REJECTION_CATEGORY_RATE_LIMIT_OR_TEMPORARY_CONSTRAINT"
    )
    BROKER_REJECTED_UNCLASSIFIED = (
        "SAFE_REJECTION_CATEGORY_BROKER_REJECTED_UNCLASSIFIED"
    )


class SafeRejectionKind(StrEnum):
    REQUIRED_PARAMETER_MISSING = "SAFE_REJECTION_KIND_REQUIRED_PARAMETER_MISSING"
    FORBIDDEN_PARAMETER_INCLUDED = (
        "SAFE_REJECTION_KIND_FORBIDDEN_PARAMETER_INCLUDED"
    )
    SIZE_AND_SETTLE_POSITION_CONFLICT = (
        "SAFE_REJECTION_KIND_SIZE_AND_SETTLE_POSITION_CONFLICT"
    )
    SIZE_FORMAT_OR_UNIT_MISMATCH = (
        "SAFE_REJECTION_KIND_SIZE_FORMAT_OR_UNIT_MISMATCH"
    )
    SIZE_BASED_TARGET_MISMATCH = "SAFE_REJECTION_KIND_SIZE_BASED_TARGET_MISMATCH"
    POSITION_SPECIFIC_REQUIRED_BUT_BLOCKED = (
        "SAFE_REJECTION_KIND_POSITION_SPECIFIC_REQUIRED_BUT_BLOCKED"
    )
    SIDE_SEMANTICS_MISMATCH_POSSIBLE = (
        "SAFE_REJECTION_KIND_SIDE_SEMANTICS_MISMATCH_POSSIBLE"
    )
    EXECUTION_TYPE_OR_MARKET_BOUND_MISMATCH = (
        "SAFE_REJECTION_KIND_EXECUTION_TYPE_OR_MARKET_BOUND_MISMATCH"
    )
    SESSION_CLOSED_OR_MAINTENANCE_POSSIBLE = (
        "SAFE_REJECTION_KIND_SESSION_CLOSED_OR_MAINTENANCE_POSSIBLE"
    )
    ACCOUNT_OR_PERMISSION_STILL_POSSIBLE = (
        "SAFE_REJECTION_KIND_ACCOUNT_OR_PERMISSION_STILL_POSSIBLE"
    )
    RATE_LIMIT_OR_TEMPORARY_CONSTRAINT = (
        "SAFE_REJECTION_KIND_RATE_LIMIT_OR_TEMPORARY_CONSTRAINT"
    )
    BROKER_REJECTED_REASON_UNAVAILABLE = (
        "SAFE_REJECTION_KIND_BROKER_REJECTED_REASON_UNAVAILABLE"
    )
    UNKNOWN_SAFE = "SAFE_REJECTION_KIND_UNKNOWN_SAFE"


class SafeRejectionSource(StrEnum):
    SANITIZED_RESULT_ONLY = "SAFE_REJECTION_SOURCE_SANITIZED_RESULT_ONLY"
    SYNTHETIC_CLASSIFIER_FIXTURE = (
        "SAFE_REJECTION_SOURCE_SYNTHETIC_CLASSIFIER_FIXTURE"
    )
    SAFE_BROKER_ERROR_CODE_LABEL = (
        "SAFE_REJECTION_SOURCE_SAFE_BROKER_ERROR_CODE_LABEL"
    )
    SAFE_HTTP_STATUS_LABEL = "SAFE_REJECTION_SOURCE_SAFE_HTTP_STATUS_LABEL"
    OPERATOR_UI_SAFE_LABEL = "SAFE_REJECTION_SOURCE_OPERATOR_UI_SAFE_LABEL"
    OFFICIAL_DOCS_SPEC_COMPARISON = (
        "SAFE_REJECTION_SOURCE_OFFICIAL_DOCS_SPEC_COMPARISON"
    )
    UNAVAILABLE = "SAFE_REJECTION_SOURCE_UNAVAILABLE"


class SafeRejectionConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SafeRejectionClassification:
    category: SafeRejectionCategory
    kind: SafeRejectionKind
    source: SafeRejectionSource
    confidence: SafeRejectionConfidence
    selected_safe_detail_label: str
    safe_rejection_reason_available: bool
    safe_rejection_reason_unavailable: bool
    requires_raw_response: bool
    requires_operator_ui_safe_label: bool

    def __post_init__(self) -> None:
        if not isinstance(self.category, SafeRejectionCategory):
            raise LiveVerificationValidationError("category must be safe enum")
        if not isinstance(self.kind, SafeRejectionKind):
            raise LiveVerificationValidationError("kind must be safe enum")
        if not isinstance(self.source, SafeRejectionSource):
            raise LiveVerificationValidationError("source must be safe enum")
        if not isinstance(self.confidence, SafeRejectionConfidence):
            raise LiveVerificationValidationError("confidence must be safe enum")
        _require_non_empty("selected_safe_detail_label", self.selected_safe_detail_label)
        _validate_bool_fields(self, _CLASSIFICATION_BOOL_FIELDS)


@dataclass(frozen=True)
class SafeRejectionCategoryCaptureInput:
    sanitized_result_category: str = (
        LiveOrderRealSafePostResultCategory.RESULT_REJECTED_SANITIZED.value
    )
    safe_http_status_label: str = UNAVAILABLE_SAFE_LABEL
    safe_broker_code_label: str = UNAVAILABLE_SAFE_LABEL
    operator_ui_safe_label: str = UNAVAILABLE_SAFE_LABEL
    official_docs_comparison_safe_result: str = UNAVAILABLE_SAFE_LABEL
    synthetic_fixture_label: str = UNAVAILABLE_SAFE_LABEL

    raw_response_supplied: bool = False
    broker_response_supplied: bool = False
    error_message_text_supplied: bool = False
    account_id_supplied: bool = False
    order_id_supplied: bool = False
    transaction_id_supplied: bool = False
    position_id_supplied: bool = False
    trade_id_supplied: bool = False
    quantity_value_supplied: bool = False
    price_value_supplied: bool = False
    credential_value_supplied: bool = False
    signature_value_supplied: bool = False
    headers_value_supplied: bool = False

    actual_settlement_post_executed: bool = False
    entry_post_executed: bool = False
    retry_attempted: bool = False
    repost_attempted: bool = False
    second_settlement_post_attempted: bool = False
    generic_close_post_executed: bool = False
    ledger_update_attempted: bool = False
    receipt_handoff_attempted: bool = False
    transport_call_count: int = 0
    real_http_call_count: int = 0
    generic_order_executor_used_for_settlement: bool = False
    live_order_once_used_for_settlement: bool = False
    one_shot_generic_order_path_used_for_settlement: bool = False
    position_specific_path_executed: bool = False
    env_read: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "sanitized_result_category",
            "safe_http_status_label",
            "safe_broker_code_label",
            "operator_ui_safe_label",
            "official_docs_comparison_safe_result",
            "synthetic_fixture_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_non_negative_int("real_http_call_count", self.real_http_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class SafeRejectionCategoryCaptureResult:
    step_name: str
    status: SafeRejectionCaptureStatus
    capture_label: str
    safe_rejection_category_capture_ready: bool
    safe_rejection_kind_capture_ready: bool
    safe_rejection_source_capture_ready: bool
    safe_rejection_confidence_capture_ready: bool
    safe_rejection_category: str
    safe_rejection_kind: str
    safe_rejection_source: str
    safe_rejection_confidence: str
    selected_safe_detail_label: str
    default_rejected_result_maps_to: str
    safe_rejection_reason_available: bool
    safe_rejection_reason_unavailable: bool
    requires_raw_response: bool
    requires_operator_ui_safe_label: bool

    actual_settlement_post_executed: bool
    entry_post_executed: bool
    retry_attempted: bool
    repost_attempted: bool
    second_settlement_post_attempted: bool
    generic_close_post_executed: bool
    ledger_update_attempted: bool
    receipt_handoff_attempted: bool
    transport_call_count: int
    real_http_call_count: int
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_executed: bool

    raw_response_rendered: bool
    broker_response_rendered: bool
    error_message_rendered: bool
    account_id_rendered: bool
    order_id_rendered: bool
    transaction_id_rendered: bool
    position_id_rendered: bool
    trade_id_rendered: bool
    quantity_value_rendered: bool
    price_value_rendered: bool
    credential_value_rendered: bool
    signature_value_rendered: bool
    headers_value_rendered: bool
    env_read: bool

    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, SafeRejectionCaptureStatus):
            raise LiveVerificationValidationError("status must be capture status")
        for field_name in (
            "step_name",
            "capture_label",
            "safe_rejection_category",
            "safe_rejection_kind",
            "safe_rejection_source",
            "safe_rejection_confidence",
            "selected_safe_detail_label",
            "default_rejected_result_maps_to",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_non_negative_int("real_http_call_count", self.real_http_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)


def build_safe_rejection_category_capture_no_post_controlled(
    *,
    input_snapshot: SafeRejectionCategoryCaptureInput | None = None,
    sanitized_result: LiveOrderRealSanitizedPostResultResult | None = None,
) -> SafeRejectionCategoryCaptureResult:
    """Build a safe rejection category capture result without raw input or POST."""
    snapshot = input_snapshot or SafeRejectionCategoryCaptureInput()
    if sanitized_result is not None:
        snapshot = replace(
            snapshot,
            sanitized_result_category=sanitized_result.safe_result_category,
            actual_settlement_post_executed=(
                snapshot.actual_settlement_post_executed
                or sanitized_result.post_executed
                or sanitized_result.http_post_executed
            ),
            ledger_update_attempted=(
                snapshot.ledger_update_attempted
                or sanitized_result.ledger_update_attempted
            ),
            receipt_handoff_attempted=(
                snapshot.receipt_handoff_attempted
                or sanitized_result.actual_receipt_handoff_executed
            ),
            live_order_once_used_for_settlement=(
                snapshot.live_order_once_used_for_settlement
                or sanitized_result.live_order_once_called
            ),
        )

    blocked_reasons = _blocked_reasons(snapshot)
    execution_blocked = _execution_attempted(snapshot)
    unsafe_blocked = _unsafe_input_supplied(snapshot)
    if execution_blocked:
        status = SafeRejectionCaptureStatus.BLOCKED_EXECUTION_ATTEMPT
    elif unsafe_blocked:
        status = SafeRejectionCaptureStatus.BLOCKED_UNSAFE_INPUT
    else:
        status = SafeRejectionCaptureStatus.READY_NO_POST

    classification = (
        _unavailable_classification(blocked=True)
        if status is not SafeRejectionCaptureStatus.READY_NO_POST
        else _classify(snapshot)
    )
    ready = status is SafeRejectionCaptureStatus.READY_NO_POST

    return SafeRejectionCategoryCaptureResult(
        step_name=STEP_NAME,
        status=status,
        capture_label=SAFE_REJECTION_CAPTURE_LABEL,
        safe_rejection_category_capture_ready=ready,
        safe_rejection_kind_capture_ready=ready,
        safe_rejection_source_capture_ready=ready,
        safe_rejection_confidence_capture_ready=ready,
        safe_rejection_category=classification.category.value,
        safe_rejection_kind=classification.kind.value,
        safe_rejection_source=classification.source.value,
        safe_rejection_confidence=classification.confidence.value,
        selected_safe_detail_label=classification.selected_safe_detail_label,
        default_rejected_result_maps_to=(
            f"{SafeRejectionCategory.UNKNOWN.value}/"
            f"{SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE.value}"
        ),
        safe_rejection_reason_available=classification.safe_rejection_reason_available,
        safe_rejection_reason_unavailable=(
            classification.safe_rejection_reason_unavailable
        ),
        requires_raw_response=classification.requires_raw_response,
        requires_operator_ui_safe_label=(
            classification.requires_operator_ui_safe_label
        ),
        actual_settlement_post_executed=False,
        entry_post_executed=False,
        retry_attempted=False,
        repost_attempted=False,
        second_settlement_post_attempted=False,
        generic_close_post_executed=False,
        ledger_update_attempted=False,
        receipt_handoff_attempted=False,
        transport_call_count=0,
        real_http_call_count=0,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_executed=False,
        raw_response_rendered=False,
        broker_response_rendered=False,
        error_message_rendered=False,
        account_id_rendered=False,
        order_id_rendered=False,
        transaction_id_rendered=False,
        position_id_rendered=False,
        trade_id_rendered=False,
        quantity_value_rendered=False,
        price_value_rendered=False,
        credential_value_rendered=False,
        signature_value_rendered=False,
        headers_value_rendered=False,
        env_read=False,
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            NEXT_STEP_SAFE_REJECTION_CAPTURE_READY
            if ready
            else NEXT_STEP_FIX_SAFE_REJECTION_CAPTURE
        ),
    )


def render_safe_rejection_category_capture_markdown(
    result: SafeRejectionCategoryCaptureResult,
) -> str:
    """Render only safe category/kind/source labels and booleans."""
    lines = [
        "# Step 6G Safe Rejection Category Capture",
        "",
        "This is a no-POST, no-raw safe rejection category capture summary.",
        "It contains only safe labels and booleans.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- safe_rejection_category_capture_ready: "
        f"{_bool_text(result.safe_rejection_category_capture_ready)}",
        f"- safe_rejection_kind_capture_ready: "
        f"{_bool_text(result.safe_rejection_kind_capture_ready)}",
        f"- safe_rejection_source_capture_ready: "
        f"{_bool_text(result.safe_rejection_source_capture_ready)}",
        f"- safe_rejection_category: {result.safe_rejection_category}",
        f"- safe_rejection_kind: {result.safe_rejection_kind}",
        f"- safe_rejection_source: {result.safe_rejection_source}",
        f"- safe_rejection_confidence: {result.safe_rejection_confidence}",
        f"- selected_safe_detail_label: {result.selected_safe_detail_label}",
        f"- safe_rejection_reason_available: "
        f"{_bool_text(result.safe_rejection_reason_available)}",
        f"- safe_rejection_reason_unavailable: "
        f"{_bool_text(result.safe_rejection_reason_unavailable)}",
        "",
        "## Exposure Boundary",
        f"- raw_response_rendered: {_bool_text(result.raw_response_rendered)}",
        f"- broker_response_rendered: "
        f"{_bool_text(result.broker_response_rendered)}",
        f"- error_message_rendered: {_bool_text(result.error_message_rendered)}",
        f"- account_id_rendered: {_bool_text(result.account_id_rendered)}",
        f"- order_id_rendered: {_bool_text(result.order_id_rendered)}",
        f"- position_id_rendered: {_bool_text(result.position_id_rendered)}",
        f"- trade_id_rendered: {_bool_text(result.trade_id_rendered)}",
        f"- quantity_value_rendered: {_bool_text(result.quantity_value_rendered)}",
        f"- price_value_rendered: {_bool_text(result.price_value_rendered)}",
        f"- credential_value_rendered: "
        f"{_bool_text(result.credential_value_rendered)}",
        f"- signature_value_rendered: {_bool_text(result.signature_value_rendered)}",
        f"- headers_value_rendered: {_bool_text(result.headers_value_rendered)}",
        f"- env_read: {_bool_text(result.env_read)}",
        "",
        "## Execution Boundary",
        f"- actual_settlement_post_executed: "
        f"{_bool_text(result.actual_settlement_post_executed)}",
        f"- entry_post_executed: {_bool_text(result.entry_post_executed)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- repost_attempted: {_bool_text(result.repost_attempted)}",
        f"- second_settlement_post_attempted: "
        f"{_bool_text(result.second_settlement_post_attempted)}",
        f"- generic_close_post_executed: "
        f"{_bool_text(result.generic_close_post_executed)}",
        f"- transport_call_count: {result.transport_call_count}",
        f"- real_http_call_count: {result.real_http_call_count}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _classify(
    snapshot: SafeRejectionCategoryCaptureInput,
) -> SafeRejectionClassification:
    if (
        snapshot.sanitized_result_category
        != LiveOrderRealSafePostResultCategory.RESULT_REJECTED_SANITIZED.value
    ):
        return SafeRejectionClassification(
            category=SafeRejectionCategory.UNKNOWN,
            kind=SafeRejectionKind.UNKNOWN_SAFE,
            source=SafeRejectionSource.SANITIZED_RESULT_ONLY,
            confidence=SafeRejectionConfidence.UNKNOWN,
            selected_safe_detail_label=UNAVAILABLE_SAFE_LABEL,
            safe_rejection_reason_available=False,
            safe_rejection_reason_unavailable=True,
            requires_raw_response=False,
            requires_operator_ui_safe_label=True,
        )

    for label, classification in _SAFE_BROKER_CODE_MAP.items():
        if snapshot.safe_broker_code_label == label:
            return classification
    for label, classification in _SAFE_HTTP_STATUS_MAP.items():
        if snapshot.safe_http_status_label == label:
            return classification
    for label, classification in _OPERATOR_UI_SAFE_LABEL_MAP.items():
        if snapshot.operator_ui_safe_label == label:
            return classification
    for label, classification in _OFFICIAL_DOCS_COMPARISON_MAP.items():
        if snapshot.official_docs_comparison_safe_result == label:
            return classification
    for label, classification in _SYNTHETIC_FIXTURE_MAP.items():
        if snapshot.synthetic_fixture_label == label:
            return classification
    return _rejected_unavailable_classification()


def _classification(
    *,
    category: SafeRejectionCategory,
    kind: SafeRejectionKind,
    source: SafeRejectionSource,
    confidence: SafeRejectionConfidence,
    label: str,
) -> SafeRejectionClassification:
    return SafeRejectionClassification(
        category=category,
        kind=kind,
        source=source,
        confidence=confidence,
        selected_safe_detail_label=label,
        safe_rejection_reason_available=True,
        safe_rejection_reason_unavailable=False,
        requires_raw_response=False,
        requires_operator_ui_safe_label=False,
    )


def _unavailable_classification(*, blocked: bool) -> SafeRejectionClassification:
    return SafeRejectionClassification(
        category=SafeRejectionCategory.UNKNOWN,
        kind=(
            SafeRejectionKind.UNKNOWN_SAFE
            if blocked
            else SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE
        ),
        source=(
            SafeRejectionSource.UNAVAILABLE
            if blocked
            else SafeRejectionSource.SANITIZED_RESULT_ONLY
        ),
        confidence=SafeRejectionConfidence.UNKNOWN,
        selected_safe_detail_label=UNAVAILABLE_SAFE_LABEL,
        safe_rejection_reason_available=False,
        safe_rejection_reason_unavailable=True,
        requires_raw_response=False,
        requires_operator_ui_safe_label=not blocked,
    )


def _rejected_unavailable_classification() -> SafeRejectionClassification:
    return SafeRejectionClassification(
        category=SafeRejectionCategory.UNKNOWN,
        kind=SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE,
        source=SafeRejectionSource.SANITIZED_RESULT_ONLY,
        confidence=SafeRejectionConfidence.UNKNOWN,
        selected_safe_detail_label=UNAVAILABLE_SAFE_LABEL,
        safe_rejection_reason_available=False,
        safe_rejection_reason_unavailable=True,
        requires_raw_response=True,
        requires_operator_ui_safe_label=True,
    )


def _unsafe_input_supplied(snapshot: SafeRejectionCategoryCaptureInput) -> bool:
    return any(
        (
            snapshot.raw_response_supplied,
            snapshot.broker_response_supplied,
            snapshot.error_message_text_supplied,
            snapshot.account_id_supplied,
            snapshot.order_id_supplied,
            snapshot.transaction_id_supplied,
            snapshot.position_id_supplied,
            snapshot.trade_id_supplied,
            snapshot.quantity_value_supplied,
            snapshot.price_value_supplied,
            snapshot.credential_value_supplied,
            snapshot.signature_value_supplied,
            snapshot.headers_value_supplied,
            snapshot.env_read,
        ),
    )


def _execution_attempted(snapshot: SafeRejectionCategoryCaptureInput) -> bool:
    return any(
        (
            snapshot.actual_settlement_post_executed,
            snapshot.entry_post_executed,
            snapshot.retry_attempted,
            snapshot.repost_attempted,
            snapshot.second_settlement_post_attempted,
            snapshot.generic_close_post_executed,
            snapshot.ledger_update_attempted,
            snapshot.receipt_handoff_attempted,
            snapshot.transport_call_count > 0,
            snapshot.real_http_call_count > 0,
            snapshot.generic_order_executor_used_for_settlement,
            snapshot.live_order_once_used_for_settlement,
            snapshot.one_shot_generic_order_path_used_for_settlement,
            snapshot.position_specific_path_executed,
        ),
    )


def _blocked_reasons(
    snapshot: SafeRejectionCategoryCaptureInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _unsafe_input_supplied(snapshot):
        reasons.append("unsafe_raw_value_or_secret_input_blocked")
    if _execution_attempted(snapshot):
        reasons.append("execution_or_transport_attempt_blocked")
    return tuple(reasons)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, bool_fields: frozenset[str]) -> None:
    for field in fields(obj):
        if field.name in bool_fields and type(getattr(obj, field.name)) is not bool:
            raise LiveVerificationValidationError(f"{field.name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_CLASSIFICATION_BOOL_FIELDS = frozenset(
    {
        "safe_rejection_reason_available",
        "safe_rejection_reason_unavailable",
        "requires_raw_response",
        "requires_operator_ui_safe_label",
    },
)

_INPUT_BOOL_FIELDS = frozenset(
    {
        "raw_response_supplied",
        "broker_response_supplied",
        "error_message_text_supplied",
        "account_id_supplied",
        "order_id_supplied",
        "transaction_id_supplied",
        "position_id_supplied",
        "trade_id_supplied",
        "quantity_value_supplied",
        "price_value_supplied",
        "credential_value_supplied",
        "signature_value_supplied",
        "headers_value_supplied",
        "actual_settlement_post_executed",
        "entry_post_executed",
        "retry_attempted",
        "repost_attempted",
        "second_settlement_post_attempted",
        "generic_close_post_executed",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_executed",
        "env_read",
    },
)

_RESULT_BOOL_FIELDS = frozenset(
    {
        "safe_rejection_category_capture_ready",
        "safe_rejection_kind_capture_ready",
        "safe_rejection_source_capture_ready",
        "safe_rejection_confidence_capture_ready",
        "safe_rejection_reason_available",
        "safe_rejection_reason_unavailable",
        "requires_raw_response",
        "requires_operator_ui_safe_label",
        "actual_settlement_post_executed",
        "entry_post_executed",
        "retry_attempted",
        "repost_attempted",
        "second_settlement_post_attempted",
        "generic_close_post_executed",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_executed",
        "raw_response_rendered",
        "broker_response_rendered",
        "error_message_rendered",
        "account_id_rendered",
        "order_id_rendered",
        "transaction_id_rendered",
        "position_id_rendered",
        "trade_id_rendered",
        "quantity_value_rendered",
        "price_value_rendered",
        "credential_value_rendered",
        "signature_value_rendered",
        "headers_value_rendered",
        "env_read",
    },
)

_SAFE_BROKER_CODE_MAP = {
    SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING: _classification(
        category=SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
        kind=SafeRejectionKind.REQUIRED_PARAMETER_MISSING,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.HIGH,
        label=SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    ),
    SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED: _classification(
        category=SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
        kind=SafeRejectionKind.FORBIDDEN_PARAMETER_INCLUDED,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.HIGH,
        label=SAFE_BROKER_CODE_FORBIDDEN_PARAMETER_INCLUDED,
    ),
    SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH: _classification(
        category=SafeRejectionCategory.SIZE_OR_TARGET_MISMATCH,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.HIGH,
        label=SAFE_BROKER_CODE_SIZE_TARGET_MISMATCH,
    ),
    SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH: _classification(
        category=SafeRejectionCategory.SIDE_OR_SETTLEMENT_SEMANTICS,
        kind=SafeRejectionKind.SIDE_SEMANTICS_MISMATCH_POSSIBLE,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.HIGH,
        label=SAFE_BROKER_CODE_SIDE_SEMANTICS_MISMATCH,
    ),
    SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND: _classification(
        category=SafeRejectionCategory.POSITION_STATE_OR_TARGET_NOT_FOUND,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.HIGH,
        label=SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND,
    ),
    SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT: _classification(
        category=SafeRejectionCategory.SESSION_OR_MARKET_CONSTRAINT,
        kind=SafeRejectionKind.SESSION_CLOSED_OR_MAINTENANCE_POSSIBLE,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=SAFE_BROKER_CODE_SESSION_MARKET_CONSTRAINT,
    ),
    SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT: _classification(
        category=SafeRejectionCategory.ACCOUNT_OR_PERMISSION_CONSTRAINT,
        kind=SafeRejectionKind.ACCOUNT_OR_PERMISSION_STILL_POSSIBLE,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=SAFE_BROKER_CODE_ACCOUNT_PERMISSION_CONSTRAINT,
    ),
    SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT: _classification(
        category=SafeRejectionCategory.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        kind=SafeRejectionKind.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        source=SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=SAFE_BROKER_CODE_RATE_LIMIT_TEMPORARY_CONSTRAINT,
    ),
}

_SAFE_HTTP_STATUS_MAP = {
    SAFE_HTTP_STATUS_CLIENT_ERROR: _classification(
        category=SafeRejectionCategory.BROKER_REJECTED_UNCLASSIFIED,
        kind=SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE,
        source=SafeRejectionSource.SAFE_HTTP_STATUS_LABEL,
        confidence=SafeRejectionConfidence.LOW,
        label=SAFE_HTTP_STATUS_CLIENT_ERROR,
    ),
    SAFE_HTTP_STATUS_RATE_LIMIT: _classification(
        category=SafeRejectionCategory.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        kind=SafeRejectionKind.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        source=SafeRejectionSource.SAFE_HTTP_STATUS_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=SAFE_HTTP_STATUS_RATE_LIMIT,
    ),
    SAFE_HTTP_STATUS_SERVER_ERROR: _classification(
        category=SafeRejectionCategory.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        kind=SafeRejectionKind.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
        source=SafeRejectionSource.SAFE_HTTP_STATUS_LABEL,
        confidence=SafeRejectionConfidence.LOW,
        label=SAFE_HTTP_STATUS_SERVER_ERROR,
    ),
}

_OPERATOR_UI_SAFE_LABEL_MAP = {
    OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED: _classification(
        category=SafeRejectionCategory.POSITION_STATE_OR_TARGET_NOT_FOUND,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.OPERATOR_UI_SAFE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED,
    ),
    OPERATOR_UI_SAFE_LABEL_MARKET_OR_SESSION_BLOCKED: _classification(
        category=SafeRejectionCategory.SESSION_OR_MARKET_CONSTRAINT,
        kind=SafeRejectionKind.SESSION_CLOSED_OR_MAINTENANCE_POSSIBLE,
        source=SafeRejectionSource.OPERATOR_UI_SAFE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=OPERATOR_UI_SAFE_LABEL_MARKET_OR_SESSION_BLOCKED,
    ),
    OPERATOR_UI_SAFE_LABEL_PERMISSION_WARNING: _classification(
        category=SafeRejectionCategory.ACCOUNT_OR_PERMISSION_CONSTRAINT,
        kind=SafeRejectionKind.ACCOUNT_OR_PERMISSION_STILL_POSSIBLE,
        source=SafeRejectionSource.OPERATOR_UI_SAFE_LABEL,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=OPERATOR_UI_SAFE_LABEL_PERMISSION_WARNING,
    ),
}

_OFFICIAL_DOCS_COMPARISON_MAP = {
    OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE: _classification(
        category=SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
        kind=SafeRejectionKind.EXECUTION_TYPE_OR_MARKET_BOUND_MISMATCH,
        source=SafeRejectionSource.OFFICIAL_DOCS_SPEC_COMPARISON,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE,
    ),
    OFFICIAL_DOCS_SPEC_COMPARISON_SIZE_TARGET_MISMATCH_CANDIDATE: _classification(
        category=SafeRejectionCategory.SIZE_OR_TARGET_MISMATCH,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.OFFICIAL_DOCS_SPEC_COMPARISON,
        confidence=SafeRejectionConfidence.MEDIUM,
        label=OFFICIAL_DOCS_SPEC_COMPARISON_SIZE_TARGET_MISMATCH_CANDIDATE,
    ),
    OFFICIAL_DOCS_SPEC_COMPARISON_SIDE_SEMANTICS_MISMATCH_CANDIDATE: (
        _classification(
            category=SafeRejectionCategory.SIDE_OR_SETTLEMENT_SEMANTICS,
            kind=SafeRejectionKind.SIDE_SEMANTICS_MISMATCH_POSSIBLE,
            source=SafeRejectionSource.OFFICIAL_DOCS_SPEC_COMPARISON,
            confidence=SafeRejectionConfidence.MEDIUM,
            label=OFFICIAL_DOCS_SPEC_COMPARISON_SIDE_SEMANTICS_MISMATCH_CANDIDATE,
        )
    ),
    OFFICIAL_DOCS_SPEC_COMPARISON_POSITION_SPECIFIC_REQUIRED_CANDIDATE: (
        _classification(
            category=SafeRejectionCategory.SIZE_OR_TARGET_MISMATCH,
            kind=SafeRejectionKind.POSITION_SPECIFIC_REQUIRED_BUT_BLOCKED,
            source=SafeRejectionSource.OFFICIAL_DOCS_SPEC_COMPARISON,
            confidence=SafeRejectionConfidence.LOW,
            label=OFFICIAL_DOCS_SPEC_COMPARISON_POSITION_SPECIFIC_REQUIRED_CANDIDATE,
        )
    ),
}

_SYNTHETIC_FIXTURE_MAP = {
    SYNTHETIC_FIXTURE_PARAMETER_SHAPE_MISMATCH: _classification(
        category=SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
        kind=SafeRejectionKind.REQUIRED_PARAMETER_MISSING,
        source=SafeRejectionSource.SYNTHETIC_CLASSIFIER_FIXTURE,
        confidence=SafeRejectionConfidence.HIGH,
        label=SYNTHETIC_FIXTURE_PARAMETER_SHAPE_MISMATCH,
    ),
    SYNTHETIC_FIXTURE_SIZE_TARGET_MISMATCH: _classification(
        category=SafeRejectionCategory.SIZE_OR_TARGET_MISMATCH,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.SYNTHETIC_CLASSIFIER_FIXTURE,
        confidence=SafeRejectionConfidence.HIGH,
        label=SYNTHETIC_FIXTURE_SIZE_TARGET_MISMATCH,
    ),
    SYNTHETIC_FIXTURE_SIDE_SEMANTICS_MISMATCH: _classification(
        category=SafeRejectionCategory.SIDE_OR_SETTLEMENT_SEMANTICS,
        kind=SafeRejectionKind.SIDE_SEMANTICS_MISMATCH_POSSIBLE,
        source=SafeRejectionSource.SYNTHETIC_CLASSIFIER_FIXTURE,
        confidence=SafeRejectionConfidence.HIGH,
        label=SYNTHETIC_FIXTURE_SIDE_SEMANTICS_MISMATCH,
    ),
    SYNTHETIC_FIXTURE_POSITION_TARGET_NOT_FOUND: _classification(
        category=SafeRejectionCategory.POSITION_STATE_OR_TARGET_NOT_FOUND,
        kind=SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
        source=SafeRejectionSource.SYNTHETIC_CLASSIFIER_FIXTURE,
        confidence=SafeRejectionConfidence.HIGH,
        label=SYNTHETIC_FIXTURE_POSITION_TARGET_NOT_FOUND,
    ),
}
