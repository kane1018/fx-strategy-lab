"""Backtest engine skeleton (synthetic fixtures only, no-POST).

Applies the existing deterministic strategy signal engine to a synthetic
historical dataset, bar by bar, with a paper entry/exit skeleton:

- The conversion boundary is explicit: candles/spreads/sessions are turned
  into safe labels FIRST (arithmetic only, no LLM), and the strategy engine
  receives safe labels only. Unknown / missing / conflicting inputs fail
  closed before any signal is produced.
- BUY/SELL previews open at most one synthetic paper trade at a time; HOLD
  and UNKNOWN_BLOCKED never enter; environment blocks happen before entry.
  Exits are classified with safe reasons (TP / SL / max hold / opposite
  signal / end of window). There is no retry, duplicate-entry, or
  duplicate-settlement branch.
- All numeric values are SYNTHETIC TEST-ONLY. Nothing here is a broker
  value, a live value, or a performance proof; the run result pins
  ``not_performance_proof`` and every actual/broker flag false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_strategy_backtest_dataset import (
    DATASET_VALID_STATUSES,
    BacktestDataset,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
    validate_backtest_dataset,
)
from app.services.gmo_strategy_signal_engine import (
    GuardSafeLabel,
    MarketSafeLabel,
    MomentumSafeLabel,
    PositionContextSafeLabel,
    SessionSafeLabel,
    SpreadSafeLabel,
    StrategyDecisionCategory,
    StrategySignalSafeInput,
    TickerFreshSafeLabel,
    TrendSafeLabel,
    VolatilitySafeLabel,
    evaluate_strategy_signal,
)


class GmoBacktestEngineError(RuntimeError):
    """Raised for fail-closed violations. Never echoes a row value."""


# ---------------------------------------------------------------------------
# Exit policy candidates (candidate-only; never officially adopted here)
# ---------------------------------------------------------------------------


class TakeProfitProfileLabel(str, Enum):
    TAKE_PROFIT_PROFILE_SMALL = "TAKE_PROFIT_PROFILE_SMALL"
    TAKE_PROFIT_PROFILE_MEDIUM = "TAKE_PROFIT_PROFILE_MEDIUM"
    TAKE_PROFIT_PROFILE_LARGE = "TAKE_PROFIT_PROFILE_LARGE"


class StopLossProfileLabel(str, Enum):
    STOP_LOSS_PROFILE_SMALL = "STOP_LOSS_PROFILE_SMALL"
    STOP_LOSS_PROFILE_MEDIUM = "STOP_LOSS_PROFILE_MEDIUM"
    STOP_LOSS_PROFILE_LARGE = "STOP_LOSS_PROFILE_LARGE"


class MaxHoldProfileLabel(str, Enum):
    MAX_HOLD_PROFILE_SHORT = "MAX_HOLD_PROFILE_SHORT"
    MAX_HOLD_PROFILE_MEDIUM = "MAX_HOLD_PROFILE_MEDIUM"
    MAX_HOLD_PROFILE_LONG = "MAX_HOLD_PROFILE_LONG"


@dataclass(frozen=True)
class ExitPolicyCandidate:
    """CANDIDATE exit policy. Numeric distances are synthetic test-only.

    Never an officially adopted value: adoption requires real-data
    backtesting, out-of-sample evaluation, and an operator decision in a
    future step. Construction refuses ``officially_adopted=True``.
    """

    take_profit_profile: TakeProfitProfileLabel
    stop_loss_profile: StopLossProfileLabel
    max_hold_profile: MaxHoldProfileLabel
    tp_distance_synthetic: float
    sl_distance_synthetic: float
    max_hold_bars: int
    exit_on_opposite_signal: bool = True
    exit_on_end_of_window: bool = True
    candidate_only: bool = True
    officially_adopted: bool = False

    def __post_init__(self) -> None:
        if self.officially_adopted:
            raise GmoBacktestEngineError(
                "exit policies are candidates only in this phase; official "
                "adoption requires real-data evaluation and an operator step"
            )
        if not self.candidate_only:
            raise GmoBacktestEngineError("exit policy must stay candidate-only")
        if self.tp_distance_synthetic <= 0 or self.sl_distance_synthetic <= 0:
            raise GmoBacktestEngineError("synthetic exit distances must be positive")
        if self.max_hold_bars <= 0:
            raise GmoBacktestEngineError("max hold bars must be positive")

    def __bool__(self) -> bool:
        return False


def build_candidate_exit_policy_profiles() -> dict[str, ExitPolicyCandidate]:
    """Named candidate profiles with synthetic test-only distances."""

    return {
        "CANDIDATE_SMALL_TIGHT": ExitPolicyCandidate(
            take_profit_profile=TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_SMALL,
            stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_SMALL,
            max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_SHORT,
            tp_distance_synthetic=0.2,
            sl_distance_synthetic=0.2,
            max_hold_bars=10,
        ),
        "CANDIDATE_MEDIUM_BALANCED": ExitPolicyCandidate(
            take_profit_profile=TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_MEDIUM,
            stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_MEDIUM,
            max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_MEDIUM,
            tp_distance_synthetic=0.5,
            sl_distance_synthetic=0.4,
            max_hold_bars=30,
        ),
        "CANDIDATE_LARGE_WIDE": ExitPolicyCandidate(
            take_profit_profile=TakeProfitProfileLabel.TAKE_PROFIT_PROFILE_LARGE,
            stop_loss_profile=StopLossProfileLabel.STOP_LOSS_PROFILE_LARGE,
            max_hold_profile=MaxHoldProfileLabel.MAX_HOLD_PROFILE_LONG,
            tp_distance_synthetic=1.0,
            sl_distance_synthetic=0.8,
            max_hold_bars=80,
        ),
    }


# ---------------------------------------------------------------------------
# Conversion boundary: dataset rows -> safe labels (arithmetic only, no LLM)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestEnvironmentAssumption:
    """Fixture-level environment labels plus optional overrides for tests.

    Defaults describe a healthy synthetic environment. Overrides let a
    fixture inject stale/unsafe/conflict conditions without touching the
    conversion arithmetic.
    """

    market_safe_label: MarketSafeLabel = MarketSafeLabel.MARKET_SAFE
    ticker_fresh_safe_label: TickerFreshSafeLabel = (
        TickerFreshSafeLabel.TICKER_FRESH
    )
    guard_safe_label: GuardSafeLabel = GuardSafeLabel.GUARD_PASS
    volatility_safe_label_override: VolatilitySafeLabel | None = None
    trend_safe_label_override: TrendSafeLabel | None = None
    momentum_safe_label_override: MomentumSafeLabel | None = None


_SPREAD_CATEGORY_TO_SAFE_LABEL = {
    SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL: (
        SpreadSafeLabel.SPREAD_WITHIN_LIMIT
    ),
    SpreadCategorySafeLabel.SPREAD_CATEGORY_WIDE: (
        SpreadSafeLabel.SPREAD_OUT_OF_LIMIT
    ),
    SpreadCategorySafeLabel.SPREAD_CATEGORY_UNKNOWN: SpreadSafeLabel.SPREAD_UNKNOWN,
}

_SESSION_TO_SAFE_LABEL = {
    SessionAllowedSafeLabel.SESSION_ALLOWED: SessionSafeLabel.SESSION_ALLOWED,
    SessionAllowedSafeLabel.SESSION_BLOCKED: SessionSafeLabel.SESSION_BLOCKED,
    SessionAllowedSafeLabel.SESSION_UNKNOWN: SessionSafeLabel.SESSION_UNKNOWN,
}

_TREND_LOOKBACK_BARS = 3


def derive_trend_momentum_labels(
    closes: tuple[float, ...],
) -> tuple[TrendSafeLabel, MomentumSafeLabel]:
    """Derive trend/momentum safe labels from synthetic closes (arithmetic).

    Fail-closed: insufficient history yields TREND_UNKNOWN.
    """

    if len(closes) < _TREND_LOOKBACK_BARS + 1:
        return (TrendSafeLabel.TREND_UNKNOWN, MomentumSafeLabel.MOMENTUM_UNKNOWN)
    window_delta = closes[-1] - closes[-1 - _TREND_LOOKBACK_BARS]
    step_delta = closes[-1] - closes[-2]
    if step_delta > 0:
        momentum = MomentumSafeLabel.MOMENTUM_UP
    elif step_delta < 0:
        momentum = MomentumSafeLabel.MOMENTUM_DOWN
    else:
        momentum = MomentumSafeLabel.MOMENTUM_FLAT
    if window_delta > 0:
        return (TrendSafeLabel.UPTREND, momentum)
    if window_delta < 0:
        return (TrendSafeLabel.DOWNTREND, momentum)
    return (TrendSafeLabel.RANGE, momentum)


def convert_bar_to_signal_input(
    *,
    dataset: BacktestDataset,
    bar_index: int,
    position_open: bool,
    environment: BacktestEnvironmentAssumption,
) -> StrategySignalSafeInput:
    """Convert one bar (plus lookback) into the fixed engine input shape."""

    closes = tuple(
        candle.close_value for candle in dataset.candles[: bar_index + 1]
    )
    trend, momentum = derive_trend_momentum_labels(closes)
    if environment.trend_safe_label_override is not None:
        trend = environment.trend_safe_label_override
    if environment.momentum_safe_label_override is not None:
        momentum = environment.momentum_safe_label_override
    volatility = (
        environment.volatility_safe_label_override
        if environment.volatility_safe_label_override is not None
        else VolatilitySafeLabel.VOLATILITY_NORMAL
    )
    return StrategySignalSafeInput(
        trend_safe_label=trend,
        momentum_safe_label=momentum,
        volatility_safe_label=volatility,
        spread_safe_label=_SPREAD_CATEGORY_TO_SAFE_LABEL[
            dataset.spreads[bar_index].spread_category
        ],
        ticker_fresh_safe_label=environment.ticker_fresh_safe_label,
        market_safe_label=environment.market_safe_label,
        session_safe_label=_SESSION_TO_SAFE_LABEL[
            dataset.sessions[bar_index].session_safe_label
        ],
        guard_safe_label=environment.guard_safe_label,
        position_context_safe_label=(
            PositionContextSafeLabel.ONE_POSITION_CONTEXT
            if position_open
            else PositionContextSafeLabel.NO_POSITION_CONTEXT
        ),
    )


# ---------------------------------------------------------------------------
# Backtest run skeleton
# ---------------------------------------------------------------------------


class GmoBacktestRunStatus(str, Enum):
    BACKTEST_SYNTHETIC_COMPLETED = "BACKTEST_SYNTHETIC_COMPLETED"
    BACKTEST_SYNTHETIC_BLOCKED = "BACKTEST_SYNTHETIC_BLOCKED"
    BACKTEST_SYNTHETIC_INVALID_DATASET = "BACKTEST_SYNTHETIC_INVALID_DATASET"


BACKTEST_NOT_PERFORMANCE_PROOF = "BACKTEST_SYNTHETIC_NOT_PERFORMANCE_PROOF"


class BacktestExitReason(str, Enum):
    EXIT_TAKE_PROFIT = "EXIT_TAKE_PROFIT"
    EXIT_STOP_LOSS = "EXIT_STOP_LOSS"
    EXIT_MAX_HOLD = "EXIT_MAX_HOLD"
    EXIT_OPPOSITE_SIGNAL = "EXIT_OPPOSITE_SIGNAL"
    EXIT_END_OF_WINDOW = "EXIT_END_OF_WINDOW"


@dataclass(frozen=True)
class BacktestTradeEvent:
    """One synthetic paper trade. No broker/order/position/account ID exists.

    ``synthetic_pnl_value`` and ``synthetic_spread_cost_value`` are
    test-only synthetic aggregates inputs -- never broker values.
    """

    trade_index: int
    side_safe_label: str
    entry_signal_safe_label: str
    exit_reason_safe_label: BacktestExitReason
    hold_duration_bars: int
    synthetic_pnl_value: float
    synthetic_spread_cost_value: float
    spread_included: bool
    synthetic_fixture: bool = True

    def __bool__(self) -> bool:
        return False


@dataclass
class _OpenPaperTrade:
    side: str  # "PAPER_LONG" / "PAPER_SHORT"
    entry_signal: str
    entry_close: float
    entry_bar: int
    spread_cost: float


@dataclass(frozen=True)
class BacktestRunResult:
    """Run outcome: safe labels, counts, and synthetic trade aggregates only."""

    status: GmoBacktestRunStatus
    blocked_reasons: tuple[str, ...]
    bars_processed: int
    trades: tuple[BacktestTradeEvent, ...]
    signal_distribution: tuple[tuple[str, int], ...]
    category_distribution: tuple[tuple[str, int], ...]
    block_reason_distribution: tuple[tuple[str, int], ...]
    spread_included: bool
    not_performance_proof: str = BACKTEST_NOT_PERFORMANCE_PROOF
    synthetic_fixture_only: bool = True
    real_data_used: bool = False
    actual_post_performed: bool = False
    broker_write_performed: bool = False
    real_http_performed: bool = False
    runtime_private_get_performed: bool = False
    credential_value_read: bool = False
    env_read_performed: bool = False
    raw_id_value_exposure: bool = False
    retry_performed: bool = False
    duplicate_entry_blocked_by_state: bool = True

    def __bool__(self) -> bool:
        return False


def _distribution(labels: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return tuple(sorted(counts.items()))


def run_synthetic_backtest(
    *,
    dataset: BacktestDataset,
    exit_policy: ExitPolicyCandidate,
    spread_included: bool = True,
    environment: BacktestEnvironmentAssumption | None = None,
    entry_momentum_strict: bool = False,
    opposite_signal_debounce_bars: int = 1,
) -> BacktestRunResult:
    """Run the skeleton once over one dataset. No retry paths.

    ``spread_included=False`` is allowed only as a reference run; the report
    layer refuses to mark such a run as official.

    Backtest-level candidate knobs (defaults reproduce the baseline behavior
    exactly, so existing runs/tests are unchanged):

    - ``entry_momentum_strict``: when True, only open a trade when the bar's
      momentum strictly aligns with the side (BUY requires MOMENTUM_UP, SELL
      requires MOMENTUM_DOWN); neutral-momentum entries are skipped. This is
      a backtest-level filter and never mutates the deterministic engine.
    - ``opposite_signal_debounce_bars``: require this many consecutive
      opposite-trend bars before an opposite-signal exit (1 = exit on the
      first opposite bar, the baseline).
    """

    debounce = max(1, opposite_signal_debounce_bars)
    env = environment if environment is not None else BacktestEnvironmentAssumption()
    validation = validate_backtest_dataset(dataset)
    if validation.status not in DATASET_VALID_STATUSES:
        return BacktestRunResult(
            status=GmoBacktestRunStatus.BACKTEST_SYNTHETIC_INVALID_DATASET,
            blocked_reasons=validation.blocked_reasons,
            bars_processed=0,
            trades=(),
            signal_distribution=(),
            category_distribution=(),
            block_reason_distribution=(),
            spread_included=spread_included,
        )

    trades: list[BacktestTradeEvent] = []
    open_trade: _OpenPaperTrade | None = None
    opposite_streak = 0
    signal_labels: list[str] = []
    category_labels: list[str] = []
    block_reasons: list[str] = []

    def _close_trade(
        *, exit_reason: BacktestExitReason, exit_price: float, bar_index: int
    ) -> None:
        nonlocal open_trade
        assert open_trade is not None
        direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
        gross = (exit_price - open_trade.entry_close) * direction
        pnl = gross - open_trade.spread_cost
        trades.append(
            BacktestTradeEvent(
                trade_index=len(trades),
                side_safe_label=open_trade.side,
                entry_signal_safe_label=open_trade.entry_signal,
                exit_reason_safe_label=exit_reason,
                hold_duration_bars=bar_index - open_trade.entry_bar,
                synthetic_pnl_value=pnl,
                synthetic_spread_cost_value=open_trade.spread_cost,
                spread_included=spread_included,
            )
        )
        open_trade = None

    last_index = len(dataset.candles) - 1
    for bar_index in range(dataset.warmup_bars, len(dataset.candles)):
        candle = dataset.candles[bar_index]
        signal_input = convert_bar_to_signal_input(
            dataset=dataset,
            bar_index=bar_index,
            position_open=open_trade is not None,
            environment=env,
        )
        decision = evaluate_strategy_signal(signal_input)
        signal_labels.append(decision.auto_preview_signal.value)
        category_labels.append(decision.strategy_decision_category.value)
        if decision.block_reason_safe_label:
            block_reasons.append(decision.block_reason_safe_label)

        if open_trade is not None:
            direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
            hit_sl = (
                candle.low_value
                <= open_trade.entry_close - exit_policy.sl_distance_synthetic
                if direction > 0
                else candle.high_value
                >= open_trade.entry_close + exit_policy.sl_distance_synthetic
            )
            hit_tp = (
                candle.high_value
                >= open_trade.entry_close + exit_policy.tp_distance_synthetic
                if direction > 0
                else candle.low_value
                <= open_trade.entry_close - exit_policy.tp_distance_synthetic
            )
            held_bars = bar_index - open_trade.entry_bar
            trend, _ = derive_trend_momentum_labels(
                tuple(c.close_value for c in dataset.candles[: bar_index + 1])
            )
            is_opposite_bar = (direction > 0 and trend is TrendSafeLabel.DOWNTREND) or (
                direction < 0 and trend is TrendSafeLabel.UPTREND
            )
            opposite_streak = opposite_streak + 1 if is_opposite_bar else 0
            opposite = (
                exit_policy.exit_on_opposite_signal and opposite_streak >= debounce
            )
            if hit_sl:
                _close_trade(
                    exit_reason=BacktestExitReason.EXIT_STOP_LOSS,
                    exit_price=(
                        open_trade.entry_close
                        - direction * exit_policy.sl_distance_synthetic
                    ),
                    bar_index=bar_index,
                )
            elif hit_tp:
                _close_trade(
                    exit_reason=BacktestExitReason.EXIT_TAKE_PROFIT,
                    exit_price=(
                        open_trade.entry_close
                        + direction * exit_policy.tp_distance_synthetic
                    ),
                    bar_index=bar_index,
                )
            elif held_bars >= exit_policy.max_hold_bars:
                _close_trade(
                    exit_reason=BacktestExitReason.EXIT_MAX_HOLD,
                    exit_price=candle.close_value,
                    bar_index=bar_index,
                )
            elif opposite:
                _close_trade(
                    exit_reason=BacktestExitReason.EXIT_OPPOSITE_SIGNAL,
                    exit_price=candle.close_value,
                    bar_index=bar_index,
                )
            continue

        # No open trade: exactly one entry may open per proposal; HOLD /
        # UNKNOWN_BLOCKED / environment blocks never enter.
        if (
            decision.strategy_decision_category
            is StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED
        ):
            is_buy = (
                decision.auto_preview_signal
                is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
            )
            momentum_aligned = (
                signal_input.momentum_safe_label is MomentumSafeLabel.MOMENTUM_UP
                if is_buy
                else signal_input.momentum_safe_label
                is MomentumSafeLabel.MOMENTUM_DOWN
            )
            if entry_momentum_strict and not momentum_aligned:
                continue
            spread_record = dataset.spreads[bar_index]
            spread_cost = (
                (spread_record.spread_value or 0.0) if spread_included else 0.0
            )
            side = "PAPER_LONG" if is_buy else "PAPER_SHORT"
            open_trade = _OpenPaperTrade(
                side=side,
                entry_signal=decision.auto_preview_signal.value,
                entry_close=candle.close_value,
                entry_bar=bar_index,
                spread_cost=spread_cost,
            )
            opposite_streak = 0

    if open_trade is not None and exit_policy.exit_on_end_of_window:
        _close_trade(
            exit_reason=BacktestExitReason.EXIT_END_OF_WINDOW,
            exit_price=dataset.candles[last_index].close_value,
            bar_index=last_index,
        )

    return BacktestRunResult(
        status=GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED,
        blocked_reasons=(),
        bars_processed=len(dataset.candles) - dataset.warmup_bars,
        trades=tuple(trades),
        signal_distribution=_distribution(signal_labels),
        category_distribution=_distribution(category_labels),
        block_reason_distribution=_distribution(block_reasons),
        spread_included=spread_included,
        synthetic_fixture_only=dataset.synthetic_fixture,
        real_data_used=not dataset.synthetic_fixture,
    )
