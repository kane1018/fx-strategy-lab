"""Step 6G real POST delegate connection contract.

This module wires a safe, non-executing delegate reference into the ledger-free
source factory. It does not execute HTTP POST, request POST confirmation, build
raw request material, expose sensitive values, or touch ledger/receipt flows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_one_shot_post_approved_primitive_actual_source_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostApprovedPrimitiveActualSource,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealOneShotPostTransportInput,
    LiveOrderRealOneShotPostTransportResult,
    LiveOrderRealOneShotPostTransportResultCategory,
)
from app.live_verification.live_order_real_one_shot_post_ledger_free_source_factory_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostLedgerFreeSourceFactory,
    LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult,
    construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled,
    map_live_order_real_one_shot_post_ledger_free_source_outcome,
)

SAFE_REAL_POST_DELEGATE_LABEL = "CONTROLLED_REAL_POST_DELEGATE_REFERENCE"
SAFE_REAL_POST_DELEGATE_SOURCE_LABEL = "CONTROLLED_REAL_POST_DELEGATE_SOURCE"
UNSUPPORTED_REAL_POST_DELEGATE_LABEL = "UNSUPPORTED_REDACTED"
REAL_POST_DELEGATE_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_retry_8_requires_new_post_specific_confirmation"
)
REAL_POST_DELEGATE_BLOCKED_NEXT_STEP = "fix_real_post_delegate_connection_no_post"


class LiveOrderRealOneShotPostRealDelegateControlledStatus(str, Enum):
    REAL_POST_DELEGATE_READY_NO_POST = "REAL_POST_DELEGATE_READY_NO_POST"
    REAL_POST_DELEGATE_BLOCKED_MISSING_FUNCTION_REFERENCE = (
        "REAL_POST_DELEGATE_BLOCKED_MISSING_FUNCTION_REFERENCE"
    )
    REAL_POST_DELEGATE_BLOCKED_MISSING_FACTORY = (
        "REAL_POST_DELEGATE_BLOCKED_MISSING_FACTORY"
    )
    REAL_POST_DELEGATE_BLOCKED_FACTORY_MISSING_DELEGATE = (
        "REAL_POST_DELEGATE_BLOCKED_FACTORY_MISSING_DELEGATE"
    )
    REAL_POST_DELEGATE_BLOCKED_POST_OR_ORDER_EXECUTION = (
        "REAL_POST_DELEGATE_BLOCKED_POST_OR_ORDER_EXECUTION"
    )
    REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY = (
        "REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY"
    )
    REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE = (
        "REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE"
    )
    REAL_POST_DELEGATE_BLOCKED_CONTRACT = "REAL_POST_DELEGATE_BLOCKED_CONTRACT"


RealDelegateStatus = LiveOrderRealOneShotPostRealDelegateControlledStatus
TransportCategory = LiveOrderRealOneShotPostTransportResultCategory
RealPostDelegate = Callable[
    [LiveOrderRealOneShotPostTransportInput],
    LiveOrderRealOneShotPostTransportResult,
]
PostFunctionReference = Callable[..., object]


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealDelegateControlledInput:
    real_post_delegate_label: str = SAFE_REAL_POST_DELEGATE_LABEL
    real_post_delegate_source_label: str = SAFE_REAL_POST_DELEGATE_SOURCE_LABEL
    real_post_delegate_ready: bool = True
    delegate_default_no_execution: bool = True
    delegate_import_executes_post: bool = False
    delegate_construct_executes_post: bool = False
    delegate_summary_executes_post: bool = False
    delegate_supply_executes_post: bool = False
    delegate_requires_sealed_request: bool = True
    delegate_requires_sealed_body: bool = True
    delegate_requires_sealed_credential_signing_provider: bool = True
    delegate_requires_safe_result_mapper: bool = True
    delegate_requires_post_specific_confirmation: bool = True
    post_live_order_with_httpx_reference_available: bool = True
    delegate_supplied_to_factory: bool = True
    factory_produces_controlled_source_callable: bool = True
    source_callable_unavailable_due_missing_delegate: bool = False
    actual_post_allowed: bool = False
    retry_allowed: bool = False
    ledger_update_allowed: bool = False
    receipt_handoff_allowed: bool = False
    actual_http_post_executed: bool = False
    order_endpoint_executed: bool = False
    live_order_once_executed: bool = False
    post_execution_count: int = 0
    second_post_attempted: bool = False
    retry_attempted: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persisted: bool = False
    receipt_handoff_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    id_exposure_attempted: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("real_post_delegate_label", self.real_post_delegate_label)
        _require_non_empty(
            "real_post_delegate_source_label",
            self.real_post_delegate_source_label,
        )
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _REAL_POST_DELEGATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealDelegateControlledResult:
    status: LiveOrderRealOneShotPostRealDelegateControlledStatus
    real_post_delegate_ready: bool
    real_post_delegate_label: str
    real_post_delegate_status: str
    real_post_delegate_source_label: str
    delegate_default_no_execution: bool
    delegate_import_executes_post: bool
    delegate_construct_executes_post: bool
    delegate_summary_executes_post: bool
    delegate_supply_executes_post: bool
    delegate_requires_sealed_request: bool
    delegate_requires_sealed_body: bool
    delegate_requires_sealed_credential_signing_provider: bool
    delegate_requires_safe_result_mapper: bool
    delegate_requires_post_specific_confirmation: bool
    post_live_order_with_httpx_reference_available: bool
    delegate_supplied_to_factory: bool
    factory_produces_controlled_source_callable: bool
    approved_primitive_actual_source_available: bool
    source_callable_unavailable_due_missing_delegate: bool
    actual_post_allowed: bool
    retry_allowed: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
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
            LiveOrderRealOneShotPostRealDelegateControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be real POST delegate status",
            )
        for field_name in (
            "real_post_delegate_label",
            "real_post_delegate_status",
            "real_post_delegate_source_label",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _REAL_POST_DELEGATE_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostRealDelegateConnection:
    summary: LiveOrderRealOneShotPostRealDelegateControlledResult
    source_delegate: RealPostDelegate
    factory: LiveOrderRealOneShotPostLedgerFreeSourceFactory
    approved_primitive_actual_source: LiveOrderRealOneShotPostApprovedPrimitiveActualSource


def build_live_order_real_one_shot_post_real_delegate_controlled(
    input_snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput | None = None,
    *,
    factory_summary: (
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult | None
    ) = None,
) -> LiveOrderRealOneShotPostRealDelegateControlledResult:
    """Build a safe readiness summary without executing the delegate."""
    snapshot = input_snapshot or LiveOrderRealOneShotPostRealDelegateControlledInput()
    status, reasons = _delegate_status(snapshot, factory_summary=factory_summary)
    ready = status is RealDelegateStatus.REAL_POST_DELEGATE_READY_NO_POST
    return LiveOrderRealOneShotPostRealDelegateControlledResult(
        status=status,
        real_post_delegate_ready=ready,
        real_post_delegate_label=_safe_label(
            snapshot.real_post_delegate_label,
            SAFE_REAL_POST_DELEGATE_LABEL,
        ),
        real_post_delegate_status=status.value,
        real_post_delegate_source_label=_safe_label(
            snapshot.real_post_delegate_source_label,
            SAFE_REAL_POST_DELEGATE_SOURCE_LABEL,
        ),
        delegate_default_no_execution=snapshot.delegate_default_no_execution,
        delegate_import_executes_post=snapshot.delegate_import_executes_post,
        delegate_construct_executes_post=snapshot.delegate_construct_executes_post,
        delegate_summary_executes_post=snapshot.delegate_summary_executes_post,
        delegate_supply_executes_post=snapshot.delegate_supply_executes_post,
        delegate_requires_sealed_request=snapshot.delegate_requires_sealed_request,
        delegate_requires_sealed_body=snapshot.delegate_requires_sealed_body,
        delegate_requires_sealed_credential_signing_provider=(
            snapshot.delegate_requires_sealed_credential_signing_provider
        ),
        delegate_requires_safe_result_mapper=(
            snapshot.delegate_requires_safe_result_mapper
        ),
        delegate_requires_post_specific_confirmation=(
            snapshot.delegate_requires_post_specific_confirmation
        ),
        post_live_order_with_httpx_reference_available=(
            snapshot.post_live_order_with_httpx_reference_available and ready
        ),
        delegate_supplied_to_factory=snapshot.delegate_supplied_to_factory and ready,
        factory_produces_controlled_source_callable=(
            snapshot.factory_produces_controlled_source_callable and ready
        ),
        approved_primitive_actual_source_available=(
            bool(
                factory_summary
                and factory_summary.approved_primitive_actual_source_available
            )
            and ready
        ),
        source_callable_unavailable_due_missing_delegate=(
            snapshot.source_callable_unavailable_due_missing_delegate and ready
        ),
        actual_post_allowed=False,
        retry_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
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
            REAL_POST_DELEGATE_RECOMMENDED_NEXT_STEP
            if ready
            else REAL_POST_DELEGATE_BLOCKED_NEXT_STEP
        ),
    )


def construct_live_order_real_one_shot_post_real_delegate_controlled(
    *,
    source_delegate: RealPostDelegate | None = None,
    input_snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput | None = None,
) -> LiveOrderRealOneShotPostRealDelegateConnection:
    """Construct the delegate-backed factory path without executing POST."""
    delegate = source_delegate or make_live_order_real_one_shot_post_real_delegate()
    factory = construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        source_delegate=delegate,
    )
    summary = build_live_order_real_one_shot_post_real_delegate_controlled(
        input_snapshot=input_snapshot,
        factory_summary=factory.summary,
    )
    return LiveOrderRealOneShotPostRealDelegateConnection(
        summary=summary,
        source_delegate=delegate,
        factory=factory,
        approved_primitive_actual_source=factory.approved_primitive_actual_source,
    )


def construct_live_order_real_one_shot_post_real_delegate_approved_actual_source_controlled(
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSource:
    """Return the current/default approved actual-source boundary with delegate."""
    connection = construct_live_order_real_one_shot_post_real_delegate_controlled()
    return connection.approved_primitive_actual_source


def make_live_order_real_one_shot_post_real_delegate(
    *,
    delegate_runner: RealPostDelegate | None = None,
    post_function_reference: PostFunctionReference | None = None,
) -> RealPostDelegate:
    """Create a controlled delegate reference; default path does not POST."""
    post_reference_available = post_function_reference is not None

    def controlled_delegate(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        if delegate_runner is None:
            _ = input_snapshot
            _ = post_reference_available
            return _safe_transport_result(
                TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
                unavailable=True,
            )
        try:
            delegate_result = delegate_runner(input_snapshot)
        except TimeoutError:
            return _safe_transport_result(
                TransportCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
                timeout=True,
            )
        except Exception:
            return _safe_transport_result(
                TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            )
        if not isinstance(delegate_result, LiveOrderRealOneShotPostTransportResult):
            return _safe_transport_result(
                TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            )
        if _unsafe_transport_result(delegate_result):
            return _safe_transport_result(
                TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED,
                failed=True,
            )
        return _safe_transport_result(
            delegate_result.result_category,
            fake_transport_used=delegate_result.fake_transport_used,
            http_post_executed=delegate_result.http_post_executed,
            timeout=delegate_result.timeout,
            unknown=delegate_result.unknown,
            unavailable=delegate_result.unavailable,
            failed=delegate_result.failed,
        )

    return controlled_delegate


def resolve_post_live_order_with_httpx_reference() -> PostFunctionReference:
    """Return the primitive function reference without executing it."""
    from app.live_verification.live_order_once import post_live_order_with_httpx

    return post_live_order_with_httpx


def map_live_order_real_one_shot_post_real_delegate_outcome(
    transport_result: LiveOrderRealOneShotPostTransportResult,
):
    """Map delegate outcome through the sealed safe result mapper."""
    return map_live_order_real_one_shot_post_ledger_free_source_outcome(
        transport_result,
    )


def render_live_order_real_one_shot_post_real_delegate_markdown(
    result: LiveOrderRealOneShotPostRealDelegateControlledResult,
) -> str:
    """Render a safe real delegate readiness summary."""
    lines = [
        "# Step 6G Real POST Delegate Controlled",
        "",
        "This is a safe delegate connection summary only.",
        "It is not POST execution and does not request POST confirmation.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw request, raw response, broker/API response, IDs,",
        "credential values, signature values, headers values, or ledger values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- real_post_delegate_ready: {_bool_text(result.real_post_delegate_ready)}",
        (
            "- delegate_supplied_to_factory: "
            f"{_bool_text(result.delegate_supplied_to_factory)}"
        ),
        (
            "- factory_produces_controlled_source_callable: "
            f"{_bool_text(result.factory_produces_controlled_source_callable)}"
        ),
        (
            "- approved_primitive_actual_source_available: "
            f"{_bool_text(result.approved_primitive_actual_source_available)}"
        ),
        (
            "- source_callable_unavailable_due_missing_delegate: "
            f"{_bool_text(result.source_callable_unavailable_due_missing_delegate)}"
        ),
        "",
        "## Delegate Guard",
        f"- delegate_default_no_execution: {_bool_text(result.delegate_default_no_execution)}",
        (
            "- delegate_import_executes_post: "
            f"{_bool_text(result.delegate_import_executes_post)}"
        ),
        (
            "- delegate_construct_executes_post: "
            f"{_bool_text(result.delegate_construct_executes_post)}"
        ),
        (
            "- delegate_summary_executes_post: "
            f"{_bool_text(result.delegate_summary_executes_post)}"
        ),
        (
            "- delegate_supply_executes_post: "
            f"{_bool_text(result.delegate_supply_executes_post)}"
        ),
        (
            "- delegate_requires_post_specific_confirmation: "
            f"{_bool_text(result.delegate_requires_post_specific_confirmation)}"
        ),
        f"- actual_post_allowed: {_bool_text(result.actual_post_allowed)}",
        "",
        "## Safety",
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
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
        "## Next",
        f"- recommended_next_step: {result.recommended_next_step}",
    ]
    if result.blocked_reasons:
        lines.extend(("", "## Blocked Reasons"))
        lines.extend(f"- {reason}" for reason in result.blocked_reasons)
    return "\n".join(lines)


def _delegate_status(
    snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput,
    *,
    factory_summary: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult
    | None,
) -> tuple[RealDelegateStatus, tuple[str, ...]]:
    if not snapshot.post_live_order_with_httpx_reference_available:
        return (
            RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_MISSING_FUNCTION_REFERENCE,
            ("post_live_order_with_httpx_reference_missing",),
        )
    if not snapshot.real_post_delegate_ready:
        return (
            RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            ("real_post_delegate_not_ready",),
        )
    if factory_summary is not None:
        if not factory_summary.ledger_free_post_only_source_factory_ready:
            return (
                RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_MISSING_FACTORY,
                ("ledger_free_source_factory_not_ready",),
            )
        if not factory_summary.source_delegate_supplied:
            return (
                RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_FACTORY_MISSING_DELEGATE,
                ("source_delegate_not_supplied_to_factory",),
            )
        if factory_summary.source_callable_unavailable_due_missing_delegate:
            return (
                RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_FACTORY_MISSING_DELEGATE,
                ("source_callable_missing_delegate",),
            )
    execution_reasons = _execution_reasons(snapshot)
    if execution_reasons:
        return (
            RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_POST_OR_ORDER_EXECUTION,
            execution_reasons,
        )
    lifecycle_reasons = _lifecycle_reasons(snapshot)
    if lifecycle_reasons:
        return (
            RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY,
            lifecycle_reasons,
        )
    exposure_reasons = _exposure_reasons(snapshot)
    if exposure_reasons:
        return (
            RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE,
            exposure_reasons,
        )
    contract_reasons = _contract_reasons(snapshot)
    if contract_reasons:
        return RealDelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT, contract_reasons
    return RealDelegateStatus.REAL_POST_DELEGATE_READY_NO_POST, ()


def _execution_reasons(
    snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
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
    snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "second_post_attempted",
        "retry_attempted",
        "ledger_update_attempted",
        "attempt_counter_persisted",
        "receipt_handoff_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _exposure_reasons(
    snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "raw_request_exposure_attempted",
        "raw_response_exposure_attempted",
        "broker_api_response_exposure_attempted",
        "credential_value_exposure_attempted",
        "signature_value_exposure_attempted",
        "headers_value_exposure_attempted",
        "id_exposure_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _contract_reasons(
    snapshot: LiveOrderRealOneShotPostRealDelegateControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "delegate_default_no_execution",
        "delegate_requires_sealed_request",
        "delegate_requires_sealed_body",
        "delegate_requires_sealed_credential_signing_provider",
        "delegate_requires_safe_result_mapper",
        "delegate_requires_post_specific_confirmation",
        "delegate_supplied_to_factory",
        "factory_produces_controlled_source_callable",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_missing")
    if snapshot.source_callable_unavailable_due_missing_delegate:
        reasons.append("source_callable_unavailable_due_missing_delegate")
    if snapshot.delegate_import_executes_post:
        reasons.append("delegate_import_executes_post")
    if snapshot.delegate_construct_executes_post:
        reasons.append("delegate_construct_executes_post")
    if snapshot.delegate_summary_executes_post:
        reasons.append("delegate_summary_executes_post")
    if snapshot.delegate_supply_executes_post:
        reasons.append("delegate_supply_executes_post")
    if snapshot.actual_post_allowed:
        reasons.append("actual_post_allowed")
    if snapshot.retry_allowed:
        reasons.append("retry_allowed")
    if snapshot.ledger_update_allowed:
        reasons.append("ledger_update_allowed")
    if snapshot.receipt_handoff_allowed:
        reasons.append("receipt_handoff_allowed")
    return tuple(reasons)


def _unsafe_transport_result(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> bool:
    return any(
        getattr(transport_result, field_name)
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
        )
    )


def _safe_transport_result(
    category: LiveOrderRealOneShotPostTransportResultCategory,
    *,
    fake_transport_used: bool = True,
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


def _validate_result_safety(
    result: LiveOrderRealOneShotPostRealDelegateControlledResult,
) -> None:
    for field_name in (
        "actual_post_allowed",
        "retry_allowed",
        "ledger_update_allowed",
        "receipt_handoff_allowed",
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
    ):
        if getattr(result, field_name):
            raise LiveVerificationValidationError(f"{field_name} must be false")
    if result.post_execution_count != 0:
        raise LiveVerificationValidationError("post_execution_count must be zero")


def _safe_label(value: str, expected: str) -> str:
    return value if value == expected else UNSUPPORTED_REAL_POST_DELEGATE_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if not isinstance(getattr(obj, field_name), bool):
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_REAL_POST_DELEGATE_INPUT_BOOL_FIELDS = (
    "real_post_delegate_ready",
    "delegate_default_no_execution",
    "delegate_import_executes_post",
    "delegate_construct_executes_post",
    "delegate_summary_executes_post",
    "delegate_supply_executes_post",
    "delegate_requires_sealed_request",
    "delegate_requires_sealed_body",
    "delegate_requires_sealed_credential_signing_provider",
    "delegate_requires_safe_result_mapper",
    "delegate_requires_post_specific_confirmation",
    "post_live_order_with_httpx_reference_available",
    "delegate_supplied_to_factory",
    "factory_produces_controlled_source_callable",
    "source_callable_unavailable_due_missing_delegate",
    "actual_post_allowed",
    "retry_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "second_post_attempted",
    "retry_attempted",
    "ledger_update_attempted",
    "attempt_counter_persisted",
    "receipt_handoff_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "id_exposure_attempted",
)

_REAL_POST_DELEGATE_RESULT_BOOL_FIELDS = (
    "real_post_delegate_ready",
    "delegate_default_no_execution",
    "delegate_import_executes_post",
    "delegate_construct_executes_post",
    "delegate_summary_executes_post",
    "delegate_supply_executes_post",
    "delegate_requires_sealed_request",
    "delegate_requires_sealed_body",
    "delegate_requires_sealed_credential_signing_provider",
    "delegate_requires_safe_result_mapper",
    "delegate_requires_post_specific_confirmation",
    "post_live_order_with_httpx_reference_available",
    "delegate_supplied_to_factory",
    "factory_produces_controlled_source_callable",
    "approved_primitive_actual_source_available",
    "source_callable_unavailable_due_missing_delegate",
    "actual_post_allowed",
    "retry_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
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
