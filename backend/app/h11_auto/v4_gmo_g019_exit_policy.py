"""Pure, no-broker G019 exit-policy and portfolio-limit evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal


class V4GmoG019ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_LIMIT_30M = "TIME_LIMIT_30M"


@dataclass(frozen=True)
class V4GmoBidAskBar:
    """A completed bar containing both executable price surfaces."""

    bid_high: Decimal
    bid_low: Decimal
    bid_close: Decimal
    ask_high: Decimal
    ask_low: Decimal
    ask_close: Decimal


@dataclass(frozen=True)
class V4GmoG019ExitResult:
    exit_reason: V4GmoG019ExitReason
    exit_price: Decimal
    gross_pips: Decimal
    bars_held: int


@dataclass(frozen=True)
class V4GmoLayer2Trade:
    trading_day: date
    realized_pnl_jpy: int


@dataclass(frozen=True)
class V4GmoLayer2Result:
    accepted_trade_count: int
    rejected_trade_count: int
    realized_pnl_jpy: int
    daily_loss_halt_count: int
    monthly_loss_halt: bool
    consecutive_loss_halt_count: int
    broker_post_authorized: bool = False
    broker_write: bool = False
    actual_post_count: int = 0


G019_HOLD_MINUTES = 30
G019_STOP_ATR_MULTIPLE = Decimal("1.50")
G019_TAKE_PROFIT_R_MULTIPLE = Decimal("1.50")
G019_MAX_ENTRIES_PER_DAY = 30
G019_DAILY_LOSS_LIMIT_JPY = 10_000
G019_MONTHLY_LOSS_LIMIT_JPY = 50_000
G019_CONSECUTIVE_LOSS_LIMIT = 5


def evaluate_g019_exit(
    *,
    side: Literal["BUY", "SELL"],
    average_fill: Decimal,
    frozen_atr_24: Decimal,
    completed_minute_bars: Iterable[V4GmoBidAskBar],
) -> V4GmoG019ExitResult:
    """Evaluate the exact G019 proposal: 1.5 ATR stop, 1.5R TP, 30m cap.

    A same-bar stop/target collision is resolved against the strategy by
    selecting the stop. BUY exits use BID and SELL exits use ASK.
    """

    bars = tuple(completed_minute_bars)
    if side not in {"BUY", "SELL"}:
        raise ValueError("G019_EXIT_SIDE_INVALID")
    if average_fill <= 0 or frozen_atr_24 <= 0:
        raise ValueError("G019_EXIT_INPUT_INVALID")
    if len(bars) != G019_HOLD_MINUTES:
        raise ValueError("G019_EXIT_REQUIRES_EXACT_30_COMPLETED_M1_BARS")

    stop_distance = frozen_atr_24 * G019_STOP_ATR_MULTIPLE
    target_distance = stop_distance * G019_TAKE_PROFIT_R_MULTIPLE
    if side == "BUY":
        stop = average_fill - stop_distance
        target = average_fill + target_distance
    else:
        stop = average_fill + stop_distance
        target = average_fill - target_distance

    for index, bar in enumerate(bars, start=1):
        if side == "BUY":
            stop_hit = bar.bid_low <= stop
            target_hit = bar.bid_high >= target
        else:
            stop_hit = bar.ask_high >= stop
            target_hit = bar.ask_low <= target
        if stop_hit:
            return _exit_result(
                side=side,
                fill=average_fill,
                price=stop,
                reason=V4GmoG019ExitReason.STOP_LOSS,
                bars_held=index,
            )
        if target_hit:
            return _exit_result(
                side=side,
                fill=average_fill,
                price=target,
                reason=V4GmoG019ExitReason.TAKE_PROFIT,
                bars_held=index,
            )

    time_exit = bars[-1].bid_close if side == "BUY" else bars[-1].ask_close
    return _exit_result(
        side=side,
        fill=average_fill,
        price=time_exit,
        reason=V4GmoG019ExitReason.TIME_LIMIT_30M,
        bars_held=G019_HOLD_MINUTES,
    )


def evaluate_g019_layer2(
    trades: Iterable[V4GmoLayer2Trade],
) -> V4GmoLayer2Result:
    """Apply bounded unattended portfolio controls to ordered trade outcomes."""

    accepted = 0
    rejected = 0
    total_pnl = 0
    monthly_pnl = 0
    daily_loss_halts: set[date] = set()
    consecutive_loss_halt = False
    monthly_halt = False
    monthly_halt_observed = False
    current_month: tuple[int, int] | None = None
    current_day: date | None = None
    daily_count = 0
    daily_pnl = 0
    consecutive_losses = 0

    for trade in trades:
        trade_month = (trade.trading_day.year, trade.trading_day.month)
        if current_month != trade_month:
            current_month = trade_month
            monthly_pnl = 0
            monthly_halt = False
        if current_day != trade.trading_day:
            current_day = trade.trading_day
            daily_count = 0
            daily_pnl = 0
        if (
            monthly_halt
            or
            daily_count >= G019_MAX_ENTRIES_PER_DAY
            or current_day in daily_loss_halts
            or consecutive_loss_halt
        ):
            rejected += 1
            continue

        accepted += 1
        daily_count += 1
        daily_pnl += trade.realized_pnl_jpy
        monthly_pnl += trade.realized_pnl_jpy
        total_pnl += trade.realized_pnl_jpy
        consecutive_losses = (
            consecutive_losses + 1 if trade.realized_pnl_jpy < 0 else 0
        )

        if daily_pnl <= -G019_DAILY_LOSS_LIMIT_JPY:
            daily_loss_halts.add(current_day)
        if consecutive_losses >= G019_CONSECUTIVE_LOSS_LIMIT:
            consecutive_loss_halt = True
        if monthly_pnl <= -G019_MONTHLY_LOSS_LIMIT_JPY:
            monthly_halt = True
            monthly_halt_observed = True

    return V4GmoLayer2Result(
        accepted_trade_count=accepted,
        rejected_trade_count=rejected,
        realized_pnl_jpy=total_pnl,
        daily_loss_halt_count=len(daily_loss_halts),
        monthly_loss_halt=monthly_halt_observed,
        consecutive_loss_halt_count=int(consecutive_loss_halt),
    )


def _exit_result(
    *,
    side: Literal["BUY", "SELL"],
    fill: Decimal,
    price: Decimal,
    reason: V4GmoG019ExitReason,
    bars_held: int,
) -> V4GmoG019ExitResult:
    signed_delta = price - fill if side == "BUY" else fill - price
    return V4GmoG019ExitResult(
        exit_reason=reason,
        exit_price=price,
        gross_pips=signed_delta * Decimal("100"),
        bars_held=bars_held,
    )
