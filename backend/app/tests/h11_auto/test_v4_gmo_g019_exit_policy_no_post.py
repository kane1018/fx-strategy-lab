from datetime import date
from decimal import Decimal

import pytest

from app.h11_auto.v4_gmo_g019_exit_policy import (
    V4GmoBidAskBar,
    V4GmoG019ExitReason,
    V4GmoLayer2Trade,
    evaluate_g019_exit,
    evaluate_g019_layer2,
)


def _bar(
    *,
    bid_high: str = "100.01",
    bid_low: str = "99.99",
    bid_close: str = "100.00",
    ask_high: str = "100.02",
    ask_low: str = "100.00",
    ask_close: str = "100.01",
) -> V4GmoBidAskBar:
    return V4GmoBidAskBar(
        bid_high=Decimal(bid_high),
        bid_low=Decimal(bid_low),
        bid_close=Decimal(bid_close),
        ask_high=Decimal(ask_high),
        ask_low=Decimal(ask_low),
        ask_close=Decimal(ask_close),
    )


def test_g019_buy_uses_bid_and_exits_at_exact_30m() -> None:
    bars = [_bar() for _ in range(29)]
    bars.append(_bar(bid_close="100.03", ask_close="100.04"))

    result = evaluate_g019_exit(
        side="BUY",
        average_fill=Decimal("100"),
        frozen_atr_24=Decimal("0.10"),
        completed_minute_bars=bars,
    )

    assert result.exit_reason is V4GmoG019ExitReason.TIME_LIMIT_30M
    assert result.exit_price == Decimal("100.03")
    assert result.gross_pips == Decimal("3.00")
    assert result.bars_held == 30


def test_g019_sell_uses_ask_and_same_bar_collision_selects_stop() -> None:
    collision = _bar(ask_high="100.16", ask_low="99.76")
    bars = [collision, *[_bar() for _ in range(29)]]

    result = evaluate_g019_exit(
        side="SELL",
        average_fill=Decimal("100"),
        frozen_atr_24=Decimal("0.10"),
        completed_minute_bars=bars,
    )

    assert result.exit_reason is V4GmoG019ExitReason.STOP_LOSS
    assert result.exit_price == Decimal("100.1500")
    assert result.gross_pips == Decimal("-15.0000")


def test_g019_exit_requires_exact_30_completed_m1_bars() -> None:
    with pytest.raises(
        ValueError, match="G019_EXIT_REQUIRES_EXACT_30_COMPLETED_M1_BARS"
    ):
        evaluate_g019_exit(
            side="BUY",
            average_fill=Decimal("100"),
            frozen_atr_24=Decimal("0.10"),
            completed_minute_bars=[_bar()],
        )


def test_layer2_rejects_entry_31_for_same_day() -> None:
    trades = [
        V4GmoLayer2Trade(date(2026, 7, 28), 100)
        for _ in range(31)
    ]

    result = evaluate_g019_layer2(trades)

    assert result.accepted_trade_count == 30
    assert result.rejected_trade_count == 1
    assert result.realized_pnl_jpy == 3000
    assert result.broker_post_authorized is False
    assert result.actual_post_count == 0


def test_layer2_stops_after_five_consecutive_losses() -> None:
    trades = [
        V4GmoLayer2Trade(date(2026, 7, 28), -1000)
        for _ in range(8)
    ]

    result = evaluate_g019_layer2(trades)

    assert result.accepted_trade_count == 5
    assert result.rejected_trade_count == 3
    assert result.consecutive_loss_halt_count == 1


def test_layer2_consecutive_loss_halt_survives_day_boundary() -> None:
    trades = [
        V4GmoLayer2Trade(date(2026, 7, 28), -1000)
        for _ in range(4)
    ]
    trades.extend(
        [
            V4GmoLayer2Trade(date(2026, 7, 29), -1000),
            V4GmoLayer2Trade(date(2026, 7, 29), 1000),
        ]
    )

    result = evaluate_g019_layer2(trades)

    assert result.accepted_trade_count == 5
    assert result.rejected_trade_count == 1
    assert result.consecutive_loss_halt_count == 1


def test_layer2_monthly_limit_stops_later_days() -> None:
    trades = [
        V4GmoLayer2Trade(date(2026, 7, day), -10_000)
        for day in range(1, 8)
    ]

    result = evaluate_g019_layer2(trades)

    assert result.accepted_trade_count == 5
    assert result.rejected_trade_count == 2
    assert result.monthly_loss_halt is True


def test_layer2_monthly_limit_resets_at_new_calendar_month() -> None:
    trades = []
    for day in range(1, 7):
        trades.extend(
            [
                V4GmoLayer2Trade(date(2026, 7, day), 1),
                V4GmoLayer2Trade(date(2026, 7, day), -10_000),
            ]
        )
    trades.append(V4GmoLayer2Trade(date(2026, 7, 7), 1000))
    trades.append(V4GmoLayer2Trade(date(2026, 8, 1), 1000))

    result = evaluate_g019_layer2(trades)

    assert result.accepted_trade_count == 13
    assert result.rejected_trade_count == 1
    assert result.realized_pnl_jpy == -58_994
