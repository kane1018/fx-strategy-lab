"""Step 6G approved one-shot POST primitive actual source callable boundary.

This module defines the safe actual-source-callable supply contract for a
caller-supplied callable that can later feed the approved primitive source
boundary. Importing, summarizing, or constructing this boundary never executes
POST. The wrapped callable is only invoked by the controlled one-shot executor
in a later step.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    ControlledTransport,
    LiveOrderRealOneShotPostTransportInput,
    LiveOrderRealOneShotPostTransportResult,
    LiveOrderRealOneShotPostTransportResultCategory,
)

SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_LABEL = (
    "CONTROLLED_ONE_SHOT_POST_APPROVED_PRIMITIVE_ACTUAL_SOURCE_BOUNDARY"
)
SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_RESULT_LABEL = (
    "APPROVED_PRIMITIVE_ACTUAL_SOURCE_SAFE_OUTCOME_ONLY"
)
APPROVED_PRIMITIVE_ACTUAL_SOURCE_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_retry_6_requires_preview_and_new_post_confirmation"
)
APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_NEXT_STEP = (
    "fix_one_shot_post_approved_primitive_actual_source_blockers_no_post"
)
APPROVED_PRIMITIVE_ACTUAL_SOURCE_NOT_ATTEMPTED_CATEGORY = "NOT_ATTEMPTED_NO_POST"

TransportResultCategory = LiveOrderRealOneShotPostTransportResultCategory
ApprovedPrimitiveActualSourceCandidate = Callable[
    [LiveOrderRealOneShotPostTransportInput],
    LiveOrderRealOneShotPostTransportResult,
]


class LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus(
    str,
    Enum,
):
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_READY_NO_POST = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_READY_NO_POST"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_MISSING_SOURCE = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_MISSING_SOURCE"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_DIRECT_LIVE_ORDER_ONCE = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_DIRECT_LIVE_ORDER_ONCE"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ORDER_ENDPOINT_DIRECT = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ORDER_ENDPOINT_DIRECT"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RETRY_ENABLED = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RETRY_ENABLED"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_LEDGER_COUPLED = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_LEDGER_COUPLED"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RECEIPT_COUPLED = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RECEIPT_COUPLED"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RAW_EXPOSURE = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RAW_EXPOSURE"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ID_EXPOSURE = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ID_EXPOSURE"
    )
    APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_VALUE_EXPOSURE = (
        "APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_VALUE_EXPOSURE"
    )


ApprovedPrimitiveActualSourceStatus = (
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus
)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput:
    approved_primitive_actual_source_label: str = (
        SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_LABEL
    )
    approved_primitive_actual_source_supplied: bool = False
    approved_primitive_actual_source_default_no_execution: bool = True
    approved_primitive_actual_source_import_executes_post: bool = False
    approved_primitive_actual_source_construct_executes_post: bool = False
    approved_primitive_actual_source_summary_executes_post: bool = False
    approved_primitive_source_boundary_compatible: bool = True
    approved_primitive_boundary_compatible: bool = True
    controlled_binding_compatible: bool = True
    controlled_executor_required: bool = True
    post_specific_confirmation_required: bool = True
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    actual_source_retry_enabled: bool = False
    actual_source_timeout_fail_closed: bool = True
    actual_source_ledger_coupled: bool = False
    actual_source_receipt_coupled: bool = False
    actual_source_raw_exposure: bool = False
    actual_source_id_exposure: bool = False
    actual_source_value_exposure: bool = False
    direct_live_order_once: bool = False
    direct_order_endpoint: bool = False
    direct_private_api_write: bool = False
    direct_broker_write: bool = False
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    actual_http_post_executed: bool = False
    order_endpoint_executed: bool = False
    live_order_once_executed: bool = False
    post_execution_count: int = 0
    second_post_attempted: bool = False
    retry_attempted: bool = False
    ledger_updated: bool = False
    attempt_counter_persisted: bool = False
    actual_receipt_handoff_executed: bool = False
    raw_request_exposed: bool = False
    raw_response_exposed: bool = False
    broker_api_response_exposed: bool = False
    credential_value_exposed: bool = False
    signature_value_exposed: bool = False
    headers_value_exposed: bool = False
    real_id_exposed: bool = False
    account_id_exposed: bool = False
    order_id_exposed: bool = False
    transaction_id_exposed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(
            "approved_primitive_actual_source_label",
            self.approved_primitive_actual_source_label,
        )
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(
            self,
            _APPROVED_PRIMITIVE_ACTUAL_SOURCE_INPUT_BOOL_FIELDS,
        )


@dataclass(frozen=True)
class LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult:
    status: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus
    approved_primitive_actual_source_available: bool
    approved_primitive_actual_source_status: str
    approved_primitive_actual_source_label: str
    approved_primitive_actual_source_default_no_execution: bool
    approved_primitive_actual_source_import_executes_post: bool
    approved_primitive_actual_source_construct_executes_post: bool
    approved_primitive_actual_source_summary_executes_post: bool
    approved_primitive_source_boundary_compatible: bool
    approved_primitive_boundary_compatible: bool
    controlled_binding_compatible: bool
    controlled_executor_required: bool
    post_specific_confirmation_required: bool
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    approved_primitive_actual_source_supplied: bool
    actual_source_retry_enabled: bool
    actual_source_timeout_fail_closed: bool
    actual_source_attempted: bool
    actual_source_call_count: int
    actual_source_safe_status: str
    actual_source_safe_label: str
    actual_source_result_category: str
    timeout: bool
    unknown: bool
    unavailable: bool
    failed: bool
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    actual_http_post_executed: bool
    order_endpoint_executed: bool
    live_order_once_executed: bool
    post_execution_count: int
    second_post_attempted: bool
    retry_attempted: bool
    ledger_updated: bool
    attempt_counter_persisted: bool
    actual_receipt_handoff_executed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    real_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be approved primitive actual source status",
            )
        for field_name in (
            "approved_primitive_actual_source_status",
            "approved_primitive_actual_source_label",
            "actual_source_safe_status",
            "actual_source_safe_label",
            "actual_source_result_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int(
            "actual_source_call_count",
            self.actual_source_call_count,
        )
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(
            self,
            _APPROVED_PRIMITIVE_ACTUAL_SOURCE_RESULT_BOOL_FIELDS,
        )
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_approved_primitive_actual_source_result_safety(self)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostApprovedPrimitiveActualSource:
    summary: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult
    approved_primitive_actual_source: ControlledTransport


def build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
    input_snapshot: (
        LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput | None
    ) = None,
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult:
    """Build an approved primitive actual source summary without executing POST."""
    snapshot = input_snapshot or (
        LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput()
    )
    status, reasons = _approved_primitive_actual_source_status(snapshot)
    available = (
        status
        is ApprovedPrimitiveActualSourceStatus
        .APPROVED_PRIMITIVE_ACTUAL_SOURCE_READY_NO_POST
    )
    return LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult(
        status=status,
        approved_primitive_actual_source_available=available,
        approved_primitive_actual_source_status=status.value,
        approved_primitive_actual_source_label=_safe_label(
            snapshot.approved_primitive_actual_source_label,
            SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_LABEL,
        ),
        approved_primitive_actual_source_default_no_execution=(
            snapshot.approved_primitive_actual_source_default_no_execution
        ),
        approved_primitive_actual_source_import_executes_post=(
            snapshot.approved_primitive_actual_source_import_executes_post
        ),
        approved_primitive_actual_source_construct_executes_post=(
            snapshot.approved_primitive_actual_source_construct_executes_post
        ),
        approved_primitive_actual_source_summary_executes_post=(
            snapshot.approved_primitive_actual_source_summary_executes_post
        ),
        approved_primitive_source_boundary_compatible=(
            snapshot.approved_primitive_source_boundary_compatible
        ),
        approved_primitive_boundary_compatible=(
            snapshot.approved_primitive_boundary_compatible
        ),
        controlled_binding_compatible=snapshot.controlled_binding_compatible,
        controlled_executor_required=snapshot.controlled_executor_required,
        post_specific_confirmation_required=(
            snapshot.post_specific_confirmation_required
        ),
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        approved_primitive_actual_source_supplied=(
            snapshot.approved_primitive_actual_source_supplied
        ),
        actual_source_retry_enabled=snapshot.actual_source_retry_enabled,
        actual_source_timeout_fail_closed=snapshot.actual_source_timeout_fail_closed,
        actual_source_attempted=False,
        actual_source_call_count=0,
        actual_source_safe_status=status.value,
        actual_source_safe_label=SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_RESULT_LABEL,
        actual_source_result_category=(
            APPROVED_PRIMITIVE_ACTUAL_SOURCE_NOT_ATTEMPTED_CATEGORY
        ),
        timeout=False,
        unknown=False,
        unavailable=False,
        failed=False,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        actual_http_post_executed=False,
        order_endpoint_executed=False,
        live_order_once_executed=False,
        post_execution_count=0,
        second_post_attempted=False,
        retry_attempted=False,
        ledger_updated=False,
        attempt_counter_persisted=False,
        actual_receipt_handoff_executed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        real_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        blocked_reasons=reasons,
        recommended_next_step=(
            APPROVED_PRIMITIVE_ACTUAL_SOURCE_RECOMMENDED_NEXT_STEP
            if available
            else APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_NEXT_STEP
        ),
    )


def construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
    *,
    actual_source: ApprovedPrimitiveActualSourceCandidate | None,
    input_snapshot: (
        LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput | None
    ) = None,
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSource:
    """Construct an actual source adapter without calling the supplied source."""
    snapshot = input_snapshot or (
        LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput(
            approved_primitive_actual_source_supplied=actual_source is not None,
        )
    )
    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            snapshot,
        )
    )
    if actual_source is None or not summary.approved_primitive_actual_source_available:
        controlled_actual_source = _blocked_actual_source(summary)
    else:
        controlled_actual_source = _sanitize_actual_source_candidate(actual_source)
    return LiveOrderRealOneShotPostApprovedPrimitiveActualSource(
        summary=summary,
        approved_primitive_actual_source=controlled_actual_source,
    )


def build_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult:
    """Build the current/default approved actual source summary without POST."""
    return (
        construct_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()
        .summary
    )


def construct_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSource:
    """Connect the delegate-backed current/default source without POST."""
    from app.live_verification.live_order_real_one_shot_post_real_delegate_controlled import (  # noqa: E501
        construct_live_order_real_one_shot_post_real_delegate_approved_actual_source_controlled,
    )

    return construct_live_order_real_one_shot_post_real_delegate_approved_actual_source_controlled()


def render_live_order_real_one_shot_post_approved_primitive_actual_source_markdown(
    result: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult,
) -> str:
    """Render the approved primitive actual source safe summary."""
    lines = [
        "# Step 6G One-Shot POST Approved Primitive Actual Source Controlled",
        "",
        "This is an approved primitive actual source boundary summary.",
        "It is not POST execution and does not request POST confirmation.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw request, raw response, broker/API response, IDs,",
        "credential values, signature values, headers values, confirmation values,",
        "or ledger state values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- approved_primitive_actual_source_available: "
            f"{_bool_text(result.approved_primitive_actual_source_available)}"
        ),
        (
            "- approved_primitive_actual_source_status: "
            f"{result.approved_primitive_actual_source_status}"
        ),
        (
            "- approved_primitive_actual_source_label: "
            f"{result.approved_primitive_actual_source_label}"
        ),
        (
            "- approved_primitive_actual_source_supplied: "
            f"{_bool_text(result.approved_primitive_actual_source_supplied)}"
        ),
        (
            "- approved_primitive_source_boundary_compatible: "
            f"{_bool_text(result.approved_primitive_source_boundary_compatible)}"
        ),
        (
            "- approved_primitive_boundary_compatible: "
            f"{_bool_text(result.approved_primitive_boundary_compatible)}"
        ),
        (
            "- controlled_binding_compatible: "
            f"{_bool_text(result.controlled_binding_compatible)}"
        ),
        f"- controlled_executor_required: {_bool_text(result.controlled_executor_required)}",
        (
            "- post_specific_confirmation_required: "
            f"{_bool_text(result.post_specific_confirmation_required)}"
        ),
        "",
        "## No-Execution Guard",
        (
            "- approved_primitive_actual_source_default_no_execution: "
            f"{_bool_text(result.approved_primitive_actual_source_default_no_execution)}"
        ),
        (
            "- approved_primitive_actual_source_import_executes_post: "
            f"{_bool_text(result.approved_primitive_actual_source_import_executes_post)}"
        ),
        (
            "- approved_primitive_actual_source_construct_executes_post: "
            f"{_bool_text(result.approved_primitive_actual_source_construct_executes_post)}"
        ),
        (
            "- approved_primitive_actual_source_summary_executes_post: "
            f"{_bool_text(result.approved_primitive_actual_source_summary_executes_post)}"
        ),
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        "",
        "## Actual Source Adapter",
        f"- actual_source_attempted: {_bool_text(result.actual_source_attempted)}",
        f"- actual_source_call_count: {result.actual_source_call_count}",
        f"- actual_source_safe_status: {result.actual_source_safe_status}",
        f"- actual_source_safe_label: {result.actual_source_safe_label}",
        f"- actual_source_result_category: {result.actual_source_result_category}",
        "",
        "## Compatibility",
        f"- one_post_max: {_bool_text(result.one_post_max)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- timeout_fail_closed: {_bool_text(result.timeout_fail_closed)}",
        (
            "- actual_source_retry_enabled: "
            f"{_bool_text(result.actual_source_retry_enabled)}"
        ),
        (
            "- actual_source_timeout_fail_closed: "
            f"{_bool_text(result.actual_source_timeout_fail_closed)}"
        ),
        f"- ledger_update_this_step: {_bool_text(result.ledger_update_this_step)}",
        f"- receipt_handoff_this_step: {_bool_text(result.receipt_handoff_this_step)}",
        "",
        "## Safety",
        f"- order_endpoint_executed: {_bool_text(result.order_endpoint_executed)}",
        f"- live_order_once_executed: {_bool_text(result.live_order_once_executed)}",
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
        f"- attempt_counter_persisted: {_bool_text(result.attempt_counter_persisted)}",
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- raw_request_exposed: {_bool_text(result.raw_request_exposed)}",
        f"- raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        (
            "- broker_api_response_exposed: "
            f"{_bool_text(result.broker_api_response_exposed)}"
        ),
        f"- credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        f"- signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        f"- headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"- real_id_exposed: {_bool_text(result.real_id_exposed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _approved_primitive_actual_source_status(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus,
    tuple[str, ...],
]:
    missing_reasons = _missing_actual_source_reasons(snapshot)
    if missing_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_MISSING_SOURCE,
            missing_reasons,
        )
    direct_live_reasons = _direct_live_order_once_reasons(snapshot)
    if direct_live_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_DIRECT_LIVE_ORDER_ONCE,
            direct_live_reasons,
        )
    order_endpoint_reasons = _direct_order_endpoint_reasons(snapshot)
    if order_endpoint_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ORDER_ENDPOINT_DIRECT,
            order_endpoint_reasons,
        )
    retry_reasons = _retry_reasons(snapshot)
    if retry_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RETRY_ENABLED,
            retry_reasons,
        )
    timeout_reasons = _timeout_reasons(snapshot)
    if timeout_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED,
            timeout_reasons,
        )
    ledger_reasons = _ledger_reasons(snapshot)
    if ledger_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_LEDGER_COUPLED,
            ledger_reasons,
        )
    receipt_reasons = _receipt_reasons(snapshot)
    if receipt_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RECEIPT_COUPLED,
            receipt_reasons,
        )
    raw_reasons = _raw_exposure_reasons(snapshot)
    if raw_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RAW_EXPOSURE,
            raw_reasons,
        )
    id_reasons = _id_exposure_reasons(snapshot)
    if id_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ID_EXPOSURE,
            id_reasons,
        )
    value_reasons = _value_exposure_reasons(snapshot)
    if value_reasons:
        return (
            ApprovedPrimitiveActualSourceStatus
            .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_VALUE_EXPOSURE,
            value_reasons,
        )
    return (
        ApprovedPrimitiveActualSourceStatus
        .APPROVED_PRIMITIVE_ACTUAL_SOURCE_READY_NO_POST,
        (),
    )


def _missing_actual_source_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.approved_primitive_actual_source_supplied:
        reasons.append("approved_primitive_actual_source_missing")
    for field_name in (
        "approved_primitive_actual_source_default_no_execution",
        "approved_primitive_source_boundary_compatible",
        "approved_primitive_boundary_compatible",
        "controlled_binding_compatible",
        "controlled_executor_required",
        "post_specific_confirmation_required",
        "one_post_max",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_missing")
    if snapshot.approved_primitive_actual_source_import_executes_post:
        reasons.append("approved_primitive_actual_source_import_executes_post")
    if snapshot.approved_primitive_actual_source_construct_executes_post:
        reasons.append("approved_primitive_actual_source_construct_executes_post")
    if snapshot.approved_primitive_actual_source_summary_executes_post:
        reasons.append("approved_primitive_actual_source_summary_executes_post")
    return tuple(reasons)


def _direct_live_order_once_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.direct_live_order_once:
        reasons.append("direct_live_order_once")
    if snapshot.live_order_once_executed:
        reasons.append("live_order_once_executed")
    return tuple(reasons)


def _direct_order_endpoint_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "direct_order_endpoint",
        "direct_private_api_write",
        "direct_broker_write",
        "actual_http_post_executed",
        "order_endpoint_executed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.post_execution_count > 0:
        reasons.append("post_execution_count_nonzero")
    return tuple(reasons)


def _retry_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.one_post_max:
        reasons.append("one_post_max_missing")
    for field_name in (
        "retry_allowed",
        "actual_source_retry_enabled",
        "second_post_attempted",
        "retry_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _timeout_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.timeout_fail_closed:
        reasons.append("timeout_fail_closed_missing")
    if not snapshot.actual_source_timeout_fail_closed:
        reasons.append("actual_source_timeout_fail_closed_missing")
    return tuple(reasons)


def _ledger_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_source_ledger_coupled",
        "ledger_update_this_step",
        "ledger_updated",
        "attempt_counter_persisted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _receipt_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_source_receipt_coupled",
        "receipt_handoff_this_step",
        "actual_receipt_handoff_executed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _raw_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_source_raw_exposure",
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _id_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_source_id_exposure",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _value_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_source_value_exposure",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _blocked_actual_source(
    summary: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult,
) -> ControlledTransport:
    def controlled_actual_source(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        _ = input_snapshot
        _ = summary
        return _safe_transport_result(
            TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
            failed=True,
        )

    return controlled_actual_source


def _sanitize_actual_source_candidate(
    actual_source: ApprovedPrimitiveActualSourceCandidate,
) -> ControlledTransport:
    def controlled_actual_source(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        try:
            actual_source_outcome = actual_source(input_snapshot)
        except TimeoutError:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
                timeout=True,
            )
        except Exception:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            )
        if not isinstance(
            actual_source_outcome,
            LiveOrderRealOneShotPostTransportResult,
        ):
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            )
        unsafe_reasons = _actual_source_outcome_unsafe_reasons(actual_source_outcome)
        if unsafe_reasons:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
                failed=True,
            )
        return _safe_transport_result(
            actual_source_outcome.result_category,
            fake_transport_used=actual_source_outcome.fake_transport_used,
            http_post_executed=actual_source_outcome.http_post_executed,
            timeout=actual_source_outcome.timeout,
            unknown=actual_source_outcome.unknown,
            unavailable=actual_source_outcome.unavailable,
            failed=actual_source_outcome.failed,
        )

    return controlled_actual_source


def _actual_source_outcome_unsafe_reasons(
    actual_source_outcome: LiveOrderRealOneShotPostTransportResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "second_post_attempted",
        "retry_attempted",
        "ledger_updated",
        "attempt_counter_persisted",
        "actual_receipt_handoff_executed",
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
    ):
        if getattr(actual_source_outcome, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _safe_transport_result(
    category: LiveOrderRealOneShotPostTransportResultCategory,
    *,
    fake_transport_used: bool = False,
    http_post_executed: bool = False,
    timeout: bool = False,
    unknown: bool = False,
    unavailable: bool = False,
    failed: bool = False,
) -> LiveOrderRealOneShotPostTransportResult:
    return LiveOrderRealOneShotPostTransportResult(
        result_category=category,
        fake_transport_used=fake_transport_used,
        http_post_executed=http_post_executed,
        second_post_attempted=False,
        retry_attempted=False,
        timeout=timeout,
        unknown=unknown,
        unavailable=unavailable,
        failed=failed,
        ledger_updated=False,
        attempt_counter_persisted=False,
        actual_receipt_handoff_executed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        real_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
    )


def _validate_approved_primitive_actual_source_result_safety(
    result: LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult,
) -> None:
    if result.approved_primitive_actual_source_available:
        unsafe_ready_fields = (
            "approved_primitive_actual_source_import_executes_post",
            "approved_primitive_actual_source_construct_executes_post",
            "approved_primitive_actual_source_summary_executes_post",
            "retry_allowed",
            "actual_source_retry_enabled",
            "actual_source_attempted",
            "timeout",
            "unknown",
            "unavailable",
            "failed",
            "ledger_update_this_step",
            "receipt_handoff_this_step",
            "actual_http_post_executed",
            "order_endpoint_executed",
            "live_order_once_executed",
            "second_post_attempted",
            "retry_attempted",
            "ledger_updated",
            "attempt_counter_persisted",
            "actual_receipt_handoff_executed",
            "raw_request_exposed",
            "raw_response_exposed",
            "broker_api_response_exposed",
            "credential_value_exposed",
            "signature_value_exposed",
            "headers_value_exposed",
            "real_id_exposed",
            "account_id_exposed",
            "order_id_exposed",
            "transaction_id_exposed",
        )
        for field_name in unsafe_ready_fields:
            if getattr(result, field_name):
                raise LiveVerificationValidationError(f"{field_name} must be false")
        for field_name in (
            "approved_primitive_actual_source_default_no_execution",
            "approved_primitive_source_boundary_compatible",
            "approved_primitive_boundary_compatible",
            "controlled_binding_compatible",
            "controlled_executor_required",
            "post_specific_confirmation_required",
            "one_post_max",
            "timeout_fail_closed",
            "actual_source_timeout_fail_closed",
        ):
            if not getattr(result, field_name):
                raise LiveVerificationValidationError(f"{field_name} must be true")
    if result.actual_source_call_count != 0:
        raise LiveVerificationValidationError(
            "actual_source_call_count must be zero",
        )
    if result.post_execution_count != 0:
        raise LiveVerificationValidationError("post_execution_count must be zero")


def _safe_label(value: str, fallback: str) -> str:
    if _unsafe_text(value):
        return fallback
    return value


def _unsafe_text(value: str) -> bool:
    blocked_fragments = (
        "://",
        "private",
        "account",
        "authorization",
        "credential",
        "secret",
        "token",
    )
    lowered = value.lower()
    return any(fragment in lowered for fragment in blocked_fragments)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_non_empty(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} must be non-empty")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LiveVerificationValidationError(
            f"{field_name} must be a non-negative integer",
        )


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if not isinstance(getattr(obj, field_name), bool):
            raise LiveVerificationValidationError(f"{field_name} must be bool")


_APPROVED_PRIMITIVE_ACTUAL_SOURCE_INPUT_BOOL_FIELDS = (
    "approved_primitive_actual_source_supplied",
    "approved_primitive_actual_source_default_no_execution",
    "approved_primitive_actual_source_import_executes_post",
    "approved_primitive_actual_source_construct_executes_post",
    "approved_primitive_actual_source_summary_executes_post",
    "approved_primitive_source_boundary_compatible",
    "approved_primitive_boundary_compatible",
    "controlled_binding_compatible",
    "controlled_executor_required",
    "post_specific_confirmation_required",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "actual_source_retry_enabled",
    "actual_source_timeout_fail_closed",
    "actual_source_ledger_coupled",
    "actual_source_receipt_coupled",
    "actual_source_raw_exposure",
    "actual_source_id_exposure",
    "actual_source_value_exposure",
    "direct_live_order_once",
    "direct_order_endpoint",
    "direct_private_api_write",
    "direct_broker_write",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "second_post_attempted",
    "retry_attempted",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "real_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
)


_APPROVED_PRIMITIVE_ACTUAL_SOURCE_RESULT_BOOL_FIELDS = (
    "approved_primitive_actual_source_available",
    "approved_primitive_actual_source_default_no_execution",
    "approved_primitive_actual_source_import_executes_post",
    "approved_primitive_actual_source_construct_executes_post",
    "approved_primitive_actual_source_summary_executes_post",
    "approved_primitive_source_boundary_compatible",
    "approved_primitive_boundary_compatible",
    "controlled_binding_compatible",
    "controlled_executor_required",
    "post_specific_confirmation_required",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "approved_primitive_actual_source_supplied",
    "actual_source_retry_enabled",
    "actual_source_timeout_fail_closed",
    "actual_source_attempted",
    "timeout",
    "unknown",
    "unavailable",
    "failed",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "second_post_attempted",
    "retry_attempted",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "real_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
)
