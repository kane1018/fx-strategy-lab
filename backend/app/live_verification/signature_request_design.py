"""Design-only model before any signed transport for Phase 3D-8."""

from __future__ import annotations

from dataclasses import dataclass

from app.live_verification.errors import LiveVerificationSignatureRequestDesignError
from app.live_verification.order_client_skeleton import (
    NO_NETWORK_CLIENT_MODE,
    DisabledOrderClientPlan,
    make_disabled_order_client_plan_id,
)
from app.live_verification.payload_candidate import (
    MockedOrderPayloadCandidate,
    make_mocked_payload_candidate_id,
)
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)

ORDER_CREATE_METHOD_LABEL = "ORDER_CREATE_METHOD_LABEL"
ORDER_CREATE_PATH_LABEL = "ORDER_CREATE_PATH_LABEL"
ORDER_CREATE_BODY_SHAPE_LABEL = "ORDER_CREATE_BODY_SHAPE_LABEL"
TIMESTAMP_PLACEHOLDER = "TIMESTAMP_PLACEHOLDER"

ALLOWED_METHOD_LABELS = frozenset({ORDER_CREATE_METHOD_LABEL})
ALLOWED_PATH_LABELS = frozenset({ORDER_CREATE_PATH_LABEL})
ALLOWED_BODY_SHAPE_LABELS = frozenset({ORDER_CREATE_BODY_SHAPE_LABEL})
ALLOWED_TIMESTAMP_PLACEHOLDERS = frozenset({TIMESTAMP_PLACEHOLDER})


@dataclass(frozen=True)
class SignatureHttpRequestDesignModel:
    signature_request_design_id: str
    order_client_plan_id: str
    mocked_payload_candidate_id: str
    verification_run_id: str
    client_mode: str
    disabled_by_default: bool
    network_enabled: bool
    credential_access_enabled: bool
    method_label: str
    path_label: str
    body_shape_label: str
    timestamp_placeholder: str
    signing_source_candidate: str
    actual_signature_created: bool
    headers_created: bool
    request_body_created: bool
    http_request_created: bool
    api_key_used: bool
    api_secret_used: bool
    hmac_used: bool
    network_used: bool
    real_order_attempted: bool

    def __post_init__(self) -> None:
        _validate_design_model(self)


def build_signature_http_request_design_model(
    *,
    order_client_plan: DisabledOrderClientPlan,
    mocked_payload_candidate: MockedOrderPayloadCandidate,
    method_label: str,
    path_label: str,
    body_shape_label: str,
    timestamp_placeholder: str,
) -> SignatureHttpRequestDesignModel:
    """Build a placeholder-only design model without credentials or transport."""
    _validate_plan_and_candidate(
        order_client_plan=order_client_plan,
        mocked_payload_candidate=mocked_payload_candidate,
    )
    _validate_design_labels(
        method_label=method_label,
        path_label=path_label,
        body_shape_label=body_shape_label,
        timestamp_placeholder=timestamp_placeholder,
    )
    signing_source_candidate = make_signing_source_candidate(
        method_label=method_label,
        path_label=path_label,
        body_shape_label=body_shape_label,
        timestamp_placeholder=timestamp_placeholder,
    )
    return SignatureHttpRequestDesignModel(
        signature_request_design_id=make_signature_request_design_id(
            order_client_plan_id=order_client_plan.client_plan_id,
            mocked_payload_candidate_id=mocked_payload_candidate.mocked_payload_candidate_id,
            verification_run_id=order_client_plan.verification_run_id,
        ),
        order_client_plan_id=order_client_plan.client_plan_id,
        mocked_payload_candidate_id=mocked_payload_candidate.mocked_payload_candidate_id,
        verification_run_id=order_client_plan.verification_run_id,
        client_mode=order_client_plan.client_mode,
        disabled_by_default=order_client_plan.disabled_by_default,
        network_enabled=order_client_plan.network_enabled,
        credential_access_enabled=order_client_plan.credential_access_enabled,
        method_label=method_label,
        path_label=path_label,
        body_shape_label=body_shape_label,
        timestamp_placeholder=timestamp_placeholder,
        signing_source_candidate=signing_source_candidate,
        actual_signature_created=False,
        headers_created=False,
        request_body_created=False,
        http_request_created=False,
        api_key_used=False,
        api_secret_used=False,
        hmac_used=False,
        network_used=False,
        real_order_attempted=False,
    )


