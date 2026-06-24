"""Sanitized schemas for GMO FX Private API read-only responses."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

OPEN_POSITION_LIST_KEYS = ("list", "positions", "openPositions", "open_positions", "data")
ACTIVE_ORDER_LIST_KEYS = ("list", "orders", "activeOrders", "active_orders", "data")


class SanitizedModel(BaseModel):
    """Base model that rejects unexpected fields after sanitization."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountAssets(SanitizedModel):
    equity: Decimal | None = None
    available_amount: Decimal | None = None
    balance: Decimal | None = None
    margin: Decimal | None = None
    margin_ratio: Decimal | None = None
    profit_loss: Decimal | None = None


class OpenPosition(SanitizedModel):
    position_id: str
    symbol: str
    side: str
    size: Decimal
    average_price: Decimal | None = None
    profit_loss: Decimal | None = None
    created_at: str | None = None


class ActiveOrder(SanitizedModel):
    order_id: str
    symbol: str
    side: str | None = None
    order_type: str | None = None
    size: Decimal | None = None
    price: Decimal | None = None
    status: str | None = None
    created_at: str | None = None


class Execution(SanitizedModel):
    execution_id: str
    order_id: str | None = None
    symbol: str
    side: str | None = None
    size: Decimal | None = None
    price: Decimal | None = None
    executed_at: str | None = None


class PositionSummary(SanitizedModel):
    symbol: str
    side: str | None = None
    size: Decimal | None = None
    average_price: Decimal | None = None
    profit_loss: Decimal | None = None


class PrivateApiError(SanitizedModel):
    code: str
    message: str
    status: int | None = None


def account_assets_from_api(raw: Mapping[str, Any]) -> AccountAssets:
    """Build a sanitized account assets model from a mocked API row."""
    return AccountAssets(
        equity=_decimal(raw, "equity", "actualAmount", "accountValue"),
        available_amount=_decimal(raw, "availableAmount", "available_amount"),
        balance=_decimal(raw, "balance", "cashAmount"),
        margin=_decimal(raw, "margin", "marginAmount"),
        margin_ratio=_decimal(raw, "marginRatio", "margin_ratio"),
        profit_loss=_decimal(raw, "profitLoss", "actualProfitLoss"),
    )


def open_position_from_api(raw: Mapping[str, Any]) -> OpenPosition:
    """Build a sanitized open position model from a mocked API row."""
    return OpenPosition(
        position_id=_string(raw, "positionId", "position_id", default=""),
        symbol=_string(raw, "symbol", default=""),
        side=_string(raw, "side", default=""),
        size=_decimal(raw, "size", "settleSize") or Decimal("0"),
        average_price=_decimal(raw, "averagePrice", "price"),
        profit_loss=_decimal(raw, "profitLoss", "lossGain"),
        created_at=_string_or_none(raw, "timestamp", "createdAt"),
    )


def open_positions_from_api_data(data: Any) -> list[OpenPosition]:
    """Build sanitized open position models from supported collection shapes."""
    return [open_position_from_api(row) for row in open_position_rows_from_api_data(data)]


def open_position_rows_from_api_data(data: Any) -> list[Mapping[str, Any]]:
    """Return open position rows without retaining unsupported raw payload shapes."""
    return _collection_rows_from_api_data(
        data=data,
        list_keys=OPEN_POSITION_LIST_KEYS,
        endpoint_name="openPositions",
    )


def active_order_from_api(raw: Mapping[str, Any]) -> ActiveOrder:
    """Build a sanitized active order model from a mocked API row."""
    return ActiveOrder(
        order_id=_string(raw, "orderId", "rootOrderId", default=""),
        symbol=_string(raw, "symbol", default=""),
        side=_string_or_none(raw, "side"),
        order_type=_string_or_none(raw, "orderType", "executionType"),
        size=_decimal(raw, "size", "orderSize"),
        price=_decimal(raw, "price"),
        status=_string_or_none(raw, "status"),
        created_at=_string_or_none(raw, "timestamp", "createdAt"),
    )


def active_orders_from_api_data(data: Any) -> list[ActiveOrder]:
    """Build sanitized active order models from supported collection shapes."""
    return [active_order_from_api(row) for row in active_order_rows_from_api_data(data)]


def active_order_rows_from_api_data(data: Any) -> list[Mapping[str, Any]]:
    """Return active order rows without retaining unsupported raw payload shapes."""
    return _collection_rows_from_api_data(
        data=data,
        list_keys=ACTIVE_ORDER_LIST_KEYS,
        endpoint_name="activeOrders",
    )


def execution_from_api(raw: Mapping[str, Any]) -> Execution:
    """Build a sanitized execution model from a mocked API row."""
    return Execution(
        execution_id=_string(raw, "executionId", "execution_id", default=""),
        order_id=_string_or_none(raw, "orderId", "rootOrderId"),
        symbol=_string(raw, "symbol", default=""),
        side=_string_or_none(raw, "side"),
        size=_decimal(raw, "size", "executionSize"),
        price=_decimal(raw, "price", "executionPrice"),
        executed_at=_string_or_none(raw, "timestamp", "executedAt"),
    )


def position_summary_from_api(raw: Mapping[str, Any]) -> PositionSummary:
    """Build a sanitized position summary model from a mocked API row."""
    return PositionSummary(
        symbol=_string(raw, "symbol", default=""),
        side=_string_or_none(raw, "side"),
        size=_decimal(raw, "size", "sumPositionQuantity"),
        average_price=_decimal(raw, "averagePrice"),
        profit_loss=_decimal(raw, "profitLoss", "sumLossGain"),
    )


def private_api_error_from_payload(raw: Mapping[str, Any]) -> PrivateApiError:
    """Build a sanitized error model from a mocked API error payload."""
    messages = raw.get("messages")
    first_message: Mapping[str, Any] | None = None
    fallback_message: str | None = None
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, Mapping):
            first_message = first
        elif first is not None:
            fallback_message = str(first)

    return PrivateApiError(
        code=(
            _string(first_message, "message_code", "code", default="unknown")
            if first_message is not None
            else "unknown"
        ),
        message=(
            _string(first_message, "message_string", "message", default="unknown")
            if first_message is not None
            else fallback_message or _string(raw, "message", "error", default="unknown")
        ),
        status=_int_or_none(raw.get("status")),
    )


def _decimal(raw: Mapping[str, Any], *keys: str) -> Decimal | None:
    value = _first(raw, *keys)
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _string(raw: Mapping[str, Any], *keys: str, default: str) -> str:
    value = _first(raw, *keys)
    if value is None:
        return default
    return str(value)


def _string_or_none(raw: Mapping[str, Any], *keys: str) -> str | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    return str(value)


def _first(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _first_list_field(raw: Mapping[str, Any], keys: tuple[str, ...]) -> list[Any] | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return value
    return None


def _collection_rows_from_api_data(
    *,
    data: Any,
    list_keys: tuple[str, ...],
    endpoint_name: str,
) -> list[Mapping[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return _ensure_mapping_rows(data, endpoint_name=endpoint_name)
    if isinstance(data, Mapping):
        nested = _first_list_field(data, list_keys)
        if nested is None:
            raise ValueError(f"{endpoint_name} data object has no list field")
        return _ensure_mapping_rows(nested, endpoint_name=endpoint_name)
    raise ValueError(f"{endpoint_name} data must be list, object, null, or missing")


def _ensure_mapping_rows(rows: list[Any], *, endpoint_name: str) -> list[Mapping[str, Any]]:
    sanitized_rows: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{endpoint_name} row must be an object")
        sanitized_rows.append(row)
    return sanitized_rows


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
