"""Sanitized schemas for GMO FX Private API read-only responses."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


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
