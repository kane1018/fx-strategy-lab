"""Pure GMO FX Private API order/settlement body builders.

Scope: this module builds request bodies and signing-ready request plans
(method/path/body_json) for a future real `GmoFxBroker` order-write path. It
does not perform any HTTP request, does not accept or read credential
values, does not read process environment configuration files, and does not
call `app.private_api.auth` (signing is left to the future real transport
boundary, which must also pass through the shared real-broker-POST hard
guard). It never imports the Step 6G controlled/simulation family or the
one-shot live order primitive.

Entry and official settlement are kept as separate types/functions on
purpose:

- The entry body targets `POST /private/v1/order` only.
- The official settlement body targets the dedicated
  `POST /private/v1/closeOrder` route only -- never a generic opposite
  entry order used as a close. It only supports size-based settlement;
  position-specific (settlePosition-based) settlement has no field on the
  body type and is rejected by the builder function, because
  `position_specific_identifier_safe_handling_ready` is false project-wide.
"""

from __future__ import annotations

import json
from enum import Enum

from app.private_api.schemas import SanitizedModel

GMO_FX_ENTRY_ORDER_METHOD = "POST"
GMO_FX_ENTRY_ORDER_PATH = "/private/v1/order"
GMO_FX_OFFICIAL_SETTLEMENT_METHOD = "POST"
GMO_FX_OFFICIAL_SETTLEMENT_PATH = "/private/v1/closeOrder"
GMO_FX_SUPPORTED_EXECUTION_TYPE = "MARKET"

REQUEST_KIND_ENTRY = "ENTRY"
REQUEST_KIND_OFFICIAL_SETTLEMENT = "OFFICIAL_SETTLEMENT"


class GmoFxOrderBuilderError(ValueError):
    """Raised when a GMO FX order/settlement body cannot be built safely."""


class GmoFxOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class GmoFxEntryOrderBody(SanitizedModel):
    """Pure entry order body. Never includes settlement-only fields."""

    symbol: str
    side: str
    size: str
    executionType: str


class GmoFxOfficialSettlementBody(SanitizedModel):
    """Pure size-based official settlement body.

    Deliberately has no settlePosition-style field: position-specific
    settlement is not actual-path-enabled.
    """

    symbol: str
    side: str
    size: str
    executionType: str


class GmoFxPrivateRequestPlan(SanitizedModel):
    """Signing-ready request shape: method/path/body_json only.

    Does not include credential values, signatures, or headers. A future
    caller combines this with real credentials via
    `app.private_api.auth.build_auth_headers` at the actual transport
    boundary; this module never does that itself.
    """

    request_kind: str
    method: str
    path: str
    body_json: str


class GmoFxPrivateRequestPlanSafeSummary(SanitizedModel):
    """Safe-label-only summary for reports.

    Never includes body content, credential values, signatures, or headers.
    """

    request_kind: str
    method: str
    path: str
    body_field_count: int
    credential_value_included: bool = False
    signature_included: bool = False
    headers_value_included: bool = False


def build_gmo_fx_entry_order_body(
    *,
    symbol: str,
    side: str | GmoFxOrderSide,
    size: str,
) -> GmoFxEntryOrderBody:
    """Build a pure entry order body. Never touches settlement fields."""
    return GmoFxEntryOrderBody(
        symbol=_validate_symbol(symbol),
        side=_normalize_side(side).value,
        size=_validate_size(size),
        executionType=GMO_FX_SUPPORTED_EXECUTION_TYPE,
    )


def build_gmo_fx_official_settlement_body(
    *,
    symbol: str,
    side: str | GmoFxOrderSide,
    size: str | None = None,
    position_specific_settlement_id: str | None = None,
) -> GmoFxOfficialSettlementBody:
    """Build a pure, size-based official settlement body.

    `position_specific_settlement_id` exists only so callers get an explicit,
    safe rejection if they try position-specific settlement; the value is
    never stored, logged, or included in the raised error's message.
    """
    if size is not None and position_specific_settlement_id is not None:
        raise GmoFxOrderBuilderError(
            "size-based and position-specific settlement are mutually exclusive"
        )
    if position_specific_settlement_id is not None:
        raise GmoFxOrderBuilderError(
            "position-specific settlement is not actual-path-enabled: "
            "position_specific_identifier_safe_handling_ready=false"
        )
    if size is None:
        raise GmoFxOrderBuilderError("size is required for size-based settlement")
    return GmoFxOfficialSettlementBody(
        symbol=_validate_symbol(symbol),
        side=_normalize_side(side).value,
        size=_validate_size(size),
        executionType=GMO_FX_SUPPORTED_EXECUTION_TYPE,
    )


def build_gmo_fx_entry_request_plan(
    *,
    symbol: str,
    side: str | GmoFxOrderSide,
    size: str,
) -> GmoFxPrivateRequestPlan:
    body = build_gmo_fx_entry_order_body(symbol=symbol, side=side, size=size)
    return GmoFxPrivateRequestPlan(
        request_kind=REQUEST_KIND_ENTRY,
        method=GMO_FX_ENTRY_ORDER_METHOD,
        path=GMO_FX_ENTRY_ORDER_PATH,
        body_json=_serialize_body(body),
    )


def build_gmo_fx_official_settlement_request_plan(
    *,
    symbol: str,
    side: str | GmoFxOrderSide,
    size: str | None = None,
    position_specific_settlement_id: str | None = None,
) -> GmoFxPrivateRequestPlan:
    body = build_gmo_fx_official_settlement_body(
        symbol=symbol,
        side=side,
        size=size,
        position_specific_settlement_id=position_specific_settlement_id,
    )
    return GmoFxPrivateRequestPlan(
        request_kind=REQUEST_KIND_OFFICIAL_SETTLEMENT,
        method=GMO_FX_OFFICIAL_SETTLEMENT_METHOD,
        path=GMO_FX_OFFICIAL_SETTLEMENT_PATH,
        body_json=_serialize_body(body),
    )


def summarize_gmo_fx_private_request_plan(
    plan: GmoFxPrivateRequestPlan,
) -> GmoFxPrivateRequestPlanSafeSummary:
    body_obj = json.loads(plan.body_json)
    return GmoFxPrivateRequestPlanSafeSummary(
        request_kind=plan.request_kind,
        method=plan.method,
        path=plan.path,
        body_field_count=len(body_obj),
    )


def _serialize_body(body: SanitizedModel) -> str:
    return json.dumps(
        body.model_dump(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _normalize_side(side: str | GmoFxOrderSide) -> GmoFxOrderSide:
    if isinstance(side, GmoFxOrderSide):
        return side
    if isinstance(side, str):
        try:
            return GmoFxOrderSide(side.strip().upper())
        except ValueError as error:
            raise GmoFxOrderBuilderError("side must be BUY or SELL") from error
    raise GmoFxOrderBuilderError("side must be BUY or SELL")


def _validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol:
        raise GmoFxOrderBuilderError("symbol is required")
    return symbol


def _validate_size(size: str) -> str:
    if not isinstance(size, str) or not size:
        raise GmoFxOrderBuilderError("size is required")
    try:
        numeric = float(size)
    except ValueError as error:
        raise GmoFxOrderBuilderError("size must be numeric") from error
    if numeric <= 0:
        raise GmoFxOrderBuilderError("size must be positive")
    return size
