from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.exit_policy import (
    ExitAction,
    ExitReason,
    FrozenExitPolicy,
    H11AutoExitError,
    SyntheticProtectedPosition,
    evaluate_exit_decision,
)
from app.h11_auto.paper import PaperQuote

OPENED = datetime(2026, 7, 15, 4, 0, tzinfo=UTC)


def policy() -> FrozenExitPolicy:
    return FrozenExitPolicy(
        stop_loss_pips=Decimal("5"),
        take_profit_pips=Decimal("8"),
        max_hold_seconds=600,
    )


def position(direction: SignalDecision = SignalDecision.BUY) -> SyntheticProtectedPosition:
    return SyntheticProtectedPosition(
        direction=direction,
        entry_price=Decimal("150.00"),
        opened_at_utc=OPENED,
        protection_confirmed=True,
    )


def decision(
    *,
    pos: SyntheticProtectedPosition | None = None,
    bid: str = "150.02",
    ask: str = "150.03",
    now: datetime | None = None,
    formal: SignalDecision | None = SignalDecision.BUY,
    fresh: bool = True,
):
    return evaluate_exit_decision(
        position=pos or position(),
        quote=PaperQuote(bid=Decimal(bid), ask=Decimal(ask)),
        now_utc=now or OPENED + timedelta(minutes=1),
        policy=policy(),
        latest_formal_decision=formal,
        market_data_fresh=fresh,
    )


def test_hold_when_protected_and_all_exit_conditions_are_clear() -> None:
    result = decision()
    assert result.action is ExitAction.HOLD_PROTECTED_POSITION
    assert result.reason is ExitReason.NONE
    assert result.generic_close_allowed is False
    assert result.opposite_entry_allowed is False
    assert result.actual_post_allowed is False


def test_buy_stop_take_profit_time_and_edge_loss_are_position_specific() -> None:
    cases = (
        (decision(bid="149.94", ask="149.95"), ExitReason.HARD_STOP_REACHED),
        (decision(bid="150.09", ask="150.10"), ExitReason.TAKE_PROFIT_REACHED),
        (
            decision(now=OPENED + timedelta(minutes=10)),
            ExitReason.MAX_HOLD_REACHED,
        ),
        (decision(formal=SignalDecision.SELL), ExitReason.FORMAL_EDGE_LOST),
        (decision(formal=SignalDecision.STAY), ExitReason.FORMAL_EDGE_LOST),
    )
    for result, reason in cases:
        assert result.action is ExitAction.EXIT_POSITION_SPECIFIC
        assert result.reason is reason
        assert result.position_specific is True
        assert result.opposite_entry_allowed is False


def test_sell_uses_ask_as_exit_mark() -> None:
    result = decision(
        pos=position(SignalDecision.SELL),
        bid="149.90",
        ask="149.91",
        formal=SignalDecision.SELL,
    )
    assert result.action is ExitAction.EXIT_POSITION_SPECIFIC
    assert result.reason is ExitReason.TAKE_PROFIT_REACHED
    assert result.unrealized_pips == Decimal("9")


@pytest.mark.parametrize(
    ("pos", "fresh", "expected"),
    [
        (
            replace(position(), protection_confirmed=False),
            True,
            ExitReason.PROTECTION_NOT_CONFIRMED,
        ),
        (position(), False, ExitReason.MARKET_DATA_NOT_FRESH),
    ],
)
def test_missing_protection_or_stale_data_halts_and_keeps_server_protection(
    pos: SyntheticProtectedPosition, fresh: bool, expected: ExitReason
) -> None:
    result = decision(pos=pos, fresh=fresh)
    assert result.action is ExitAction.HALT_KEEP_SERVER_PROTECTION
    assert result.reason is expected
    assert result.actual_post_allowed is False


def test_exit_contract_cannot_enable_generic_or_opposite_close() -> None:
    with pytest.raises(H11AutoExitError):
        replace(policy(), position_specific_exit_required=False)
    with pytest.raises(H11AutoExitError):
        replace(policy(), opposite_entry_as_exit_allowed=True)
    with pytest.raises(H11AutoExitError):
        position(SignalDecision.STAY)
    with pytest.raises(H11AutoExitError):
        replace(policy(), stop_loss_pips=Decimal("NaN"))
    with pytest.raises(H11AutoExitError):
        replace(policy(), max_hold_seconds=True)  # type: ignore[arg-type]
    with pytest.raises(H11AutoExitError):
        replace(position(), protection_confirmed=1)  # type: ignore[arg-type]
