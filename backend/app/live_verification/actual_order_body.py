"""Local-only actual order body model without transport or credentials."""

from __future__ import annotations

from dataclasses import dataclass

from app.live_verification.errors import LiveVerificationActualOrderBodyError
from app.live_verification.intent import OrderIntentSide
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS
from app.live_verification.signature_headers_body_plan import SignatureHeadersBodyPlan

ACTUAL_ORDER_EXECUTION_TYPE = "MARKET"
ACTUAL_ORDER_TIME_IN_FORCE = "FAK"
ACTUAL_ORDER_SETTLE_TYPE = "OPEN"


@dataclass(frozen=True)
class ActualOrderRequestBody:
    actual_order_body_id: str
    signature_headers_body_plan_id: str
    http_request_client_skeleton_id: str
    verification_run_id: str
    symbol: str
    side: OrderIntentSide
    size: int
    executionType: str
    timeInForce: str
    settleType: str
    body_created: bool
    http_post_enabled: bool
    headers_created: bool
    signature_created: bool
    raw_request_saved: bool
    raw_response_saved: bool
    credential_values_logged: bool
    real_order_attempted: bool

    def __post_init__(self) -> None:
        _validate_actual_order_body(self)


def build_actual_order_request_body(
    *,
    signature_headers_body_plan: SignatureHeadersBodyPlan,
    side: str | OrderIntentSide,
    symbol: str = SUPPORTED_SYMBOL,
    size: int = SUPPORTED_UNITS,
    execution_type: str = ACTUAL_ORDER_EXECUTION_TYPE,
    time_in_force: str = ACTUAL_ORDER_TIME_IN_FORCE,
    settle_type: str = ACTUAL_ORDER_SETTLE_TYPE,
    body_created: bool = True,
    http_post_enabled: bool = False,
    headers_created: bool = False,
    signature_created: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    credential_values_logged: bool = False,
    real_order_attempted: bool = False,
) -> ActualOrderRequestBody:
    """Build the body model only; never create headers, signatures, or transport."""
    _ensure_plan_type(signature_headers_body_plan)
    _validate_plan_is_safe(signature_headers_body_plan)
    normalized_side = _normalize_side(side)
    _validate_bool_map({
        "body_created": body_created,
        "http_post_enabled": http_post_enabled,
        "headers_created": headers_created,
        "signature_created": signature_created,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
        "real_order_attempted": real_order_attempted,
    })
    return ActualOrderRequestBody(
        actual_order_body_id=make_actual_order_body_id(
            signature_headers_body_plan_id=(
                signature_headers_body_plan.signature_headers_body_plan_id
            ),
            http_request_client_skeleton_id=(
                signature_headers_body_plan.http_request_client_skeleton_id
            ),
            verification_run_id=signature_headers_body_plan.verification_run_id,
        ),
        signature_headers_body_plan_id=(
            signature_headers_body_plan.signature_headers_body_plan_id
        ),
        http_request_client_skeleton_id=(
            signature_headers_body_plan.http_request_client_skeleton_id
        ),
        verification_run_id=signature_headers_body_plan.verification_run_id,
        symbol=symbol,
        side=normalized_side,
        size=size,
        executionType=execution_type,
        timeInForce=time_in_force,
        settleType=settle_type,
        body_created=body_created,
        http_post_enabled=http_post_enabled,
        headers_created=headers_created,
        signature_created=signature_created,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        credential_values_logged=credential_values_logged,
        real_order_attempted=real_order_attempted,
    )


