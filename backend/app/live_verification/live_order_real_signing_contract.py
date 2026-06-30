"""Step 6G real signing contract, no credential values and no signatures.

This module models only the metadata required before a future real signing
step. It does not read environment variables, use credentials, generate signed
values, build header values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_order_transport_core import (
    TRANSPORT_CORE_HEADER_NAME_SUMMARY,
    TRANSPORT_CORE_ORDER_PATH,
)

SIGNING_CONTRACT_METHOD = "POST"
SIGNING_CONTRACT_BODY_LABEL = "step6g_stable_body_contract_metadata_only"
SIGNING_CONTRACT_ALGORITHM_LABEL = "HMAC-SHA256"
SIGNING_CONTRACT_RECOMMENDED_NEXT_STEP = (
    "future_real_signing_and_real_transport_must_be_a_separate_step"
)


class LiveOrderRealSigningContractStatus(str, Enum):
    SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE = (
        "SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE"
    )
    SIGNING_CONTRACT_REDACTED_HEADER_READY = "SIGNING_CONTRACT_REDACTED_HEADER_READY"
    BLOCKED_SIGNING_CONTRACT_INPUT = "BLOCKED_SIGNING_CONTRACT_INPUT"
    BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE = (
        "BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE"
    )
    BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE = (
        "BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE"
    )
    BLOCKED_SIGNING_CONTRACT_HEADER_VALUE_EXPOSURE = (
        "BLOCKED_SIGNING_CONTRACT_HEADER_VALUE_EXPOSURE"
    )
    BLOCKED_SIGNING_CONTRACT_ENV_ACCESS = "BLOCKED_SIGNING_CONTRACT_ENV_ACCESS"
    BLOCKED_SIGNING_CONTRACT_UNSUPPORTED = "BLOCKED_SIGNING_CONTRACT_UNSUPPORTED"


SigningContractStatus = LiveOrderRealSigningContractStatus


@dataclass(frozen=True)
class LiveOrderRealSigningInputContract:
    method: str = SIGNING_CONTRACT_METHOD
    path: str = TRANSPORT_CORE_ORDER_PATH
    stable_serialized_body_contract_ready: bool = True
    body_contract_label: str = SIGNING_CONTRACT_BODY_LABEL
    timestamp_required: bool = True
    timestamp_value_generated: bool = False
    credential_presence_required: bool = True
    credential_values_provided: bool = False
    signature_algorithm_label: str = SIGNING_CONTRACT_ALGORITHM_LABEL
    signature_value_generated: bool = False
    header_names_allowed: tuple[str, ...] = TRANSPORT_CORE_HEADER_NAME_SUMMARY
    header_values_redacted: bool = True
    headers_displayed: bool = False
    headers_saved: bool = False
    credentials_displayed: bool = False
    credentials_saved: bool = False
    signature_displayed: bool = False
    signature_saved: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _require_non_empty("body_contract_label", self.body_contract_label)
        _require_non_empty("signature_algorithm_label", self.signature_algorithm_label)
        _validate_str_tuple("header_names_allowed", self.header_names_allowed)
        _validate_bool_fields(
            self,
            (
                "stable_serialized_body_contract_ready",
                "timestamp_required",
                "timestamp_value_generated",
                "credential_presence_required",
                "credential_values_provided",
                "signature_value_generated",
                "header_values_redacted",
                "headers_displayed",
                "headers_saved",
                "credentials_displayed",
                "credentials_saved",
                "signature_displayed",
                "signature_saved",
                "env_access_requested",
                "dotenv_access_requested",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealRedactedHeaderContract:
    redacted_header_contract_ready: bool = True
    allowed_header_names: tuple[str, ...] = TRANSPORT_CORE_HEADER_NAME_SUMMARY
    header_values_present: bool = False
    header_values_redacted: bool = True
    signature_value_present: bool = False
    credential_value_present: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _validate_str_tuple("allowed_header_names", self.allowed_header_names)
        _validate_bool_fields(
            self,
            (
                "redacted_header_contract_ready",
                "header_values_present",
                "header_values_redacted",
                "signature_value_present",
                "credential_value_present",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealSigningContractCheckResult:
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
class LiveOrderRealSigningContractResult:
    status: LiveOrderRealSigningContractStatus
    signing_contract_ready: bool
    redacted_header_contract_ready: bool
    method: str
    path: str
    body_contract_label: str
    timestamp_required: bool
    timestamp_value_generated: bool
    credential_presence_required: bool
    credential_values_provided: bool
    signature_algorithm_label: str
    signature_value_generated: bool
    header_names_allowed: tuple[str, ...]
    header_values_redacted: bool
    headers_displayed: bool
    headers_saved: bool
    credentials_displayed: bool
    credentials_saved: bool
    signature_displayed: bool
    signature_saved: bool
    no_api_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    check_results: tuple[LiveOrderRealSigningContractCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealSigningContractStatus):
            raise LiveVerificationValidationError("status must be signing contract status")
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _require_non_empty("body_contract_label", self.body_contract_label)
        _require_non_empty("signature_algorithm_label", self.signature_algorithm_label)
        _validate_str_tuple("header_names_allowed", self.header_names_allowed)
        _validate_bool_fields(
            self,
            (
                "signing_contract_ready",
                "redacted_header_contract_ready",
                "timestamp_required",
                "timestamp_value_generated",
                "credential_presence_required",
                "credential_values_provided",
                "signature_value_generated",
                "header_values_redacted",
                "headers_displayed",
                "headers_saved",
                "credentials_displayed",
                "credentials_saved",
                "signature_displayed",
                "signature_saved",
                "no_api_executed",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if self.http_post_executed:
            raise LiveVerificationValidationError("signing contract must not execute HTTP POST")
        if self.order_endpoint_called:
            raise LiveVerificationValidationError("signing contract must not call order endpoint")
        if self.live_order_once_called:
            raise LiveVerificationValidationError("signing contract must not call live_order_once")


def validate_signing_inputs_without_secret_exposure(
    input_contract: LiveOrderRealSigningInputContract,
) -> LiveOrderRealSigningContractCheckResult:
    reasons = _input_reasons(input_contract)
    return LiveOrderRealSigningContractCheckResult(
        name="signing input contract",
        passed=not reasons,
        sanitized_value="ready" if not reasons else ",".join(reasons),
        expected="POST /v1/order metadata only, no values",
    )


def build_redacted_private_order_header_contract(
    *,
    redacted_header_contract_ready: bool = True,
    allowed_header_names: tuple[str, ...] = TRANSPORT_CORE_HEADER_NAME_SUMMARY,
    header_values_present: bool = False,
    header_values_redacted: bool = True,
    signature_value_present: bool = False,
    credential_value_present: bool = False,
    safe_to_render: bool = True,
    safe_to_serialize: bool = True,
) -> LiveOrderRealRedactedHeaderContract:
    """Build header-name metadata only; never carry header values."""
    return LiveOrderRealRedactedHeaderContract(
        redacted_header_contract_ready=redacted_header_contract_ready,
        allowed_header_names=allowed_header_names,
        header_values_present=header_values_present,
        header_values_redacted=header_values_redacted,
        signature_value_present=signature_value_present,
        credential_value_present=credential_value_present,
        safe_to_render=safe_to_render,
        safe_to_serialize=safe_to_serialize,
    )


def ensure_signature_not_displayed_or_saved(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> LiveOrderRealSigningContractCheckResult:
    reasons = _signature_reasons(input_contract, header_contract)
    return LiveOrderRealSigningContractCheckResult(
        name="signature not displayed or saved",
        passed=not reasons,
        sanitized_value="none" if not reasons else ",".join(reasons),
        expected="no signature value generated displayed saved or present",
    )


def ensure_credentials_not_displayed_or_saved(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> LiveOrderRealSigningContractCheckResult:
    reasons = _credential_reasons(input_contract, header_contract)
    return LiveOrderRealSigningContractCheckResult(
        name="credentials not displayed or saved",
        passed=not reasons,
        sanitized_value="none" if not reasons else ",".join(reasons),
        expected="no credential values provided displayed saved or present",
    )


def build_live_order_real_signing_contract(
    *,
    input_contract: LiveOrderRealSigningInputContract | None = None,
    header_contract: LiveOrderRealRedactedHeaderContract | None = None,
) -> LiveOrderRealSigningContractResult:
    """Build a contract-only Step 6G signing decision."""
    signing_input = input_contract or LiveOrderRealSigningInputContract()
    redacted_header = header_contract or build_redacted_private_order_header_contract()

    env_reasons = _env_reasons(signing_input)
    credential_reasons = _credential_reasons(signing_input, redacted_header)
    signature_reasons = _signature_reasons(signing_input, redacted_header)
    header_reasons = _header_reasons(signing_input, redacted_header)
    input_reasons = _input_reasons(signing_input)
    unsupported_reasons = _unsupported_reasons(signing_input)

    if env_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_ENV_ACCESS
        primary_reasons = env_reasons
    elif credential_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE
        primary_reasons = credential_reasons
    elif signature_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE
        primary_reasons = signature_reasons
    elif header_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_HEADER_VALUE_EXPOSURE
        primary_reasons = header_reasons
    elif input_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_INPUT
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = SigningContractStatus.BLOCKED_SIGNING_CONTRACT_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = SigningContractStatus.SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE
        primary_reasons = ()

    ready = status is SigningContractStatus.SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE
    checks = _build_check_results(signing_input, redacted_header)
    blocked_reasons = _merge_reasons(
        primary_reasons,
        env_reasons,
        credential_reasons,
        signature_reasons,
        header_reasons,
        input_reasons,
        unsupported_reasons,
    )

    return LiveOrderRealSigningContractResult(
        status=status,
        signing_contract_ready=ready,
        redacted_header_contract_ready=not _header_contract_reasons(redacted_header),
        method=signing_input.method,
        path=signing_input.path,
        body_contract_label=signing_input.body_contract_label,
        timestamp_required=signing_input.timestamp_required,
        timestamp_value_generated=signing_input.timestamp_value_generated,
        credential_presence_required=signing_input.credential_presence_required,
        credential_values_provided=signing_input.credential_values_provided,
        signature_algorithm_label=signing_input.signature_algorithm_label,
        signature_value_generated=signing_input.signature_value_generated,
        header_names_allowed=signing_input.header_names_allowed,
        header_values_redacted=signing_input.header_values_redacted
        and redacted_header.header_values_redacted,
        headers_displayed=signing_input.headers_displayed,
        headers_saved=signing_input.headers_saved,
        credentials_displayed=signing_input.credentials_displayed,
        credentials_saved=signing_input.credentials_saved,
        signature_displayed=signing_input.signature_displayed,
        signature_saved=signing_input.signature_saved,
        no_api_executed=True,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        check_results=checks,
        blocked_reasons=blocked_reasons,
        recommended_next_step=SIGNING_CONTRACT_RECOMMENDED_NEXT_STEP,
    )


def render_live_order_real_signing_contract_markdown(
    result: LiveOrderRealSigningContractResult,
) -> str:
    """Render a sanitized signing summary with names only and no values."""
    lines = [
        "# Step 6G Real Signing Contract",
        "",
        "This signing contract does not use real credentials.",
        "This signing contract does not generate real signatures.",
        "This transport contract does not execute API calls.",
        "This transport contract does not execute HTTP POST.",
        "This transport contract does not call order endpoint.",
        "This transport contract does not call live_order_once.",
        "Future real signing and real transport must be a separate Step.",
        "",
        "## Status",
        f"- signing_status: {result.status.value}",
        f"- signing_contract_ready: {_bool_text(result.signing_contract_ready)}",
        (
            "- redacted_header_contract_ready: "
            f"{_bool_text(result.redacted_header_contract_ready)}"
        ),
        f"- method: {result.method}",
        f"- path: {result.path}",
        f"- header_names_only: {','.join(result.header_names_allowed)}",
        f"- header_values_redacted: {_bool_text(result.header_values_redacted)}",
        (
            "- credential_values_provided: "
            f"{_bool_text(result.credential_values_provided)}"
        ),
        f"- signature_value_generated: {_bool_text(result.signature_value_generated)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Check Results",
        *[
            (
                f"- {check.name}: {_bool_text(check.passed)} "
                f"({check.sanitized_value}; expected {check.expected})"
            )
            for check in result.check_results
        ],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _build_check_results(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> tuple[LiveOrderRealSigningContractCheckResult, ...]:
    header_reasons = _header_contract_reasons(header_contract)
    return (
        validate_signing_inputs_without_secret_exposure(input_contract),
        LiveOrderRealSigningContractCheckResult(
            name="redacted header contract",
            passed=not header_reasons,
            sanitized_value="ready" if not header_reasons else ",".join(header_reasons),
            expected="header names only and values absent",
        ),
        ensure_signature_not_displayed_or_saved(input_contract, header_contract),
        ensure_credentials_not_displayed_or_saved(input_contract, header_contract),
    )


def _input_reasons(input_contract: LiveOrderRealSigningInputContract) -> tuple[str, ...]:
    reasons: list[str] = []
    if input_contract.method != SIGNING_CONTRACT_METHOD:
        reasons.append("method_not_post")
    if input_contract.path != TRANSPORT_CORE_ORDER_PATH:
        reasons.append("path_not_order_contract")
    if not input_contract.stable_serialized_body_contract_ready:
        reasons.append("body_contract_not_ready")
    if not input_contract.timestamp_required:
        reasons.append("timestamp_not_required")
    if not input_contract.credential_presence_required:
        reasons.append("credential_presence_not_required")
    if input_contract.header_names_allowed != TRANSPORT_CORE_HEADER_NAME_SUMMARY:
        reasons.append("header_names_not_allowed")
    if not input_contract.header_values_redacted:
        reasons.append("header_values_not_redacted")
    return tuple(reasons)


def _header_contract_reasons(
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not header_contract.redacted_header_contract_ready:
        reasons.append("redacted_header_contract_not_ready")
    if header_contract.allowed_header_names != TRANSPORT_CORE_HEADER_NAME_SUMMARY:
        reasons.append("header_names_not_allowed")
    if not header_contract.header_values_redacted:
        reasons.append("header_values_not_redacted")
    if not header_contract.safe_to_render:
        reasons.append("header_contract_not_safe_to_render")
    if not header_contract.safe_to_serialize:
        reasons.append("header_contract_not_safe_to_serialize")
    return tuple(reasons)


def _header_reasons(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if header_contract.header_values_present:
        reasons.append("header_values_present")
    for field_name in ("headers_displayed", "headers_saved"):
        if getattr(input_contract, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_reasons(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if input_contract.credential_values_provided:
        reasons.append("credential_values_provided")
    if header_contract.credential_value_present:
        reasons.append("credential_value_present")
    for field_name in ("credentials_displayed", "credentials_saved"):
        if getattr(input_contract, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _signature_reasons(
    input_contract: LiveOrderRealSigningInputContract,
    header_contract: LiveOrderRealRedactedHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if input_contract.timestamp_value_generated:
        reasons.append("timestamp_value_generated")
    if input_contract.signature_value_generated:
        reasons.append("signature_value_generated")
    if header_contract.signature_value_present:
        reasons.append("signature_value_present")
    for field_name in ("signature_displayed", "signature_saved"):
        if getattr(input_contract, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_reasons(input_contract: LiveOrderRealSigningInputContract) -> tuple[str, ...]:
    reasons: list[str] = []
    if input_contract.env_access_requested:
        reasons.append("env_access_requested")
    if input_contract.dotenv_access_requested:
        reasons.append("dotenv_access_requested")
    return tuple(reasons)


def _unsupported_reasons(
    input_contract: LiveOrderRealSigningInputContract,
) -> tuple[str, ...]:
    if input_contract.signature_algorithm_label != SIGNING_CONTRACT_ALGORITHM_LABEL:
        return ("unsupported_signature_algorithm",)
    return ()


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_str_tuple(field_name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
        raise LiveVerificationValidationError(f"{field_name} must be tuple[str, ...]")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