def make_signature_request_design_id(
    *,
    order_client_plan_id: str,
    mocked_payload_candidate_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("order_client_plan_id", order_client_plan_id)
    _require_non_empty("mocked_payload_candidate_id", mocked_payload_candidate_id)
    _require_non_empty("verification_run_id", verification_run_id)
    return (
        "sigreq_design_"
        f"{verification_run_id}_{order_client_plan_id}_{mocked_payload_candidate_id}"
    )


def make_signing_source_candidate(
    *,
    method_label: str,
    path_label: str,
    body_shape_label: str,
    timestamp_placeholder: str,
) -> str:
    _validate_design_labels(
        method_label=method_label,
        path_label=path_label,
        body_shape_label=body_shape_label,
        timestamp_placeholder=timestamp_placeholder,
    )
    return "|".join((
        timestamp_placeholder,
        method_label,
        path_label,
        body_shape_label,
    ))


def _validate_plan_and_candidate(
    *,
    order_client_plan: DisabledOrderClientPlan,
    mocked_payload_candidate: MockedOrderPayloadCandidate,
) -> None:
    _validate_plan(order_client_plan)
    _validate_candidate(mocked_payload_candidate)
    if order_client_plan.payload_candidate_id != (
        mocked_payload_candidate.mocked_payload_candidate_id
    ):
        raise LiveVerificationSignatureRequestDesignError("payload candidate id mismatch")
    if order_client_plan.verification_run_id != mocked_payload_candidate.verification_run_id:
        raise LiveVerificationSignatureRequestDesignError("verification_run_id mismatch")
    if order_client_plan.symbol != mocked_payload_candidate.symbol:
        raise LiveVerificationSignatureRequestDesignError("symbol mismatch")
    if order_client_plan.units != mocked_payload_candidate.size:
        raise LiveVerificationSignatureRequestDesignError("units mismatch")
    if order_client_plan.order_review_id != mocked_payload_candidate.order_review_id:
        raise LiveVerificationSignatureRequestDesignError("order_review_id mismatch")
    if order_client_plan.final_checklist_id != mocked_payload_candidate.final_checklist_id:
        raise LiveVerificationSignatureRequestDesignError("final_checklist_id mismatch")
    if order_client_plan.boundary_check_id != mocked_payload_candidate.boundary_check_id:
        raise LiveVerificationSignatureRequestDesignError("boundary_check_id mismatch")


def _validate_plan(plan: DisabledOrderClientPlan) -> None:
    for field_name, value in (
        ("client_plan_id", plan.client_plan_id),
        ("payload_candidate_id", plan.payload_candidate_id),
        ("order_review_id", plan.order_review_id),
        ("final_checklist_id", plan.final_checklist_id),
        ("boundary_check_id", plan.boundary_check_id),
        ("verification_run_id", plan.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_disabled_order_client_plan_id(
        payload_candidate_id=plan.payload_candidate_id,
        verification_run_id=plan.verification_run_id,
    )
    if plan.client_plan_id != expected_id:
        raise LiveVerificationSignatureRequestDesignError("client_plan_id mismatch")
    if plan.client_mode != NO_NETWORK_CLIENT_MODE:
        raise LiveVerificationSignatureRequestDesignError("client mode is not allowed")
    if plan.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationSignatureRequestDesignError("symbol must be USD_JPY")
    if plan.units != SUPPORTED_UNITS:
        raise LiveVerificationSignatureRequestDesignError("units must be 100")
    _require_true("disabled_by_default", plan.disabled_by_default)
    _require_false("network_enabled", plan.network_enabled)
    _require_false("credential_access_enabled", plan.credential_access_enabled)


def _validate_candidate(candidate: MockedOrderPayloadCandidate) -> None:
    for field_name, value in (
        ("mocked_payload_candidate_id", candidate.mocked_payload_candidate_id),
        ("order_review_id", candidate.order_review_id),
        ("final_checklist_id", candidate.final_checklist_id),
        ("boundary_check_id", candidate.boundary_check_id),
        ("verification_run_id", candidate.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_mocked_payload_candidate_id(
        order_review_id=candidate.order_review_id,
        final_checklist_id=candidate.final_checklist_id,
        boundary_check_id=candidate.boundary_check_id,
        verification_run_id=candidate.verification_run_id,
    )
    if candidate.mocked_payload_candidate_id != expected_id:
        raise LiveVerificationSignatureRequestDesignError("mocked payload id mismatch")
    if candidate.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationSignatureRequestDesignError("symbol must be USD_JPY")
    if candidate.size != SUPPORTED_UNITS:
        raise LiveVerificationSignatureRequestDesignError("size must be 100")
    if candidate.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationSignatureRequestDesignError("mode must be live_verification")
    _validate_false_flags({
        "network_used": candidate.network_used,
        "api_key_used": candidate.api_key_used,
        "broker_called": candidate.broker_called,
        "real_order_attempted": candidate.real_order_attempted,
    })


def _validate_design_model(model: SignatureHttpRequestDesignModel) -> None:
    for field_name, value in (
        ("signature_request_design_id", model.signature_request_design_id),
        ("order_client_plan_id", model.order_client_plan_id),
        ("mocked_payload_candidate_id", model.mocked_payload_candidate_id),
        ("verification_run_id", model.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_signature_request_design_id(
        order_client_plan_id=model.order_client_plan_id,
        mocked_payload_candidate_id=model.mocked_payload_candidate_id,
        verification_run_id=model.verification_run_id,
    )
    if model.signature_request_design_id != expected_id:
        raise LiveVerificationSignatureRequestDesignError("design id mismatch")
    if model.client_mode != NO_NETWORK_CLIENT_MODE:
        raise LiveVerificationSignatureRequestDesignError("client mode is not allowed")
    _require_true("disabled_by_default", model.disabled_by_default)
    _require_false("network_enabled", model.network_enabled)
    _require_false("credential_access_enabled", model.credential_access_enabled)
    _validate_design_labels(
        method_label=model.method_label,
        path_label=model.path_label,
        body_shape_label=model.body_shape_label,
        timestamp_placeholder=model.timestamp_placeholder,
    )
    expected_candidate = make_signing_source_candidate(
        method_label=model.method_label,
        path_label=model.path_label,
        body_shape_label=model.body_shape_label,
        timestamp_placeholder=model.timestamp_placeholder,
    )
    if model.signing_source_candidate != expected_candidate:
        raise LiveVerificationSignatureRequestDesignError("source candidate mismatch")
    _validate_false_flags({
        "actual_signature_created": model.actual_signature_created,
        "headers_created": model.headers_created,
        "request_body_created": model.request_body_created,
        "http_request_created": model.http_request_created,
        "api_key_used": model.api_key_used,
        "api_secret_used": model.api_secret_used,
        "hmac_used": model.hmac_used,
        "network_used": model.network_used,
        "real_order_attempted": model.real_order_attempted,
    })


def _validate_design_labels(
    *,
    method_label: str,
    path_label: str,
    body_shape_label: str,
    timestamp_placeholder: str,
) -> None:
    if method_label not in ALLOWED_METHOD_LABELS:
        raise LiveVerificationSignatureRequestDesignError("method_label is not allowed")
    if path_label not in ALLOWED_PATH_LABELS:
        raise LiveVerificationSignatureRequestDesignError("path_label is not allowed")
    if body_shape_label not in ALLOWED_BODY_SHAPE_LABELS:
        raise LiveVerificationSignatureRequestDesignError("body_shape_label is not allowed")
    if timestamp_placeholder not in ALLOWED_TIMESTAMP_PLACEHOLDERS:
        raise LiveVerificationSignatureRequestDesignError(
            "timestamp_placeholder is not allowed"
        )


def _validate_false_flags(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        _require_false(name, value)


def _require_true(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationSignatureRequestDesignError(f"{field_name} must be bool")
    if not value:
        raise LiveVerificationSignatureRequestDesignError(f"{field_name} must be true")


def _require_false(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationSignatureRequestDesignError(f"{field_name} must be bool")
    if value:
        raise LiveVerificationSignatureRequestDesignError(f"{field_name} must be false")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationSignatureRequestDesignError(f"{field_name} is required")
