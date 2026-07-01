"""Step 6G controlled signing and headers boundary.

This module converts a safe credential-injection result into signing and
headers readiness labels, safe statuses, and booleans only. It does not receive
credential values or raw handles, generate signature or headers values, read
env, call APIs, execute transport, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_credential_injection_controlled import (
    SAFE_CREDENTIAL_HANDLE_LABEL,
    LiveOrderRealCredentialInjectionControlledResult,
)

SIGNING_HEADERS_CONTROLLED_RECOMMENDED_NEXT_STEP = (
    "signing_headers_controlled_boundary_review_no_signature_values_no_api_no_post"
)
SAFE_SIGNING_LABEL = "CONTROLLED_SIGNING_BOUNDARY"
SAFE_HEADERS_LABEL = "CONTROLLED_HEADERS_BOUNDARY"
UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealSigningHeadersControlledStatus(str, Enum):
    SIGNING_HEADERS_NOT_READY = "SIGNING_HEADERS_NOT_READY"
    SIGNING_HEADERS_READY_NO_TRANSPORT = "SIGNING_HEADERS_READY_NO_TRANSPORT"
    SIGNING_HEADERS_BLOCKED_MISSING_INJECTION = (
        "SIGNING_HEADERS_BLOCKED_MISSING_INJECTION"
    )
    SIGNING_HEADERS_BLOCKED_UNKNOWN = "SIGNING_HEADERS_BLOCKED_UNKNOWN"
    SIGNING_HEADERS_BLOCKED_FAILED = "SIGNING_HEADERS_BLOCKED_FAILED"
    SIGNING_HEADERS_BLOCKED_UNAVAILABLE = "SIGNING_HEADERS_BLOCKED_UNAVAILABLE"
    SIGNING_HEADERS_BLOCKED_TIMEOUT = "SIGNING_HEADERS_BLOCKED_TIMEOUT"
    SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_CREDENTIAL_VALUE_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_CREDENTIAL_VALUE_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_RAW_HANDLE_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_RAW_HANDLE_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_SIGNATURE_VALUE_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_SIGNATURE_VALUE_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_HEADERS_VALUE_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_HEADERS_VALUE_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE = (
        "SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE"
    )
    SIGNING_HEADERS_BLOCKED_TRANSPORT_OR_API = (
        "SIGNING_HEADERS_BLOCKED_TRANSPORT_OR_API"
    )
    SIGNING_HEADERS_BLOCKED_POST_OR_ORDER = "SIGNING_HEADERS_BLOCKED_POST_OR_ORDER"
    SIGNING_HEADERS_BLOCKED_LIVE_ORDER_ONCE = (
        "SIGNING_HEADERS_BLOCKED_LIVE_ORDER_ONCE"
    )


class LiveOrderRealSigningHeadersControlledMode(str, Enum):
    SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY = (
        "SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY"
    )


SigningHeadersControlledStatus = LiveOrderRealSigningHeadersControlledStatus
SigningHeadersControlledMode = LiveOrderRealSigningHeadersControlledMode


@dataclass(frozen=True)
class LiveOrderRealSigningHeadersControlledInput:
    signing_headers_mode: str = (
        SigningHeadersControlledMode
        .SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    )
    signing_declared: bool = True
    headers_declared: bool = True
    signing_requested: bool = True
    headers_requested: bool = True
    injection_prerequisite_checked: bool = True
    credential_injection_controlled_ready: bool = True
    credential_injection_ready: bool = True
    injection_prerequisite_satisfied: bool = True
    safe_credential_handle_label: str = SAFE_CREDENTIAL_HANDLE_LABEL
    safe_injection_status: str = "CREDENTIAL_INJECTION_READY_NO_SIGNING"
    safe_signing_label: str = SAFE_SIGNING_LABEL
    safe_headers_label: str = SAFE_HEADERS_LABEL
    signing_unknown: bool = False
    signing_failed: bool = False
    signing_unavailable: bool = False
    signing_timeout: bool = False
    headers_unknown: bool = False
    headers_failed: bool = False
    headers_unavailable: bool = False
    headers_timeout: bool = False
    unsafe_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    credential_raw_handle_exposure_attempted: bool = False
    credential_metadata_exposure_attempted: bool = False
    credential_length_exposure_attempted: bool = False
    credential_hash_exposure_attempted: bool = False
    credential_fingerprint_exposure_attempted: bool = False
    env_actual_name_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    signature_length_exposure_attempted: bool = False
    signature_hash_exposure_attempted: bool = False
    signature_fingerprint_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    headers_metadata_exposure_attempted: bool = False
    real_signing_attempted: bool = False
    real_headers_generation_attempted: bool = False
    real_transport_allowed: bool = False
    real_transport_attempted: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("signing_headers_mode", self.signing_headers_mode)
        _require_non_empty("safe_credential_handle_label", self.safe_credential_handle_label)
        _require_non_empty("safe_injection_status", self.safe_injection_status)
        _require_non_empty("safe_signing_label", self.safe_signing_label)
        _require_non_empty("safe_headers_label", self.safe_headers_label)
        _validate_bool_fields(
            self,
            (
                "signing_declared",
                "headers_declared",
                "signing_requested",
                "headers_requested",
                "injection_prerequisite_checked",
                "credential_injection_controlled_ready",
                "credential_injection_ready",
                "injection_prerequisite_satisfied",
                "signing_unknown",
                "signing_failed",
                "signing_unavailable",
                "signing_timeout",
                "headers_unknown",
                "headers_failed",
                "headers_unavailable",
                "headers_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "credential_raw_handle_exposure_attempted",
                "credential_metadata_exposure_attempted",
                "credential_length_exposure_attempted",
                "credential_hash_exposure_attempted",
                "credential_fingerprint_exposure_attempted",
                "env_actual_name_exposure_attempted",
                "signature_value_exposure_attempted",
                "signature_length_exposure_attempted",
                "signature_hash_exposure_attempted",
                "signature_fingerprint_exposure_attempted",
                "headers_value_exposure_attempted",
                "headers_metadata_exposure_attempted",
                "real_signing_attempted",
                "real_headers_generation_attempted",
                "real_transport_allowed",
                "real_transport_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealSigningHeadersControlledCheckResult:
    name: str
    passed: bool
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealSigningHeadersControlledResult:
    status: LiveOrderRealSigningHeadersControlledStatus
    signing_headers_controlled_ready: bool
    signing_controlled_ready: bool
    headers_controlled_ready: bool
    signing_headers_mode: str
    signing_declared: bool
    headers_declared: bool
    signing_requested: bool
    headers_requested: bool
    injection_prerequisite_checked: bool
    injection_prerequisite_satisfied: bool
    credential_injection_controlled_ready: bool
    credential_injection_ready: bool
    safe_credential_handle_label: str
    safe_injection_status: str
    safe_signing_label: str
    safe_headers_label: str
    safe_signing_status: str
    safe_headers_status: str
    signing_unknown: bool
    signing_failed: bool
    signing_unavailable: bool
    signing_timeout: bool
    headers_unknown: bool
    headers_failed: bool
    headers_unavailable: bool
    headers_timeout: bool
    unsafe_exposure_attempted: bool
    credential_value_exposure_attempted: bool
    credential_raw_handle_exposure_attempted: bool
    credential_metadata_exposure_attempted: bool
    credential_length_exposure_attempted: bool
    credential_hash_exposure_attempted: bool
    credential_fingerprint_exposure_attempted: bool
    env_actual_name_exposure_attempted: bool
    signature_value_exposure_attempted: bool
    signature_length_exposure_attempted: bool
    signature_hash_exposure_attempted: bool
    signature_fingerprint_exposure_attempted: bool
    headers_value_exposure_attempted: bool
    headers_metadata_exposure_attempted: bool
    real_signing_attempted: bool
    real_headers_generation_attempted: bool
    real_transport_allowed: bool
    real_transport_attempted: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealSigningHeadersControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealSigningHeadersControlledStatus):
            raise LiveVerificationValidationError(
                "status must be signing headers controlled status",
            )
        _require_non_empty("signing_headers_mode", self.signing_headers_mode)
        _require_non_empty("safe_credential_handle_label", self.safe_credential_handle_label)
        _require_non_empty("safe_injection_status", self.safe_injection_status)
        _require_non_empty("safe_signing_label", self.safe_signing_label)
        _require_non_empty("safe_headers_label", self.safe_headers_label)
        _require_non_empty("safe_signing_status", self.safe_signing_status)
        _require_non_empty("safe_headers_status", self.safe_headers_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "signing_headers_controlled_ready",
                "signing_controlled_ready",
                "headers_controlled_ready",
                "signing_declared",
                "headers_declared",
                "signing_requested",
                "headers_requested",
                "injection_prerequisite_checked",
                "injection_prerequisite_satisfied",
                "credential_injection_controlled_ready",
                "credential_injection_ready",
                "signing_unknown",
                "signing_failed",
                "signing_unavailable",
                "signing_timeout",
                "headers_unknown",
                "headers_failed",
                "headers_unavailable",
                "headers_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "credential_raw_handle_exposure_attempted",
                "credential_metadata_exposure_attempted",
                "credential_length_exposure_attempted",
                "credential_hash_exposure_attempted",
                "credential_fingerprint_exposure_attempted",
                "env_actual_name_exposure_attempted",
                "signature_value_exposure_attempted",
                "signature_length_exposure_attempted",
                "signature_hash_exposure_attempted",
                "signature_fingerprint_exposure_attempted",
                "headers_value_exposure_attempted",
                "headers_metadata_exposure_attempted",
                "real_signing_attempted",
                "real_headers_generation_attempted",
                "real_transport_allowed",
                "real_transport_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_signing_headers_controlled(
    *,
    input_snapshot: LiveOrderRealSigningHeadersControlledInput | None = None,
    injection_result: LiveOrderRealCredentialInjectionControlledResult | None = None,
) -> LiveOrderRealSigningHeadersControlledResult:
    """Build a safe signing and headers readiness result without values."""
    snapshot = input_snapshot or LiveOrderRealSigningHeadersControlledInput()
    if injection_result is not None:
        snapshot = _merge_injection_result(snapshot, injection_result)

    status, primary_reasons = _status_from_input(snapshot)
    blocked_reasons = _blocked_reasons(snapshot=snapshot, primary_reasons=primary_reasons)
    ready = status is SigningHeadersControlledStatus.SIGNING_HEADERS_READY_NO_TRANSPORT
    injection_satisfied = (
        snapshot.injection_prerequisite_checked
        and snapshot.credential_injection_controlled_ready
        and snapshot.credential_injection_ready
        and snapshot.injection_prerequisite_satisfied
        and snapshot.safe_credential_handle_label == SAFE_CREDENTIAL_HANDLE_LABEL
        and not snapshot.signing_unknown
        and not snapshot.signing_failed
        and not snapshot.signing_unavailable
        and not snapshot.signing_timeout
        and not snapshot.headers_unknown
        and not snapshot.headers_failed
        and not snapshot.headers_unavailable
        and not snapshot.headers_timeout
    )
    safe_mode = (
        snapshot.signing_headers_mode
        if snapshot.signing_headers_mode
        == SigningHeadersControlledMode.SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY.value
        else UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL
    )
    safe_credential_label = (
        snapshot.safe_credential_handle_label
        if snapshot.safe_credential_handle_label == SAFE_CREDENTIAL_HANDLE_LABEL
        else UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL
    )
    safe_signing_label = (
        snapshot.safe_signing_label
        if snapshot.safe_signing_label == SAFE_SIGNING_LABEL
        else UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL
    )
    safe_headers_label = (
        snapshot.safe_headers_label
        if snapshot.safe_headers_label == SAFE_HEADERS_LABEL
        else UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL
    )

    return LiveOrderRealSigningHeadersControlledResult(
        status=status,
        signing_headers_controlled_ready=ready,
        signing_controlled_ready=ready,
        headers_controlled_ready=ready,
        signing_headers_mode=safe_mode,
        signing_declared=snapshot.signing_declared,
        headers_declared=snapshot.headers_declared,
        signing_requested=snapshot.signing_requested,
        headers_requested=snapshot.headers_requested,
        injection_prerequisite_checked=snapshot.injection_prerequisite_checked,
        injection_prerequisite_satisfied=injection_satisfied,
        credential_injection_controlled_ready=snapshot.credential_injection_controlled_ready,
        credential_injection_ready=snapshot.credential_injection_ready,
        safe_credential_handle_label=safe_credential_label,
        safe_injection_status=snapshot.safe_injection_status,
        safe_signing_label=safe_signing_label,
        safe_headers_label=safe_headers_label,
        safe_signing_status=status.value,
        safe_headers_status=status.value,
        signing_unknown=snapshot.signing_unknown,
        signing_failed=snapshot.signing_failed,
        signing_unavailable=snapshot.signing_unavailable,
        signing_timeout=snapshot.signing_timeout,
        headers_unknown=snapshot.headers_unknown,
        headers_failed=snapshot.headers_failed,
        headers_unavailable=snapshot.headers_unavailable,
        headers_timeout=snapshot.headers_timeout,
        unsafe_exposure_attempted=False,
        credential_value_exposure_attempted=False,
        credential_raw_handle_exposure_attempted=False,
        credential_metadata_exposure_attempted=False,
        credential_length_exposure_attempted=False,
        credential_hash_exposure_attempted=False,
        credential_fingerprint_exposure_attempted=False,
        env_actual_name_exposure_attempted=False,
        signature_value_exposure_attempted=False,
        signature_length_exposure_attempted=False,
        signature_hash_exposure_attempted=False,
        signature_fingerprint_exposure_attempted=False,
        headers_value_exposure_attempted=False,
        headers_metadata_exposure_attempted=False,
        real_signing_attempted=False,
        real_headers_generation_attempted=False,
        real_transport_allowed=False,
        real_transport_attempted=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            injection_satisfied=injection_satisfied,
            safe_signing_label=safe_signing_label,
            safe_headers_label=safe_headers_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            SIGNING_HEADERS_CONTROLLED_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_signing_headers_controlled_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_signing_headers_controlled_markdown(
    result: LiveOrderRealSigningHeadersControlledResult,
) -> str:
    """Render a safe controlled signing and headers summary only."""
    lines = [
        "# Step 6G Signing Headers Controlled Boundary",
        "",
        "This is a controlled signing and headers boundary, not real signing.",
        "This result contains only safe labels, safe statuses, and booleans.",
        "This result does not contain credential values.",
        "This result does not contain raw handle values.",
        "This result does not calculate credential length, hash, or fingerprint.",
        "This result does not expose credential metadata.",
        "This result does not expose env actual names.",
        "This result does not contain signature values.",
        "This result does not contain headers values.",
        "This result does not calculate signature length, hash, or fingerprint.",
        "This result does not expose headers metadata.",
        "Signing ready does not allow API calls.",
        "Signing ready does not allow HTTP POST.",
        "Signing ready does not allow real transport.",
        "Signing ready does not allow live_order_once.",
        "Headers ready does not allow headers value display.",
        "Headers ready does not allow API calls.",
        "Missing, unknown, failed, unavailable, and timeout states fail closed.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- signing_headers_controlled_ready: "
            f"{_bool_text(result.signing_headers_controlled_ready)}"
        ),
        f"- signing_controlled_ready: {_bool_text(result.signing_controlled_ready)}",
        f"- headers_controlled_ready: {_bool_text(result.headers_controlled_ready)}",
        f"- signing_headers_mode: {result.signing_headers_mode}",
        f"- safe_signing_label: {result.safe_signing_label}",
        f"- safe_headers_label: {result.safe_headers_label}",
        f"- safe_signing_status: {result.safe_signing_status}",
        f"- safe_headers_status: {result.safe_headers_status}",
        (
            "- injection_prerequisite_checked: "
            f"{_bool_text(result.injection_prerequisite_checked)}"
        ),
        (
            "- injection_prerequisite_satisfied: "
            f"{_bool_text(result.injection_prerequisite_satisfied)}"
        ),
        (
            "- credential_injection_controlled_ready: "
            f"{_bool_text(result.credential_injection_controlled_ready)}"
        ),
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        "",
        "## Safety",
        f"- unsafe_exposure_attempted: {_bool_text(result.unsafe_exposure_attempted)}",
        (
            "- credential_value_exposure_attempted: "
            f"{_bool_text(result.credential_value_exposure_attempted)}"
        ),
        (
            "- credential_raw_handle_exposure_attempted: "
            f"{_bool_text(result.credential_raw_handle_exposure_attempted)}"
        ),
        (
            "- credential_metadata_exposure_attempted: "
            f"{_bool_text(result.credential_metadata_exposure_attempted)}"
        ),
        (
            "- credential_length_exposure_attempted: "
            f"{_bool_text(result.credential_length_exposure_attempted)}"
        ),
        (
            "- credential_hash_exposure_attempted: "
            f"{_bool_text(result.credential_hash_exposure_attempted)}"
        ),
        (
            "- credential_fingerprint_exposure_attempted: "
            f"{_bool_text(result.credential_fingerprint_exposure_attempted)}"
        ),
        (
            "- env_actual_name_exposure_attempted: "
            f"{_bool_text(result.env_actual_name_exposure_attempted)}"
        ),
        (
            "- signature_value_exposure_attempted: "
            f"{_bool_text(result.signature_value_exposure_attempted)}"
        ),
        (
            "- signature_length_exposure_attempted: "
            f"{_bool_text(result.signature_length_exposure_attempted)}"
        ),
        (
            "- signature_hash_exposure_attempted: "
            f"{_bool_text(result.signature_hash_exposure_attempted)}"
        ),
        (
            "- signature_fingerprint_exposure_attempted: "
            f"{_bool_text(result.signature_fingerprint_exposure_attempted)}"
        ),
        (
            "- headers_value_exposure_attempted: "
            f"{_bool_text(result.headers_value_exposure_attempted)}"
        ),
        (
            "- headers_metadata_exposure_attempted: "
            f"{_bool_text(result.headers_metadata_exposure_attempted)}"
        ),
        f"- real_signing_attempted: {_bool_text(result.real_signing_attempted)}",
        (
            "- real_headers_generation_attempted: "
            f"{_bool_text(result.real_headers_generation_attempted)}"
        ),
        f"- real_transport_allowed: {_bool_text(result.real_transport_allowed)}",
        f"- real_transport_attempted: {_bool_text(result.real_transport_attempted)}",
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- api_call_attempted: {_bool_text(result.api_call_attempted)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        (
            "- actual_checker_execution_performed: "
            f"{_bool_text(result.actual_checker_execution_performed)}"
        ),
        (
            "- actual_result_receipt_received: "
            f"{_bool_text(result.actual_result_receipt_received)}"
        ),
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        f"recommended_next_step: {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_injection_result(
    snapshot: LiveOrderRealSigningHeadersControlledInput,
    injection_result: LiveOrderRealCredentialInjectionControlledResult,
) -> LiveOrderRealSigningHeadersControlledInput:
    return replace(
        snapshot,
        injection_prerequisite_checked=injection_result.presence_prerequisite_checked,
        credential_injection_controlled_ready=injection_result.credential_injection_ready,
        credential_injection_ready=injection_result.credential_injection_ready,
        injection_prerequisite_satisfied=(
            injection_result.presence_prerequisite_satisfied
            and injection_result.credential_injection_ready
        ),
        safe_credential_handle_label=injection_result.safe_credential_handle_label,
        safe_injection_status=injection_result.safe_injection_status,
        signing_unknown=snapshot.signing_unknown or injection_result.presence_unknown,
        signing_failed=snapshot.signing_failed or injection_result.presence_failed,
        signing_unavailable=(
            snapshot.signing_unavailable or injection_result.presence_unavailable
        ),
        signing_timeout=snapshot.signing_timeout or injection_result.presence_timeout,
        headers_unknown=snapshot.headers_unknown or injection_result.presence_unknown,
        headers_failed=snapshot.headers_failed or injection_result.presence_failed,
        headers_unavailable=(
            snapshot.headers_unavailable or injection_result.presence_unavailable
        ),
        headers_timeout=snapshot.headers_timeout or injection_result.presence_timeout,
        unsafe_exposure_attempted=(
            snapshot.unsafe_exposure_attempted
            or injection_result.unsafe_exposure_attempted
        ),
        credential_value_exposure_attempted=(
            snapshot.credential_value_exposure_attempted
            or injection_result.credential_value_exposure_attempted
        ),
        credential_raw_handle_exposure_attempted=(
            snapshot.credential_raw_handle_exposure_attempted
            or injection_result.credential_raw_handle_exposure_attempted
        ),
        credential_metadata_exposure_attempted=(
            snapshot.credential_metadata_exposure_attempted
            or injection_result.credential_metadata_exposure_attempted
        ),
        credential_length_exposure_attempted=(
            snapshot.credential_length_exposure_attempted
            or injection_result.credential_length_exposure_attempted
        ),
        credential_hash_exposure_attempted=(
            snapshot.credential_hash_exposure_attempted
            or injection_result.credential_hash_exposure_attempted
        ),
        credential_fingerprint_exposure_attempted=(
            snapshot.credential_fingerprint_exposure_attempted
            or injection_result.credential_fingerprint_exposure_attempted
        ),
        env_actual_name_exposure_attempted=(
            snapshot.env_actual_name_exposure_attempted
            or injection_result.env_actual_name_exposure_attempted
        ),
        real_signing_attempted=(
            snapshot.real_signing_attempted
            or injection_result.can_generate_real_signature
            or injection_result.real_signing_allowed
        ),
        real_headers_generation_attempted=(
            snapshot.real_headers_generation_attempted
            or injection_result.can_generate_real_headers
            or injection_result.real_headers_generation_allowed
        ),
        real_transport_allowed=(
            snapshot.real_transport_allowed or injection_result.real_transport_allowed
        ),
        api_call_allowed=snapshot.api_call_allowed or injection_result.api_call_allowed,
        api_call_attempted=snapshot.api_call_attempted or injection_result.api_call_attempted,
        http_post_executed=snapshot.http_post_executed or injection_result.http_post_executed,
        order_endpoint_called=(
            snapshot.order_endpoint_called or injection_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or injection_result.live_order_once_called
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or injection_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or injection_result.post_executed,
        actual_checker_execution_performed=(
            snapshot.actual_checker_execution_performed
            or injection_result.actual_checker_execution_performed
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or injection_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or injection_result.actual_receipt_handoff_executed
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or injection_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or injection_result.final_confirmation_received
        ),
        safe_to_render=snapshot.safe_to_render and injection_result.safe_to_render,
        safe_to_serialize=snapshot.safe_to_serialize and injection_result.safe_to_serialize,
    )


def _status_from_input(
    snapshot: LiveOrderRealSigningHeadersControlledInput,
) -> tuple[LiveOrderRealSigningHeadersControlledStatus, tuple[str, ...]]:
    if (
        snapshot.signing_headers_mode
        != SigningHeadersControlledMode.SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY.value
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_UNKNOWN,
            ("unsupported_signing_headers_mode",),
        )
    if (
        not snapshot.signing_declared
        or not snapshot.headers_declared
        or not snapshot.signing_requested
        or not snapshot.headers_requested
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_NOT_READY,
            ("signing_headers_not_declared_or_requested",),
        )
    if (
        snapshot.safe_credential_handle_label != SAFE_CREDENTIAL_HANDLE_LABEL
        or snapshot.safe_signing_label != SAFE_SIGNING_LABEL
        or snapshot.safe_headers_label != SAFE_HEADERS_LABEL
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
            ("safe_signing_headers_label_not_fixed",),
        )
    if snapshot.signing_unknown or snapshot.headers_unknown:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_UNKNOWN,
            ("signing_headers_unknown",),
        )
    if snapshot.signing_failed or snapshot.headers_failed:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_FAILED,
            ("signing_headers_failed",),
        )
    if snapshot.signing_unavailable or snapshot.headers_unavailable:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_UNAVAILABLE,
            ("signing_headers_unavailable",),
        )
    if snapshot.signing_timeout or snapshot.headers_timeout:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_TIMEOUT,
            ("signing_headers_timeout",),
        )
    if (
        not snapshot.injection_prerequisite_checked
        or not snapshot.credential_injection_controlled_ready
        or not snapshot.credential_injection_ready
        or not snapshot.injection_prerequisite_satisfied
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION,
            ("credential_injection_prerequisite_missing",),
        )
    if snapshot.credential_value_exposure_attempted:
        return (
            SigningHeadersControlledStatus
            .SIGNING_HEADERS_BLOCKED_CREDENTIAL_VALUE_EXPOSURE,
            ("credential_value_exposure_attempted",),
        )
    if snapshot.credential_raw_handle_exposure_attempted:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_RAW_HANDLE_EXPOSURE,
            ("credential_raw_handle_exposure_attempted",),
        )
    if snapshot.credential_metadata_exposure_attempted:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE,
            ("credential_metadata_exposure_attempted",),
        )
    if snapshot.signature_value_exposure_attempted:
        return (
            SigningHeadersControlledStatus
            .SIGNING_HEADERS_BLOCKED_SIGNATURE_VALUE_EXPOSURE,
            ("signature_value_exposure_attempted",),
        )
    if snapshot.headers_value_exposure_attempted:
        return (
            SigningHeadersControlledStatus
            .SIGNING_HEADERS_BLOCKED_HEADERS_VALUE_EXPOSURE,
            ("headers_value_exposure_attempted",),
        )
    if snapshot.headers_metadata_exposure_attempted:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE,
            ("headers_metadata_exposure_attempted",),
        )
    if (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_length_exposure_attempted
        or snapshot.credential_hash_exposure_attempted
        or snapshot.credential_fingerprint_exposure_attempted
        or snapshot.env_actual_name_exposure_attempted
        or snapshot.signature_length_exposure_attempted
        or snapshot.signature_hash_exposure_attempted
        or snapshot.signature_fingerprint_exposure_attempted
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
            ("signing_headers_unsafe_exposure_attempted",),
        )
    if snapshot.live_order_once_called:
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_attempted",),
        )
    if (
        snapshot.real_signing_attempted
        or snapshot.real_headers_generation_attempted
        or snapshot.real_transport_allowed
        or snapshot.real_transport_attempted
        or snapshot.api_call_allowed
        or snapshot.api_call_attempted
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_TRANSPORT_OR_API,
            ("signing_headers_transport_or_api_attempted",),
        )
    if (
        snapshot.http_post_executed
        or snapshot.order_endpoint_called
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.actual_checker_execution_performed
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.fresh_preflight_executed
        or snapshot.final_confirmation_received
    ):
        return (
            SigningHeadersControlledStatus.SIGNING_HEADERS_BLOCKED_POST_OR_ORDER,
            ("signing_headers_post_order_or_actual_execution_attempted",),
        )
    return (
        SigningHeadersControlledStatus.SIGNING_HEADERS_READY_NO_TRANSPORT,
        (),
    )


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealSigningHeadersControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = list(primary_reasons)
    for field_name in (
        "credential_length_exposure_attempted",
        "credential_hash_exposure_attempted",
        "credential_fingerprint_exposure_attempted",
        "env_actual_name_exposure_attempted",
        "signature_length_exposure_attempted",
        "signature_hash_exposure_attempted",
        "signature_fingerprint_exposure_attempted",
        "actual_checker_execution_performed",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "fresh_preflight_executed",
        "final_confirmation_received",
    ):
        if getattr(snapshot, field_name):
            reasons.append(f"{field_name}_blocked")
    return _dedupe(reasons)


def _build_check_results(
    *,
    snapshot: LiveOrderRealSigningHeadersControlledInput,
    status: LiveOrderRealSigningHeadersControlledStatus,
    ready: bool,
    injection_satisfied: bool,
    safe_signing_label: str,
    safe_headers_label: str,
) -> tuple[LiveOrderRealSigningHeadersControlledCheckResult, ...]:
    return (
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="controlled signing headers mode",
            passed=(
                snapshot.signing_headers_mode
                == SigningHeadersControlledMode
                .SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
            sanitized_value=(
                snapshot.signing_headers_mode
                if snapshot.signing_headers_mode
                == SigningHeadersControlledMode
                .SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY
                .value
                else UNSUPPORTED_SIGNING_HEADERS_CONTROLLED_LABEL
            ),
            expected=(
                SigningHeadersControlledMode
                .SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="controlled injection prerequisite",
            passed=injection_satisfied,
            sanitized_value="satisfied" if injection_satisfied else "blocked",
            expected="safe_injection_boolean_satisfied",
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="safe signing label",
            passed=safe_signing_label == SAFE_SIGNING_LABEL,
            sanitized_value=safe_signing_label,
            expected=SAFE_SIGNING_LABEL,
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="safe headers label",
            passed=safe_headers_label == SAFE_HEADERS_LABEL,
            sanitized_value=safe_headers_label,
            expected=SAFE_HEADERS_LABEL,
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="no credential signature headers exposure",
            passed=not (
                snapshot.unsafe_exposure_attempted
                or snapshot.credential_value_exposure_attempted
                or snapshot.credential_raw_handle_exposure_attempted
                or snapshot.credential_metadata_exposure_attempted
                or snapshot.credential_length_exposure_attempted
                or snapshot.credential_hash_exposure_attempted
                or snapshot.credential_fingerprint_exposure_attempted
                or snapshot.env_actual_name_exposure_attempted
                or snapshot.signature_value_exposure_attempted
                or snapshot.signature_length_exposure_attempted
                or snapshot.signature_hash_exposure_attempted
                or snapshot.signature_fingerprint_exposure_attempted
                or snapshot.headers_value_exposure_attempted
                or snapshot.headers_metadata_exposure_attempted
            ),
            sanitized_value="safe_boolean_only",
            expected="safe_boolean_only",
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="no transport api post live_order_once",
            passed=not (
                snapshot.real_signing_attempted
                or snapshot.real_headers_generation_attempted
                or snapshot.real_transport_allowed
                or snapshot.real_transport_attempted
                or snapshot.api_call_allowed
                or snapshot.api_call_attempted
                or snapshot.http_post_executed
                or snapshot.order_endpoint_called
                or snapshot.live_order_once_called
                or snapshot.post_allowed_this_step
                or snapshot.post_executed
                or snapshot.actual_checker_execution_performed
                or snapshot.actual_result_receipt_received
                or snapshot.actual_receipt_handoff_executed
                or snapshot.fresh_preflight_executed
                or snapshot.final_confirmation_received
            ),
            sanitized_value="not_allowed",
            expected="not_allowed",
        ),
        LiveOrderRealSigningHeadersControlledCheckResult(
            name="ready is not execution permission",
            passed=ready
            and not (
                snapshot.real_transport_allowed
                or snapshot.real_transport_attempted
                or snapshot.api_call_allowed
                or snapshot.post_allowed_this_step
                or snapshot.live_order_once_called
            ),
            sanitized_value=status.value,
            expected="ready_no_transport_no_api_no_post",
        ),
    )


def _validate_result_safety(
    result: LiveOrderRealSigningHeadersControlledResult,
) -> None:
    unsafe_flags = (
        result.unsafe_exposure_attempted,
        result.credential_value_exposure_attempted,
        result.credential_raw_handle_exposure_attempted,
        result.credential_metadata_exposure_attempted,
        result.credential_length_exposure_attempted,
        result.credential_hash_exposure_attempted,
        result.credential_fingerprint_exposure_attempted,
        result.env_actual_name_exposure_attempted,
        result.signature_value_exposure_attempted,
        result.signature_length_exposure_attempted,
        result.signature_hash_exposure_attempted,
        result.signature_fingerprint_exposure_attempted,
        result.headers_value_exposure_attempted,
        result.headers_metadata_exposure_attempted,
        result.real_signing_attempted,
        result.real_headers_generation_attempted,
        result.real_transport_allowed,
        result.real_transport_attempted,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.actual_checker_execution_performed,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.fresh_preflight_executed,
        result.final_confirmation_received,
        not result.safe_to_render,
        not result.safe_to_serialize,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "signing headers controlled result is unsafe",
        )
    if result.signing_headers_controlled_ready and (
        result.safe_signing_label != SAFE_SIGNING_LABEL
        or result.safe_headers_label != SAFE_HEADERS_LABEL
        or result.safe_credential_handle_label != SAFE_CREDENTIAL_HANDLE_LABEL
    ):
        raise LiveVerificationValidationError(
            "signing headers controlled ready requires safe labels",
        )
    if result.signing_headers_controlled_ready and (
        result.api_call_allowed
        or result.post_allowed_this_step
        or result.real_transport_allowed
        or result.live_order_once_called
    ):
        raise LiveVerificationValidationError(
            "signing headers controlled ready is not execution permission",
        )


def _dedupe(values: list[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return tuple(deduped)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} must be non-empty")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
