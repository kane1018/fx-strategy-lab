"""Step 6G controlled credential presence check.

This module is the narrow env-access step allowed after the ENV-GATE review.
It checks process env presence only, converts it immediately to safe booleans,
and never returns or renders env names, values, lengths, hashes, fingerprints,
metadata, signatures, headers, requests, responses, or real IDs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_CONTROLLED_RECOMMENDED_NEXT_STEP = (
    "credential_presence_controlled_boundary_review_or_injection_gate_no_api_no_post"
)
UNSUPPORTED_CREDENTIAL_PRESENCE_CONTROLLED_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealCredentialPresenceControlledStatus(str, Enum):
    CREDENTIAL_PRESENCE_NOT_CHECKED = "CREDENTIAL_PRESENCE_NOT_CHECKED"
    CREDENTIAL_PRESENCE_PRESENT_NO_POST = "CREDENTIAL_PRESENCE_PRESENT_NO_POST"
    CREDENTIAL_PRESENCE_MISSING_NO_POST = "CREDENTIAL_PRESENCE_MISSING_NO_POST"
    CREDENTIAL_PRESENCE_BLOCKED_UNKNOWN = "CREDENTIAL_PRESENCE_BLOCKED_UNKNOWN"
    CREDENTIAL_PRESENCE_BLOCKED_FAILED = "CREDENTIAL_PRESENCE_BLOCKED_FAILED"
    CREDENTIAL_PRESENCE_BLOCKED_UNAVAILABLE = (
        "CREDENTIAL_PRESENCE_BLOCKED_UNAVAILABLE"
    )
    CREDENTIAL_PRESENCE_BLOCKED_TIMEOUT = "CREDENTIAL_PRESENCE_BLOCKED_TIMEOUT"
    CREDENTIAL_PRESENCE_BLOCKED_UNSAFE_EXPOSURE = (
        "CREDENTIAL_PRESENCE_BLOCKED_UNSAFE_EXPOSURE"
    )
    CREDENTIAL_PRESENCE_BLOCKED_ACTUAL_EXECUTION_OR_RECEIPT = (
        "CREDENTIAL_PRESENCE_BLOCKED_ACTUAL_EXECUTION_OR_RECEIPT"
    )
    CREDENTIAL_PRESENCE_BLOCKED_API_OR_POST = (
        "CREDENTIAL_PRESENCE_BLOCKED_API_OR_POST"
    )
    CREDENTIAL_PRESENCE_BLOCKED_SIGNING_OR_TRANSPORT = (
        "CREDENTIAL_PRESENCE_BLOCKED_SIGNING_OR_TRANSPORT"
    )
    CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED = (
        "CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceControlledMode(str, Enum):
    CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY = (
        "CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY"
    )


CredentialPresenceControlledStatus = LiveOrderRealCredentialPresenceControlledStatus
CredentialPresenceControlledMode = LiveOrderRealCredentialPresenceControlledMode

PRIMARY_CREDENTIAL_LABEL = "PRIMARY_CREDENTIAL"
SECONDARY_CREDENTIAL_LABEL = "SECONDARY_CREDENTIAL"
DEFAULT_REQUIRED_CREDENTIAL_LABELS = (
    PRIMARY_CREDENTIAL_LABEL,
    SECONDARY_CREDENTIAL_LABEL,
)


def _join_env_label_parts(*parts: str) -> str:
    return "_".join(parts)


_CONTROLLED_LABEL_TO_ENV_NAME = {
    PRIMARY_CREDENTIAL_LABEL: _join_env_label_parts("GMO", "FX", "API", "KEY"),
    SECONDARY_CREDENTIAL_LABEL: _join_env_label_parts("GMO", "FX", "API", "SECRET"),
}


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceControlledInput:
    presence_mode: str = (
        CredentialPresenceControlledMode
        .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    )
    presence_check_declared: bool = True
    presence_check_requested: bool = True
    env_access_limited_to_presence: bool = True
    process_env_access_allowed: bool = True
    required_credential_labels: tuple[str, ...] = DEFAULT_REQUIRED_CREDENTIAL_LABELS
    env_file_read: bool = False
    env_example_file_read: bool = False
    env_actual_names_present: bool = False
    credential_values_present: bool = False
    credential_lengths_present: bool = False
    credential_hashes_present: bool = False
    credential_fingerprints_present: bool = False
    credential_metadata_present: bool = False
    presence_unknown: bool = False
    presence_failed: bool = False
    presence_unavailable: bool = False
    presence_timeout: bool = False
    unsafe_exposure_attempted: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    can_execute_http_post: bool = False
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
        _require_non_empty("presence_mode", self.presence_mode)
        if not self.required_credential_labels:
            raise LiveVerificationValidationError(
                "required_credential_labels must not be empty",
            )
        for label in self.required_credential_labels:
            _require_non_empty("required_credential_label", label)
        _validate_bool_fields(
            self,
            (
                "presence_check_declared",
                "presence_check_requested",
                "env_access_limited_to_presence",
                "process_env_access_allowed",
                "env_file_read",
                "env_example_file_read",
                "env_actual_names_present",
                "credential_values_present",
                "credential_lengths_present",
                "credential_hashes_present",
                "credential_fingerprints_present",
                "credential_metadata_present",
                "presence_unknown",
                "presence_failed",
                "presence_unavailable",
                "presence_timeout",
                "unsafe_exposure_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
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
class LiveOrderRealCredentialPresenceControlledCredentialResult:
    safe_label: str
    present: bool

    def __post_init__(self) -> None:
        _require_non_empty("safe_label", self.safe_label)
        if type(self.present) is not bool:
            raise LiveVerificationValidationError("present must be bool")


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceControlledCheckResult:
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
class LiveOrderRealCredentialPresenceControlledResult:
    status: LiveOrderRealCredentialPresenceControlledStatus
    credential_presence_controlled_ready: bool
    presence_mode: str
    presence_check_declared: bool
    presence_check_requested: bool
    env_access_limited_to_presence: bool
    process_env_access_allowed: bool
    process_env_checked_for_presence_only: bool
    required_credential_labels: tuple[str, ...]
    credential_presence_results: tuple[
        LiveOrderRealCredentialPresenceControlledCredentialResult,
        ...,
    ]
    required_credentials_present: bool
    all_required_credentials_present: bool
    presence_missing: bool
    presence_unknown: bool
    presence_failed: bool
    presence_unavailable: bool
    presence_timeout: bool
    env_file_read: bool
    env_example_file_read: bool
    env_actual_names_present: bool
    credential_values_present: bool
    credential_lengths_present: bool
    credential_hashes_present: bool
    credential_fingerprints_present: bool
    credential_metadata_present: bool
    unsafe_exposure_attempted: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    can_execute_http_post: bool
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
    check_results: tuple[LiveOrderRealCredentialPresenceControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialPresenceControlledStatus):
            raise LiveVerificationValidationError(
                "status must be credential presence controlled status",
            )
        _require_non_empty("presence_mode", self.presence_mode)
        if not self.required_credential_labels:
            raise LiveVerificationValidationError(
                "required_credential_labels must not be empty",
            )
        for label in self.required_credential_labels:
            _require_non_empty("required_credential_label", label)
        _validate_bool_fields(
            self,
            (
                "credential_presence_controlled_ready",
                "presence_check_declared",
                "presence_check_requested",
                "env_access_limited_to_presence",
                "process_env_access_allowed",
                "process_env_checked_for_presence_only",
                "required_credentials_present",
                "all_required_credentials_present",
                "presence_missing",
                "presence_unknown",
                "presence_failed",
                "presence_unavailable",
                "presence_timeout",
                "env_file_read",
                "env_example_file_read",
                "env_actual_names_present",
                "credential_values_present",
                "credential_lengths_present",
                "credential_hashes_present",
                "credential_fingerprints_present",
                "credential_metadata_present",
                "unsafe_exposure_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
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


def build_live_order_real_credential_presence_controlled(
    *,
    input_snapshot: LiveOrderRealCredentialPresenceControlledInput | None = None,
    env_snapshot: Mapping[str, str] | None = None,
) -> LiveOrderRealCredentialPresenceControlledResult:
    """Check required process env presence and return only safe booleans."""
    snapshot = input_snapshot or LiveOrderRealCredentialPresenceControlledInput()
    status, status_reasons = _status_from_input(snapshot)
    process_env_checked = False
    credential_results: tuple[
        LiveOrderRealCredentialPresenceControlledCredentialResult,
        ...,
    ] = ()
    presence_missing = False
    all_present = False

    if status is None:
        status, credential_results = _presence_status_from_env(
            snapshot=snapshot,
            env_snapshot=env_snapshot,
        )
        process_env_checked = True
        all_present = all(result.present for result in credential_results)
        presence_missing = not all_present
    else:
        credential_results = tuple(
            LiveOrderRealCredentialPresenceControlledCredentialResult(
                safe_label=label
                if label in _CONTROLLED_LABEL_TO_ENV_NAME
                else UNSUPPORTED_CREDENTIAL_PRESENCE_CONTROLLED_LABEL,
                present=False,
            )
            for label in snapshot.required_credential_labels
        )
        all_present = False
        presence_missing = (
            status is CredentialPresenceControlledStatus
            .CREDENTIAL_PRESENCE_MISSING_NO_POST
        )

    if status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_MISSING_NO_POST:
        presence_missing = True

    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        status=status,
        status_reasons=status_reasons,
        presence_missing=presence_missing,
    )
    ready = status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_PRESENT_NO_POST

    result = LiveOrderRealCredentialPresenceControlledResult(
        status=status,
        credential_presence_controlled_ready=ready,
        presence_mode=snapshot.presence_mode
        if snapshot.presence_mode
        == CredentialPresenceControlledMode
        .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
        .value
        else UNSUPPORTED_CREDENTIAL_PRESENCE_CONTROLLED_LABEL,
        presence_check_declared=snapshot.presence_check_declared,
        presence_check_requested=snapshot.presence_check_requested,
        env_access_limited_to_presence=snapshot.env_access_limited_to_presence,
        process_env_access_allowed=snapshot.process_env_access_allowed,
        process_env_checked_for_presence_only=process_env_checked,
        required_credential_labels=tuple(result.safe_label for result in credential_results),
        credential_presence_results=credential_results,
        required_credentials_present=ready,
        all_required_credentials_present=ready and all_present,
        presence_missing=presence_missing,
        presence_unknown=snapshot.presence_unknown,
        presence_failed=(
            snapshot.presence_failed
            or status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_FAILED
        ),
        presence_unavailable=snapshot.presence_unavailable,
        presence_timeout=snapshot.presence_timeout,
        env_file_read=False,
        env_example_file_read=False,
        env_actual_names_present=False,
        credential_values_present=False,
        credential_lengths_present=False,
        credential_hashes_present=False,
        credential_fingerprints_present=False,
        credential_metadata_present=False,
        unsafe_exposure_attempted=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        can_execute_http_post=False,
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
        safe_to_render=snapshot.safe_to_render,
        safe_to_serialize=snapshot.safe_to_serialize,
        check_results=_build_check_results(
            status=status,
            ready=ready,
            process_env_checked=process_env_checked,
            all_present=all_present,
            presence_missing=presence_missing,
            snapshot=snapshot,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=CREDENTIAL_PRESENCE_CONTROLLED_RECOMMENDED_NEXT_STEP,
    )
    return result


def render_live_order_real_credential_presence_controlled_markdown(
    result: LiveOrderRealCredentialPresenceControlledResult,
) -> str:
    """Render safe credential presence summary only."""
    lines = [
        "# Step 6G Credential Presence Controlled Check",
        "",
        "This controlled check only converts process env presence to safe booleans.",
        "This controlled check does not read .env or .env.example files.",
        "This controlled check does not expose env actual names.",
        "This controlled check does not expose credential values.",
        "This controlled check does not calculate credential length, hash, or fingerprint.",
        "This controlled check does not expose credential metadata.",
        "Credential present does not allow POST.",
        "Credential present does not allow signing.",
        "Credential present does not allow API calls.",
        "Credential present does not allow live_order_once.",
        "Missing, unknown, failed, unavailable, and timeout states fail closed.",
        "READY_CONFIRMED is not POST permission.",
        "NOT_PROVIDED is not actual result receipt.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- credential_presence_controlled_ready: "
            f"{_bool_text(result.credential_presence_controlled_ready)}"
        ),
        f"- presence_mode: {result.presence_mode}",
        (
            "- process_env_checked_for_presence_only: "
            f"{_bool_text(result.process_env_checked_for_presence_only)}"
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
        f"- env_file_read: {_bool_text(result.env_file_read)}",
        f"- env_example_file_read: {_bool_text(result.env_example_file_read)}",
        f"- env_actual_names_present: {_bool_text(result.env_actual_names_present)}",
        (
            "- credential_values_present: "
            f"{_bool_text(result.credential_values_present)}"
        ),
        (
            "- credential_lengths_present: "
            f"{_bool_text(result.credential_lengths_present)}"
        ),
        (
            "- credential_hashes_present: "
            f"{_bool_text(result.credential_hashes_present)}"
        ),
        (
            "- credential_fingerprints_present: "
            f"{_bool_text(result.credential_fingerprints_present)}"
        ),
        (
            "- credential_metadata_present: "
            f"{_bool_text(result.credential_metadata_present)}"
        ),
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- can_generate_real_signature: {_bool_text(result.can_generate_real_signature)}",
        f"- can_generate_real_headers: {_bool_text(result.can_generate_real_headers)}",
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        "",
        "## Safe Labels",
    ]
    lines.extend(
        f"- {credential.safe_label}: {'present' if credential.present else 'missing'}"
        for credential in result.credential_presence_results
    )
    lines.extend(
        [
            "",
            "## Blocked Reasons",
            *(f"- {reason}" for reason in result.blocked_reasons),
            "",
            f"recommended_next_step: {result.recommended_next_step}",
        ],
    )
    return "\n".join(lines)


def _status_from_input(
    snapshot: LiveOrderRealCredentialPresenceControlledInput,
) -> tuple[LiveOrderRealCredentialPresenceControlledStatus | None, tuple[str, ...]]:
    reasons: list[str] = []
    if (
        snapshot.presence_mode
        != CredentialPresenceControlledMode
        .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    ):
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED,
            ("unsupported_presence_mode",),
        )
    unsupported_labels = tuple(
        label
        for label in snapshot.required_credential_labels
        if label not in _CONTROLLED_LABEL_TO_ENV_NAME
    )
    if unsupported_labels:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED,
            ("unsupported_required_credential_label",),
        )
    if not snapshot.presence_check_declared or not snapshot.presence_check_requested:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_NOT_CHECKED,
            ("presence_check_not_requested",),
        )
    if (
        not snapshot.env_access_limited_to_presence
        or not snapshot.process_env_access_allowed
    ):
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_NOT_CHECKED,
            ("env_access_not_limited_to_presence",),
        )
    unsafe_fields = (
        "env_file_read",
        "env_example_file_read",
        "env_actual_names_present",
        "credential_values_present",
        "credential_lengths_present",
        "credential_hashes_present",
        "credential_fingerprints_present",
        "credential_metadata_present",
        "unsafe_exposure_attempted",
    )
    for field_name in unsafe_fields:
        if getattr(snapshot, field_name):
            reasons.append(f"{field_name}_blocked")
    if not snapshot.safe_to_render:
        reasons.append("safe_to_render_false")
    if not snapshot.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    if reasons:
        return (
            CredentialPresenceControlledStatus
            .CREDENTIAL_PRESENCE_BLOCKED_UNSAFE_EXPOSURE,
            tuple(reasons),
        )
    if snapshot.presence_unknown:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_UNKNOWN,
            ("presence_unknown",),
        )
    if snapshot.presence_failed:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_FAILED,
            ("presence_failed",),
        )
    if snapshot.presence_unavailable:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_UNAVAILABLE,
            ("presence_unavailable",),
        )
    if snapshot.presence_timeout:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_TIMEOUT,
            ("presence_timeout",),
        )
    if (
        snapshot.actual_checker_execution_performed
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
    ):
        return (
            CredentialPresenceControlledStatus
            .CREDENTIAL_PRESENCE_BLOCKED_ACTUAL_EXECUTION_OR_RECEIPT,
            ("actual_execution_or_receipt_attempted",),
        )
    if (
        snapshot.can_execute_http_post
        or snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_post_executed
        or snapshot.order_endpoint_called
        or snapshot.live_order_once_called
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
    ):
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_API_OR_POST,
            ("api_or_post_attempted",),
        )
    if (
        snapshot.can_generate_real_signature
        or snapshot.can_generate_real_headers
        or snapshot.real_signing_allowed
        or snapshot.real_headers_generation_allowed
        or snapshot.real_transport_allowed
    ):
        return (
            CredentialPresenceControlledStatus
            .CREDENTIAL_PRESENCE_BLOCKED_SIGNING_OR_TRANSPORT,
            ("signing_or_transport_attempted",),
        )
    if snapshot.fresh_preflight_executed or snapshot.final_confirmation_received:
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_API_OR_POST,
            ("preflight_or_confirmation_attempted",),
        )
    return None, ()


def _presence_status_from_env(
    *,
    snapshot: LiveOrderRealCredentialPresenceControlledInput,
    env_snapshot: Mapping[str, str] | None,
) -> tuple[
    LiveOrderRealCredentialPresenceControlledStatus,
    tuple[LiveOrderRealCredentialPresenceControlledCredentialResult, ...],
]:
    env_source = os.environ if env_snapshot is None else env_snapshot
    credential_results: list[
        LiveOrderRealCredentialPresenceControlledCredentialResult
    ] = []
    try:
        for safe_label in snapshot.required_credential_labels:
            raw_value = env_source.get(_CONTROLLED_LABEL_TO_ENV_NAME[safe_label])
            present = bool(raw_value and raw_value.strip())
            raw_value = None
            credential_results.append(
                LiveOrderRealCredentialPresenceControlledCredentialResult(
                    safe_label=safe_label,
                    present=present,
                ),
            )
    except Exception:
        credential_results = [
            LiveOrderRealCredentialPresenceControlledCredentialResult(
                safe_label=safe_label,
                present=False,
            )
            for safe_label in snapshot.required_credential_labels
        ]
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_BLOCKED_FAILED,
            tuple(credential_results),
        )
    if all(result.present for result in credential_results):
        return (
            CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_PRESENT_NO_POST,
            tuple(credential_results),
        )
    return (
        CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_MISSING_NO_POST,
        tuple(credential_results),
    )


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealCredentialPresenceControlledInput,
    status: LiveOrderRealCredentialPresenceControlledStatus,
    status_reasons: tuple[str, ...],
    presence_missing: bool,
) -> tuple[str, ...]:
    reasons: list[str] = list(status_reasons)
    if status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_NOT_CHECKED:
        reasons.append("credential_presence_not_checked")
    if presence_missing:
        reasons.append("credential_presence_missing")
    if status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_PRESENT_NO_POST:
        return ()
    if status is CredentialPresenceControlledStatus.CREDENTIAL_PRESENCE_MISSING_NO_POST:
        return tuple(_dedupe(reasons))
    if not reasons:
        reasons.append(status.value)
    if snapshot.post_allowed_this_step or snapshot.post_executed:
        reasons.append("post_not_allowed_for_presence")
    return tuple(_dedupe(reasons))


def _build_check_results(
    *,
    status: LiveOrderRealCredentialPresenceControlledStatus,
    ready: bool,
    process_env_checked: bool,
    all_present: bool,
    presence_missing: bool,
    snapshot: LiveOrderRealCredentialPresenceControlledInput,
) -> tuple[LiveOrderRealCredentialPresenceControlledCheckResult, ...]:
    return (
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="mode",
            passed=(
                snapshot.presence_mode
                == CredentialPresenceControlledMode
                .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
            sanitized_value=(
                snapshot.presence_mode
                if snapshot.presence_mode
                == CredentialPresenceControlledMode
                .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
                .value
                else UNSUPPORTED_CREDENTIAL_PRESENCE_CONTROLLED_LABEL
            ),
            expected=(
                CredentialPresenceControlledMode
                .CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY
                .value
            ),
        ),
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="process env presence-only check",
            passed=process_env_checked,
            sanitized_value="checked" if process_env_checked else "not_checked",
            expected="checked_without_value_exposure",
        ),
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="all required credentials present",
            passed=all_present,
            sanitized_value="present" if all_present else "missing",
            expected="present_without_post_permission",
        ),
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="presence missing fail closed",
            passed=not presence_missing or not ready,
            sanitized_value="fail_closed" if presence_missing else "not_missing",
            expected="missing_blocks_post",
        ),
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="no exposure",
            passed=not (
                snapshot.env_file_read
                or snapshot.env_example_file_read
                or snapshot.env_actual_names_present
                or snapshot.credential_values_present
                or snapshot.credential_lengths_present
                or snapshot.credential_hashes_present
                or snapshot.credential_fingerprints_present
                or snapshot.credential_metadata_present
            ),
            sanitized_value="no_values_names_or_metadata",
            expected="no_values_names_or_metadata",
        ),
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="no signing api post",
            passed=not (
                snapshot.can_generate_real_signature
                or snapshot.can_generate_real_headers
                or snapshot.can_execute_http_post
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
        LiveOrderRealCredentialPresenceControlledCheckResult(
            name="status",
            passed=status
            in {
                CredentialPresenceControlledStatus
                .CREDENTIAL_PRESENCE_PRESENT_NO_POST,
                CredentialPresenceControlledStatus
                .CREDENTIAL_PRESENCE_MISSING_NO_POST,
            },
            sanitized_value=status.value,
            expected="present_or_missing_safe_status",
        ),
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
