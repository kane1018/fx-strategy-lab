import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.trading import OrderRequest, RiskConfig, Side
from app.services.risk_service import evaluate_order_risk


def order(mode: str = "demo") -> OrderRequest:
    return OrderRequest(
        client_order_id="TEST-ORDER-001",
        mode=mode,
        symbol="USD_JPY",
        side=Side.BUY,
        units=100,
        current_price=150,
        stop_loss=149.7,
        take_profit=150.6,
        estimated_loss=10,
        api_connection_ok=True,
    )


def test_demo_order_passes_nominal_risk_checks() -> None:
    decision = evaluate_order_risk(
        order(),
        RiskConfig(),
        Settings(),
        open_positions=0,
        daily_loss=0,
        consecutive_losses=0,
    )
    assert decision.allowed


def test_live_order_is_always_blocked_in_mvp() -> None:
    request = order("live")
    request.admin_live_enabled = True
    request.confirmation_text = "LIVE TRADING ENABLED"
    decision = evaluate_order_risk(
        request,
        RiskConfig(),
        Settings(enable_live_trading=True),
        open_positions=0,
        daily_loss=0,
        consecutive_losses=0,
    )
    assert not decision.allowed
    assert "実資金ブローカーアダプターが未実装" in decision.reasons


def test_order_with_invalid_stop_is_rejected() -> None:
    request = order()
    request.stop_loss = request.current_price
    decision = evaluate_order_risk(
        request,
        RiskConfig(),
        Settings(),
        open_positions=0,
        daily_loss=0,
        consecutive_losses=0,
    )
    assert not decision.allowed
    assert "買い注文の損切り・利確価格が不正" in decision.reasons


def test_order_without_stop_loss_is_invalid() -> None:
    payload = order().model_dump()
    del payload["stop_loss"]
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(payload)


def test_order_without_take_profit_is_invalid() -> None:
    payload = order().model_dump()
    del payload["take_profit"]
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(payload)