def make_actual_order_body_id(
    *,
    signature_headers_body_plan_id: str,
    http_request_client_skeleton_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("signature_headers_body_plan_id", signature_headers_body_plan_id)
    _require_non_empty("http_request_client_skeleton_id", http_request_client_skeleton_id)
    _require_non_empty("verification_run_id", verification_run_id)
    return "_".join((
        "actual_order_body",
        verification_run_id,
        signature_headers_body_plan_id,
        http_request_client_skeleton_id,
    ))


def _ensure_plan_type(plan: SignatureHeadersBodyPlan) -> None:
    if not isinstance(plan, SignatureHeadersBodyPlan):
        raise LiveVerificationActualOrderBodyError(
            "signature_headers_body_plan is required"
        )


def _validate_plan_is_safe(plan: SignatureHeadersBodyPlan) -> None:
    for field_name, value in (
        ("signature_headers_body_plan_id", plan.signature_headers_body_plan_id),
        ("http_request_client_skeleton_id", plan.http_request_client_skeleton_id),
        ("verification_run_id", plan.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    if not plan.plan_passed:
        raise LiveVerificationActualOrderBodyError(
            "signature_headers_body_plan must pass"
        )
    if plan.fail_reasons:
        raise LiveVerificationActualOrderBodyError(
            "signature_headers_body_plan has fail reasons"
        )
    if not all((
        plan.body_plan_created,
        plan.headers_plan_created,
        plan.signature_plan_created,
    )):
        raise LiveVerificationActualOrderBodyError(
            "signature_headers_body_plan markers must be present"
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
        raise LiveVerificationActualOrderBodyError(
            "signature_headers_body_plan crossed safety flags"
        )


def _validate_actual_order_body(body: ActualOrderRequestBody) -> None:
    for field_name, value in (
        ("actual_order_body_id", body.actual_order_body_id),
        ("signature_headers_body_plan_id", body.signature_headers_body_plan_id),
        ("http_request_client_skeleton_id", body.http_request_client_skeleton_id),
        ("verification_run_id", body.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_actual_order_body_id(
        signature_headers_body_plan_id=body.signature_headers_body_plan_id,
        http_request_client_skeleton_id=body.http_request_client_skeleton_id,
        verification_run_id=body.verification_run_id,
    )
    if body.actual_order_body_id != expected_id:
        raise LiveVerificationActualOrderBodyError("actual_order_body_id mismatch")
    if body.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationActualOrderBodyError("symbol must be USD_JPY")
    if not isinstance(body.side, OrderIntentSide):
        raise LiveVerificationActualOrderBodyError("side must be BUY or SELL")
    if body.size != SUPPORTED_UNITS:
        raise LiveVerificationActualOrderBodyError("size must be 100")
    if body.executionType != ACTUAL_ORDER_EXECUTION_TYPE:
        raise LiveVerificationActualOrderBodyError("executionType must be MARKET")
    if body.timeInForce != ACTUAL_ORDER_TIME_IN_FORCE:
        raise LiveVerificationActualOrderBodyError("timeInForce must be FAK")
    if body.settleType != ACTUAL_ORDER_SETTLE_TYPE:
        raise LiveVerificationActualOrderBodyError("settleType must be OPEN")
    _validate_bool_map({
        "body_created": body.body_created,
        "http_post_enabled": body.http_post_enabled,
        "headers_created": body.headers_created,
        "signature_created": body.signature_created,
        "raw_request_saved": body.raw_request_saved,
        "raw_response_saved": body.raw_response_saved,
        "credential_values_logged": body.credential_values_logged,
        "real_order_attempted": body.real_order_attempted,
    })
    if not body.body_created:
        raise LiveVerificationActualOrderBodyError("body_created must be true")
    if any((
        body.http_post_enabled,
        body.headers_created,
        body.signature_created,
        body.raw_request_saved,
        body.raw_response_saved,
        body.credential_values_logged,
        body.real_order_attempted,
    )):
        raise LiveVerificationActualOrderBodyError("actual body crossed safety flags")


def _normalize_side(side: str | OrderIntentSide) -> OrderIntentSide:
    if isinstance(side, OrderIntentSide):
        return side
    if isinstance(side, str):
        try:
            return OrderIntentSide(side.strip().upper())
        except ValueError as error:
            raise LiveVerificationActualOrderBodyError(
                "side must be BUY or SELL"
            ) from error
    raise LiveVerificationActualOrderBodyError("side must be BUY or SELL")


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationActualOrderBodyError(f"{name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationActualOrderBodyError(f"{field_name} is required")
