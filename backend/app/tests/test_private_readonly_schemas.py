from decimal import Decimal

from app.private_api.schemas import (
    account_assets_from_api,
    open_position_from_api,
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
