"""Plan-only boundary before body, header, and signing implementation."""

from __future__ import annotations

from dataclasses import dataclass

from app.live_verification.errors import LiveVerificationSignatureHeadersBodyPlanError
from app.live_verification.http_request_skeleton import (
    DisabledHttpRequestClientSkeletonPlan,
    make_disabled_http_request_client_skeleton_id,
)

SIGNATURE_HEADERS_BODY_PLAN_MODE = "signature_headers_body_plan"


@dataclass(frozen=True)
class SignatureHeadersBodyPlan:
    signature_headers_body_plan_id: str
    http_request_client_skeleton_id: str
    signature_request_design_id: str
    order_client_plan_id: str
    mocked_payload_candidate_id: str
    verification_run_id: str
    plan_mode: str
    body_plan_created: bool
    headers_plan_created: bool
    signature_plan_created: bool
    actual_body_created: bool
    actual_headers_created: bool
    actual_signature_created: bool
    http_post_enabled: bool
    credential_values_exposed: bool
    raw_request_saved: bool
    raw_response_saved: bool
    headers_saved: bool
    signature_saved: bool
    api_key_value_exposed: bool
    api_secret_value_exposed: bool
    hmac_used: bool
    real_order_attempted: bool
    plan_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_signature_headers_body_plan(self)


def build_signature_headers_body_plan(
    *,
    http_request_skeleton: DisabledHttpRequestClientSkeletonPlan,
    plan_mode: str = SIGNATURE_HEADERS_BODY_PLAN_MODE,
    body_plan_created: bool = True,
    headers_plan_created: bool = True,
    signature_plan_created: bool = True,
    actual_body_created: bool = False,
    actual_headers_created: bool = False,
    actual_signature_created: bool = False,
    http_post_enabled: bool = False,
    credential_values_exposed: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    headers_saved: bool = False,
    signature_saved: bool = False,
    api_key_value_exposed: bool = False,
    api_secret_value_exposed: bool = False,
    hmac_used: bool = False,
    real_order_attempted: bool = False,
) -> SignatureHeadersBodyPlan:
    """Build a local-only plan without constructing body, header, or signing values."""
    _ensure_skeleton_type(http_request_skeleton)
    _validate_bool_map({
        "body_plan_created": body_plan_created,
        "headers_plan_created": headers_plan_created,
        "signature_plan_created": signature_plan_created,
        "actual_body_created": actual_body_created,
        "actual_headers_created": actual_headers_created,
        "actual_signature_created": actual_signature_created,
        "http_post_enabled": http_post_enabled,
        "credential_values_exposed": credential_values_exposed,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "headers_saved": headers_saved,
        "signature_saved": signature_saved,
        "api_key_value_exposed": api_key_value_exposed,
        "api_secret_value_exposed": api_secret_value_exposed,
        "hmac_used": hmac_used,
        "real_order_attempted": real_order_attempted,
    })
    http_request_client_skeleton_id = _safe_text(
        http_request_skeleton.http_request_client_skeleton_id,
        "missing_http_request_client_skeleton_id",
    )
    signature_request_design_id = _safe_text(
        http_request_skeleton.signature_request_design_id,
        "missing_signature_request_design_id",
    )
    order_client_plan_id = _safe_text(
        http_request_skeleton.order_client_plan_id,
        "missing_order_client_plan_id",
    )
    mocked_payload_candidate_id = _safe_text(
        http_request_skeleton.mocked_payload_candidate_id,
        "missing_mocked_payload_candidate_id",
    )
    verification_run_id = _safe_text(
        http_request_skeleton.verification_run_id,
        "missing_verification_run_id",
    )
    fail_reasons = [
        *_http_request_skeleton_fail_reasons(http_request_skeleton),
        *_plan_fail_reasons(
            plan_mode=plan_mode,
            body_plan_created=body_plan_created,
            headers_plan_created=headers_plan_created,
            signature_plan_created=signature_plan_created,
            actual_body_created=actual_body_created,
            actual_headers_created=actual_headers_created,
            actual_signature_created=actual_signature_created,
            http_post_enabled=http_post_enabled,
            credential_values_exposed=credential_values_exposed,
            raw_request_saved=raw_request_saved,
            raw_response_saved=raw_response_saved,
            headers_saved=headers_saved,
            signature_saved=signature_saved,
            api_key_value_exposed=api_key_value_exposed,
            api_secret_value_exposed=api_secret_value_exposed,
            hmac_used=hmac_used,
            real_order_attempted=real_order_attempted,
        ),
    ]
    return SignatureHeadersBodyPlan(
        signature_headers_body_plan_id=make_signature_headers_body_plan_id(
            http_request_client_skeleton_id=http_request_client_skeleton_id,
            signature_request_design_id=signature_request_design_id,
            verification_run_id=verification_run_id,
        ),
        http_request_client_skeleton_id=http_request_client_skeleton_id,
        signature_request_design_id=signature_request_design_id,
        order_client_plan_id=order_client_plan_id,
        mocked_payload_candidate_id=mocked_payload_candidate_id,
        verification_run_id=verification_run_id,
        plan_mode=plan_mode,
        body_plan_created=body_plan_created,
        headers_plan_created=headers_plan_created,
        signature_plan_created=signature_plan_created,
        actual_body_created=actual_body_created,
        actual_headers_created=actual_headers_created,
        actual_signature_created=actual_signature_created,
        http_post_enabled=http_post_enabled,
        credential_values_exposed=credential_values_exposed,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        headers_saved=headers_saved,
        signature_saved=signature_saved,
        api_key_value_exposed=api_key_value_exposed,
        api_secret_value_exposed=api_secret_value_exposed,
        hmac_used=hmac_used,
        real_order_attempted=real_order_attempted,
        plan_passed=not fail_reasons,
        fail_reasons=tuple(fail_reasons),
    )


