"""Step 6G ledger-free POST-only source factory.

This module composes the sealed request/body/result foundation with the sealed
credential/signing/header provider foundation. It constructs a controlled
source callable and connects it to the approved primitive actual source
boundary without executing POST, reading env files, exposing raw values, or
touching ledger/receipt flows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_one_shot_post_approved_primitive_actual_source_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostApprovedPrimitiveActualSource,
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult,
    construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    ControlledTransport,
    LiveOrderRealOneShotPostTransportInput,
    LiveOrderRealOneShotPostTransportResult,
    LiveOrderRealOneShotPostTransportResultCategory,
)
from app.live_verification.live_order_real_one_shot_post_sealed_credential_signing_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedCredentialSigningControlledResult,
    build_live_order_real_one_shot_post_sealed_credential_signing_controlled,
)
from app.live_verification.live_order_real_one_shot_post_sealed_request_result_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedRequestResultControlledResult,
    LiveOrderRealSealedTransportResultMappingInput,
    LiveOrderRealSealedTransportResultMappingResult,
    LiveOrderRealSealedTransportSafeCategory,
    build_live_order_real_one_shot_post_sealed_request_result_controlled,
    map_live_order_real_one_shot_post_sealed_transport_result,
)

SAFE_LEDGER_FREE_SOURCE_FACTORY_LABEL = (
    "CONTROLLED_LEDGER_FREE_POST_ONLY_SOURCE_FACTORY"
)
SAFE_LEDGER_FREE_SOURCE_CALLABLE_LABEL = (
    "LEDGER_FREE_POST_ONLY_SOURCE_CALLABLE_SAFE_OUTCOME_ONLY"
)
LEDGER_FREE_SOURCE_FACTORY_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_retry_7_requires_preview_and_new_post_confirmation"
)
LEDGER_FREE_SOURCE_FACTORY_BLOCKED_NEXT_STEP = (
    "fix_ledger_free_post_only_source_factory_blockers_no_post"
)
LEDGER_FREE_SOURCE_NOT_ATTEMPTED_CATEGORY = "NOT_ATTEMPTED_NO_POST"
UNSUPPORTED_LEDGER_FREE_SOURCE_FACTORY_LABEL = "UNSUPPORTED_REDACTED"

TransportResultCategory = LiveOrderRealOneShotPostTransportResultCategory
SealedTransportSafeCategory = LiveOrderRealSealedTransportSafeCategory
LedgerFreeSourceDelegate = Callable[
    [LiveOrderRealOneShotPostTransportInput],
    LiveOrderRealOneShotPostTransportResult,
]


class LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus(str, Enum):
    LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST = (
        "LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_REQUEST = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_REQUEST"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_BODY = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_BODY"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SAFE_RESULT_MAPPER = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SAFE_RESULT_MAPPER"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SIGNING_PROVIDER = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SIGNING_PROVIDER"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_HEADERS = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_HEADERS"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_CREDENTIAL_UNAVAILABLE = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_CREDENTIAL_UNAVAILABLE"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_ID_EXPOSURE = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_ID_EXPOSURE"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY"
    )
    LEDGER_FREE_SOURCE_FACTORY_BLOCKED_FACTORY_CONTRACT = (
        "LEDGER_FREE_SOURCE_FACTORY_BLOCKED_FACTORY_CONTRACT"
    )


LedgerFreeSourceFactoryStatus = (
    LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus
)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput:
    ledger_free_post_only_source_factory_label: str = (
        SAFE_LEDGER_FREE_SOURCE_FACTORY_LABEL
    )
    source_safe_label: str = SAFE_LEDGER_FREE_SOURCE_CALLABLE_LABEL
    factory_default_no_execution: bool = True
    factory_import_executes_post: bool = False
    factory_construct_executes_post: bool = False
    factory_summary_executes_post: bool = False
    factory_requires_sealed_request: bool = True
    factory_requires_sealed_body: bool = True
    factory_requires_sealed_credential_signing_provider: bool = True
    factory_requires_safe_result_mapper: bool = True
    factory_requires_post_specific_confirmation: bool = True
    factory_produces_controlled_source_callable: bool = True
    source_delegate_supplied: bool = False
    source_callable_unavailable_due_missing_delegate: bool = True
    sealed_request_model_ready: bool = True
    sealed_body_builder_ready: bool = True
    safe_result_mapper_ready: bool = True
    sealed_credential_signing_provider_ready: bool = True
    sealed_credential_provider_ready: bool = True
    sealed_signing_provider_ready: bool = True
    sealed_headers_ready: bool = True
    credential_presence_available: bool = True
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    actual_post_allowed: bool = False
    ledger_update_allowed: bool = False
    receipt_handoff_allowed: bool = False
    approval_phrase_validation_coupled: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    client_order_id_actual_value_exposure_attempted: bool = False
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
        _require_non_empty(
            "ledger_free_post_only_source_factory_label",
            self.ledger_free_post_only_source_factory_label,
        )
        _require_non_empty("source_safe_label", self.source_safe_label)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _LEDGER_FREE_SOURCE_FACTORY_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult:
    status: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus
    ledger_free_post_only_source_factory_ready: bool
    ledger_free_post_only_source_factory_label: str
    ledger_free_post_only_source_factory_status: str
    factory_default_no_execution: bool
    factory_import_executes_post: bool
    factory_construct_executes_post: bool
    factory_summary_executes_post: bool
    factory_requires_sealed_request: bool
    factory_requires_sealed_body: bool
    factory_requires_sealed_credential_signing_provider: bool
    factory_requires_safe_result_mapper: bool
    factory_requires_post_specific_confirmation: bool
    factory_produces_controlled_source_callable: bool
    source_delegate_supplied: bool
    source_callable_unavailable_due_missing_delegate: bool
    sealed_request_model_ready: bool
    sealed_body_builder_ready: bool
    safe_result_mapper_ready: bool
    sealed_credential_signing_provider_ready: bool
    sealed_credential_provider_ready: bool
    sealed_signing_provider_ready: bool
    sealed_headers_ready: bool
    credential_presence_available: bool
    approved_primitive_actual_source_available: bool
    approved_primitive_actual_source_status: str
    source_attempted: bool
    source_call_count: int
    source_safe_status: str
    source_safe_label: str
    source_result_category: str
    accepted: bool
    rejected: bool
    timeout: bool
    unknown: bool
    unavailable: bool
    failed: bool
    actual_post_allowed: bool
    retry_allowed: bool
    timeout_fail_closed: bool
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
    client_order_id_actual_value_exposed: bool
    real_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be ledger-free source factory status",
            )
        for field_name in (
            "ledger_free_post_only_source_factory_label",
            "ledger_free_post_only_source_factory_status",
            "approved_primitive_actual_source_status",
            "source_safe_status",
            "source_safe_label",
            "source_result_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("source_call_count", self.source_call_count)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _LEDGER_FREE_SOURCE_FACTORY_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_factory_result_safety(self)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostLedgerFreeSourceFactory:
    summary: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult
    controlled_source: ControlledTransport
    approved_primitive_actual_source: LiveOrderRealOneShotPostApprovedPrimitiveActualSource


def build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
    input_snapshot: (
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput | None
    ) = None,
    *,
    sealed_request_result: (
        LiveOrderRealOneShotPostSealedRequestResultControlledResult | None
    ) = None,
    sealed_credential_signing_result: (
        LiveOrderRealOneShotPostSealedCredentialSigningControlledResult | None
    ) = None,
) -> LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult:
    """Build the safe factory readiness summary without executing POST."""
    snapshot = _merge_factory_prerequisites(
        input_snapshot
        or LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(),
        sealed_request_result=sealed_request_result,
        sealed_credential_signing_result=sealed_credential_signing_result,
    )
    status, reasons = _factory_status(snapshot)
    ready = status is LedgerFreeSourceFactoryStatus.LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST
    approved_actual_source_summary = (
        _build_approved_primitive_actual_source_summary_for_factory(ready)
    )
    approved_available = (
        ready
        and approved_actual_source_summary.approved_primitive_actual_source_available
    )
    return LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult(
        status=status,
        ledger_free_post_only_source_factory_ready=ready,
        ledger_free_post_only_source_factory_label=_safe_label(
            snapshot.ledger_free_post_only_source_factory_label,
            SAFE_LEDGER_FREE_SOURCE_FACTORY_LABEL,
        ),
        ledger_free_post_only_source_factory_status=status.value,
        factory_default_no_execution=snapshot.factory_default_no_execution,
        factory_import_executes_post=snapshot.factory_import_executes_post,
        factory_construct_executes_post=snapshot.factory_construct_executes_post,
        factory_summary_executes_post=snapshot.factory_summary_executes_post,
        factory_requires_sealed_request=snapshot.factory_requires_sealed_request,
        factory_requires_sealed_body=snapshot.factory_requires_sealed_body,
        factory_requires_sealed_credential_signing_provider=(
            snapshot.factory_requires_sealed_credential_signing_provider
        ),
        factory_requires_safe_result_mapper=(
            snapshot.factory_requires_safe_result_mapper
        ),
        factory_requires_post_specific_confirmation=(
            snapshot.factory_requires_post_specific_confirmation
        ),
        factory_produces_controlled_source_callable=(
            snapshot.factory_produces_controlled_source_callable and ready
        ),
        source_delegate_supplied=snapshot.source_delegate_supplied and ready,
        source_callable_unavailable_due_missing_delegate=(
            snapshot.source_callable_unavailable_due_missing_delegate and ready
        ),
        sealed_request_model_ready=snapshot.sealed_request_model_ready and ready,
        sealed_body_builder_ready=snapshot.sealed_body_builder_ready and ready,
        safe_result_mapper_ready=snapshot.safe_result_mapper_ready and ready,
        sealed_credential_signing_provider_ready=(
            snapshot.sealed_credential_signing_provider_ready and ready
        ),
        sealed_credential_provider_ready=(
            snapshot.sealed_credential_provider_ready and ready
        ),
        sealed_signing_provider_ready=snapshot.sealed_signing_provider_ready and ready,
        sealed_headers_ready=snapshot.sealed_headers_ready and ready,
        credential_presence_available=snapshot.credential_presence_available and ready,
        approved_primitive_actual_source_available=approved_available,
        approved_primitive_actual_source_status=(
            approved_actual_source_summary.approved_primitive_actual_source_status
        ),
        source_attempted=False,
        source_call_count=0,
        source_safe_status=status.value,
        source_safe_label=_safe_label(
            snapshot.source_safe_label,
            SAFE_LEDGER_FREE_SOURCE_CALLABLE_LABEL,
        ),
        source_result_category=LEDGER_FREE_SOURCE_NOT_ATTEMPTED_CATEGORY,
        accepted=False,
        rejected=False,
        timeout=False,
        unknown=False,
        unavailable=False,
        failed=False,
        actual_post_allowed=False,
        retry_allowed=False,
        timeout_fail_closed=snapshot.timeout_fail_closed,
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
        client_order_id_actual_value_exposed=False,
        real_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        blocked_reasons=reasons,
        recommended_next_step=(
            LEDGER_FREE_SOURCE_FACTORY_RECOMMENDED_NEXT_STEP
            if approved_available
            else LEDGER_FREE_SOURCE_FACTORY_BLOCKED_NEXT_STEP
        ),
    )


def construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
    *,
    source_delegate: LedgerFreeSourceDelegate | None = None,
    input_snapshot: (
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput | None
    ) = None,
    sealed_request_result: (
        LiveOrderRealOneShotPostSealedRequestResultControlledResult | None
    ) = None,
    sealed_credential_signing_result: (
        LiveOrderRealOneShotPostSealedCredentialSigningControlledResult | None
    ) = None,
) -> LiveOrderRealOneShotPostLedgerFreeSourceFactory:
    """Construct the factory and approved actual-source boundary without POST."""
    if source_delegate is not None:
        input_snapshot = replace(
            input_snapshot
            or LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(),
            source_delegate_supplied=True,
            source_callable_unavailable_due_missing_delegate=False,
        )
    summary = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        input_snapshot=input_snapshot,
        sealed_request_result=sealed_request_result,
        sealed_credential_signing_result=sealed_credential_signing_result,
    )
    controlled_source = _blocked_source
    actual_source_for_boundary: ControlledTransport | None = None
    if summary.ledger_free_post_only_source_factory_ready:
        controlled_source = make_live_order_real_one_shot_post_ledger_free_source(
            source_delegate=source_delegate,
        )
        actual_source_for_boundary = controlled_source
    approved_actual_source = (
        construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            actual_source=actual_source_for_boundary,
        )
    )
    return LiveOrderRealOneShotPostLedgerFreeSourceFactory(
        summary=summary,
        controlled_source=controlled_source,
        approved_primitive_actual_source=approved_actual_source,
    )


def construct_live_order_real_one_shot_post_ledger_free_approved_actual_source_controlled(
    *,
    source_delegate: LedgerFreeSourceDelegate | None = None,
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSource:
    """Return the approved actual-source boundary for the current factory path."""
    return construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        source_delegate=source_delegate,
    ).approved_primitive_actual_source


def make_live_order_real_one_shot_post_ledger_free_source(
    *,
    source_delegate: LedgerFreeSourceDelegate | None = None,
) -> ControlledTransport:
    """Create a controlled source callable; it does not retry internally."""

    def controlled_source(
        input_snapshot: LiveOrderRealOneShotPostTransportInput,
    ) -> LiveOrderRealOneShotPostTransportResult:
        if source_delegate is None:
            _ = input_snapshot
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
                fake_transport_used=True,
                unavailable=True,
            )
        try:
            delegate_outcome = source_delegate(input_snapshot)
        except TimeoutError:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
                fake_transport_used=True,
                timeout=True,
            )
        except Exception:
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                fake_transport_used=True,
                unknown=True,
            )
        if not isinstance(delegate_outcome, LiveOrderRealOneShotPostTransportResult):
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                fake_transport_used=True,
                unknown=True,
            )
        if _transport_outcome_unsafe_reasons(delegate_outcome):
            return _safe_transport_result(
                TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
                fake_transport_used=delegate_outcome.fake_transport_used,
                failed=True,
            )
        return _safe_transport_result(
            delegate_outcome.result_category,
            fake_transport_used=delegate_outcome.fake_transport_used,
            http_post_executed=delegate_outcome.http_post_executed,
            timeout=delegate_outcome.timeout,
            unknown=delegate_outcome.unknown,
            unavailable=delegate_outcome.unavailable,
            failed=delegate_outcome.failed,
        )

    return controlled_source


def map_live_order_real_one_shot_post_ledger_free_source_outcome(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> LiveOrderRealSealedTransportResultMappingResult:
    """Map a safe source outcome through the sealed safe result mapper."""
    return map_live_order_real_one_shot_post_sealed_transport_result(
        LiveOrderRealSealedTransportResultMappingInput(
            transport_safe_category=_sealed_safe_category_from_transport(
                transport_result,
            ).value,
            raw_response_exposure_attempted=transport_result.raw_response_exposed,
            broker_api_response_exposure_attempted=(
                transport_result.broker_api_response_exposed
            ),
            id_exposure_attempted=(
                transport_result.real_id_exposed
                or transport_result.account_id_exposed
                or transport_result.order_id_exposed
                or transport_result.transaction_id_exposed
            ),
            credential_value_exposure_attempted=(
                transport_result.credential_value_exposed
            ),
            signature_value_exposure_attempted=transport_result.signature_value_exposed,
            headers_value_exposure_attempted=transport_result.headers_value_exposed,
            retry_attempted=transport_result.retry_attempted,
            ledger_update_attempted=transport_result.ledger_updated
            or transport_result.attempt_counter_persisted,
            receipt_handoff_attempted=transport_result.actual_receipt_handoff_executed,
        ),
    )


def render_live_order_real_one_shot_post_ledger_free_source_factory_markdown(
    result: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult,
) -> str:
    """Render the factory safe summary."""
    lines = [
        "# Step 6G Ledger-Free POST-Only Source Factory Controlled",
        "",
        "This is a safe factory summary only.",
        "It is not POST execution and does not request POST confirmation.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw request, raw response, broker/API response, IDs,",
        "credential values, signature values, headers values, or ledger values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- ledger_free_post_only_source_factory_ready: "
            f"{_bool_text(result.ledger_free_post_only_source_factory_ready)}"
        ),
        (
            "- factory_produces_controlled_source_callable: "
            f"{_bool_text(result.factory_produces_controlled_source_callable)}"
        ),
        f"- source_delegate_supplied: {_bool_text(result.source_delegate_supplied)}",
        (
            "- source_callable_unavailable_due_missing_delegate: "
            f"{_bool_text(result.source_callable_unavailable_due_missing_delegate)}"
        ),
        (
            "- approved_primitive_actual_source_available: "
            f"{_bool_text(result.approved_primitive_actual_source_available)}"
        ),
        (
            "- approved_primitive_actual_source_status: "
            f"{result.approved_primitive_actual_source_status}"
        ),
        "",
        "## Factory Guard",
        f"- factory_default_no_execution: {_bool_text(result.factory_default_no_execution)}",
        (
            "- factory_import_executes_post: "
            f"{_bool_text(result.factory_import_executes_post)}"
        ),
        (
            "- factory_construct_executes_post: "
            f"{_bool_text(result.factory_construct_executes_post)}"
        ),
        (
            "- factory_summary_executes_post: "
            f"{_bool_text(result.factory_summary_executes_post)}"
        ),
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        "",
        "## Prerequisites",
        (
            "- factory_requires_sealed_request: "
            f"{_bool_text(result.factory_requires_sealed_request)}"
        ),
        (
            "- factory_requires_sealed_body: "
            f"{_bool_text(result.factory_requires_sealed_body)}"
        ),
        (
            "- factory_requires_sealed_credential_signing_provider: "
            f"{_bool_text(result.factory_requires_sealed_credential_signing_provider)}"
        ),
        (
            "- factory_requires_safe_result_mapper: "
            f"{_bool_text(result.factory_requires_safe_result_mapper)}"
        ),
        (
            "- factory_requires_post_specific_confirmation: "
            f"{_bool_text(result.factory_requires_post_specific_confirmation)}"
        ),
        f"- sealed_request_model_ready: {_bool_text(result.sealed_request_model_ready)}",
        f"- sealed_body_builder_ready: {_bool_text(result.sealed_body_builder_ready)}",
        f"- safe_result_mapper_ready: {_bool_text(result.safe_result_mapper_ready)}",
        (
            "- sealed_credential_signing_provider_ready: "
            f"{_bool_text(result.sealed_credential_signing_provider_ready)}"
        ),
        (
            "- sealed_credential_provider_ready: "
            f"{_bool_text(result.sealed_credential_provider_ready)}"
        ),
        f"- sealed_signing_provider_ready: {_bool_text(result.sealed_signing_provider_ready)}",
        f"- sealed_headers_ready: {_bool_text(result.sealed_headers_ready)}",
        (
            "- credential_presence_available: "
            f"{_bool_text(result.credential_presence_available)}"
        ),
        "",
        "## Source Callable",
        f"- source_attempted: {_bool_text(result.source_attempted)}",
        f"- source_call_count: {result.source_call_count}",
        f"- source_safe_status: {result.source_safe_status}",
        f"- source_safe_label: {result.source_safe_label}",
        f"- source_result_category: {result.source_result_category}",
        "",
        "## Safety",
        f"- actual_post_allowed: {_bool_text(result.actual_post_allowed)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- timeout_fail_closed: {_bool_text(result.timeout_fail_closed)}",
        f"- ledger_update_allowed: {_bool_text(result.ledger_update_allowed)}",
        f"- receipt_handoff_allowed: {_bool_text(result.receipt_handoff_allowed)}",
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


def _merge_factory_prerequisites(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
    *,
    sealed_request_result: (
        LiveOrderRealOneShotPostSealedRequestResultControlledResult | None
    ),
    sealed_credential_signing_result: (
        LiveOrderRealOneShotPostSealedCredentialSigningControlledResult | None
    ),
) -> LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput:
    request_result = (
        sealed_request_result
        or build_live_order_real_one_shot_post_sealed_request_result_controlled()
    )
    provider_result = (
        sealed_credential_signing_result
        or build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
            sealed_request_result=request_result,
        )
    )
    return replace(
        snapshot,
        sealed_request_model_ready=(
            snapshot.sealed_request_model_ready
            and request_result.sealed_request_model_ready
        ),
        sealed_body_builder_ready=(
            snapshot.sealed_body_builder_ready
            and request_result.sealed_body_builder_ready
        ),
        safe_result_mapper_ready=(
            snapshot.safe_result_mapper_ready
            and request_result.safe_result_mapper_ready
        ),
        sealed_credential_signing_provider_ready=(
            snapshot.sealed_credential_signing_provider_ready
            and provider_result.sealed_credential_signing_provider_ready
        ),
        sealed_credential_provider_ready=(
            snapshot.sealed_credential_provider_ready
            and provider_result.sealed_credential_provider_ready
        ),
        sealed_signing_provider_ready=(
            snapshot.sealed_signing_provider_ready
            and provider_result.sealed_signing_provider_ready
        ),
        sealed_headers_ready=(
            snapshot.sealed_headers_ready and provider_result.sealed_headers_ready
        ),
        credential_presence_available=(
            snapshot.credential_presence_available
            and provider_result.credential_presence_available
        ),
        raw_request_exposure_attempted=(
            snapshot.raw_request_exposure_attempted
            or request_result.raw_body_exposed
            or provider_result.raw_body_exposed
        ),
        raw_response_exposure_attempted=(
            snapshot.raw_response_exposure_attempted
            or request_result.raw_response_exposed
            or provider_result.raw_response_exposed
        ),
        broker_api_response_exposure_attempted=(
            snapshot.broker_api_response_exposure_attempted
            or request_result.broker_api_response_exposed
            or provider_result.broker_api_response_exposed
        ),
        credential_value_exposure_attempted=(
            snapshot.credential_value_exposure_attempted
            or request_result.credential_value_exposed
            or provider_result.credential_value_exposed
        ),
        signature_value_exposure_attempted=(
            snapshot.signature_value_exposure_attempted
            or request_result.signature_value_exposed
            or provider_result.signature_value_exposed
        ),
        headers_value_exposure_attempted=(
            snapshot.headers_value_exposure_attempted
            or request_result.headers_value_exposed
            or provider_result.headers_value_exposed
        ),
        client_order_id_actual_value_exposure_attempted=(
            snapshot.client_order_id_actual_value_exposure_attempted
            or request_result.client_order_id_actual_value_exposed
        ),
        id_exposure_attempted=(
            snapshot.id_exposure_attempted
            or request_result.id_exposed
            or request_result.real_account_order_transaction_id_exposed
            or provider_result.id_exposed
            or provider_result.real_account_order_transaction_id_exposed
        ),
        actual_http_post_executed=(
            snapshot.actual_http_post_executed
            or request_result.actual_http_post_executed
            or provider_result.actual_http_post_executed
        ),
        order_endpoint_executed=(
            snapshot.order_endpoint_executed
            or request_result.order_endpoint_executed
            or provider_result.order_endpoint_executed
        ),
        live_order_once_executed=(
            snapshot.live_order_once_executed
            or request_result.live_order_once_executed
            or provider_result.live_order_once_executed
        ),
        post_execution_count=(
            snapshot.post_execution_count
            + request_result.post_execution_count
            + provider_result.post_execution_count
        ),
        second_post_attempted=(
            snapshot.second_post_attempted
            or request_result.second_post_attempted
            or provider_result.second_post_attempted
        ),
        retry_attempted=(
            snapshot.retry_attempted
            or request_result.retry_attempted
            or provider_result.retry_attempted
        ),
        ledger_update_attempted=(
            snapshot.ledger_update_attempted
            or request_result.ledger_updated
            or provider_result.ledger_updated
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or request_result.attempt_counter_persisted
            or provider_result.attempt_counter_persisted
        ),
        receipt_handoff_attempted=(
            snapshot.receipt_handoff_attempted
            or request_result.actual_receipt_handoff_executed
            or provider_result.actual_receipt_handoff_executed
        ),
    )


def _build_approved_primitive_actual_source_summary_for_factory(
    ready: bool,
) -> LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledResult:
    return construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(  # noqa: E501
        actual_source=make_live_order_real_one_shot_post_ledger_free_source()
        if ready
        else None,
        input_snapshot=LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput(
            approved_primitive_actual_source_supplied=ready,
        ),
    ).summary


def _factory_status(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[
    LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus,
    tuple[str, ...],
]:
    raw_reasons = _raw_exposure_reasons(snapshot)
    if raw_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE,
            raw_reasons,
        )
    id_reasons = _id_exposure_reasons(snapshot)
    if id_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_ID_EXPOSURE,
            id_reasons,
        )
    value_reasons = _value_exposure_reasons(snapshot)
    if value_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE,
            value_reasons,
        )
    execution_reasons = _execution_reasons(snapshot)
    if execution_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION,
            execution_reasons,
        )
    lifecycle_reasons = _lifecycle_reasons(snapshot)
    if lifecycle_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            lifecycle_reasons,
        )
    if snapshot.factory_requires_sealed_request and not snapshot.sealed_request_model_ready:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_REQUEST,
            ("sealed_request_model_missing",),
        )
    if snapshot.factory_requires_sealed_body and not snapshot.sealed_body_builder_ready:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_BODY,
            ("sealed_body_builder_missing",),
        )
    if snapshot.factory_requires_safe_result_mapper and not snapshot.safe_result_mapper_ready:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SAFE_RESULT_MAPPER,
            ("safe_result_mapper_missing",),
        )
    if not snapshot.credential_presence_available:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_CREDENTIAL_UNAVAILABLE,
            ("credential_presence_unavailable",),
        )
    if (
        snapshot.factory_requires_sealed_credential_signing_provider
        and not snapshot.sealed_credential_signing_provider_ready
    ):
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER,
            ("sealed_credential_signing_provider_missing",),
        )
    if (
        snapshot.factory_requires_sealed_credential_signing_provider
        and not snapshot.sealed_credential_provider_ready
    ):
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER,
            ("sealed_credential_provider_missing",),
        )
    if (
        snapshot.factory_requires_sealed_credential_signing_provider
        and not snapshot.sealed_signing_provider_ready
    ):
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SIGNING_PROVIDER,
            ("sealed_signing_provider_missing",),
        )
    if (
        snapshot.factory_requires_sealed_credential_signing_provider
        and not snapshot.sealed_headers_ready
    ):
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_HEADERS,
            ("sealed_headers_missing",),
        )
    contract_reasons = _factory_contract_reasons(snapshot)
    if contract_reasons:
        return (
            LedgerFreeSourceFactoryStatus
            .LEDGER_FREE_SOURCE_FACTORY_BLOCKED_FACTORY_CONTRACT,
            contract_reasons,
        )
    return LedgerFreeSourceFactoryStatus.LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST, ()


def _factory_contract_reasons(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "factory_default_no_execution",
        "factory_requires_post_specific_confirmation",
        "factory_produces_controlled_source_callable",
        "one_post_max",
        "timeout_fail_closed",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_missing")
    if snapshot.factory_import_executes_post:
        reasons.append("factory_import_executes_post")
    if snapshot.factory_construct_executes_post:
        reasons.append("factory_construct_executes_post")
    if snapshot.factory_summary_executes_post:
        reasons.append("factory_summary_executes_post")
    if snapshot.actual_post_allowed:
        reasons.append("actual_post_allowed")
    if snapshot.retry_allowed:
        reasons.append("retry_allowed")
    if snapshot.ledger_update_allowed:
        reasons.append("ledger_update_allowed")
    if snapshot.receipt_handoff_allowed:
        reasons.append("receipt_handoff_allowed")
    if snapshot.approval_phrase_validation_coupled:
        reasons.append("approval_phrase_validation_coupled")
    return tuple(reasons)


def _raw_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.raw_request_exposure_attempted:
        reasons.append("raw_request_exposure_attempted")
    if snapshot.raw_response_exposure_attempted:
        reasons.append("raw_response_exposure_attempted")
    if snapshot.broker_api_response_exposure_attempted:
        reasons.append("broker_api_response_exposure_attempted")
    return tuple(reasons)


def _id_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.id_exposure_attempted:
        reasons.append("id_exposure_attempted")
    if snapshot.client_order_id_actual_value_exposure_attempted:
        reasons.append("client_order_id_actual_value_exposure_attempted")
    return tuple(reasons)


def _value_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
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
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.actual_http_post_executed:
        reasons.append("actual_http_post_executed")
    if snapshot.order_endpoint_executed:
        reasons.append("order_endpoint_executed")
    if snapshot.live_order_once_executed:
        reasons.append("live_order_once_executed")
    if snapshot.post_execution_count:
        reasons.append("post_execution_count_nonzero")
    return tuple(reasons)


def _lifecycle_reasons(
    snapshot: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.second_post_attempted:
        reasons.append("second_post_attempted")
    if snapshot.retry_attempted:
        reasons.append("retry_attempted")
    if snapshot.ledger_update_attempted:
        reasons.append("ledger_update_attempted")
    if snapshot.attempt_counter_persisted:
        reasons.append("attempt_counter_persisted")
    if snapshot.receipt_handoff_attempted:
        reasons.append("receipt_handoff_attempted")
    return tuple(reasons)


def _blocked_source(
    input_snapshot: LiveOrderRealOneShotPostTransportInput,
) -> LiveOrderRealOneShotPostTransportResult:
    _ = input_snapshot
    return _safe_transport_result(
        TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED,
        fake_transport_used=True,
        failed=True,
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


def _transport_outcome_unsafe_reasons(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> tuple[str, ...]:
    reasons = []
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
        if getattr(transport_result, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _sealed_safe_category_from_transport(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> LiveOrderRealSealedTransportSafeCategory:
    if transport_result.timeout:
        return SealedTransportSafeCategory.TIMEOUT
    if transport_result.unavailable:
        return SealedTransportSafeCategory.UNAVAILABLE
    if transport_result.unknown:
        return SealedTransportSafeCategory.UNKNOWN
    if transport_result.failed:
        return SealedTransportSafeCategory.FAILED
    if (
        transport_result.result_category
        is TransportResultCategory.TRANSPORT_ACCEPTED_SANITIZED
    ):
        return SealedTransportSafeCategory.ACCEPTED
    if (
        transport_result.result_category
        is TransportResultCategory.TRANSPORT_REJECTED_SANITIZED
    ):
        return SealedTransportSafeCategory.REJECTED
    if (
        transport_result.result_category
        is TransportResultCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED
    ):
        return SealedTransportSafeCategory.TIMEOUT
    if (
        transport_result.result_category
        is TransportResultCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED
    ):
        return SealedTransportSafeCategory.UNAVAILABLE
    if (
        transport_result.result_category
        is TransportResultCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED
    ):
        return SealedTransportSafeCategory.UNKNOWN
    return SealedTransportSafeCategory.FAILED


def _validate_factory_result_safety(
    result: LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledResult,
) -> None:
    always_false_fields = (
        "source_attempted",
        "accepted",
        "rejected",
        "timeout",
        "unknown",
        "unavailable",
        "failed",
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
        "client_order_id_actual_value_exposed",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
    )
    for field_name in always_false_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(f"{field_name} must be false")
    if result.source_call_count != 0:
        raise LiveVerificationValidationError("source_call_count must be zero")
    if result.post_execution_count != 0:
        raise LiveVerificationValidationError("post_execution_count must be zero")
    if result.ledger_free_post_only_source_factory_ready:
        for field_name in (
            "factory_default_no_execution",
            "factory_requires_sealed_request",
            "factory_requires_sealed_body",
            "factory_requires_sealed_credential_signing_provider",
            "factory_requires_safe_result_mapper",
            "factory_requires_post_specific_confirmation",
            "factory_produces_controlled_source_callable",
            "sealed_request_model_ready",
            "sealed_body_builder_ready",
            "safe_result_mapper_ready",
            "sealed_credential_signing_provider_ready",
            "sealed_credential_provider_ready",
            "sealed_signing_provider_ready",
            "sealed_headers_ready",
            "credential_presence_available",
            "approved_primitive_actual_source_available",
            "timeout_fail_closed",
        ):
            if not getattr(result, field_name):
                raise LiveVerificationValidationError(f"{field_name} must be true")
        for field_name in (
            "factory_import_executes_post",
            "factory_construct_executes_post",
            "factory_summary_executes_post",
        ):
            if getattr(result, field_name):
                raise LiveVerificationValidationError(f"{field_name} must be false")


def _safe_label(value: str, expected: str) -> str:
    return value if value == expected else UNSUPPORTED_LEDGER_FREE_SOURCE_FACTORY_LABEL


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


_LEDGER_FREE_SOURCE_FACTORY_INPUT_BOOL_FIELDS = (
    "factory_default_no_execution",
    "factory_import_executes_post",
    "factory_construct_executes_post",
    "factory_summary_executes_post",
    "factory_requires_sealed_request",
    "factory_requires_sealed_body",
    "factory_requires_sealed_credential_signing_provider",
    "factory_requires_safe_result_mapper",
    "factory_requires_post_specific_confirmation",
    "factory_produces_controlled_source_callable",
    "source_delegate_supplied",
    "source_callable_unavailable_due_missing_delegate",
    "sealed_request_model_ready",
    "sealed_body_builder_ready",
    "safe_result_mapper_ready",
    "sealed_credential_signing_provider_ready",
    "sealed_credential_provider_ready",
    "sealed_signing_provider_ready",
    "sealed_headers_ready",
    "credential_presence_available",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "actual_post_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "approval_phrase_validation_coupled",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "client_order_id_actual_value_exposure_attempted",
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

_LEDGER_FREE_SOURCE_FACTORY_RESULT_BOOL_FIELDS = (
    "ledger_free_post_only_source_factory_ready",
    "factory_default_no_execution",
    "factory_import_executes_post",
    "factory_construct_executes_post",
    "factory_summary_executes_post",
    "factory_requires_sealed_request",
    "factory_requires_sealed_body",
    "factory_requires_sealed_credential_signing_provider",
    "factory_requires_safe_result_mapper",
    "factory_requires_post_specific_confirmation",
    "factory_produces_controlled_source_callable",
    "source_delegate_supplied",
    "source_callable_unavailable_due_missing_delegate",
    "sealed_request_model_ready",
    "sealed_body_builder_ready",
    "safe_result_mapper_ready",
    "sealed_credential_signing_provider_ready",
    "sealed_credential_provider_ready",
    "sealed_signing_provider_ready",
    "sealed_headers_ready",
    "credential_presence_available",
    "approved_primitive_actual_source_available",
    "source_attempted",
    "accepted",
    "rejected",
    "timeout",
    "unknown",
    "unavailable",
    "failed",
    "actual_post_allowed",
    "retry_allowed",
    "timeout_fail_closed",
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
    "client_order_id_actual_value_exposed",
    "real_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
)
