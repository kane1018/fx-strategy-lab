"""Pure position-specific exit decision for fake/paper H-11 cycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.paper import USD_JPY_PIP_SIZE, PaperQuote


class H11AutoExitError(ValueError):
    """Invalid frozen exit policy or synthetic position input."""


class ExitAction(str, Enum):
    HOLD_PROTECTED_POSITION = "HOLD_PROTECTED_POSITION"
    EXIT_POSITION_SPECIFIC = "EXIT_POSITION_SPECIFIC"
    HALT_KEEP_SERVER_PROTECTION = "HALT_KEEP_SERVER_PROTECTION"


class ExitReason(str, Enum):
    NONE = "NONE"
    HARD_STOP_REACHED = "HARD_STOP_REACHED"
    TAKE_PROFIT_REACHED = "TAKE_PROFIT_REACHED"
    MAX_HOLD_REACHED = "MAX_HOLD_REACHED"
    FORMAL_EDGE_LOST = "FORMAL_EDGE_LOST"
    PROTECTION_NOT_CONFIRMED = "PROTECTION_NOT_CONFIRMED"
    MARKET_DATA_NOT_FRESH = "MARKET_DATA_NOT_FRESH"
    CLOCK_INVALID = "CLOCK_INVALID"


@dataclass(frozen=True)
class FrozenExitPolicy:
    stop_loss_pips: Decimal
    take_profit_pips: Decimal
    max_hold_seconds: int
    formal_edge_exit_enabled: bool = True
    position_specific_exit_required: bool = True
    opposite_entry_as_exit_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not _finite_decimal(self.stop_loss_pips)
            or not _finite_decimal(self.take_profit_pips)
            or type(self.max_hold_seconds) is not int
            or self.stop_loss_pips <= 0
            or self.take_profit_pips <= 0
            or self.max_hold_seconds <= 0
        ):
            raise H11AutoExitError("exit thresholds must be positive")
        if (
            type(self.formal_edge_exit_enabled) is not bool
            or type(self.position_specific_exit_required) is not bool
            or type(self.opposite_entry_as_exit_allowed) is not bool
        ):
            raise H11AutoExitError("exit policy flags are invalid")
        if not self.position_specific_exit_required:
            raise H11AutoExitError("position-specific exit must remain required")
        if self.opposite_entry_as_exit_allowed:
            raise H11AutoExitError("opposite entry cannot be used as exit")


@dataclass(frozen=True)
class SyntheticProtectedPosition:
    direction: SignalDecision
    entry_price: Decimal
    opened_at_utc: datetime
    protection_confirmed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.direction, SignalDecision):
            raise H11AutoExitError("position direction is invalid")
        if self.direction is SignalDecision.STAY:
            raise H11AutoExitError("Stay cannot create a position")
        if (
            not _finite_decimal(self.entry_price)
            or self.entry_price <= 0
            or not isinstance(self.opened_at_utc, datetime)
            or self.opened_at_utc.tzinfo is None
            or type(self.protection_confirmed) is not bool
        ):
            raise H11AutoExitError("position input is invalid")


@dataclass(frozen=True)
class ExitDecision:
    action: ExitAction
    reason: ExitReason
    unrealized_pips: Decimal | None
    position_specific: bool
    generic_close_allowed: bool = False
    opposite_entry_allowed: bool = False
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_exit_decision(
    *,
    position: SyntheticProtectedPosition,
    quote: PaperQuote,
    now_utc: datetime,
    policy: FrozenExitPolicy,
    latest_formal_decision: SignalDecision | None,
    market_data_fresh: bool,
) -> ExitDecision:
    if (
        not isinstance(now_utc, datetime)
        or now_utc.tzinfo is None
        or now_utc < position.opened_at_utc
    ):
        return _halt(ExitReason.CLOCK_INVALID)
    if not position.protection_confirmed:
        return _halt(ExitReason.PROTECTION_NOT_CONFIRMED)
    if market_data_fresh is not True:
        return _halt(ExitReason.MARKET_DATA_NOT_FRESH)

    mark = quote.bid if position.direction is SignalDecision.BUY else quote.ask
    signed_move = (
        mark - position.entry_price
        if position.direction is SignalDecision.BUY
        else position.entry_price - mark
    )
    pips = signed_move / USD_JPY_PIP_SIZE
    if pips <= -policy.stop_loss_pips:
        return _exit(ExitReason.HARD_STOP_REACHED, pips)
    if pips >= policy.take_profit_pips:
        return _exit(ExitReason.TAKE_PROFIT_REACHED, pips)
    held_seconds = (now_utc - position.opened_at_utc).total_seconds()
    if held_seconds >= policy.max_hold_seconds:
        return _exit(ExitReason.MAX_HOLD_REACHED, pips)
    if policy.formal_edge_exit_enabled and latest_formal_decision is not None:
        edge_maintained = latest_formal_decision is position.direction
        if not edge_maintained:
            return _exit(ExitReason.FORMAL_EDGE_LOST, pips)
    return ExitDecision(
        action=ExitAction.HOLD_PROTECTED_POSITION,
        reason=ExitReason.NONE,
        unrealized_pips=pips,
        position_specific=True,
    )


def _finite_decimal(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


def _exit(reason: ExitReason, pips: Decimal) -> ExitDecision:
    return ExitDecision(
        action=ExitAction.EXIT_POSITION_SPECIFIC,
        reason=reason,
        unrealized_pips=pips,
        position_specific=True,
    )


def _halt(reason: ExitReason) -> ExitDecision:
    return ExitDecision(
        action=ExitAction.HALT_KEEP_SERVER_PROTECTION,
        reason=reason,
        unrealized_pips=None,
        position_specific=True,
    )
