"""Disabled HTTP skeleton plan for Phase 3D-10 live verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.errors import LiveVerificationHttpRequestSkeletonError
from app.live_verification.order_client_skeleton import NO_NETWORK_CLIENT_MODE
from app.live_verification.signature_request_design import (
    SignatureHttpRequestDesignModel,
    make_signature_request_design_id,
)

NO_NETWORK_HTTP_REQUEST_CLIENT_MODE = "no_network_http_request_skeleton"


@dataclass(frozen=True)
class DisabledHttpRequestClientSkeletonPlan:
    http_request_client_skeleton_id: str
    signature_request_design_id: str
    order_client_plan_id: str
    mocked_payload_candidate_id: str
    verification_run_id: str
    client_mode: str
    disabled_by_default: bool
    network_enabled: bool
    credential_access_enabled: bool
    http_client_enabled: bool
    http_post_enabled: bool
    headers_created: bool
    request_body_created: bool
    actual_signature_created: bool
    raw_request_created: bool
    raw_response_saved: bool
    signature_saved: bool
    api_key_used: bool
    api_secret_used: bool
    hmac_used: bool
    real_order_attempted: bool
    skeleton_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_skeleton_plan(self)


def build_disabled_http_request_client_skeleton_plan(
    *,
    signature_design: SignatureHttpRequestDesignModel,
    client_mode: str = NO_NETWORK_HTTP_REQUEST_CLIENT_MODE,
    disabled_by_default: bool = True,
    network_enabled: bool = False,
    credential_access_enabled: bool = False,
    http_client_enabled: bool = False,
    http_post_enabled: bool = False,
    headers_created: bool = False,
    request_body_created: bool = False,
    actual_signature_created: bool = False,
    raw_request_created: bool = False,
    raw_response_saved: bool = False,
    signature_saved: bool = False,
    api_key_used: bool = False,
    api_secret_used: bool = False,
    hmac_used: bool = False,
    real_order_attempted: bool = False,
) -> DisabledHttpRequestClientSkeletonPlan:
    """Build a disabled local-only plan after the design-only model."""
    _validate_signature_design(signature_design)
    return DisabledHttpRequestClientSkeletonPlan(
        http_request_client_skeleton_id=make_disabled_http_request_client_skeleton_id(
            signature_request_design_id=signature_design.signature_request_design_id,
            order_client_plan_id=signature_design.order_client_plan_id,
            mocked_payload_candidate_id=signature_design.mocked_payload_candidate_id,
            verification_run_id=signature_design.verification_run_id,
        ),
        signature_request_design_id=signature_design.signature_request_design_id,
        order_client_plan_id=signature_design.order_client_plan_id,
        mocked_payload_candidate_id=signature_design.mocked_payload_candidate_id,
        verification_run_id=signature_design.verification_run_id,
        client_mode=client_mode,
        disabled_by_default=disabled_by_default,
        network_enabled=network_enabled,
        credential_access_enabled=credential_access_enabled,
        http_client_enabled=http_client_enabled,
        http_post_enabled=http_post_enabled,
        headers_created=headers_created,
        request_body_created=request_body_created,
        actual_signature_created=actual_signature_created,
        raw_request_created=raw_request_created,
        raw_response_saved=raw_response_saved,
        signature_saved=signature_saved,
        api_key_used=api_key_used,
        api_secret_used=api_secret_used,
        hmac_used=hmac_used,
        real_order_attempted=real_order_attempted,
        skeleton_passed=True,
        fail_reasons=(),
    )


def make_disabled_http_request_client_skeleton_id(
    *,
    signature_request_design_id: str,
    order_client_plan_id: str,
    mocked_payload_candidate_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("signature_request_design_id", signature_request_design_id)
    _require_non_empty("order_client_plan_id", order_client_plan_id)
    _require_non_empty("mocked_payload_candidate_id", mocked_payload_candidate_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "mocked_payload_candidate_id": mocked_payload_candidate_id,
        "order_client_plan_id": order_client_plan_id,
        "signature_request_design_id": signature_request_design_id,
        "verification_run_id": verification_run_id,
    })
    return f"disabled_http_skeleton_{verification_run_id}_{digest}"


def _validate_signature_design(model: SignatureHttpRequestDesignModel) -> None:
    if not isinstance(model, SignatureHttpRequestDesignModel):
        raise LiveVerificationHttpRequestSkeletonError("signature design is required")
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
        raise LiveVerificationHttpRequestSkeletonError("design id mismatch")
    if model.client_mode != NO_NETWORK_CLIENT_MODE:
        raise LiveVerificationHttpRequestSkeletonError("client mode is not allowed")
    _require_true("disabled_by_default", model.disabled_by_default)
    _validate_false_flags({
        "network_enabled": model.network_enabled,
        "credential_access_enabled": model.credential_access_enabled,
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


def _validate_skeleton_plan(plan: DisabledHttpRequestClientSkeletonPlan) -> None:
    for field_name, value in (
        ("http_request_client_skeleton_id", plan.http_request_client_skeleton_id),
        ("signature_request_design_id", plan.signature_request_design_id),
        ("order_client_plan_id", plan.order_client_plan_id),
        ("mocked_payload_candidate_id", plan.mocked_payload_candidate_id),
        ("verification_run_id", plan.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_disabled_http_request_client_skeleton_id(
        signature_request_design_id=plan.signature_request_design_id,
        order_client_plan_id=plan.order_client_plan_id,
        mocked_payload_candidate_id=plan.mocked_payload_candidate_id,
        verification_run_id=plan.verification_run_id,
    )
    if plan.http_request_client_skeleton_id != expected_id:
        raise LiveVerificationHttpRequestSkeletonError("skeleton id mismatch")
    if plan.client_mode != NO_NETWORK_HTTP_REQUEST_CLIENT_MODE:
        raise LiveVerificationHttpRequestSkeletonError("client mode is not allowed")
    _require_true("disabled_by_default", plan.disabled_by_default)
    _validate_false_flags({
        "network_enabled": plan.network_enabled,
        "credential_access_enabled": plan.credential_access_enabled,
        "http_client_enabled": plan.http_client_enabled,
        "http_post_enabled": plan.http_post_enabled,
        "headers_created": plan.headers_created,
        "request_body_created": plan.request_body_created,
        "actual_signature_created": plan.actual_signature_created,
        "raw_request_created": plan.raw_request_created,
        "raw_response_saved": plan.raw_response_saved,
        "signature_saved": plan.signature_saved,
        "api_key_used": plan.api_key_used,
        "api_secret_used": plan.api_secret_used,
        "hmac_used": plan.hmac_used,
        "real_order_attempted": plan.real_order_attempted,
    })
    _require_true("skeleton_passed", plan.skeleton_passed)
    if plan.fail_reasons != ():
        raise LiveVerificationHttpRequestSkeletonError("fail_reasons must be empty")


def _validate_false_flags(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        _require_false(name, value)


def _require_true(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} must be bool")
    if not value:
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} must be true")


def _require_false(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} must be bool")
    if value:
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} must be false")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} is required")


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