def make_signature_headers_body_plan_id(
    *,
    http_request_client_skeleton_id: str,
    signature_request_design_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("http_request_client_skeleton_id", http_request_client_skeleton_id)
    _require_non_empty("signature_request_design_id", signature_request_design_id)
    _require_non_empty("verification_run_id", verification_run_id)
    return "_".join((
        "sig_headers_body",
        verification_run_id,
        http_request_client_skeleton_id,
        signature_request_design_id,
    ))


def _ensure_skeleton_type(model: DisabledHttpRequestClientSkeletonPlan) -> None:
    if not isinstance(model, DisabledHttpRequestClientSkeletonPlan):
        raise LiveVerificationSignatureHeadersBodyPlanError(
            "http request skeleton is required"
        )


def _http_request_skeleton_fail_reasons(
    model: DisabledHttpRequestClientSkeletonPlan,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("http_request_client_skeleton_id", model.http_request_client_skeleton_id),
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
            model.http_request_client_skeleton_id,
            model.signature_request_design_id,
            model.order_client_plan_id,
            model.mocked_payload_candidate_id,
            model.verification_run_id,
        )
    ):
        expected_id = make_disabled_http_request_client_skeleton_id(
            signature_request_design_id=model.signature_request_design_id,
            order_client_plan_id=model.order_client_plan_id,
            mocked_payload_candidate_id=model.mocked_payload_candidate_id,
            verification_run_id=model.verification_run_id,
        )
        if model.http_request_client_skeleton_id != expected_id:
            fail_reasons.append("http_request_client_skeleton_id_mismatch")
    if _is_bool(model.skeleton_passed):
        if not model.skeleton_passed:
            fail_reasons.append("http_request_skeleton:not_passed")
    else:
        fail_reasons.append("http_request_skeleton:skeleton_passed_not_bool")
    if getattr(model, "fail_reasons", ()) != ():
        fail_reasons.append("http_request_skeleton:fail_reasons")
    if _is_bool(model.disabled_by_default):
        if not model.disabled_by_default:
            fail_reasons.append("http_request_skeleton:disabled_by_default")
    else:
        fail_reasons.append("http_request_skeleton:disabled_by_default_not_bool")
    for name, value in {
        "network_enabled": model.network_enabled,
        "credential_access_enabled": model.credential_access_enabled,
        "http_client_enabled": model.http_client_enabled,
        "http_post_enabled": model.http_post_enabled,
        "headers_created": model.headers_created,
        "request_body_created": model.request_body_created,
        "actual_signature_created": model.actual_signature_created,
        "raw_request_created": model.raw_request_created,
        "raw_response_saved": model.raw_response_saved,
        "signature_saved": model.signature_saved,
        "api_key_used": model.api_key_used,
        "api_secret_used": model.api_secret_used,
        "hmac_used": model.hmac_used,
        "real_order_attempted": model.real_order_attempted,
    }.items():
        if _is_bool(value):
            if value:
                fail_reasons.append(f"http_request_skeleton:{name}")
        else:
            fail_reasons.append(f"http_request_skeleton:{name}_not_bool")
    return tuple(fail_reasons)


