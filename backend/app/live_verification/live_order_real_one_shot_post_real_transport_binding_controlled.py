"""Step 6G controlled real transport binding contract.

This module prepares a binding that can be injected into the controlled
one-shot POST execution route in a later, separate step. Importing, building a
summary, or constructing the binding does not execute POST. The callable only
wraps a caller-supplied primitive and returns sanitized transport outcomes.
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

SAFE_REAL_TRANSPORT_BINDING_LABEL = (
    "CONTROLLED_ONE_SHOT_POST_REAL_TRANSPORT_BINDING"
)
REAL_TRANSPORT_BINDING_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_retry_2_requires_preview_and_post_confirmation"
)
REAL_TRANSPORT_BINDING_BLOCKED_NEXT_STEP = (
    "fix_one_shot_post_real_transport_binding_blockers_no_post"
)

TransportResultCategory = LiveOrderRealOneShotPostTransportResultCategory
ApprovedRealTransportPrimitive = Callable[
    [LiveOrderRealOneShotPostTransportInput],
    LiveOrderRealOneShotPostTransportResult,
]


class LiveOrderRealOneShotPostRealTransportBindingControlledStatus(str, Enum):
    REAL_TRANSPORT_BINDING_READY_NO_POST = (
        "REAL_TRANSPORT_BINDING_READY_NO_POST"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_MISSING_APPROVED_PRIMITIVE = (
        "REAL_TRANSPORT_BINDING_BLOCKED_MISSING_APPROVED_PRIMITIVE"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_DIRECT_LIVE_ORDER_ONCE = (
        "REAL_TRANSPORT_BINDING_BLOCKED_DIRECT_LIVE_ORDER_ONCE"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_ORDER_ENDPOINT_DIRECT = (
        "REAL_TRANSPORT_BINDING_BLOCKED_ORDER_ENDPOINT_DIRECT"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_RETRY_ENABLED = (
        "REAL_TRANSPORT_BINDING_BLOCKED_RETRY_ENABLED"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED = (
        "REAL_TRANSPORT_BINDING_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_LEDGER_COUPLED = (
        "REAL_TRANSPORT_BINDING_BLOCKED_LEDGER_COUPLED"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_RECEIPT_COUPLED = (
        "REAL_TRANSPORT_BINDING_BLOCKED_RECEIPT_COUPLED"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_RAW_EXPOSURE = (
        "REAL_TRANSPORT_BINDING_BLOCKED_RAW_EXPOSURE"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_ID_EXPOSURE = (
        "REAL_TRANSPORT_BINDING_BLOCKED_ID_EXPOSURE"
    )
    REAL_TRANSPORT_BINDING_BLOCKED_VALUE_EXPOSURE = (
        "REAL_TRANSPORT_BINDING_BLOCKED_VALUE_EXPOSURE"
    )


RealTransportBindingStatus = (
    LiveOrderRealOneShotPostRealTransportBindingControlledStatus
)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealTransportBindingControlledInput:
    real_transport_binding_label: str = SAFE_REAL_TRANSPORT_BINDING_LABEL
    approved_primitive_supplied: bool = False
    binding_default_no_execution: bool = True
    binding_import_executes_post: bool = False
    binding_construct_executes_post: bool = False
    binding_summary_executes_post: bool = False
    controlled_executor_required: bool = True
    post_specific_confirmation_required: bool = True
    credential_presence_required: bool = True
    credential_presence_checked: bool = False
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    primitive_retry_enabled: bool = False
    primitive_timeout_fail_closed: bool = True
    primitive_ledger_coupled: bool = False
    primitive_receipt_coupled: bool = False
    primitive_raw_exposure: bool = False
    primitive_id_exposure: bool = False
    primitive_value_exposure: bool = False
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
            "real_transport_binding_label",
            self.real_transport_binding_label,
        )
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _BINDING_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealTransportBindingControlledResult:
    status: LiveOrderRealOneShotPostRealTransportBindingControlledStatus
    real_transport_binding_available: bool
    real_transport_binding_label: str
    real_transport_binding_status: str
    binding_default_no_execution: bool
    binding_import_executes_post: bool
    binding_construct_executes_post: bool
    binding_summary_executes_post: bool
    controlled_executor_required: bool
    post_specific_confirmation_required: bool
    credential_presence_required: bool
    credential_presence_checked: bool
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    approved_primitive_supplied: bool
    primitive_retry_enabled: bool
    primitive_timeout_fail_closed: bool
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
            LiveOrderRealOneShotPostRealTransportBindingControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be real transport binding status",
            )
        _require_non_empty(
            "real_transport_binding_label",
            self.real_transport_binding_label,
        )
        _require_non_empty(
            "real_transport_binding_status",
            self.real_transport_binding_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _BINDING_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_binding_result_safety(self)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealTransportBinding:
    summary: LiveOrderRealOneShotPostRealTransportBindingControlledResult
    controlled_transport: ControlledTransport


def build_live_order_real_one_shot_post_real_transport_binding_controlled(
    input_snapshot: (
        LiveOrderRealOneShotPostRealTransportBindingControlledInput | None
    ) = None,
) -> LiveOrderRealOneShotPostRealTransportBindingControlledResult:
    """Build a safe real transport binding summary without executing POST."""
    snapshot = input_snapshot or (
        LiveOrderRealOneShotPostRealTransportBindingControlledInput()
    )
    status, reasons = _binding_status(snapshot)
    available = status is RealTransportBindingStatus.REAL_TRANSPORT_BINDING_READY_NO_POST
    return LiveOrderRealOneShotPostRealTransportBindingControlledResult(
        status=status,
        real_transport_binding_available=available,
        real_transport_binding_label=_safe_label(
            snapshot.real_transport_binding_label,
            SAFE_REAL_TRANSPORT_BINDING_LABEL,
        ),
        real_transport_binding_status=status.value,
        binding_default_no_execution=snapshot.binding_default_no_execution,
        binding_import_executes_post=snapshot.binding_import_executes_post,
        binding_construct_executes_post=snapshot.binding_construct_executes_post,
        binding_summary_executes_post=snapshot.binding_summary_executes_post,
        controlled_executor_required=snapshot.controlled_executor_required,
        post_specific_confirmation_required=(
            snapshot.post_specific_confirmation_required
        ),
        credential_presence_required=snapshot.credential_presence_required,
        credential_presence_checked=False,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        approved_primitive_supplied=snapshot.approved_primitive_supplied,
        primitive_retry_enabled=snapshot.primitive_retry_enabled,
        primitive_timeout_fail_closed=snapshot.primitive_timeout_fail_closed,
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
            REAL_TRANSPORT_BINDING_RECOMMENDED_NEXT_STEP
            if available
            else REAL_TRANSPORT_BINDING_BLOCKED_NEXT_STEP
        ),
    )


def construct_live_order_real_one_shot_post_real_transport_binding_controlled(
    *,
    primitive: ApprovedRealTransportPrimitive | None,
    input_snapshot: (
        LiveOrderRealOneShotPostRealTransportBindingControlledInput | None
    ) = None,
) -> LiveOrderRealOneShotPostRealTransportBinding:
    """Construct a binding without calling the supplied primitive."""
    snapshot = input_snapshot or (
        LiveOrderRealOneShotPostRealTransportBindingControlledInput(
            approved_primitive_supplied=primitive is not None,
        )
    )
    summary = build_live_order_real_one_shot_post_real_transport_binding_controlled(
        snapshot,
    )
    if primitive is None or not summary.real_transport_binding_available:
        controlled_transport = _blocked_transport(summary)
    else:
        controlled_transport = _sanitize_primitive_transport(primitive)
    return LiveOrderRealOneShotPostRealTransportBinding(
        summary=summary,
        controlled_transport=controlled_transport,
    )


def render_live_order_real_one_shot_post_real_transport_binding_markdown(
    result: LiveOrderRealOneShotPostRealTransportBindingControlledResult,
) -> str:
    """Render the safe real transport binding summary."""
    lines = [
        "# Step 6G One-Shot POST Real Transport Binding Controlled",
        "",
        "This is a binding summary. It is not POST execution.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw request, raw response, broker/API response, IDs,",
        "credential values, signature values, headers values, confirmation values,",
        "or ledger state values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- real_transport_binding_available: "
            f"{_bool_text(result.real_transport_binding_available)}"
        ),
        f"- real_transport_binding_label: {result.real_transport_binding_label}",
        f"- real_transport_binding_status: {result.real_transport_binding_status}",
        f"- approved_primitive_supplied: {_bool_text(result.approved_primitive_supplied)}",
        f"- controlled_executor_required: {_bool_text(result.controlled_executor_required)}",
        (
            "- post_specific_confirmation_required: "
            f"{_bool_text(result.post_specific_confirmation_required)}"
        ),
        "",
        "## No-Execution Guard",
        (
            "- binding_default_no_execution: "
            f"{_bool_text(result.binding_default_no_execution)}"
        ),
        (
            "- binding_import_executes_post: "
            f"{_bool_text(result.binding_import_executes_post)}"
        ),
        (
            "- binding_construct_executes_post: "
            f"{_bool_text(result.binding_construct_executes_post)}"
        ),
        (
            "- binding_summary_executes_post: "
            f"{_bool_text(result.binding_summary_executes_post)}"
        ),
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        "",
        "## Compatibility",
        f"- one_post_max: {_bool_text(result.one_post_max)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- timeout_fail_closed: {_bool_text(result.timeout_fail_closed)}",
        f"- primitive_retry_enabled: {_bool_text(result.primitive_retry_enabled)}",
        (
            "- primitive_timeout_fail_closed: "
            f"{_bool_text(result.primitive_timeout_fail_closed)}"
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


def _binding_status(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[LiveOrderRealOneShotPostRealTransportBindingControlledStatus, tuple[str, ...]]:
    missing_reasons = _missing_primitive_reasons(snapshot)
    if missing_reasons:
        return (
            RealTransportBindingStatus
            .REAL_TRANSPORT_BINDING_BLOCKED_MISSING_APPROVED_PRIMITIVE,
            missing_reasons,
        )
    direct_live_reasons = _direct_live_order_once_reasons(snapshot)
    if direct_live_reasons:
        return (
            RealTransportBindingStatus
            .REAL_TRANSPORT_BINDING_BLOCKED_DIRECT_LIVE_ORDER_ONCE,
            direct_live_reasons,
        )
    order_endpoint_reasons = _direct_order_endpoint_reasons(snapshot)
    if order_endpoint_reasons:
        return (
            RealTransportBindingStatus
            .REAL_TRANSPORT_BINDING_BLOCKED_ORDER_ENDPOINT_DIRECT,
            order_endpoint_reasons,
        )
    retry_reasons = _retry_reasons(snapshot)
    if retry_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_RETRY_ENABLED,
            retry_reasons,
        )
    timeout_reasons = _timeout_reasons(snapshot)
    if timeout_reasons:
        return (
            RealTransportBindingStatus
            .REAL_TRANSPORT_BINDING_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED,
            timeout_reasons,
        )
    ledger_reasons = _ledger_reasons(snapshot)
    if ledger_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_LEDGER_COUPLED,
            ledger_reasons,
        )
    receipt_reasons = _receipt_reasons(snapshot)
    if receipt_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_RECEIPT_COUPLED,
            receipt_reasons,
        )
    raw_reasons = _raw_exposure_reasons(snapshot)
    if raw_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_RAW_EXPOSURE,
            raw_reasons,
        )
    id_reasons = _id_exposure_reasons(snapshot)
    if id_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_ID_EXPOSURE,
            id_reasons,
        )
    value_reasons = _value_exposure_reasons(snapshot)
    if value_reasons:
        return (
            RealTransportBindingStatus.REAL_TRANSPORT_BINDING_BLOCKED_VALUE_EXPOSURE,
            value_reasons,
        )
    return RealTransportBindingStatus.REAL_TRANSPORT_BINDING_READY_NO_POST, ()


def _missing_primitive_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.approved_primitive_supplied:
        reasons.append("approved_primitive_missing")
    for field_name in (
        "binding_default_no_execution",
        "controlled_executor_required",
        "post_specific_confirmation_required",
        "one_post_max",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_missing")
    if snapshot.binding_import_executes_post:
        reasons.append("binding_import_executes_post")
    if snapshot.binding_construct_executes_post:
        reasons.append("binding_construct_executes_post")
    if snapshot.binding_summary_executes_post:
        reasons.append("binding_summary_executes_post")
    return tuple(reasons)


def _direct_live_order_once_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.direct_live_order_once:
        reasons.append("direct_live_order_once")
    if snapshot.live_order_once_executed:
        reasons.append("live_order_once_executed")
    return tuple(reasons)


def _direct_order_endpoint_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
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
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.one_post_max:
        reasons.append("one_post_max_missing")
    for field_name in (
        "retry_allowed",
        "primitive_retry_enabled",
        "second_post_attempted",
        "retry_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _timeout_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.timeout_fail_closed:
        reasons.append("timeout_fail_closed_missing")
    if not snapshot.primitive_timeout_fail_closed:
        reasons.append("primitive_timeout_fail_closed_missing")
    return tuple(reasons)


def _ledger_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "primitive_ledger_coupled",
        "ledger_update_this_step",
        "ledger_updated",
        "attempt_counter_persisted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _receipt_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "primitive_receipt_coupled",
        "receipt_handoff_this_step",
        "actual_receipt_handoff_executed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _raw_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "primitive_raw_exposure",
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _id_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "primitive_id_exposure",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _value_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostRealTransportBindingControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "primitive_value_exposure",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _blocked_transport(
    summary: LiveOrderRealOneShotPostRealTransportBindingControlledResult,
) -> ControlledTransport:
    def controlled_transport(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        _ = input_snapshot
        _ = summary
        return _safe_transport_result(
            TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
            failed=True,
        )

    return controlled_transport


def _sanitize_primitive_transport(
    primitive: ApprovedRealTransportPrimitive,
) -> ControlledTransport:
    def controlled_transport(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        try:
            primitive_outcome = primitive(input_snapshot)
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
        if not isinstance(primitive_outcome, LiveOrderRealOneShotPostTransportResult):
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            )
        unsafe_reasons = _primitive_outcome_unsafe_reasons(primitive_outcome)
        if unsafe_reasons:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
                failed=True,
            )
        return _safe_transport_result(
            primitive_outcome.result_category,
            fake_transport_used=primitive_outcome.fake_transport_used,
            http_post_executed=primitive_outcome.http_post_executed,
            timeout=primitive_outcome.timeout,
            unknown=primitive_outcome.unknown,
            unavailable=primitive_outcome.unavailable,
            failed=primitive_outcome.failed,
        )

    return controlled_transport


def _primitive_outcome_unsafe_reasons(
    primitive_outcome: LiveOrderRealOneShotPostTransportResult,
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
        if getattr(primitive_outcome, field_name):
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


def _validate_binding_result_safety(
    result: LiveOrderRealOneShotPostRealTransportBindingControlledResult,
) -> None:
    if result.real_transport_binding_available:
        unsafe_ready_fields = (
            "binding_import_executes_post",
            "binding_construct_executes_post",
            "binding_summary_executes_post",
            "retry_allowed",
            "primitive_retry_enabled",
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
            "binding_default_no_execution",
            "controlled_executor_required",
            "post_specific_confirmation_required",
            "one_post_max",
            "timeout_fail_closed",
            "primitive_timeout_fail_closed",
        ):
            if not getattr(result, field_name):
                raise LiveVerificationValidationError(f"{field_name} must be true")
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


_BINDING_INPUT_BOOL_FIELDS = (
    "approved_primitive_supplied",
    "binding_default_no_execution",
    "binding_import_executes_post",
    "binding_construct_executes_post",
    "binding_summary_executes_post",
    "controlled_executor_required",
    "post_specific_confirmation_required",
    "credential_presence_required",
    "credential_presence_checked",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "primitive_retry_enabled",
    "primitive_timeout_fail_closed",
    "primitive_ledger_coupled",
    "primitive_receipt_coupled",
    "primitive_raw_exposure",
    "primitive_id_exposure",
    "primitive_value_exposure",
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

_BINDING_RESULT_BOOL_FIELDS = (
    "real_transport_binding_available",
    "binding_default_no_execution",
    "binding_import_executes_post",
    "binding_construct_executes_post",
    "binding_summary_executes_post",
    "controlled_executor_required",
    "post_specific_confirmation_required",
    "credential_presence_required",
    "credential_presence_checked",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "approved_primitive_supplied",
    "primitive_retry_enabled",
    "primitive_timeout_fail_closed",
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

__all__ = [
    "ApprovedRealTransportPrimitive",
    "LiveOrderRealOneShotPostRealTransportBinding",
    "LiveOrderRealOneShotPostRealTransportBindingControlledInput",
    "LiveOrderRealOneShotPostRealTransportBindingControlledResult",
    "LiveOrderRealOneShotPostRealTransportBindingControlledStatus",
    "RealTransportBindingStatus",
    "SAFE_REAL_TRANSPORT_BINDING_LABEL",
    "build_live_order_real_one_shot_post_real_transport_binding_controlled",
    "construct_live_order_real_one_shot_post_real_transport_binding_controlled",
    "render_live_order_real_one_shot_post_real_transport_binding_markdown",
]
