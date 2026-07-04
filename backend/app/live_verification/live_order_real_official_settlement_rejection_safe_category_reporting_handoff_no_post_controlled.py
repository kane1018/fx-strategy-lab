"""Official settlement rejection safe category reporting handoff, no POST.

This module turns the official-settlement safe category integration result into
final-report and ChatGPT handoff safe fields. It never calls transport, reads
environment files, or accepts raw broker payloads as reportable content.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import StrEnum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_rejection_safe_category_capture_integration_no_post_controlled import (  # noqa: E501
    OfficialSettlementRejectionSafeCategoryIntegrationInput,
    OfficialSettlementRejectionSafeCategoryIntegrationResult,
    OfficialSettlementRejectionSafeCategoryIntegrationStatus,
    build_official_settlement_rejection_safe_category_capture_integration_no_post,
)

STEP_NAME = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-"
    "REPORTING-HANDOFF-NO-POST-C"
)
REPORTING_HANDOFF_LABEL = (
    "OFFICIAL_SETTLEMENT_REJECTION_SAFE_CATEGORY_REPORTING_HANDOFF_NO_POST"
)
NEXT_STEP_AFTER_REPORTING_HANDOFF = (
    "Step 6G-PC-OX-R-FRESH-ENTRY-SIGNAL-SAFE-LABEL-CONFIRMATION-NO-POST-C"
)
NEXT_STEP_FIX_REPORTING_HANDOFF = "fix_safe_rejection_reporting_handoff_no_post"


class OfficialSettlementRejectionSafeCategoryReportingHandoffStatus(StrEnum):
    READY_NO_POST = "OFFICIAL_SETTLEMENT_REJECTION_REPORTING_HANDOFF_READY_NO_POST"
    BLOCKED_UNSAFE_INPUT = (
        "OFFICIAL_SETTLEMENT_REJECTION_REPORTING_HANDOFF_BLOCKED_UNSAFE_INPUT"
    )
    BLOCKED_EXECUTION_ATTEMPT = (
        "OFFICIAL_SETTLEMENT_REJECTION_REPORTING_HANDOFF_BLOCKED_EXECUTION"
    )


@dataclass(frozen=True)
class OfficialSettlementRejectionSafeCategoryReportingHandoffInput:
    integration_input: OfficialSettlementRejectionSafeCategoryIntegrationInput = (
        field(default_factory=OfficialSettlementRejectionSafeCategoryIntegrationInput)
    )
    final_report_requested: bool = True
    chatgpt_handoff_requested: bool = True
    docs_handoff_requested: bool = True

    actual_settlement_post_this_step: bool = False
    entry_post_this_step: bool = False
    retry_this_step: bool = False
    repost_this_step: bool = False
    second_settlement_post_this_step: bool = False
    generic_close_this_step: bool = False
    ledger_update: bool = False
    receipt_handoff: bool = False
    raw_id_value_exposure: bool = False
    env_read: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.integration_input,
            OfficialSettlementRejectionSafeCategoryIntegrationInput,
        ):
            raise LiveVerificationValidationError(
                "integration_input must be safe integration input",
            )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRejectionSafeCategoryReportingHandoffResult:
    step_name: str
    status: OfficialSettlementRejectionSafeCategoryReportingHandoffStatus
    reporting_handoff_label: str
    safe_rejection_reporting_handoff_ready: bool
    final_report_includes_safe_rejection_fields: bool
    chatgpt_handoff_includes_safe_rejection_fields: bool
    docs_status_handoff_includes_safe_rejection_fields: bool

    safe_rejection_category: str
    safe_rejection_kind: str
    safe_rejection_source: str
    safe_rejection_confidence: str
    safe_rejection_reason_available: bool
    safe_rejection_reason_unavailable: bool
    safe_rejection_requires_raw_response: bool
    safe_rejection_requires_operator_ui_safe_label: bool
    default_rejected_result_maps_to: str

    raw_response_inspected: bool
    broker_response_exposed: bool
    error_message_rendered: bool
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

    actual_settlement_post_this_step: bool
    entry_post_this_step: bool
    retry_this_step: bool
    repost_this_step: bool
    second_settlement_post_this_step: bool
    generic_close_this_step: bool
    ledger_update: bool
    receipt_handoff: bool
    settlement_post_count: int
    transport_call_count: int
    real_http_call_count: int
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_executed: bool

    integration_result: OfficialSettlementRejectionSafeCategoryIntegrationResult
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            OfficialSettlementRejectionSafeCategoryReportingHandoffStatus,
        ):
            raise LiveVerificationValidationError("status must be reporting enum")
        for field_name in (
            "step_name",
            "reporting_handoff_label",
            "safe_rejection_category",
            "safe_rejection_kind",
            "safe_rejection_source",
            "safe_rejection_confidence",
            "default_rejected_result_maps_to",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        if not isinstance(
            self.integration_result,
            OfficialSettlementRejectionSafeCategoryIntegrationResult,
        ):
            raise LiveVerificationValidationError(
                "integration_result must be safe integration result",
            )
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_non_negative_int("real_http_call_count", self.real_http_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)


def build_official_settlement_rejection_safe_category_reporting_handoff_no_post(
    input_snapshot: (
        OfficialSettlementRejectionSafeCategoryReportingHandoffInput | None
    ) = None,
    integration_result: (
        OfficialSettlementRejectionSafeCategoryIntegrationResult | None
    ) = None,
) -> OfficialSettlementRejectionSafeCategoryReportingHandoffResult:
    snapshot = (
        input_snapshot
        or OfficialSettlementRejectionSafeCategoryReportingHandoffInput()
    )
    integration = integration_result or (
        build_official_settlement_rejection_safe_category_capture_integration_no_post(
            snapshot.integration_input,
        )
    )
    blocked_reasons = _blocked_reasons(snapshot, integration)
    if "execution_or_transport_attempt_blocked" in blocked_reasons:
        status = (
            OfficialSettlementRejectionSafeCategoryReportingHandoffStatus
            .BLOCKED_EXECUTION_ATTEMPT
        )
    elif blocked_reasons:
        status = (
            OfficialSettlementRejectionSafeCategoryReportingHandoffStatus
            .BLOCKED_UNSAFE_INPUT
        )
    else:
        status = OfficialSettlementRejectionSafeCategoryReportingHandoffStatus.READY_NO_POST
    ready = (
        status
        is OfficialSettlementRejectionSafeCategoryReportingHandoffStatus.READY_NO_POST
    )

    return OfficialSettlementRejectionSafeCategoryReportingHandoffResult(
        step_name=STEP_NAME,
        status=status,
        reporting_handoff_label=REPORTING_HANDOFF_LABEL,
        safe_rejection_reporting_handoff_ready=ready,
        final_report_includes_safe_rejection_fields=ready,
        chatgpt_handoff_includes_safe_rejection_fields=ready,
        docs_status_handoff_includes_safe_rejection_fields=ready,
        safe_rejection_category=integration.safe_rejection_category,
        safe_rejection_kind=integration.safe_rejection_kind,
        safe_rejection_source=integration.safe_rejection_source,
        safe_rejection_confidence=integration.safe_rejection_confidence,
        safe_rejection_reason_available=integration.safe_rejection_reason_available,
        safe_rejection_reason_unavailable=(
            integration.safe_rejection_reason_unavailable
        ),
        safe_rejection_requires_raw_response=(
            integration.safe_rejection_requires_raw_response
        ),
        safe_rejection_requires_operator_ui_safe_label=(
            integration.safe_rejection_requires_operator_ui_safe_label
        ),
        default_rejected_result_maps_to=integration.default_rejected_result_maps_to,
        raw_response_inspected=False,
        broker_response_exposed=False,
        error_message_rendered=False,
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
        actual_settlement_post_this_step=False,
        entry_post_this_step=False,
        retry_this_step=False,
        repost_this_step=False,
        second_settlement_post_this_step=False,
        generic_close_this_step=False,
        ledger_update=False,
        receipt_handoff=False,
        settlement_post_count=0,
        transport_call_count=0,
        real_http_call_count=0,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_executed=False,
        integration_result=integration,
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            NEXT_STEP_AFTER_REPORTING_HANDOFF
            if ready
            else NEXT_STEP_FIX_REPORTING_HANDOFF
        ),
    )


def render_official_settlement_rejection_safe_category_final_report_markdown(
    result: OfficialSettlementRejectionSafeCategoryReportingHandoffResult,
) -> str:
    """Render a safe final-report fragment for rejected official settlements."""
    lines = [
        "# Official Settlement Rejection Safe Category Reporting Handoff",
        "",
        "## Reporting / Handoff Result",
        f"- safe_rejection_reporting_handoff_ready: "
        f"{_bool_text(result.safe_rejection_reporting_handoff_ready)}",
        f"- final_report_includes_safe_rejection_fields: "
        f"{_bool_text(result.final_report_includes_safe_rejection_fields)}",
        f"- chatgpt_handoff_includes_safe_rejection_fields: "
        f"{_bool_text(result.chatgpt_handoff_includes_safe_rejection_fields)}",
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
        f"- broker_response_exposed: {_bool_text(result.broker_response_exposed)}",
        f"- error_message_rendered: {_bool_text(result.error_message_rendered)}",
        f"- raw_id_value_exposure: {_bool_text(result.raw_id_value_exposure)}",
        f"- env_read: {_bool_text(result.env_read)}",
        "",
        "## Execution Boundary",
        f"- actual_settlement_POST_this_step: "
        f"{_bool_text(result.actual_settlement_post_this_step)}",
        f"- entry_POST_this_step: {_bool_text(result.entry_post_this_step)}",
        f"- retry_this_step: {_bool_text(result.retry_this_step)}",
        f"- repost_this_step: {_bool_text(result.repost_this_step)}",
        f"- second_settlement_POST_this_step: "
        f"{_bool_text(result.second_settlement_post_this_step)}",
        f"- generic_close_this_step: {_bool_text(result.generic_close_this_step)}",
        f"- settlement_post_count: {result.settlement_post_count}",
        f"- transport_call_count: {result.transport_call_count}",
        f"- real_http_call_count: {result.real_http_call_count}",
        "",
        "## ChatGPT Handoff Summary",
        *render_official_settlement_rejection_safe_category_chatgpt_handoff_summary(
            result,
        ).splitlines(),
    ]
    return "\n".join(lines)


def render_official_settlement_rejection_safe_category_chatgpt_handoff_summary(
    result: OfficialSettlementRejectionSafeCategoryReportingHandoffResult,
) -> str:
    lines = [
        f"- Step名: {STEP_NAME}",
        f"- CASE: {'CASE 1' if result.safe_rejection_reporting_handoff_ready else 'CASE 3'}",
        f"- safe_rejection_reporting_handoff_ready: "
        f"{_bool_text(result.safe_rejection_reporting_handoff_ready)}",
        f"- final_report_includes_safe_rejection_fields: "
        f"{_bool_text(result.final_report_includes_safe_rejection_fields)}",
        f"- chatgpt_handoff_includes_safe_rejection_fields: "
        f"{_bool_text(result.chatgpt_handoff_includes_safe_rejection_fields)}",
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
        f"- actual POST this Step: "
        f"{_bool_text(result.actual_settlement_post_this_step)}",
        f"- raw_response_inspected: {_bool_text(result.raw_response_inspected)}",
        f"- raw/ID/value exposure: {_bool_text(result.raw_id_value_exposure)}",
        f"- 推奨次Step: {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _blocked_reasons(
    snapshot: OfficialSettlementRejectionSafeCategoryReportingHandoffInput,
    integration: OfficialSettlementRejectionSafeCategoryIntegrationResult,
) -> tuple[str, ...]:
    reasons = list(integration.blocked_reasons)
    if integration.status is (
        OfficialSettlementRejectionSafeCategoryIntegrationStatus
        .BLOCKED_EXECUTION_ATTEMPT
    ):
        reasons.append("execution_or_transport_attempt_blocked")
    if integration.status is (
        OfficialSettlementRejectionSafeCategoryIntegrationStatus
        .BLOCKED_UNSAFE_INPUT
    ):
        reasons.append("unsafe_integration_result_blocked")
    if not snapshot.final_report_requested:
        reasons.append("final_report_not_requested")
    if not snapshot.chatgpt_handoff_requested:
        reasons.append("chatgpt_handoff_not_requested")
    if not snapshot.docs_handoff_requested:
        reasons.append("docs_handoff_not_requested")
    if _execution_or_exposure_attempted(snapshot):
        reasons.append("execution_or_exposure_attempt_blocked")
        reasons.append("execution_or_transport_attempt_blocked")
    return tuple(dict.fromkeys(reasons))


def _execution_or_exposure_attempted(
    snapshot: OfficialSettlementRejectionSafeCategoryReportingHandoffInput,
) -> bool:
    return any(
        (
            snapshot.actual_settlement_post_this_step,
            snapshot.entry_post_this_step,
            snapshot.retry_this_step,
            snapshot.repost_this_step,
            snapshot.second_settlement_post_this_step,
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


def _validate_bool_fields(obj: object, bool_fields: frozenset[str]) -> None:
    for item in fields(obj):
        if item.name in bool_fields and type(getattr(obj, item.name)) is not bool:
            raise LiveVerificationValidationError(f"{item.name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_INPUT_BOOL_FIELDS = frozenset(
    {
        "final_report_requested",
        "chatgpt_handoff_requested",
        "docs_handoff_requested",
        "actual_settlement_post_this_step",
        "entry_post_this_step",
        "retry_this_step",
        "repost_this_step",
        "second_settlement_post_this_step",
        "generic_close_this_step",
        "ledger_update",
        "receipt_handoff",
        "raw_id_value_exposure",
        "env_read",
    },
)

_RESULT_BOOL_FIELDS = frozenset(
    {
        "safe_rejection_reporting_handoff_ready",
        "final_report_includes_safe_rejection_fields",
        "chatgpt_handoff_includes_safe_rejection_fields",
        "docs_status_handoff_includes_safe_rejection_fields",
        "safe_rejection_reason_available",
        "safe_rejection_reason_unavailable",
        "safe_rejection_requires_raw_response",
        "safe_rejection_requires_operator_ui_safe_label",
        "raw_response_inspected",
        "broker_response_exposed",
        "error_message_rendered",
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
        "actual_settlement_post_this_step",
        "entry_post_this_step",
        "retry_this_step",
        "repost_this_step",
        "second_settlement_post_this_step",
        "generic_close_this_step",
        "ledger_update",
        "receipt_handoff",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_executed",
    },
)