def _plan_fail_reasons(
    *,
    plan_mode: str,
    body_plan_created: bool,
    headers_plan_created: bool,
    signature_plan_created: bool,
    actual_body_created: bool,
    actual_headers_created: bool,
    actual_signature_created: bool,
    http_post_enabled: bool,
    credential_values_exposed: bool,
    raw_request_saved: bool,
    raw_response_saved: bool,
    headers_saved: bool,
    signature_saved: bool,
    api_key_value_exposed: bool,
    api_secret_value_exposed: bool,
    hmac_used: bool,
    real_order_attempted: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if plan_mode != SIGNATURE_HEADERS_BODY_PLAN_MODE:
        fail_reasons.append("plan_mode")
    for name, value in {
        "body_plan_created": body_plan_created,
        "headers_plan_created": headers_plan_created,
        "signature_plan_created": signature_plan_created,
    }.items():
        if not value:
            fail_reasons.append(name)
    for name, value in {
        "actual_body_created": actual_body_created,
        "actual_headers_created": actual_headers_created,
        "actual_signature_created": actual_signature_created,
        "http_post_enabled": http_post_enabled,
        "credential_values_exposed": credential_values_exposed,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "headers_saved": headers_saved,
        "signature_saved": signature_saved,
        "api_key_value_exposed": api_key_value_exposed,
        "api_secret_value_exposed": api_secret_value_exposed,
        "hmac_used": hmac_used,
        "real_order_attempted": real_order_attempted,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


def _validate_signature_headers_body_plan(plan: SignatureHeadersBodyPlan) -> None:
    for field_name, value in (
        ("signature_headers_body_plan_id", plan.signature_headers_body_plan_id),
        ("http_request_client_skeleton_id", plan.http_request_client_skeleton_id),
        ("signature_request_design_id", plan.signature_request_design_id),
        ("order_client_plan_id", plan.order_client_plan_id),
        ("mocked_payload_candidate_id", plan.mocked_payload_candidate_id),
        ("verification_run_id", plan.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_signature_headers_body_plan_id(
        http_request_client_skeleton_id=plan.http_request_client_skeleton_id,
        signature_request_design_id=plan.signature_request_design_id,
        verification_run_id=plan.verification_run_id,
    )
    if plan.signature_headers_body_plan_id != expected_id:
        raise LiveVerificationSignatureHeadersBodyPlanError("plan id mismatch")
    _validate_bool_map({
        "body_plan_created": plan.body_plan_created,
        "headers_plan_created": plan.headers_plan_created,
        "signature_plan_created": plan.signature_plan_created,
        "actual_body_created": plan.actual_body_created,
        "actual_headers_created": plan.actual_headers_created,
        "actual_signature_created": plan.actual_signature_created,
        "http_post_enabled": plan.http_post_enabled,
        "credential_values_exposed": plan.credential_values_exposed,
        "raw_request_saved": plan.raw_request_saved,
        "raw_response_saved": plan.raw_response_saved,
        "headers_saved": plan.headers_saved,
        "signature_saved": plan.signature_saved,
        "api_key_value_exposed": plan.api_key_value_exposed,
        "api_secret_value_exposed": plan.api_secret_value_exposed,
        "hmac_used": plan.hmac_used,
        "real_order_attempted": plan.real_order_attempted,
        "plan_passed": plan.plan_passed,
    })
    if not isinstance(plan.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in plan.fail_reasons
    ):
        raise LiveVerificationSignatureHeadersBodyPlanError(
            "fail_reasons must be tuple[str, ...]"
        )
    if plan.plan_passed and plan.fail_reasons:
        raise LiveVerificationSignatureHeadersBodyPlanError(
            "passed plan cannot contain reasons"
        )
    if not plan.plan_passed and not plan.fail_reasons:
        raise LiveVerificationSignatureHeadersBodyPlanError(
            "failed plan requires reasons"
        )
    if plan.plan_passed:
        if plan.plan_mode != SIGNATURE_HEADERS_BODY_PLAN_MODE:
            raise LiveVerificationSignatureHeadersBodyPlanError("plan mode is not allowed")
        if not all((
            plan.body_plan_created,
            plan.headers_plan_created,
            plan.signature_plan_created,
        )):
            raise LiveVerificationSignatureHeadersBodyPlanError(
                "passed plan requires plan-only markers"
            )
        if any((
            plan.actual_body_created,
            plan.actual_headers_created,
            plan.actual_signature_created,
            plan.http_post_enabled,
            plan.credential_values_exposed,
            plan.raw_request_saved,
            plan.raw_response_saved,
            plan.headers_saved,
            plan.signature_saved,
            plan.api_key_value_exposed,
            plan.api_secret_value_exposed,
            plan.hmac_used,
            plan.real_order_attempted,
        )):
            raise LiveVerificationSignatureHeadersBodyPlanError(
                "passed plan cannot cross no-secret or no-request flags"
            )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if not _is_bool(value):
            raise LiveVerificationSignatureHeadersBodyPlanError(f"{name} must be bool")


def _is_bool(value: object) -> bool:
    return type(value) is bool


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationSignatureHeadersBodyPlanError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_text(value: object, missing_value: str) -> str:
    if _has_text(value):
        return str(value)
    return missing_value
