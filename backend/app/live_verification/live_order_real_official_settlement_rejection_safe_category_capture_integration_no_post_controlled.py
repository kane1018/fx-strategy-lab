"""Official settlement rejected-result safe category integration, no POST.

This adapter connects official settlement sanitized result handling to the safe
rejection category capture boundary. It accepts only safe labels and execution
counters/booleans, never raw broker payloads or identifying/value fields.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_safe_rejection_category_no_post_controlled import (  # noqa: E501
    SafeRejectionCategoryCaptureInput,
    SafeRejectionCategoryCaptureResult,
    build_safe_rejection_category_capture_no_post_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSafePostResultCategory,
)

STEP_NAME = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-"
    "CAPTURE-INTEGRATION-NO-POST-C"
)
SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION_LABEL = (
    "OFFICIAL_SETTLEMENT_REJECTION_SAFE_CATEGORY_CAPTURE_INTEGRATION_NO_POST"
)
NEXT_STEP_AFTER_SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-"
    "REPORTING-HANDOFF-NO-POST-C"
)
NEXT_STEP_FIX_SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION = (
    "fix_official_settlement_rejection_safe_category_capture_integration_no_post"
)
UNAVAILABLE_SAFE_LABEL = "UNAVAILABLE"


class OfficialSettlementRejectionSafeCategoryIntegrationStatus(StrEnum):
    READY_NO_POST = (
        "OFFICIAL_SETTLEMENT_REJECTION_SAFE_CATEGORY_CAPTURE_INTEGRATED_NO_POST"
    )
    BLOCKED_UNSAFE_INPUT = (
        "OFFICIAL_SETTLEMENT_REJECTION_SAFE_CATEGORY_CAPTURE_BLOCKED_UNSAFE_INPUT"
    )
    BLOCKED_EXECUTION_ATTEMPT = (
        "OFFICIAL_SETTLEMENT_REJECTION_SAFE_CATEGORY_CAPTURE_BLOCKED_EXECUTION"
    )


@dataclass(frozen=True)
class OfficialSettlementRejectionSafeCategoryIntegrationInput:
    official_settlement_result_category: str = (
        LiveOrderRealSafePostResultCategory.RESULT_REJECTED_SANITIZED.value
    )
    safe_http_status_label: str = UNAVAILABLE_SAFE_LABEL
    safe_broker_code_label: str = UNAVAILABLE_SAFE_LABEL
    operator_ui_safe_label: str = UNAVAILABLE_SAFE_LABEL
    official_docs_comparison_safe_result: str = UNAVAILABLE_SAFE_LABEL

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

    actual_post_executed: bool = False
    settlement_post_count: int = 0
    transport_call_count: int = 0
    real_http_call_count: int = 0
    retry: bool = False
    repost: bool = False
    second_post: bool = False
    entry_post_executed: bool = False
    generic_close_executed: bool = False
    ledger_update_attempted: bool = False
    receipt_handoff_attempted: bool = False
    generic_order_executor_used_for_settlement: bool = False
    live_order_once_used_for_settlement: bool = False
    one_shot_generic_order_path_used_for_settlement: bool = False
    position_specific_path_executed: bool = False
    env_read: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "official_settlement_result_category",
            "safe_http_status_label",
            "safe_broker_code_label",
            "operator_ui_safe_label",
            "official_docs_comparison_safe_result",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_non_negative_int("real_http_call_count", self.real_http_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRejectionSafeCategoryIntegrationResult:
    step_name: str
    status: OfficialSettlementRejectionSafeCategoryIntegrationStatus
    integration_label: str
    safe_rejection_category_capture_integrated: bool
    official_settlement_rejected_result_uses_safe_category_capture: bool
    default_rejected_result_maps_to: str
    safe_detail_labels_can_map_to_category: bool
    safe_detail_labels_required_for_non_unknown_category: bool

    safe_rejection_category: str
    safe_rejection_kind: str
    safe_rejection_source: str
    safe_rejection_confidence: str
    safe_rejection_reason_available: bool
    safe_rejection_reason_unavailable: bool
    safe_rejection_requires_raw_response: bool
    safe_rejection_requires_operator_ui_safe_label: bool
    raw_response_inspected: bool
    broker_response_exposed: bool
    error_message_rendered: bool

    actual_post_executed: bool
    settlement_post_count: int
    transport_call_count: int
    real_http_call_count: int
    retry: bool
    repost: bool
    second_post: bool
    entry_post_executed: bool
    generic_close_executed: bool
    ledger_update_attempted: bool
    receipt_handoff_attempted: bool
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_executed: bool

    raw_response_rendered: bool
    broker_response_rendered: bool
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
    raw_id_value_exposure: bool
    env_read: bool

    safe_rejection_capture_result: SafeRejectionCategoryCaptureResult
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            OfficialSettlementRejectionSafeCategoryIntegrationStatus,
        ):
            raise LiveVerificationValidationError("status must be integration enum")
        for field_name in (
            "step_name",
            "integration_label",
            "default_rejected_result_maps_to",
            "safe_rejection_category",
            "safe_rejection_kind",
            "safe_rejection_source",
            "safe_rejection_confidence",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        if not isinstance(
            self.safe_rejection_capture_result,
            SafeRejectionCategoryCaptureResult,
        ):
            raise LiveVerificationValidationError(
                "safe_rejection_capture_result must be safe capture result",
            )
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_non_negative_int("real_http_call_count", self.real_http_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)


def build_official_settlement_rejection_safe_category_capture_integration_no_post(
    input_snapshot: (
        OfficialSettlementRejectionSafeCategoryIntegrationInput | None
    ) = None,
) -> OfficialSettlementRejectionSafeCategoryIntegrationResult:
    snapshot = (
        input_snapshot or OfficialSettlementRejectionSafeCategoryIntegrationInput()
    )
    capture = build_safe_rejection_category_capture_no_post_controlled(
        input_snapshot=SafeRejectionCategoryCaptureInput(
            sanitized_result_category=snapshot.official_settlement_result_category,
            safe_http_status_label=snapshot.safe_http_status_label,
            safe_broker_code_label=snapshot.safe_broker_code_label,
            operator_ui_safe_label=snapshot.operator_ui_safe_label,
            official_docs_comparison_safe_result=(
                snapshot.official_docs_comparison_safe_result
            ),
            raw_response_supplied=snapshot.raw_response_supplied,
            broker_response_supplied=snapshot.broker_response_supplied,
            error_message_text_supplied=snapshot.error_message_text_supplied,
            account_id_supplied=snapshot.account_id_supplied,
            order_id_supplied=snapshot.order_id_supplied,
            transaction_id_supplied=snapshot.transaction_id_supplied,
            position_id_supplied=snapshot.position_id_supplied,
            trade_id_supplied=snapshot.trade_id_supplied,
            quantity_value_supplied=snapshot.quantity_value_supplied,
            price_value_supplied=snapshot.price_value_supplied,
            credential_value_supplied=snapshot.credential_value_supplied,
            signature_value_supplied=snapshot.signature_value_supplied,
            headers_value_supplied=snapshot.headers_value_supplied,
            actual_settlement_post_executed=snapshot.actual_post_executed,
            entry_post_executed=snapshot.entry_post_executed,
            retry_attempted=snapshot.retry,
            repost_attempted=snapshot.repost,
            second_settlement_post_attempted=snapshot.second_post,
            generic_close_post_executed=snapshot.generic_close_executed,
            ledger_update_attempted=snapshot.ledger_update_attempted,
            receipt_handoff_attempted=snapshot.receipt_handoff_attempted,
            transport_call_count=snapshot.transport_call_count,
            real_http_call_count=snapshot.real_http_call_count,
            generic_order_executor_used_for_settlement=(
                snapshot.generic_order_executor_used_for_settlement
            ),
            live_order_once_used_for_settlement=(
                snapshot.live_order_once_used_for_settlement
            ),
            one_shot_generic_order_path_used_for_settlement=(
                snapshot.one_shot_generic_order_path_used_for_settlement
            ),
            position_specific_path_executed=snapshot.position_specific_path_executed,
            env_read=snapshot.env_read,
        ),
    )
    blocked_reasons = _blocked_reasons(snapshot, capture)
    if any(reason == "execution_or_transport_attempt_blocked" for reason in blocked_reasons):
        status = (
            OfficialSettlementRejectionSafeCategoryIntegrationStatus
            .BLOCKED_EXECUTION_ATTEMPT
        )
    elif blocked_reasons:
        status = (
            OfficialSettlementRejectionSafeCategoryIntegrationStatus
            .BLOCKED_UNSAFE_INPUT
        )
    else:
        status = (
            OfficialSettlementRejectionSafeCategoryIntegrationStatus.READY_NO_POST
        )
    ready = status is OfficialSettlementRejectionSafeCategoryIntegrationStatus.READY_NO_POST

    return OfficialSettlementRejectionSafeCategoryIntegrationResult(
        step_name=STEP_NAME,
        status=status,
        integration_label=SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION_LABEL,
        safe_rejection_category_capture_integrated=ready,
        official_settlement_rejected_result_uses_safe_category_capture=(
            ready
            and snapshot.official_settlement_result_category
            == LiveOrderRealSafePostResultCategory.RESULT_REJECTED_SANITIZED.value
        ),
        default_rejected_result_maps_to=capture.default_rejected_result_maps_to,
        safe_detail_labels_can_map_to_category=ready,
        safe_detail_labels_required_for_non_unknown_category=True,
        safe_rejection_category=capture.safe_rejection_category,
        safe_rejection_kind=capture.safe_rejection_kind,
        safe_rejection_source=capture.safe_rejection_source,
        safe_rejection_confidence=capture.safe_rejection_confidence,
        safe_rejection_reason_available=capture.safe_rejection_reason_available,
        safe_rejection_reason_unavailable=capture.safe_rejection_reason_unavailable,
        safe_rejection_requires_raw_response=capture.requires_raw_response,
        safe_rejection_requires_operator_ui_safe_label=(
            capture.requires_operator_ui_safe_label
        ),
        raw_response_inspected=False,
        broker_response_exposed=False,
        error_message_rendered=False,
        actual_post_executed=False,
        settlement_post_count=0,
        transport_call_count=0,
        real_http_call_count=0,
        retry=False,
        repost=False,
        second_post=False,
        entry_post_executed=False,
        generic_close_executed=False,
        ledger_update_attempted=False,
        receipt_handoff_attempted=False,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_executed=False,
        raw_response_rendered=False,
        broker_response_rendered=False,
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
        raw_id_value_exposure=False,
        env_read=False,
        safe_rejection_capture_result=capture,
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            NEXT_STEP_AFTER_SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION
            if ready
            else NEXT_STEP_FIX_SAFE_REJECTION_CATEGORY_CAPTURE_INTEGRATION
        ),
    )


def render_official_settlement_rejection_safe_category_capture_integration_markdown(
    result: OfficialSettlementRejectionSafeCategoryIntegrationResult,
) -> str:
    lines = [
        "# Official Settlement Rejection Safe Category Capture Integration",
        "",
        "This is a no-POST, no-raw official settlement result integration summary.",
        "",
        "## Integration",
        f"- status: {result.status.value}",
        f"- safe_rejection_category_capture_integrated: "
        f"{_bool_text(result.safe_rejection_category_capture_integrated)}",
        f"- official_settlement_rejected_result_uses_safe_category_capture: "
        f"{_bool_text(result.official_settlement_rejected_result_uses_safe_category_capture)}",
        f"- default_rejected_result_maps_to: {result.default_rejected_result_maps_to}",
        f"- safe_detail_labels_can_map_to_category: "
        f"{_bool_text(result.safe_detail_labels_can_map_to_category)}",
        "",
        "## Safe Rejection Fields",
        f"- safe_rejection_category: {result.safe_rejection_category}",
        f"- safe_rejection_kind: {result.safe_rejection_kind}",
        f"- safe_rejection_source: {result.safe_rejection_source}",
        f"- safe_rejection_confidence: {result.safe_rejection_confidence}",
        f"- safe_rejection_reason_available: "
        f"{_bool_text(result.safe_rejection_reason_available)}",
        f"- safe_rejection_reason_unavailable: "
        f"{_bool_text(result.safe_rejection_reason_unavailable)}",
        f"- safe_rejection_requires_raw_response: "
        f"{_bool_text(result.safe_rejection_requires_raw_response)}",
        f"- safe_rejection_requires_operator_ui_safe_label: "
        f"{_bool_text(result.safe_rejection_requires_operator_ui_safe_label)}",
        "",
        "## Exposure Boundary",
        f"- raw_response_inspected: {_bool_text(result.raw_response_inspected)}",
        f"- raw_response_rendered: {_bool_text(result.raw_response_rendered)}",
        f"- broker_response_exposed: {_bool_text(result.broker_response_exposed)}",
        f"- broker_response_rendered: {_bool_text(result.broker_response_rendered)}",
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
        f"- raw_id_value_exposure: {_bool_text(result.raw_id_value_exposure)}",
        f"- env_read: {_bool_text(result.env_read)}",
        "",
        "## Execution Boundary",
        f"- actual_post_executed: {_bool_text(result.actual_post_executed)}",
        f"- settlement_post_count: {result.settlement_post_count}",
        f"- transport_call_count: {result.transport_call_count}",
        f"- real_http_call_count: {result.real_http_call_count}",
        f"- retry: {_bool_text(result.retry)}",
        f"- repost: {_bool_text(result.repost)}",
        f"- second_post: {_bool_text(result.second_post)}",
        f"- entry_post_executed: {_bool_text(result.entry_post_executed)}",
        f"- generic_close_executed: {_bool_text(result.generic_close_executed)}",
        f"- live_order_once_used_for_settlement: "
        f"{_bool_text(result.live_order_once_used_for_settlement)}",
        f"- position_specific_path_executed: "
        f"{_bool_text(result.position_specific_path_executed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _blocked_reasons(
    snapshot: OfficialSettlementRejectionSafeCategoryIntegrationInput,
    capture: SafeRejectionCategoryCaptureResult,
) -> tuple[str, ...]:
    reasons = list(capture.blocked_reasons)
    if snapshot.settlement_post_count > 0:
        reasons.append("execution_or_transport_attempt_blocked")
    if (
        snapshot.official_settlement_result_category
        != LiveOrderRealSafePostResultCategory.RESULT_REJECTED_SANITIZED.value
    ):
        reasons.append("official_settlement_result_not_rejected_sanitized")
    return tuple(dict.fromkeys(reasons))


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
        "actual_post_executed",
        "retry",
        "repost",
        "second_post",
        "entry_post_executed",
        "generic_close_executed",
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
        "safe_rejection_category_capture_integrated",
        "official_settlement_rejected_result_uses_safe_category_capture",
        "safe_detail_labels_can_map_to_category",
        "safe_detail_labels_required_for_non_unknown_category",
        "safe_rejection_reason_available",
        "safe_rejection_reason_unavailable",
        "safe_rejection_requires_raw_response",
        "safe_rejection_requires_operator_ui_safe_label",
        "raw_response_inspected",
        "broker_response_exposed",
        "error_message_rendered",
        "actual_post_executed",
        "retry",
        "repost",
        "second_post",
        "entry_post_executed",
        "generic_close_executed",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_executed",
        "raw_response_rendered",
        "broker_response_rendered",
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
        "raw_id_value_exposure",
        "env_read",
    },
)
