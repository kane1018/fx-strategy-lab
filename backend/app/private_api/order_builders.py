"""Pure GMO FX Private API order/settlement body builders.

Scope: this module builds request bodies and signing-ready request plans
(method/path/body_json) for a future real `GmoFxBroker` order-write path. It
does not perform any HTTP request, does not accept or read credential
values, does not read process environment configuration files, and does not
call `app.private_api.auth` (signing is left to the future real transport
boundary, which must also pass through the shared real-broker-POST hard
guard). It never imports the Step 6G controlled/simulation family or the
one-shot live order primitive.

Entry, IFDOCO-protected entry, and official settlement are kept as separate
types/functions on purpose:

- The entry body targets `POST /private/v1/order` only.
- The IFDOCO body targets `POST /private/v1/ifoOrder` only and atomically
  describes one pending entry plus broker-side OCO protection. It remains a
  pure request plan in this module; no sender is bound here.
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
GMO_FX_IFDOCO_ORDER_METHOD = "POST"
GMO_FX_IFDOCO_ORDER_PATH = "/private/v1/ifoOrder"
GMO_FX_OFFICIAL_SETTLEMENT_METHOD = "POST"
GMO_FX_OFFICIAL_SETTLEMENT_PATH = "/private/v1/closeOrder"
GMO_FX_SUPPORTED_EXECUTION_TYPE = "MARKET"

REQUEST_KIND_ENTRY = "ENTRY"
REQUEST_KIND_IFDOCO_PROTECTED_ENTRY = "IFDOCO_PROTECTED_ENTRY"
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


class GmoFxIfdocoOrderBody(SanitizedModel):
    """Pure IFDOCO body: one pending entry and broker-side OCO protection."""

    symbol: str
    clientOrderId: str | None = None
    firstSide: str
    firstExecutionType: str
    firstSize: str
    firstPrice: str
    secondSize: str
    secondLimitPrice: str
    secondStopPrice: str


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


def build_gmo_fx_ifdoco_order_body(
    *,
    symbol: str,
    first_side: str | GmoFxOrderSide,
    first_size: str,
    first_price: str,
    second_size: str,
    second_limit_price: str,
    second_stop_price: str,
    client_order_id: str | None = None,
    first_execution_type: str = "STOP",
) -> GmoFxIfdocoOrderBody:
    """Build a pure H-11 v3 IFDOCO protected-entry body.

    The first execution type is frozen to STOP. Supporting LIMIT later would
    be a different frozen execution profile rather than a runtime switch.
    """

    if first_execution_type != "STOP":
        raise GmoFxOrderBuilderError(
            "H-11 v3 IFDOCO first execution type must be STOP"
        )
    size = _validate_size(first_size)
    protective_size = _validate_size(second_size)
    if size != protective_size:
        raise GmoFxOrderBuilderError(
            "IFDOCO entry and protective close sizes must match"
        )
    normalized_side = _normalize_side(first_side)
    entry_price = _validate_positive_decimal(first_price, field_name="first_price")
    take_profit = _validate_positive_decimal(
        second_limit_price, field_name="second_limit_price"
    )
    stop_loss = _validate_positive_decimal(
        second_stop_price, field_name="second_stop_price"
    )
    _validate_ifdoco_price_ordering(
        side=normalized_side,
        entry_price=entry_price,
        take_profit=take_profit,
        stop_loss=stop_loss,
    )
    return GmoFxIfdocoOrderBody(
        symbol=_validate_symbol(symbol),
        clientOrderId=_validate_client_order_id(client_order_id),
        firstSide=normalized_side.value,
        firstExecutionType="STOP",
        firstSize=size,
        firstPrice=entry_price,
        secondSize=protective_size,
        secondLimitPrice=take_profit,
        secondStopPrice=stop_loss,
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


def build_gmo_fx_ifdoco_request_plan(
    *,
    symbol: str,
    first_side: str | GmoFxOrderSide,
    first_size: str,
    first_price: str,
    second_size: str,
    second_limit_price: str,
    second_stop_price: str,
    client_order_id: str | None = None,
    first_execution_type: str = "STOP",
) -> GmoFxPrivateRequestPlan:
    body = build_gmo_fx_ifdoco_order_body(
        symbol=symbol,
        first_side=first_side,
        first_size=first_size,
        first_price=first_price,
        second_size=second_size,
        second_limit_price=second_limit_price,
        second_stop_price=second_stop_price,
        client_order_id=client_order_id,
        first_execution_type=first_execution_type,
    )
    return GmoFxPrivateRequestPlan(
        request_kind=REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
        method=GMO_FX_IFDOCO_ORDER_METHOD,
        path=GMO_FX_IFDOCO_ORDER_PATH,
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
        body.model_dump(exclude_none=True),
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


def _validate_positive_decimal(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise GmoFxOrderBuilderError(f"{field_name} is required")
    try:
        numeric = float(value)
    except ValueError as error:
        raise GmoFxOrderBuilderError(f"{field_name} must be numeric") from error
    if numeric <= 0:
        raise GmoFxOrderBuilderError(f"{field_name} must be positive")
    return value


def _validate_client_order_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not value or len(value) > 36 or not value.isascii() or not value.isalnum():
        raise GmoFxOrderBuilderError(
            "client_order_id must be 1-36 ASCII alphanumeric characters"
        )
    return value


def _validate_ifdoco_price_ordering(
    *,
    side: GmoFxOrderSide,
    entry_price: str,
    take_profit: str,
    stop_loss: str,
) -> None:
    entry = float(entry_price)
    take = float(take_profit)
    stop = float(stop_loss)
    valid = stop < entry < take if side is GmoFxOrderSide.BUY else take < entry < stop
    if not valid:
        raise GmoFxOrderBuilderError(
            "IFDOCO protective prices must bracket the entry in the correct direction"
        )
