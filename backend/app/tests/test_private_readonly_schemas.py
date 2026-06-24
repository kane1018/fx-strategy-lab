from decimal import Decimal

import pytest

from app.private_api.schemas import (
    account_assets_from_api,
    active_order_from_api,
    execution_from_api,
    open_position_from_api,
    open_positions_from_api_data,
    position_summary_from_api,
    private_api_error_from_payload,
)


def test_account_assets_sanitizer_uses_known_fields_only() -> None:
    model = account_assets_from_api(
        {
            "actualAmount": "1000000.5",
            "availableAmount": "900000.25",
            "cashAmount": "950000",
            "marginAmount": "10000",
            "marginRatio": "250.5",
            "actualProfitLoss": "-123.45",
            "API-KEY": "<API_KEY>",
            "API-SIGN": "<SIGNATURE>",
        }
    )

    dumped = model.model_dump()
    assert dumped["equity"] == Decimal("1000000.5")
    assert dumped["available_amount"] == Decimal("900000.25")
    assert dumped["profit_loss"] == Decimal("-123.45")
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped


def test_open_position_sanitizer_uses_known_fields_only() -> None:
    model = open_position_from_api(
        {
            "positionId": "pos-1",
            "symbol": "USD_JPY",
            "side": "BUY",
            "size": "100",
            "price": "150.1",
            "lossGain": "12.3",
            "timestamp": "2026-06-24T00:00:00.000Z",
            "API-KEY": "<API_KEY>",
            "API-SIGN": "<SIGNATURE>",
        }
    )

    dumped = model.model_dump()
    assert dumped["position_id"] == "pos-1"
    assert dumped["symbol"] == "USD_JPY"
    assert dumped["size"] == Decimal("100")
    assert dumped["profit_loss"] == Decimal("12.3")
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped


def test_open_positions_collection_accepts_list_data() -> None:
    models = open_positions_from_api_data(
        [
            {
                "positionId": "pos-1",
                "symbol": "USD_JPY",
                "side": "BUY",
                "size": "100",
                "API-KEY": "<API_KEY>",
            }
        ]
    )

    dumped = models[0].model_dump()
    assert dumped["position_id"] == "pos-1"
    assert dumped["size"] == Decimal("100")
    assert "API-KEY" not in dumped


def test_open_positions_collection_accepts_object_with_list_field() -> None:
    models = open_positions_from_api_data(
        {
            "list": [
                {
                    "positionId": "pos-1",
                    "symbol": "USD_JPY",
                    "side": "SELL",
                    "size": "200",
                    "API-SIGN": "<SIGNATURE>",
                }
            ],
            "API-KEY": "<API_KEY>",
        }
    )

    dumped = models[0].model_dump()
    assert dumped["position_id"] == "pos-1"
    assert dumped["side"] == "SELL"
    assert dumped["size"] == Decimal("200")
    assert "API-SIGN" not in dumped
    assert "API-KEY" not in dumped


@pytest.mark.parametrize("data", [[], None])
def test_open_positions_collection_empty_or_null_returns_empty_list(data) -> None:
    assert open_positions_from_api_data(data) == []


def test_open_positions_collection_unknown_object_shape_raises_sanitized_error() -> None:
    with pytest.raises(ValueError, match="openPositions data object has no list field"):
        open_positions_from_api_data({"unexpected": []})


def test_open_positions_collection_non_object_rows_raise_sanitized_error() -> None:
    with pytest.raises(ValueError, match="openPositions row must be an object"):
        open_positions_from_api_data(["not-object"])


def test_active_order_sanitizer_uses_known_fields_only() -> None:
    model = active_order_from_api(
        {
            "rootOrderId": "ord-1",
            "symbol": "USD_JPY",
            "side": "SELL",
            "executionType": "LIMIT",
            "orderSize": "100",
            "price": "151.0",
            "status": "ORDERED",
            "timestamp": "2026-06-24T00:01:00.000Z",
            "API-KEY": "<API_KEY>",
            "API-SIGN": "<SIGNATURE>",
        }
    )

    dumped = model.model_dump()
    assert dumped["order_id"] == "ord-1"
    assert dumped["order_type"] == "LIMIT"
    assert dumped["size"] == Decimal("100")
    assert dumped["status"] == "ORDERED"
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped


def test_execution_sanitizer_uses_known_fields_only() -> None:
    model = execution_from_api(
        {
            "executionId": "exec-1",
            "rootOrderId": "ord-1",
            "symbol": "USD_JPY",
            "side": "BUY",
            "executionSize": "200",
            "executionPrice": "150.2",
            "timestamp": "2026-06-24T00:02:00.000Z",
            "API-KEY": "<API_KEY>",
            "API-SIGN": "<SIGNATURE>",
        }
    )

    dumped = model.model_dump()
    assert dumped["execution_id"] == "exec-1"
    assert dumped["order_id"] == "ord-1"
    assert dumped["size"] == Decimal("200")
    assert dumped["price"] == Decimal("150.2")
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped


def test_position_summary_sanitizer_uses_known_fields_only() -> None:
    model = position_summary_from_api(
        {
            "symbol": "USD_JPY",
            "side": "BUY",
            "sumPositionQuantity": "300",
            "averagePrice": "150.3",
            "sumLossGain": "-45.6",
            "API-KEY": "<API_KEY>",
            "API-SIGN": "<SIGNATURE>",
        }
    )

    dumped = model.model_dump()
    assert dumped["symbol"] == "USD_JPY"
    assert dumped["size"] == Decimal("300")
    assert dumped["profit_loss"] == Decimal("-45.6")
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped


def test_private_api_error_sanitizer_uses_known_fields_only() -> None:
    model = private_api_error_from_payload(
        {
            "status": "1",
            "messages": [
                {
                    "message_code": "ERR-001",
                    "message_string": "mocked error",
                    "API-KEY": "<API_KEY>",
                }
            ],
            "API-SIGN": "<SIGNATURE>",
            "API-TIMESTAMP": "1700000000000",
        }
    )

    dumped = model.model_dump()
    assert dumped == {"code": "ERR-001", "message": "mocked error", "status": 1}
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped
    assert "API-TIMESTAMP" not in dumped
