"""Step 6G controlled credential injection boundary.

This module converts a safe credential-presence result into an opaque handle
label, a safe status, and booleans only. It does not receive credential values
or raw handles, read env, generate signatures or headers, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_credential_presence_controlled import (
    LiveOrderRealCredentialPresenceControlledResult,
)

CREDENTIAL_INJECTION_CONTROLLED_RECOMMENDED_NEXT_STEP = (
    "credential_injection_controlled_boundary_review_no_signing_no_api_no_post"
)
SAFE_CREDENTIAL_HANDLE_LABEL = "CONTROLLED_CREDENTIAL_HANDLE"
UNSUPPORTED_CREDENTIAL_INJECTION_CONTROLLED_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealCredentialInjectionControlledStatus(str, Enum):
    CREDENTIAL_INJECTION_NOT_READY = "CREDENTIAL_INJECTION_NOT_READY"
    CREDENTIAL_INJECTION_READY_NO_SIGNING = (
        "CREDENTIAL_INJECTION_READY_NO_SIGNING"
    )
    CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE = (
        "CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE"
    )
    CREDENTIAL_INJECTION_BLOCKED_UNKNOWN = "CREDENTIAL_INJECTION_BLOCKED_UNKNOWN"
    CREDENTIAL_INJECTION_BLOCKED_FAILED = "CREDENTIAL_INJECTION_BLOCKED_FAILED"
    CREDENTIAL_INJECTION_BLOCKED_UNAVAILABLE = (
        "CREDENTIAL_INJECTION_BLOCKED_UNAVAILABLE"
    )
    CREDENTIAL_INJECTION_BLOCKED_TIMEOUT = "CREDENTIAL_INJECTION_BLOCKED_TIMEOUT"
    CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE = (
        "CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE"
    )
    CREDENTIAL_INJECTION_BLOCKED_VALUE_EXPOSURE = (
        "CREDENTIAL_INJECTION_BLOCKED_VALUE_EXPOSURE"
    )
    CREDENTIAL_INJECTION_BLOCKED_RAW_HANDLE_EXPOSURE = (
        "CREDENTIAL_INJECTION_BLOCKED_RAW_HANDLE_EXPOSURE"
    )
    CREDENTIAL_INJECTION_BLOCKED_METADATA_EXPOSURE = (
        "CREDENTIAL_INJECTION_BLOCKED_METADATA_EXPOSURE"
    )
    CREDENTIAL_INJECTION_BLOCKED_SIGNING_OR_HEADERS = (
        "CREDENTIAL_INJECTION_BLOCKED_SIGNING_OR_HEADERS"
    )
    CREDENTIAL_INJECTION_BLOCKED_API_OR_POST = (
        "CREDENTIAL_INJECTION_BLOCKED_API_OR_POST"
    )
    CREDENTIAL_INJECTION_BLOCKED_LIVE_ORDER_ONCE = (
        "CREDENTIAL_INJECTION_BLOCKED_LIVE_ORDER_ONCE"
    )


class LiveOrderRealCredentialInjectionControlledMode(str, Enum):
    CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY = (
        "CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY"
    )


CredentialInjectionControlledStatus = LiveOrderRealCredentialInjectionControlledStatus
CredentialInjectionControlledMode = LiveOrderRealCredentialInjectionControlledMode


@dataclass(frozen=True)
class LiveOrderRealCredentialInjectionControlledInput:
    injection_mode: str = (
        CredentialInjectionControlledMode
        .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    )
    injection_declared: bool = True
    injection_requested: bool = True
    presence_prerequisite_checked: bool = True
    credential_presence_controlled_ready: bool = True
    required_credentials_present: bool = True
    all_required_credentials_present: bool = True
    presence_missing: bool = False
    presence_unknown: bool = False
    presence_failed: bool = False
    presence_unavailable: bool = False
    presence_timeout: bool = False
    safe_credential_handle_label: str = SAFE_CREDENTIAL_HANDLE_LABEL
    unsafe_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    credential_raw_handle_exposure_attempted: bool = False
    credential_metadata_exposure_attempted: bool = False
    credential_length_exposure_attempted: bool = False
    credential_hash_exposure_attempted: bool = False
    credential_fingerprint_exposure_attempted: bool = False
    env_actual_name_exposure_attempted: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    real_signing_allowed: bool = False
    real_headers_generation_allowed: bool = False
    real_transport_allowed: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("injection_mode", self.injection_mode)
        _require_non_empty("safe_credential_handle_label", self.safe_credential_handle_label)
        _validate_bool_fields(
            self,
            (
                "injection_declared",
                "injection_requested",
                "presence_prerequisite_checked",
                "credential_presence_controlled_ready",
                "required_credentials_present",
                "all_required_credentials_present",
                "presence_missing",
                "presence_unknown",
                "presence_failed",
                "presence_unavailable",
                "presence_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "credential_raw_handle_exposure_attempted",
                "credential_metadata_exposure_attempted",
                "credential_length_exposure_attempted",
                "credential_hash_exposure_attempted",
                "credential_fingerprint_exposure_attempted",
                "env_actual_name_exposure_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "real_signing_allowed",
                "real_headers_generation_allowed",
                "real_transport_allowed",
                "api_call_allowed",
                "api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealCredentialInjectionControlledCheckResult:
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
class LiveOrderRealCredentialInjectionControlledResult:
    status: LiveOrderRealCredentialInjectionControlledStatus
    credential_injection_ready: bool
    injection_mode: str
    injection_declared: bool
    injection_requested: bool
    presence_prerequisite_checked: bool
    presence_prerequisite_satisfied: bool
    credential_presence_controlled_ready: bool
    required_credentials_present: bool
    all_required_credentials_present: bool
    presence_missing: bool
    presence_unknown: bool
    presence_failed: bool
    presence_unavailable: bool
    presence_timeout: bool
    safe_credential_handle_label: str
    safe_injection_status: str
    unsafe_exposure_attempted: bool
    credential_value_exposure_attempted: bool
    credential_raw_handle_exposure_attempted: bool
    credential_metadata_exposure_attempted: bool
    credential_length_exposure_attempted: bool
    credential_hash_exposure_attempted: bool
    credential_fingerprint_exposure_attempted: bool
    env_actual_name_exposure_attempted: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    real_signing_allowed: bool
    real_headers_generation_allowed: bool
    real_transport_allowed: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealCredentialInjectionControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialInjectionControlledStatus):
            raise LiveVerificationValidationError(
                "status must be credential injection controlled status",
            )
        _require_non_empty("injection_mode", self.injection_mode)
        _require_non_empty("safe_credential_handle_label", self.safe_credential_handle_label)
        _require_non_empty("safe_injection_status", self.safe_injection_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_injection_ready",
                "injection_declared",
                "injection_requested",
                "presence_prerequisite_checked",
                "presence_prerequisite_satisfied",
                "credential_presence_controlled_ready",
                "required_credentials_present",
                "all_required_credentials_present",
                "presence_missing",
                "presence_unknown",
                "presence_failed",
                "presence_unavailable",
                "presence_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "credential_raw_handle_exposure_attempted",
                "credential_metadata_exposure_attempted",
                "credential_length_exposure_attempted",
                "credential_hash_exposure_attempted",
                "credential_fingerprint_exposure_attempted",
                "env_actual_name_exposure_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "real_signing_allowed",
                "real_headers_generation_allowed",
                "real_transport_allowed",
                "api_call_allowed",
                "api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
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


def build_live_order_real_credential_injection_controlled(
    *,
    input_snapshot: LiveOrderRealCredentialInjectionControlledInput | None = None,
    presence_result: LiveOrderRealCredentialPresenceControlledResult | None = None,
) -> LiveOrderRealCredentialInjectionControlledResult:
    """Build a controlled opaque credential injection readiness result."""
    snapshot = input_snapshot or LiveOrderRealCredentialInjectionControlledInput()
    if presence_result is not None:
        snapshot = _merge_presence_result(snapshot, presence_result)

    status, primary_reasons = _status_from_input(snapshot)
    blocked_reasons = _blocked_reasons(snapshot=snapshot, primary_reasons=primary_reasons)
    ready = (
        status
        is CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_READY_NO_SIGNING
    )
    presence_satisfied = (
        snapshot.presence_prerequisite_checked
        and snapshot.credential_presence_controlled_ready
        and snapshot.required_credentials_present
        and snapshot.all_required_credentials_present
        and not snapshot.presence_missing
        and not snapshot.presence_unknown
        and not snapshot.presence_failed
        and not snapshot.presence_unavailable
        and not snapshot.presence_timeout
    )
    safe_label = (
        snapshot.safe_credential_handle_label
        if snapshot.safe_credential_handle_label == SAFE_CREDENTIAL_HANDLE_LABEL
        else UNSUPPORTED_CREDENTIAL_INJECTION_CONTROLLED_LABEL
    )

    return LiveOrderRealCredentialInjectionControlledResult(
        status=status,
        credential_injection_ready=ready,
        injection_mode=(
            snapshot.injection_mode
            if snapshot.injection_mode
            == CredentialInjectionControlledMode
            .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
            .value
            else UNSUPPORTED_CREDENTIAL_INJECTION_CONTROLLED_LABEL
        ),
        injection_declared=snapshot.injection_declared,
        injection_requested=snapshot.injection_requested,
        presence_prerequisite_checked=snapshot.presence_prerequisite_checked,
        presence_prerequisite_satisfied=presence_satisfied,
        credential_presence_controlled_ready=snapshot.credential_presence_controlled_ready,
        required_credentials_present=snapshot.required_credentials_present,
        all_required_credentials_present=snapshot.all_required_credentials_present,
        presence_missing=snapshot.presence_missing,
        presence_unknown=snapshot.presence_unknown,
        presence_failed=snapshot.presence_failed,
        presence_unavailable=snapshot.presence_unavailable,
        presence_timeout=snapshot.presence_timeout,
        safe_credential_handle_label=safe_label,
        safe_injection_status=status.value,
        unsafe_exposure_attempted=False,
        credential_value_exposure_attempted=False,
        credential_raw_handle_exposure_attempted=False,
        credential_metadata_exposure_attempted=False,
        credential_length_exposure_attempted=False,
        credential_hash_exposure_attempted=False,
        credential_fingerprint_exposure_attempted=False,
        env_actual_name_exposure_attempted=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        real_signing_allowed=False,
        real_headers_generation_allowed=False,
        real_transport_allowed=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            presence_satisfied=presence_satisfied,
            safe_label=safe_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_INJECTION_CONTROLLED_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_injection_controlled_blockers_no_signing_no_api_no_post"
        ),
    )


def render_live_order_real_credential_injection_controlled_markdown(
    result: LiveOrderRealCredentialInjectionControlledResult,
) -> str:
    """Render a safe controlled credential injection summary only."""
    lines = [
        "# Step 6G Credential Injection Controlled Boundary",
        "",
        "This is a controlled injection boundary, not real credential injection.",
        "This result contains only a safe handle label, safe status, and booleans.",
        "This result does not contain credential values.",
        "This result does not contain raw handle values.",
        "This result does not calculate credential length, hash, or fingerprint.",
        "This result does not expose credential metadata.",
        "This result does not expose env actual names.",
        "Injection ready does not allow signing.",
        "Injection ready does not allow headers generation.",
        "Injection ready does not allow API calls.",
        "Injection ready does not allow HTTP POST.",
        "Injection ready does not allow live_order_once.",
        "Missing, unknown, failed, unavailable, and timeout states fail closed.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- safe_injection_status: {result.safe_injection_status}",
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        f"- injection_mode: {result.injection_mode}",
        f"- safe_credential_handle_label: {result.safe_credential_handle_label}",
        (
            "- presence_prerequisite_checked: "
            f"{_bool_text(result.presence_prerequisite_checked)}"
        ),
        (
            "- presence_prerequisite_satisfied: "
            f"{_bool_text(result.presence_prerequisite_satisfied)}"
        ),
        (
            "- all_required_credentials_present: "
            f"{_bool_text(result.all_required_credentials_present)}"
        ),
        f"- presence_missing: {_bool_text(result.presence_missing)}",
        f"- presence_unknown: {_bool_text(result.presence_unknown)}",
        f"- presence_failed: {_bool_text(result.presence_failed)}",
        f"- presence_unavailable: {_bool_text(result.presence_unavailable)}",
        f"- presence_timeout: {_bool_text(result.presence_timeout)}",
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
        f"- can_generate_real_signature: {_bool_text(result.can_generate_real_signature)}",
        f"- can_generate_real_headers: {_bool_text(result.can_generate_real_headers)}",
        f"- real_signing_allowed: {_bool_text(result.real_signing_allowed)}",
        (
            "- real_headers_generation_allowed: "
            f"{_bool_text(result.real_headers_generation_allowed)}"
        ),
        f"- real_transport_allowed: {_bool_text(result.real_transport_allowed)}",
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- api_call_attempted: {_bool_text(result.api_call_attempted)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
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


def _merge_presence_result(
    snapshot: LiveOrderRealCredentialInjectionControlledInput,
    presence_result: LiveOrderRealCredentialPresenceControlledResult,
) -> LiveOrderRealCredentialInjectionControlledInput:
    return replace(
        snapshot,
        presence_prerequisite_checked=(
            presence_result.process_env_checked_for_presence_only
        ),
        credential_presence_controlled_ready=(
            presence_result.credential_presence_controlled_ready
        ),
        required_credentials_present=presence_result.required_credentials_present,
        all_required_credentials_present=(
            presence_result.all_required_credentials_present
        ),
        presence_missing=presence_result.presence_missing,
        presence_unknown=snapshot.presence_unknown or presence_result.presence_unknown,
        presence_failed=snapshot.presence_failed or presence_result.presence_failed,
        presence_unavailable=(
            snapshot.presence_unavailable or presence_result.presence_unavailable
        ),
        presence_timeout=snapshot.presence_timeout or presence_result.presence_timeout,
        unsafe_exposure_attempted=(
            snapshot.unsafe_exposure_attempted
            or presence_result.unsafe_exposure_attempted
            or presence_result.env_file_read
            or presence_result.env_example_file_read
            or presence_result.env_actual_names_present
            or presence_result.credential_values_present
            or presence_result.credential_lengths_present
            or presence_result.credential_hashes_present
            or presence_result.credential_fingerprints_present
            or presence_result.credential_metadata_present
        ),
        actual_checker_execution_performed=(
            snapshot.actual_checker_execution_performed
            or presence_result.actual_checker_execution_performed
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or presence_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or presence_result.actual_receipt_handoff_executed
        ),
        can_generate_real_signature=(
            snapshot.can_generate_real_signature
            or presence_result.can_generate_real_signature
        ),
        can_generate_real_headers=(
            snapshot.can_generate_real_headers
            or presence_result.can_generate_real_headers
        ),
        real_signing_allowed=(
            snapshot.real_signing_allowed or presence_result.real_signing_allowed
        ),
        real_headers_generation_allowed=(
            snapshot.real_headers_generation_allowed
            or presence_result.real_headers_generation_allowed
        ),
        real_transport_allowed=(
            snapshot.real_transport_allowed or presence_result.real_transport_allowed
        ),
        api_call_allowed=snapshot.api_call_allowed or presence_result.api_call_allowed,
        api_call_attempted=snapshot.api_call_attempted or presence_result.api_call_attempted,
        http_post_executed=snapshot.http_post_executed or presence_result.http_post_executed,
        order_endpoint_called=(
            snapshot.order_endpoint_called or presence_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or presence_result.live_order_once_called
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or presence_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or presence_result.post_executed,
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or presence_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or presence_result.final_confirmation_received
        ),
        safe_to_render=snapshot.safe_to_render and presence_result.safe_to_render,
        safe_to_serialize=snapshot.safe_to_serialize and presence_result.safe_to_serialize,
    )


def _status_from_input(
    snapshot: LiveOrderRealCredentialInjectionControlledInput,
) -> tuple[LiveOrderRealCredentialInjectionControlledStatus, tuple[str, ...]]:
    if (
        snapshot.injection_mode
        != CredentialInjectionControlledMode
        .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    ):
        return (
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_BLOCKED_UNKNOWN,
            ("unsupported_injection_mode",),
        )
    if not snapshot.injection_declared or not snapshot.injection_requested:
        return (
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_NOT_READY,
            ("credential_injection_not_declared_or_requested",),
        )
    if snapshot.safe_credential_handle_label != SAFE_CREDENTIAL_HANDLE_LABEL:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
            ("safe_credential_handle_label_not_fixed",),
        )
    if snapshot.presence_unknown:
        return (
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_BLOCKED_UNKNOWN,
            ("credential_presence_unknown",),
        )
    if snapshot.presence_failed:
        return (
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_BLOCKED_FAILED,
            ("credential_presence_failed",),
        )
    if snapshot.presence_unavailable:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_UNAVAILABLE,
            ("credential_presence_unavailable",),
        )
    if snapshot.presence_timeout:
        return (
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_BLOCKED_TIMEOUT,
            ("credential_presence_timeout",),
        )
    if (
        not snapshot.presence_prerequisite_checked
        or not snapshot.credential_presence_controlled_ready
        or not snapshot.required_credentials_present
        or not snapshot.all_required_credentials_present
        or snapshot.presence_missing
    ):
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
            ("credential_presence_prerequisite_missing",),
        )
    if snapshot.credential_value_exposure_attempted:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_VALUE_EXPOSURE,
            ("credential_value_exposure_attempted",),
        )
    if snapshot.credential_raw_handle_exposure_attempted:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_RAW_HANDLE_EXPOSURE,
            ("credential_raw_handle_exposure_attempted",),
        )
    if snapshot.credential_metadata_exposure_attempted:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_METADATA_EXPOSURE,
            ("credential_metadata_exposure_attempted",),
        )
    if (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_length_exposure_attempted
        or snapshot.credential_hash_exposure_attempted
        or snapshot.credential_fingerprint_exposure_attempted
        or snapshot.env_actual_name_exposure_attempted
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    ):
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
            ("credential_injection_unsafe_exposure_attempted",),
        )
    if (
        snapshot.can_generate_real_signature
        or snapshot.can_generate_real_headers
        or snapshot.real_signing_allowed
        or snapshot.real_headers_generation_allowed
        or snapshot.real_transport_allowed
    ):
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_SIGNING_OR_HEADERS,
            ("signing_or_headers_attempted",),
        )
    if snapshot.live_order_once_called:
        return (
            CredentialInjectionControlledStatus
            .CREDENTIAL_INJECTION_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_attempted",),
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_post_executed
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
            CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_BLOCKED_API_OR_POST,
            ("api_post_or_actual_execution_attempted",),
        )
    return (
        CredentialInjectionControlledStatus.CREDENTIAL_INJECTION_READY_NO_SIGNING,
        (),
    )


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealCredentialInjectionControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = list(primary_reasons)
    for field_name in (
        "credential_length_exposure_attempted",
        "credential_hash_exposure_attempted",
        "credential_fingerprint_exposure_attempted",
        "env_actual_name_exposure_attempted",
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
    snapshot: LiveOrderRealCredentialInjectionControlledInput,
    status: LiveOrderRealCredentialInjectionControlledStatus,
    ready: bool,
    presence_satisfied: bool,
    safe_label: str,
) -> tuple[LiveOrderRealCredentialInjectionControlledCheckResult, ...]:
    return (
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="controlled injection mode",
            passed=(
                snapshot.injection_mode
                == CredentialInjectionControlledMode
                .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
            sanitized_value=(
                snapshot.injection_mode
                if snapshot.injection_mode
                == CredentialInjectionControlledMode
                .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
                .value
                else UNSUPPORTED_CREDENTIAL_INJECTION_CONTROLLED_LABEL
            ),
            expected=(
                CredentialInjectionControlledMode
                .CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
        ),
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="presence prerequisite",
            passed=presence_satisfied,
            sanitized_value="satisfied" if presence_satisfied else "blocked",
            expected="safe_presence_boolean_satisfied",
        ),
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="safe handle label",
            passed=safe_label == SAFE_CREDENTIAL_HANDLE_LABEL,
            sanitized_value=safe_label,
            expected=SAFE_CREDENTIAL_HANDLE_LABEL,
        ),
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="no credential or handle exposure",
            passed=not (
                snapshot.unsafe_exposure_attempted
                or snapshot.credential_value_exposure_attempted
                or snapshot.credential_raw_handle_exposure_attempted
                or snapshot.credential_metadata_exposure_attempted
                or snapshot.credential_length_exposure_attempted
                or snapshot.credential_hash_exposure_attempted
                or snapshot.credential_fingerprint_exposure_attempted
                or snapshot.env_actual_name_exposure_attempted
            ),
            sanitized_value="safe_boolean_only",
            expected="safe_boolean_only",
        ),
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="no signing api post live_order_once",
            passed=not (
                snapshot.can_generate_real_signature
                or snapshot.can_generate_real_headers
                or snapshot.real_signing_allowed
                or snapshot.real_headers_generation_allowed
                or snapshot.real_transport_allowed
                or snapshot.api_call_allowed
                or snapshot.api_call_attempted
                or snapshot.http_post_executed
                or snapshot.order_endpoint_called
                or snapshot.live_order_once_called
                or snapshot.post_allowed_this_step
                or snapshot.post_executed
            ),
            sanitized_value="not_allowed",
            expected="not_allowed",
        ),
        LiveOrderRealCredentialInjectionControlledCheckResult(
            name="ready is not permission",
            passed=ready
            and not (
                snapshot.real_signing_allowed
                or snapshot.real_headers_generation_allowed
                or snapshot.api_call_allowed
                or snapshot.post_allowed_this_step
                or snapshot.live_order_once_called
            ),
            sanitized_value=status.value,
            expected="ready_no_signing_no_api_no_post",
        ),
    )


def _validate_result_safety(
    result: LiveOrderRealCredentialInjectionControlledResult,
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
        result.actual_checker_execution_performed,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.can_generate_real_signature,
        result.can_generate_real_headers,
        result.real_signing_allowed,
        result.real_headers_generation_allowed,
        result.real_transport_allowed,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.fresh_preflight_executed,
        result.final_confirmation_received,
        not result.safe_to_render,
        not result.safe_to_serialize,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "credential injection controlled result is unsafe",
        )
    if result.credential_injection_ready and (
        result.safe_credential_handle_label != SAFE_CREDENTIAL_HANDLE_LABEL
    ):
        raise LiveVerificationValidationError(
            "credential injection controlled ready requires safe handle label",
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
