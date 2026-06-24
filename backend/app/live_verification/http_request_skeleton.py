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
    _ensure_signature_design_type(signature_design)
    _validate_bool_map({
        "disabled_by_default": disabled_by_default,
        "network_enabled": network_enabled,
        "credential_access_enabled": credential_access_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "headers_created": headers_created,
        "request_body_created": request_body_created,
        "actual_signature_created": actual_signature_created,
        "raw_request_created": raw_request_created,
        "raw_response_saved": raw_response_saved,
        "signature_saved": signature_saved,
        "api_key_used": api_key_used,
        "api_secret_used": api_secret_used,
        "hmac_used": hmac_used,
        "real_order_attempted": real_order_attempted,
    })
    signature_request_design_id = _safe_text(
        signature_design.signature_request_design_id,
        "missing_signature_request_design_id",
    )
    order_client_plan_id = _safe_text(
        signature_design.order_client_plan_id,
        "missing_order_client_plan_id",
    )
    mocked_payload_candidate_id = _safe_text(
        signature_design.mocked_payload_candidate_id,
        "missing_mocked_payload_candidate_id",
    )
    verification_run_id = _safe_text(
        signature_design.verification_run_id,
        "missing_verification_run_id",
    )
    fail_reasons = [
        *_signature_design_fail_reasons(signature_design),
        *_skeleton_fail_reasons(
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
        ),
    ]
    return DisabledHttpRequestClientSkeletonPlan(
        http_request_client_skeleton_id=make_disabled_http_request_client_skeleton_id(
            signature_request_design_id=signature_request_design_id,
            order_client_plan_id=order_client_plan_id,
            mocked_payload_candidate_id=mocked_payload_candidate_id,
            verification_run_id=verification_run_id,
        ),
        signature_request_design_id=signature_request_design_id,
        order_client_plan_id=order_client_plan_id,
        mocked_payload_candidate_id=mocked_payload_candidate_id,
        verification_run_id=verification_run_id,
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
        skeleton_passed=not fail_reasons,
        fail_reasons=tuple(fail_reasons),
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


def _ensure_signature_design_type(model: SignatureHttpRequestDesignModel) -> None:
    if not isinstance(model, SignatureHttpRequestDesignModel):
        raise LiveVerificationHttpRequestSkeletonError("signature design is required")


def _signature_design_fail_reasons(model: SignatureHttpRequestDesignModel) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("signature_request_design_id", model.signature_request_design_id),
        ("order_client_plan_id", model.order_client_plan_id),
        ("mocked_payload_candidate_id", model.mocked_payload_candidate_id),
        ("verification_run_id", model.verification_run_id),
    ):
        if not _has_text(value):
            fail_reasons.append(f"{field_name}_missing")
    if all(
        _has_text(value)
        for value in (
            model.signature_request_design_id,
            model.order_client_plan_id,
            model.mocked_payload_candidate_id,
            model.verification_run_id,
        )
    ):
        expected_id = make_signature_request_design_id(
            order_client_plan_id=model.order_client_plan_id,
            mocked_payload_candidate_id=model.mocked_payload_candidate_id,
            verification_run_id=model.verification_run_id,
        )
        if model.signature_request_design_id != expected_id:
            fail_reasons.append("signature_request_design_id_mismatch")
    if model.client_mode != NO_NETWORK_CLIENT_MODE:
        fail_reasons.append("signature_design_client_mode")
    if _is_bool(model.disabled_by_default):
        if not model.disabled_by_default:
            fail_reasons.append("signature_design:disabled_by_default")
    else:
        fail_reasons.append("signature_design:disabled_by_default_not_bool")
    for name, value in {
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
    }.items():
        if _is_bool(value):
            if value:
                fail_reasons.append(f"signature_design:{name}")
        else:
            fail_reasons.append(f"signature_design:{name}_not_bool")
    return tuple(fail_reasons)


def _skeleton_fail_reasons(
    *,
    client_mode: str,
    disabled_by_default: bool,
    network_enabled: bool,
    credential_access_enabled: bool,
    http_client_enabled: bool,
    http_post_enabled: bool,
    headers_created: bool,
    request_body_created: bool,
    actual_signature_created: bool,
    raw_request_created: bool,
    raw_response_saved: bool,
    signature_saved: bool,
    api_key_used: bool,
    api_secret_used: bool,
    hmac_used: bool,
    real_order_attempted: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if client_mode != NO_NETWORK_HTTP_REQUEST_CLIENT_MODE:
        fail_reasons.append("client_mode")
    if not disabled_by_default:
        fail_reasons.append("disabled_by_default")
    for name, value in {
        "network_enabled": network_enabled,
        "credential_access_enabled": credential_access_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "headers_created": headers_created,
        "request_body_created": request_body_created,
        "actual_signature_created": actual_signature_created,
        "raw_request_created": raw_request_created,
        "raw_response_saved": raw_response_saved,
        "signature_saved": signature_saved,
        "api_key_used": api_key_used,
        "api_secret_used": api_secret_used,
        "hmac_used": hmac_used,
        "real_order_attempted": real_order_attempted,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


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
    _validate_bool_map({
        "disabled_by_default": plan.disabled_by_default,
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
        "skeleton_passed": plan.skeleton_passed,
    })
    if not isinstance(plan.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in plan.fail_reasons
    ):
        raise LiveVerificationHttpRequestSkeletonError("fail_reasons must be tuple[str, ...]")
    if plan.skeleton_passed and plan.fail_reasons:
        raise LiveVerificationHttpRequestSkeletonError("passed skeleton cannot contain reasons")
    if not plan.skeleton_passed and not plan.fail_reasons:
        raise LiveVerificationHttpRequestSkeletonError("failed skeleton requires reasons")
    if plan.skeleton_passed:
        if plan.client_mode != NO_NETWORK_HTTP_REQUEST_CLIENT_MODE:
            raise LiveVerificationHttpRequestSkeletonError("client mode is not allowed")
        if not plan.disabled_by_default:
            raise LiveVerificationHttpRequestSkeletonError("disabled_by_default must be true")
        if any((
            plan.network_enabled,
            plan.credential_access_enabled,
            plan.http_client_enabled,
            plan.http_post_enabled,
            plan.headers_created,
            plan.request_body_created,
            plan.actual_signature_created,
            plan.raw_request_created,
            plan.raw_response_saved,
            plan.signature_saved,
            plan.api_key_used,
            plan.api_secret_used,
            plan.hmac_used,
            plan.real_order_attempted,
        )):
            raise LiveVerificationHttpRequestSkeletonError(
                "passed skeleton cannot cross no-network flags"
            )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if not _is_bool(value):
            raise LiveVerificationHttpRequestSkeletonError(f"{name} must be bool")


def _is_bool(value: object) -> bool:
    return type(value) is bool


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationHttpRequestSkeletonError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_text(value: object, missing_value: str) -> str:
    if _has_text(value):
        return str(value)
    return missing_value


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
