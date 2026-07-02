"""Step 6G sealed credential/signing/header provider foundation.

This module defines a safe-only provider summary for the future POST-only
source factory. It does not read env files, display process env, load
credential values, generate real signing material, build actual header maps,
import HTTP clients, call live_order_once, update ledgers, or hand off receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_one_shot_post_sealed_request_result_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedRequestResultControlledResult,
    build_live_order_real_one_shot_post_sealed_request_result_controlled,
)

SAFE_SEALED_CREDENTIAL_SIGNING_PROVIDER_LABEL = (
    "CONTROLLED_SEALED_CREDENTIAL_SIGNING_PROVIDER_FOUNDATION"
)
SAFE_SEALED_CREDENTIAL_PROVIDER_LABEL = "SEALED_CREDENTIAL_PROVIDER_SAFE_BOOLEAN_ONLY"
SAFE_SEALED_SIGNING_PROVIDER_LABEL = "SEALED_SIGNING_PROVIDER_SAFE_SUMMARY_ONLY"
SAFE_SEALED_HEADERS_LABEL = "SEALED_HEADERS_SAFE_SUMMARY_ONLY"
SAFE_CREDENTIAL_PRESENCE_LABEL = "CONTROLLED_CREDENTIAL_PRESENCE_SAFE_BOOLEAN_ONLY"
DEFAULT_CREDENTIAL_PRESENCE_SAFE_STATUS = "CREDENTIAL_PRESENCE_PRESENT_NO_POST"
SEALED_CREDENTIAL_SIGNING_RECOMMENDED_NEXT_STEP = (
    "ledger_free_post_only_source_factory_no_post"
)
UNSUPPORTED_SEALED_CREDENTIAL_SIGNING_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus(str, Enum):
    SEALED_CREDENTIAL_SIGNING_READY_NO_POST = (
        "SEALED_CREDENTIAL_SIGNING_READY_NO_POST"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_REQUEST = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_REQUEST"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_BODY = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_BODY"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_CREDENTIAL_PRESENCE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_CREDENTIAL_PRESENCE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_UNAVAILABLE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_UNAVAILABLE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_ID_EXPOSURE = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_ID_EXPOSURE"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION"
    )
    SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY = (
        "SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY"
    )


SealedCredentialSigningStatus = (
    LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus
)


@dataclass(frozen=True)
class LiveOrderRealSealedCredentialProviderSummary:
    sealed_credential_provider_ready: bool
    sealed_credential_provider_label: str
    sealed_credential_provider_status: str
    credential_presence_required: bool
    credential_presence_checked: bool
    credential_presence_available: bool
    credential_presence_safe_status: str
    credential_presence_safe_label: str
    credential_values_loaded_internal: bool
    credential_value_exposed: bool
    credential_length_exposed: bool
    credential_hash_exposed: bool
    credential_fingerprint_exposed: bool
    credential_metadata_exposed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "sealed_credential_provider_label",
            "sealed_credential_provider_status",
            "credential_presence_safe_status",
            "credential_presence_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _SEALED_CREDENTIAL_PROVIDER_BOOL_FIELDS)
        _validate_credential_provider_summary_safety(self)


@dataclass(frozen=True)
class LiveOrderRealSealedSigningProviderSummary:
    sealed_signing_provider_ready: bool
    sealed_signing_provider_label: str
    sealed_signing_provider_status: str
    requires_sealed_request: bool
    requires_sealed_body: bool
    requires_sealed_credential_provider: bool
    signing_generation_internal_only: bool
    signature_value_exposed: bool
    signature_length_exposed: bool
    signature_hash_exposed: bool
    signature_fingerprint_exposed: bool
    raw_body_exposed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "sealed_signing_provider_label",
            "sealed_signing_provider_status",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _SEALED_SIGNING_PROVIDER_BOOL_FIELDS)
        _validate_signing_provider_summary_safety(self)


@dataclass(frozen=True)
class LiveOrderRealSealedHeadersObject:
    sealed_headers_ready: bool
    sealed_headers_label: str
    sealed_headers_status: str
    headers_present: bool
    headers_value_exposed: bool
    headers_metadata_exposed: bool
    headers_count_exposed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "sealed_headers_label",
            "sealed_headers_status",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _SEALED_HEADERS_BOOL_FIELDS)
        _validate_headers_summary_safety(self)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostSealedCredentialSigningControlledInput:
    sealed_credential_signing_provider_label: str = (
        SAFE_SEALED_CREDENTIAL_SIGNING_PROVIDER_LABEL
    )
    sealed_credential_provider_label: str = SAFE_SEALED_CREDENTIAL_PROVIDER_LABEL
    sealed_signing_provider_label: str = SAFE_SEALED_SIGNING_PROVIDER_LABEL
    sealed_headers_label: str = SAFE_SEALED_HEADERS_LABEL
    requires_sealed_request: bool = True
    requires_sealed_body: bool = True
    requires_credential_presence: bool = True
    sealed_request_model_ready: bool = True
    sealed_body_builder_ready: bool = True
    sealed_credential_provider_declared: bool = True
    sealed_signing_provider_declared: bool = True
    sealed_headers_declared: bool = True
    credential_presence_checked: bool = True
    credential_presence_available: bool = True
    credential_presence_safe_status: str = DEFAULT_CREDENTIAL_PRESENCE_SAFE_STATUS
    credential_presence_safe_label: str = SAFE_CREDENTIAL_PRESENCE_LABEL
    credential_values_loaded_internal: bool = False
    signing_generation_internal_only: bool = True
    headers_present: bool = True
    credential_value_exposure_attempted: bool = False
    credential_length_exposure_attempted: bool = False
    credential_hash_exposure_attempted: bool = False
    credential_fingerprint_exposure_attempted: bool = False
    credential_metadata_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    signature_length_exposure_attempted: bool = False
    signature_hash_exposure_attempted: bool = False
    signature_fingerprint_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    headers_metadata_exposure_attempted: bool = False
    headers_count_exposure_attempted: bool = False
    raw_body_exposure_attempted: bool = False
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
            "sealed_credential_signing_provider_label",
            "sealed_credential_provider_label",
            "sealed_signing_provider_label",
            "sealed_headers_label",
            "credential_presence_safe_status",
            "credential_presence_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _SEALED_CREDENTIAL_SIGNING_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostSealedCredentialSigningControlledResult:
    status: LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus
    sealed_credential_signing_provider_ready: bool
    sealed_credential_provider_ready: bool
    sealed_signing_provider_ready: bool
    sealed_headers_ready: bool
    sealed_credential_signing_provider_label: str
    sealed_credential_signing_provider_status: str
    sealed_credential_provider: LiveOrderRealSealedCredentialProviderSummary
    sealed_signing_provider: LiveOrderRealSealedSigningProviderSummary
    sealed_headers_object: LiveOrderRealSealedHeadersObject
    requires_sealed_request: bool
    requires_sealed_body: bool
    requires_credential_presence: bool
    credential_presence_checked: bool
    credential_presence_available: bool
    credential_presence_safe_status: str
    credential_presence_safe_label: str
    credential_values_loaded_internal: bool
    actual_post_allowed: bool
    retry_allowed: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    credential_value_exposed: bool
    credential_length_exposed: bool
    credential_hash_exposed: bool
    credential_fingerprint_exposed: bool
    credential_metadata_exposed: bool
    signature_value_exposed: bool
    signature_length_exposed: bool
    signature_hash_exposed: bool
    signature_fingerprint_exposed: bool
    headers_value_exposed: bool
    headers_metadata_exposed: bool
    headers_count_exposed: bool
    raw_body_exposed: bool
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
            LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be sealed credential signing status",
            )
        for field_name in (
            "sealed_credential_signing_provider_label",
            "sealed_credential_signing_provider_status",
            "credential_presence_safe_status",
            "credential_presence_safe_label",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _SEALED_CREDENTIAL_SIGNING_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_provider_result_safety(self)


def build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
    input_snapshot: (
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput | None
    ) = None,
    *,
    sealed_request_result: (
        LiveOrderRealOneShotPostSealedRequestResultControlledResult | None
    ) = None,
    credential_presence_result: object | None = None,
) -> LiveOrderRealOneShotPostSealedCredentialSigningControlledResult:
    """Build a safe sealed credential/signing/header provider summary only."""
    snapshot = _merge_safe_prerequisites(
        input_snapshot or LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(),
        sealed_request_result=sealed_request_result,
        credential_presence_result=credential_presence_result,
    )
    status, reasons = _provider_status(snapshot)
    ready = status is SealedCredentialSigningStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST
    credential_provider_ready = ready and snapshot.sealed_credential_provider_declared
    signing_provider_ready = ready and snapshot.sealed_signing_provider_declared
    headers_ready = ready and snapshot.sealed_headers_declared
    provider_status = status.value
    safe_credential_provider = LiveOrderRealSealedCredentialProviderSummary(
        sealed_credential_provider_ready=credential_provider_ready,
        sealed_credential_provider_label=_safe_label(
            snapshot.sealed_credential_provider_label,
            SAFE_SEALED_CREDENTIAL_PROVIDER_LABEL,
        ),
        sealed_credential_provider_status=provider_status,
        credential_presence_required=snapshot.requires_credential_presence,
        credential_presence_checked=snapshot.credential_presence_checked,
        credential_presence_available=snapshot.credential_presence_available and ready,
        credential_presence_safe_status=_safe_text_label(
            snapshot.credential_presence_safe_status,
        ),
        credential_presence_safe_label=_safe_label(
            snapshot.credential_presence_safe_label,
            SAFE_CREDENTIAL_PRESENCE_LABEL,
        ),
        credential_values_loaded_internal=False,
        credential_value_exposed=False,
        credential_length_exposed=False,
        credential_hash_exposed=False,
        credential_fingerprint_exposed=False,
        credential_metadata_exposed=False,
    )
    safe_signing_provider = LiveOrderRealSealedSigningProviderSummary(
        sealed_signing_provider_ready=signing_provider_ready,
        sealed_signing_provider_label=_safe_label(
            snapshot.sealed_signing_provider_label,
            SAFE_SEALED_SIGNING_PROVIDER_LABEL,
        ),
        sealed_signing_provider_status=provider_status,
        requires_sealed_request=snapshot.requires_sealed_request,
        requires_sealed_body=snapshot.requires_sealed_body,
        requires_sealed_credential_provider=True,
        signing_generation_internal_only=snapshot.signing_generation_internal_only
        and ready,
        signature_value_exposed=False,
        signature_length_exposed=False,
        signature_hash_exposed=False,
        signature_fingerprint_exposed=False,
        raw_body_exposed=False,
    )
    safe_headers_object = LiveOrderRealSealedHeadersObject(
        sealed_headers_ready=headers_ready,
        sealed_headers_label=_safe_label(
            snapshot.sealed_headers_label,
            SAFE_SEALED_HEADERS_LABEL,
        ),
        sealed_headers_status=provider_status,
        headers_present=snapshot.headers_present and ready,
        headers_value_exposed=False,
        headers_metadata_exposed=False,
        headers_count_exposed=False,
    )
    return LiveOrderRealOneShotPostSealedCredentialSigningControlledResult(
        status=status,
        sealed_credential_signing_provider_ready=ready,
        sealed_credential_provider_ready=credential_provider_ready,
        sealed_signing_provider_ready=signing_provider_ready,
        sealed_headers_ready=headers_ready,
        sealed_credential_signing_provider_label=_safe_label(
            snapshot.sealed_credential_signing_provider_label,
            SAFE_SEALED_CREDENTIAL_SIGNING_PROVIDER_LABEL,
        ),
        sealed_credential_signing_provider_status=provider_status,
        sealed_credential_provider=safe_credential_provider,
        sealed_signing_provider=safe_signing_provider,
        sealed_headers_object=safe_headers_object,
        requires_sealed_request=snapshot.requires_sealed_request,
        requires_sealed_body=snapshot.requires_sealed_body,
        requires_credential_presence=snapshot.requires_credential_presence,
        credential_presence_checked=snapshot.credential_presence_checked,
        credential_presence_available=snapshot.credential_presence_available and ready,
        credential_presence_safe_status=_safe_text_label(
            snapshot.credential_presence_safe_status,
        ),
        credential_presence_safe_label=_safe_label(
            snapshot.credential_presence_safe_label,
            SAFE_CREDENTIAL_PRESENCE_LABEL,
        ),
        credential_values_loaded_internal=False,
        actual_post_allowed=False,
        retry_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        credential_value_exposed=False,
        credential_length_exposed=False,
        credential_hash_exposed=False,
        credential_fingerprint_exposed=False,
        credential_metadata_exposed=False,
        signature_value_exposed=False,
        signature_length_exposed=False,
        signature_hash_exposed=False,
        signature_fingerprint_exposed=False,
        headers_value_exposed=False,
        headers_metadata_exposed=False,
        headers_count_exposed=False,
        raw_body_exposed=False,
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
        recommended_next_step=SEALED_CREDENTIAL_SIGNING_RECOMMENDED_NEXT_STEP,
    )


def build_live_order_real_one_shot_post_sealed_credential_signing_from_foundation(
) -> LiveOrderRealOneShotPostSealedCredentialSigningControlledResult:
    """Connect to the sealed request foundation without executing anything."""
    sealed_request_result = (
        build_live_order_real_one_shot_post_sealed_request_result_controlled()
    )
    return build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        sealed_request_result=sealed_request_result,
    )


def render_live_order_real_one_shot_post_sealed_credential_signing_markdown(
    result: LiveOrderRealOneShotPostSealedCredentialSigningControlledResult,
) -> str:
    """Render safe provider readiness only."""
    lines = [
        "# Step 6G Sealed Credential Signing Controlled",
        "",
        "This is a safe provider foundation summary only.",
        "It contains safe labels, statuses, booleans, and blocked reason labels.",
        "It does not expose credential values, signing values, headers values,",
        "raw bodies, raw responses, broker/API responses, or IDs.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- sealed_credential_signing_provider_ready: "
            f"{_bool_text(result.sealed_credential_signing_provider_ready)}"
        ),
        (
            "- sealed_credential_provider_ready: "
            f"{_bool_text(result.sealed_credential_provider_ready)}"
        ),
        (
            "- sealed_signing_provider_ready: "
            f"{_bool_text(result.sealed_signing_provider_ready)}"
        ),
        f"- sealed_headers_ready: {_bool_text(result.sealed_headers_ready)}",
        "",
        "## Prerequisites",
        f"- requires_sealed_request: {_bool_text(result.requires_sealed_request)}",
        f"- requires_sealed_body: {_bool_text(result.requires_sealed_body)}",
        (
            "- requires_credential_presence: "
            f"{_bool_text(result.requires_credential_presence)}"
        ),
        (
            "- credential_presence_checked: "
            f"{_bool_text(result.credential_presence_checked)}"
        ),
        (
            "- credential_presence_available: "
            f"{_bool_text(result.credential_presence_available)}"
        ),
        f"- credential_presence_safe_status: {result.credential_presence_safe_status}",
        f"- credential_presence_safe_label: {result.credential_presence_safe_label}",
        "",
        "## Sealed Objects",
        (
            "- sealed_credential_provider_label: "
            f"{result.sealed_credential_provider.sealed_credential_provider_label}"
        ),
        (
            "- sealed_signing_provider_label: "
            f"{result.sealed_signing_provider.sealed_signing_provider_label}"
        ),
        (
            "- sealed_headers_label: "
            f"{result.sealed_headers_object.sealed_headers_label}"
        ),
        (
            "- headers_present: "
            f"{_bool_text(result.sealed_headers_object.headers_present)}"
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
        f"- credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        (
            "- credential_length_exposed: "
            f"{_bool_text(result.credential_length_exposed)}"
        ),
        (
            "- credential_hash_exposed: "
            f"{_bool_text(result.credential_hash_exposed)}"
        ),
        (
            "- credential_fingerprint_exposed: "
            f"{_bool_text(result.credential_fingerprint_exposed)}"
        ),
        (
            "- credential_metadata_exposed: "
            f"{_bool_text(result.credential_metadata_exposed)}"
        ),
        f"- signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        (
            "- signature_length_exposed: "
            f"{_bool_text(result.signature_length_exposed)}"
        ),
        (
            "- signature_hash_exposed: "
            f"{_bool_text(result.signature_hash_exposed)}"
        ),
        (
            "- signature_fingerprint_exposed: "
            f"{_bool_text(result.signature_fingerprint_exposed)}"
        ),
        f"- headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"- headers_metadata_exposed: {_bool_text(result.headers_metadata_exposed)}",
        f"- headers_count_exposed: {_bool_text(result.headers_count_exposed)}",
        f"- raw_body_exposed: {_bool_text(result.raw_body_exposed)}",
        f"- raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        f"- id_exposed: {_bool_text(result.id_exposed)}",
        f"- actual_post_allowed: {_bool_text(result.actual_post_allowed)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- ledger_update_allowed: {_bool_text(result.ledger_update_allowed)}",
        f"- receipt_handoff_allowed: {_bool_text(result.receipt_handoff_allowed)}",
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


def _merge_safe_prerequisites(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
    *,
    sealed_request_result: (
        LiveOrderRealOneShotPostSealedRequestResultControlledResult | None
    ),
    credential_presence_result: object | None,
) -> LiveOrderRealOneShotPostSealedCredentialSigningControlledInput:
    if sealed_request_result is not None:
        snapshot = replace(
            snapshot,
            sealed_request_model_ready=(
                snapshot.sealed_request_model_ready
                and sealed_request_result.sealed_request_model_ready
            ),
            sealed_body_builder_ready=(
                snapshot.sealed_body_builder_ready
                and sealed_request_result.sealed_body_builder_ready
            ),
        )
    if credential_presence_result is not None:
        ready = bool(
            getattr(
                credential_presence_result,
                "credential_presence_controlled_ready",
                False,
            ),
        )
        available = bool(
            getattr(credential_presence_result, "all_required_credentials_present", False),
        )
        status = getattr(credential_presence_result, "status", "")
        status_value = getattr(status, "value", status)
        snapshot = replace(
            snapshot,
            credential_presence_checked=True,
            credential_presence_available=(
                snapshot.credential_presence_available and ready and available
            ),
            credential_presence_safe_status=(
                status_value
                if isinstance(status_value, str) and status_value
                else snapshot.credential_presence_safe_status
            ),
        )
    return snapshot


def _provider_status(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[
    LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus,
    tuple[str, ...],
]:
    raw_reasons = _raw_exposure_reasons(snapshot)
    if raw_reasons:
        return (
            SealedCredentialSigningStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE,
            raw_reasons,
        )
    credential_reasons = _credential_exposure_reasons(snapshot)
    if credential_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            credential_reasons,
        )
    signing_reasons = _signing_exposure_reasons(snapshot)
    if signing_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE,
            signing_reasons,
        )
    headers_reasons = _headers_exposure_reasons(snapshot)
    if headers_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE,
            headers_reasons,
        )
    if snapshot.id_exposure_attempted:
        return (
            SealedCredentialSigningStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_ID_EXPOSURE,
            ("id_exposure_attempted",),
        )
    execution_reasons = _execution_reasons(snapshot)
    if execution_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION,
            execution_reasons,
        )
    lifecycle_reasons = _lifecycle_reasons(snapshot)
    if lifecycle_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            lifecycle_reasons,
        )
    if snapshot.requires_sealed_request and not snapshot.sealed_request_model_ready:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_REQUEST,
            ("sealed_request_model_missing",),
        )
    if snapshot.requires_sealed_body and not snapshot.sealed_body_builder_ready:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_BODY,
            ("sealed_body_builder_missing",),
        )
    if snapshot.requires_credential_presence and not snapshot.credential_presence_checked:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_CREDENTIAL_PRESENCE,
            ("credential_presence_not_checked",),
        )
    if snapshot.requires_credential_presence and not snapshot.credential_presence_available:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_UNAVAILABLE,
            ("credential_presence_unavailable",),
        )
    provider_reasons = _provider_declaration_reasons(snapshot)
    if provider_reasons:
        return (
            SealedCredentialSigningStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            provider_reasons,
        )
    return SealedCredentialSigningStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST, ()


def _credential_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.credential_values_loaded_internal:
        reasons.append("credential_values_loaded_internal")
    if snapshot.credential_value_exposure_attempted:
        reasons.append("credential_value_exposure_attempted")
    if snapshot.credential_length_exposure_attempted:
        reasons.append("credential_length_exposure_attempted")
    if snapshot.credential_hash_exposure_attempted:
        reasons.append("credential_hash_exposure_attempted")
    if snapshot.credential_fingerprint_exposure_attempted:
        reasons.append("credential_fingerprint_exposure_attempted")
    if snapshot.credential_metadata_exposure_attempted:
        reasons.append("credential_metadata_exposure_attempted")
    return tuple(reasons)


def _signing_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.signature_value_exposure_attempted:
        reasons.append("signature_value_exposure_attempted")
    if snapshot.signature_length_exposure_attempted:
        reasons.append("signature_length_exposure_attempted")
    if snapshot.signature_hash_exposure_attempted:
        reasons.append("signature_hash_exposure_attempted")
    if snapshot.signature_fingerprint_exposure_attempted:
        reasons.append("signature_fingerprint_exposure_attempted")
    return tuple(reasons)


def _headers_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.headers_value_exposure_attempted:
        reasons.append("headers_value_exposure_attempted")
    if snapshot.headers_metadata_exposure_attempted:
        reasons.append("headers_metadata_exposure_attempted")
    if snapshot.headers_count_exposure_attempted:
        reasons.append("headers_count_exposure_attempted")
    return tuple(reasons)


def _raw_exposure_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if snapshot.raw_body_exposure_attempted:
        reasons.append("raw_body_exposure_attempted")
    if snapshot.raw_response_exposure_attempted:
        reasons.append("raw_response_exposure_attempted")
    if snapshot.broker_api_response_exposure_attempted:
        reasons.append("broker_api_response_exposure_attempted")
    return tuple(reasons)


def _execution_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
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
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
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


def _provider_declaration_reasons(
    snapshot: LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
) -> tuple[str, ...]:
    reasons = []
    if not snapshot.sealed_credential_provider_declared:
        reasons.append("sealed_credential_provider_missing")
    if not snapshot.sealed_signing_provider_declared:
        reasons.append("sealed_signing_provider_missing")
    if not snapshot.sealed_headers_declared:
        reasons.append("sealed_headers_missing")
    if not snapshot.signing_generation_internal_only:
        reasons.append("sealed_signing_not_internal_only")
    if not snapshot.headers_present:
        reasons.append("sealed_headers_not_present")
    return tuple(reasons)


def _validate_provider_result_safety(
    result: LiveOrderRealOneShotPostSealedCredentialSigningControlledResult,
) -> None:
    if any((
        result.actual_post_allowed,
        result.retry_allowed,
        result.ledger_update_allowed,
        result.receipt_handoff_allowed,
        result.credential_value_exposed,
        result.credential_length_exposed,
        result.credential_hash_exposed,
        result.credential_fingerprint_exposed,
        result.credential_metadata_exposed,
        result.signature_value_exposed,
        result.signature_length_exposed,
        result.signature_hash_exposed,
        result.signature_fingerprint_exposed,
        result.headers_value_exposed,
        result.headers_metadata_exposed,
        result.headers_count_exposed,
        result.raw_body_exposed,
        result.raw_response_exposed,
        result.broker_api_response_exposed,
        result.id_exposed,
        result.real_account_order_transaction_id_exposed,
        result.actual_http_post_executed,
        result.order_endpoint_executed,
        result.live_order_once_executed,
        result.post_execution_count != 0,
        result.second_post_attempted,
        result.retry_attempted,
        result.ledger_updated,
        result.attempt_counter_persisted,
        result.actual_receipt_handoff_executed,
        result.approved_primitive_actual_source_available,
    )):
        raise LiveVerificationValidationError(
            "sealed credential signing provider crossed safety boundary",
        )


def _validate_credential_provider_summary_safety(
    result: LiveOrderRealSealedCredentialProviderSummary,
) -> None:
    if any((
        result.credential_values_loaded_internal,
        result.credential_value_exposed,
        result.credential_length_exposed,
        result.credential_hash_exposed,
        result.credential_fingerprint_exposed,
        result.credential_metadata_exposed,
    )):
        raise LiveVerificationValidationError("sealed credential provider exposed data")


def _validate_signing_provider_summary_safety(
    result: LiveOrderRealSealedSigningProviderSummary,
) -> None:
    if any((
        result.signature_value_exposed,
        result.signature_length_exposed,
        result.signature_hash_exposed,
        result.signature_fingerprint_exposed,
        result.raw_body_exposed,
    )):
        raise LiveVerificationValidationError("sealed signing provider exposed data")


def _validate_headers_summary_safety(
    result: LiveOrderRealSealedHeadersObject,
) -> None:
    if any((
        result.headers_value_exposed,
        result.headers_metadata_exposed,
        result.headers_count_exposed,
    )):
        raise LiveVerificationValidationError("sealed headers object exposed data")


def _safe_label(value: str, expected: str) -> str:
    return value if value == expected else UNSUPPORTED_SEALED_CREDENTIAL_SIGNING_LABEL


def _safe_text_label(value: str) -> str:
    if isinstance(value, str) and value in _ALLOWED_SAFE_TEXT_LABELS:
        return value
    return UNSUPPORTED_SEALED_CREDENTIAL_SIGNING_LABEL


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


_SEALED_CREDENTIAL_PROVIDER_BOOL_FIELDS = (
    "sealed_credential_provider_ready",
    "credential_presence_required",
    "credential_presence_checked",
    "credential_presence_available",
    "credential_values_loaded_internal",
    "credential_value_exposed",
    "credential_length_exposed",
    "credential_hash_exposed",
    "credential_fingerprint_exposed",
    "credential_metadata_exposed",
)

_SEALED_SIGNING_PROVIDER_BOOL_FIELDS = (
    "sealed_signing_provider_ready",
    "requires_sealed_request",
    "requires_sealed_body",
    "requires_sealed_credential_provider",
    "signing_generation_internal_only",
    "signature_value_exposed",
    "signature_length_exposed",
    "signature_hash_exposed",
    "signature_fingerprint_exposed",
    "raw_body_exposed",
)

_SEALED_HEADERS_BOOL_FIELDS = (
    "sealed_headers_ready",
    "headers_present",
    "headers_value_exposed",
    "headers_metadata_exposed",
    "headers_count_exposed",
)

_SEALED_CREDENTIAL_SIGNING_INPUT_BOOL_FIELDS = (
    "requires_sealed_request",
    "requires_sealed_body",
    "requires_credential_presence",
    "sealed_request_model_ready",
    "sealed_body_builder_ready",
    "sealed_credential_provider_declared",
    "sealed_signing_provider_declared",
    "sealed_headers_declared",
    "credential_presence_checked",
    "credential_presence_available",
    "credential_values_loaded_internal",
    "signing_generation_internal_only",
    "headers_present",
    "credential_value_exposure_attempted",
    "credential_length_exposure_attempted",
    "credential_hash_exposure_attempted",
    "credential_fingerprint_exposure_attempted",
    "credential_metadata_exposure_attempted",
    "signature_value_exposure_attempted",
    "signature_length_exposure_attempted",
    "signature_hash_exposure_attempted",
    "signature_fingerprint_exposure_attempted",
    "headers_value_exposure_attempted",
    "headers_metadata_exposure_attempted",
    "headers_count_exposure_attempted",
    "raw_body_exposure_attempted",
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

_SEALED_CREDENTIAL_SIGNING_RESULT_BOOL_FIELDS = (
    "sealed_credential_signing_provider_ready",
    "sealed_credential_provider_ready",
    "sealed_signing_provider_ready",
    "sealed_headers_ready",
    "requires_sealed_request",
    "requires_sealed_body",
    "requires_credential_presence",
    "credential_presence_checked",
    "credential_presence_available",
    "credential_values_loaded_internal",
    "actual_post_allowed",
    "retry_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "credential_value_exposed",
    "credential_length_exposed",
    "credential_hash_exposed",
    "credential_fingerprint_exposed",
    "credential_metadata_exposed",
    "signature_value_exposed",
    "signature_length_exposed",
    "signature_hash_exposed",
    "signature_fingerprint_exposed",
    "headers_value_exposed",
    "headers_metadata_exposed",
    "headers_count_exposed",
    "raw_body_exposed",
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

_ALLOWED_SAFE_TEXT_LABELS = frozenset(
    {
        DEFAULT_CREDENTIAL_PRESENCE_SAFE_STATUS,
        "CREDENTIAL_PRESENCE_MISSING_NO_POST",
        "CREDENTIAL_PRESENCE_BLOCKED_UNKNOWN",
        "CREDENTIAL_PRESENCE_BLOCKED_FAILED",
        "CREDENTIAL_PRESENCE_BLOCKED_UNAVAILABLE",
        "CREDENTIAL_PRESENCE_BLOCKED_TIMEOUT",
        UNSUPPORTED_SEALED_CREDENTIAL_SIGNING_LABEL,
    },
)
