"""Strategy rule redesign (backtest-only, deterministic, no-POST).

The M5 trend/momentum-flip baseline had no edge net of spread: it entered
very frequently and almost always exited on an immediate opposite signal,
with fixed take-profit / stop-loss distances so wide (tens of pips on M5)
that they essentially never triggered.

This module implements a bounded set of genuinely different, deterministic,
safe-label-only entry FAMILIES plus ATR-relative exits, evaluated by a
dedicated backtest-only runner. It deliberately does NOT touch the frozen
deterministic signal engine (`gmo_strategy_signal_engine`) or its rulebook /
supervised-evaluation tests. Everything here is candidate-only:
``officially_adopted=True`` is refused, ``actual_entry_POST_allowed`` /
``actual_settlement_POST_allowed`` are hardcoded false, results are never
truthy, and nothing is ever a performance proof or a live permission.

An arithmetic feature converter turns candle closes/highs/lows into safe
regime labels (SMA-trend, momentum, breakout, mean-reversion overextension)
plus an internal ATR-like scale used ONLY to size exits. No raw price,
spread, or PnL value ever leaves this module: reports carry safe labels,
safe counts, and aggregate metrics only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_strategy_backtest_dataset import (
    BacktestDataset,
    ChronologicalSplit,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
)
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    BacktestRunResult,
    BacktestTradeEvent,
    GmoBacktestRunStatus,
    build_candidate_exit_policy_profiles,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_backtest_metrics import (
    MINIMUM_TRADE_COUNT_FOR_EVALUATION,
    BacktestMetricsSummary,
    compute_backtest_metrics,
)

REDESIGN_RULE_VERSION = "REDESIGN_RULES_V1_ATR_RELATIVE_EXITS"
# Indicator lead-in each evaluation slice carries as warmup (never traded).
REDESIGN_SLICE_LEAD_IN_BARS = 40


class RedesignRuleError(RuntimeError):
    """Raised when a redesign candidate is misused (e.g. officially adopted)."""


# ---------------------------------------------------------------------------
# Arithmetic feature converter -> safe regime labels (no raw values escape)
# ---------------------------------------------------------------------------


class RedesignTrendRegime(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


class RedesignMomentum(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class RedesignBreakout(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class RedesignOverextension(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RedesignFeatureConfig:
    sma_fast: int = 8
    sma_slow: int = 20
    momentum_lookback: int = 6
    breakout_lookback: int = 20
    atr_lookback: int = 14
    overext_atr_mult: float = 1.5
    trend_margin_ratio: float = 0.0005


@dataclass(frozen=True)
class RedesignFeatures:
    trend: RedesignTrendRegime
    momentum: RedesignMomentum
    breakout: RedesignBreakout
    overextension: RedesignOverextension
    # Internal only: never reported. Used to size ATR-relative exits.
    atr_like: float
    ready: bool


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def compute_redesign_features(
    *,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    index: int,
    config: RedesignFeatureConfig,
) -> RedesignFeatures:
    """Compute safe regime labels + internal ATR from arithmetic. Fail-closed."""

    need = max(
        config.sma_slow,
        config.breakout_lookback,
        config.atr_lookback,
        config.momentum_lookback + 1,
    )
    if index < need:
        return RedesignFeatures(
            trend=RedesignTrendRegime.UNKNOWN,
            momentum=RedesignMomentum.UNKNOWN,
            breakout=RedesignBreakout.UNKNOWN,
            overextension=RedesignOverextension.UNKNOWN,
            atr_like=0.0,
            ready=False,
        )
    fast = _mean(closes[index - config.sma_fast + 1 : index + 1])
    slow = _mean(closes[index - config.sma_slow + 1 : index + 1])
    margin = abs(slow) * config.trend_margin_ratio
    if fast > slow + margin:
        trend = RedesignTrendRegime.UP
    elif fast < slow - margin:
        trend = RedesignTrendRegime.DOWN
    else:
        trend = RedesignTrendRegime.RANGE

    mom_delta = closes[index] - closes[index - config.momentum_lookback]
    if mom_delta > 0:
        momentum = RedesignMomentum.UP
    elif mom_delta < 0:
        momentum = RedesignMomentum.DOWN
    else:
        momentum = RedesignMomentum.FLAT

    prev_highs = highs[index - config.breakout_lookback : index]
    prev_lows = lows[index - config.breakout_lookback : index]
    if closes[index] > max(prev_highs):
        breakout = RedesignBreakout.UP
    elif closes[index] < min(prev_lows):
        breakout = RedesignBreakout.DOWN
    else:
        breakout = RedesignBreakout.NONE

    atr_like = _mean(
        [
            highs[j] - lows[j]
            for j in range(index - config.atr_lookback + 1, index + 1)
        ]
    )
    deviation = closes[index] - fast
    threshold = config.overext_atr_mult * atr_like
    if atr_like <= 0:
        overextension = RedesignOverextension.NONE
    elif deviation > threshold:
        overextension = RedesignOverextension.UP
    elif deviation < -threshold:
        overextension = RedesignOverextension.DOWN
    else:
        overextension = RedesignOverextension.NONE

    return RedesignFeatures(
        trend=trend,
        momentum=momentum,
        breakout=breakout,
        overextension=overextension,
        atr_like=atr_like,
        ready=True,
    )


# ---------------------------------------------------------------------------
# Entry families + exit config (all candidate-only)
# ---------------------------------------------------------------------------


class RedesignEntryFamily(str, Enum):
    TREND_CONTINUATION = "TREND_CONTINUATION"
    BREAKOUT = "BREAKOUT"
    MEAN_REVERSION_RANGE = "MEAN_REVERSION_RANGE"
    DUAL_CONFIRMATION = "DUAL_CONFIRMATION"


class RedesignEntrySide(str, Enum):
    REDESIGN_ENTRY_LONG = "REDESIGN_ENTRY_LONG"
    REDESIGN_ENTRY_SHORT = "REDESIGN_ENTRY_SHORT"
    REDESIGN_NO_ENTRY = "REDESIGN_NO_ENTRY"


@dataclass(frozen=True)
class RedesignEntryDecision:
    """Safe-label entry decision. Never a permission, never an operator signal."""

    entry_side: RedesignEntrySide
    block_reason_safe_label: str
    is_operator_signal: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def _no_entry(reason: str) -> RedesignEntryDecision:
    return RedesignEntryDecision(
        entry_side=RedesignEntrySide.REDESIGN_NO_ENTRY,
        block_reason_safe_label=reason,
    )


def redesign_entry_decision(
    *,
    family: RedesignEntryFamily,
    features: RedesignFeatures,
    spread_within_limit: bool,
    session_allowed: bool,
) -> RedesignEntryDecision:
    """Deterministic entry rule per family. Fail-closed on unknown/unsafe.

    Only ever consulted when flat (the runner never calls this in a position),
    so an open position can never produce an entry preview.
    """

    if not features.ready:
        return _no_entry("REDESIGN_FEATURES_NOT_READY")
    if not spread_within_limit:
        return _no_entry("REDESIGN_BLOCK_SPREAD_NOT_WITHIN_LIMIT")
    if not session_allowed:
        return _no_entry("REDESIGN_BLOCK_SESSION_NOT_ALLOWED")
    if features.atr_like <= 0:
        return _no_entry("REDESIGN_BLOCK_ATR_NOT_POSITIVE")

    long_side = RedesignEntrySide.REDESIGN_ENTRY_LONG
    short_side = RedesignEntrySide.REDESIGN_ENTRY_SHORT

    if family is RedesignEntryFamily.TREND_CONTINUATION:
        if (
            features.trend is RedesignTrendRegime.UP
            and features.momentum is RedesignMomentum.UP
        ):
            return RedesignEntryDecision(long_side, "")
        if (
            features.trend is RedesignTrendRegime.DOWN
            and features.momentum is RedesignMomentum.DOWN
        ):
            return RedesignEntryDecision(short_side, "")
        return _no_entry("REDESIGN_NO_TREND_MOMENTUM_ALIGNMENT")

    if family is RedesignEntryFamily.BREAKOUT:
        if (
            features.breakout is RedesignBreakout.UP
            and features.trend is not RedesignTrendRegime.DOWN
        ):
            return RedesignEntryDecision(long_side, "")
        if (
            features.breakout is RedesignBreakout.DOWN
            and features.trend is not RedesignTrendRegime.UP
        ):
            return RedesignEntryDecision(short_side, "")
        return _no_entry("REDESIGN_NO_BREAKOUT")

    if family is RedesignEntryFamily.MEAN_REVERSION_RANGE:
        if features.trend is not RedesignTrendRegime.RANGE:
            return _no_entry("REDESIGN_NOT_RANGE_REGIME")
        if features.overextension is RedesignOverextension.DOWN:
            return RedesignEntryDecision(long_side, "")
        if features.overextension is RedesignOverextension.UP:
            return RedesignEntryDecision(short_side, "")
        return _no_entry("REDESIGN_NO_OVEREXTENSION")

    # DUAL_CONFIRMATION
    if (
        features.trend is RedesignTrendRegime.UP
        and features.breakout is RedesignBreakout.UP
    ):
        return RedesignEntryDecision(long_side, "")
    if (
        features.trend is RedesignTrendRegime.DOWN
        and features.breakout is RedesignBreakout.DOWN
    ):
        return RedesignEntryDecision(short_side, "")
    return _no_entry("REDESIGN_NO_DUAL_CONFIRMATION")


@dataclass(frozen=True)
class RedesignExitConfig:
    """ATR-relative exit config. Candidate-only; distances are relative."""

    name: str
    tp_atr_mult: float
    sl_atr_mult: float
    max_hold_bars: int
    opposite_debounce_bars: int

    def __post_init__(self) -> None:
        if self.tp_atr_mult <= 0 or self.sl_atr_mult <= 0:
            raise RedesignRuleError("ATR exit multiples must be positive")
        if self.max_hold_bars <= 0:
            raise RedesignRuleError("max hold bars must be positive")
        if self.opposite_debounce_bars < 1:
            raise RedesignRuleError("debounce bars must be >= 1")

    def __bool__(self) -> bool:
        return False


EXIT_TIGHT = RedesignExitConfig(
    name="EXIT_TIGHT_ATR",
    tp_atr_mult=1.0,
    sl_atr_mult=1.0,
    max_hold_bars=12,
    opposite_debounce_bars=2,
)
EXIT_RIDE = RedesignExitConfig(
    name="EXIT_RIDE_ATR",
    tp_atr_mult=2.5,
    sl_atr_mult=1.0,
    max_hold_bars=48,
    opposite_debounce_bars=3,
)


@dataclass(frozen=True)
class RedesignCandidate:
    """A redesign candidate. Never officially adopted, never a permission."""

    candidate_name: str
    family: RedesignEntryFamily
    exit_config: RedesignExitConfig
    feature_config: RedesignFeatureConfig = RedesignFeatureConfig()
    rule_version: str = REDESIGN_RULE_VERSION
    candidate_only: bool = True
    officially_adopted: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False

    def __post_init__(self) -> None:
        if self.officially_adopted:
            raise RedesignRuleError(
                "redesign candidates are candidate-only; official adoption "
                "requires OOS review, paper-forward, and an operator decision"
            )
        if not self.candidate_only:
            raise RedesignRuleError("candidate must stay candidate-only")

    def __bool__(self) -> bool:
        return False


def build_default_redesign_candidates() -> tuple[RedesignCandidate, ...]:
    """Four entry families x two ATR exit configs (8 candidates)."""

    candidates: list[RedesignCandidate] = []
    for family in RedesignEntryFamily:
        for exit_config in (EXIT_TIGHT, EXIT_RIDE):
            candidates.append(
                RedesignCandidate(
                    candidate_name=f"{family.value}__{exit_config.name}",
                    family=family,
                    exit_config=exit_config,
                )
            )
    return tuple(candidates)


# ---------------------------------------------------------------------------
# Backtest-only redesign runner (own loop; produces a BacktestRunResult)
# ---------------------------------------------------------------------------


@dataclass
class _OpenRedesignTrade:
    side: str
    entry_close: float
    entry_bar: int
    spread_cost: float
    tp_distance: float
    sl_distance: float


def _spread_within(category: SpreadCategorySafeLabel) -> bool:
    return category is SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL


def _distribution(labels: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return tuple(sorted(counts.items()))


def run_redesign_backtest(
    *,
    dataset: BacktestDataset,
    candidate: RedesignCandidate,
    spread_included: bool = True,
    spread_cost_multiplier: float = 1.0,
    slippage_price_per_side: float = 0.0,
) -> BacktestRunResult:
    """Run one redesign candidate over one (sub-)dataset. No retry paths.

    ``spread_cost_multiplier`` (default 1.0) scales the per-trade spread cost
    for cost-sensitivity stress tests; ``slippage_price_per_side`` (default
    0.0) charges an additional adverse fill on entry and exit (latency /
    market impact / stop gap-through). Neither changes entry/exit decisions.
    """

    candles = dataset.candles
    closes = [c.close_value for c in candles]
    highs = [c.high_value for c in candles]
    lows = [c.low_value for c in candles]

    trades: list[BacktestTradeEvent] = []
    open_trade: _OpenRedesignTrade | None = None
    opposite_streak = 0
    entry_side_labels: list[str] = []
    block_reasons: list[str] = []

    def _close(*, reason: BacktestExitReason, exit_price: float, bar: int) -> None:
        nonlocal open_trade
        assert open_trade is not None
        direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
        pnl = (
            (exit_price - open_trade.entry_close) * direction
            - open_trade.spread_cost
            - 2.0 * slippage_price_per_side
        )
        trades.append(
            BacktestTradeEvent(
                trade_index=len(trades),
                side_safe_label=open_trade.side,
                entry_signal_safe_label=(
                    "REDESIGN_ENTRY_LONG"
                    if open_trade.side == "PAPER_LONG"
                    else "REDESIGN_ENTRY_SHORT"
                ),
                exit_reason_safe_label=reason,
                hold_duration_bars=bar - open_trade.entry_bar,
                synthetic_pnl_value=pnl,
                synthetic_spread_cost_value=open_trade.spread_cost,
                spread_included=spread_included,
                synthetic_fixture=dataset.synthetic_fixture,
            )
        )
        open_trade = None

    exit_config = candidate.exit_config
    last_index = len(candles) - 1
    for bar_index in range(dataset.warmup_bars, len(candles)):
        candle = candles[bar_index]
        features = compute_redesign_features(
            closes=closes,
            highs=highs,
            lows=lows,
            index=bar_index,
            config=candidate.feature_config,
        )

        if open_trade is not None:
            direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
            hit_sl = (
                candle.low_value <= open_trade.entry_close - open_trade.sl_distance
                if direction > 0
                else candle.high_value
                >= open_trade.entry_close + open_trade.sl_distance
            )
            hit_tp = (
                candle.high_value >= open_trade.entry_close + open_trade.tp_distance
                if direction > 0
                else candle.low_value
                <= open_trade.entry_close - open_trade.tp_distance
            )
            held = bar_index - open_trade.entry_bar
            is_opposite = (
                direction > 0 and features.trend is RedesignTrendRegime.DOWN
            ) or (direction < 0 and features.trend is RedesignTrendRegime.UP)
            opposite_streak = opposite_streak + 1 if is_opposite else 0
            if hit_sl:
                _close(
                    reason=BacktestExitReason.EXIT_STOP_LOSS,
                    exit_price=open_trade.entry_close
                    - direction * open_trade.sl_distance,
                    bar=bar_index,
                )
            elif hit_tp:
                _close(
                    reason=BacktestExitReason.EXIT_TAKE_PROFIT,
                    exit_price=open_trade.entry_close
                    + direction * open_trade.tp_distance,
                    bar=bar_index,
                )
            elif held >= exit_config.max_hold_bars:
                _close(
                    reason=BacktestExitReason.EXIT_MAX_HOLD,
                    exit_price=candle.close_value,
                    bar=bar_index,
                )
            elif opposite_streak >= exit_config.opposite_debounce_bars:
                _close(
                    reason=BacktestExitReason.EXIT_OPPOSITE_SIGNAL,
                    exit_price=candle.close_value,
                    bar=bar_index,
                )
            continue

        decision = redesign_entry_decision(
            family=candidate.family,
            features=features,
            spread_within_limit=_spread_within(
                dataset.spreads[bar_index].spread_category
            ),
            session_allowed=(
                dataset.sessions[bar_index].session_safe_label
                is SessionAllowedSafeLabel.SESSION_ALLOWED
            ),
        )
        entry_side_labels.append(decision.entry_side.value)
        if decision.block_reason_safe_label:
            block_reasons.append(decision.block_reason_safe_label)
        if decision.entry_side is RedesignEntrySide.REDESIGN_NO_ENTRY:
            continue

        spread_record = dataset.spreads[bar_index]
        spread_cost = (
            (spread_record.spread_value or 0.0) * spread_cost_multiplier
            if spread_included
            else 0.0
        )
        side = (
            "PAPER_LONG"
            if decision.entry_side is RedesignEntrySide.REDESIGN_ENTRY_LONG
            else "PAPER_SHORT"
        )
        open_trade = _OpenRedesignTrade(
            side=side,
            entry_close=candle.close_value,
            entry_bar=bar_index,
            spread_cost=spread_cost,
            tp_distance=exit_config.tp_atr_mult * features.atr_like,
            sl_distance=exit_config.sl_atr_mult * features.atr_like,
        )
        opposite_streak = 0

    if open_trade is not None:
        _close(
            reason=BacktestExitReason.EXIT_END_OF_WINDOW,
            exit_price=candles[last_index].close_value,
            bar=last_index,
        )

    return BacktestRunResult(
        status=GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED,
        blocked_reasons=(),
        bars_processed=len(candles) - dataset.warmup_bars,
        trades=tuple(trades),
        signal_distribution=_distribution(entry_side_labels),
        category_distribution=(),
        block_reason_distribution=_distribution(block_reasons),
        spread_included=spread_included,
        synthetic_fixture_only=dataset.synthetic_fixture,
        real_data_used=not dataset.synthetic_fixture,
    )


# ---------------------------------------------------------------------------
# Split slicing with redesign-sized lead-in (indicator warmup, not leakage)
# ---------------------------------------------------------------------------


def _slice(
    dataset: BacktestDataset, *, start: int, end: int, warmup: int
) -> BacktestDataset:
    return BacktestDataset(
        symbol_safe_label=dataset.symbol_safe_label,
        timeframe_safe_label=dataset.timeframe_safe_label,
        candles=dataset.candles[start:end],
        spreads=dataset.spreads[start:end],
        sessions=dataset.sessions[start:end],
        warmup_bars=warmup,
        synthetic_fixture=dataset.synthetic_fixture,
        validated_operator_local_csv=dataset.validated_operator_local_csv,
    )


def build_redesign_split_datasets(
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    *,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
) -> dict[str, BacktestDataset]:
    """Train / validation / OOS slices with a redesign-sized indicator lead-in."""

    return {
        "TRAIN": _slice(dataset, start=0, end=split.train_end, warmup=lead),
        "VALIDATION": _slice(
            dataset,
            start=max(0, split.train_end - lead),
            end=split.validation_end,
            warmup=min(lead, split.train_end),
        ),
        "OOS": _slice(
            dataset,
            start=max(0, split.validation_end - lead),
            end=split.oos_end,
            warmup=min(lead, split.validation_end),
        ),
    }


# ---------------------------------------------------------------------------
# Aggregate safe views, comparison, freeze, one-time OOS
# ---------------------------------------------------------------------------


def _sign(value: float) -> str:
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "ZERO"


@dataclass(frozen=True)
class RedesignSplitMetricsSafe:
    candidate_name: str
    split_label: str
    trade_count: int
    win_rate_rounded: float
    profit_factor_rounded: float
    expectancy_sign: str
    max_consecutive_losses: int
    spread_cost_ratio_sign: str

    def __bool__(self) -> bool:
        return False


def _view(
    name: str, split_label: str, metrics: BacktestMetricsSummary
) -> RedesignSplitMetricsSafe:
    return RedesignSplitMetricsSafe(
        candidate_name=name,
        split_label=split_label,
        trade_count=metrics.trade_count,
        win_rate_rounded=round(metrics.win_rate, 4),
        profit_factor_rounded=round(metrics.profit_factor, 4),
        expectancy_sign=_sign(metrics.expectancy),
        max_consecutive_losses=metrics.max_consecutive_losses,
        spread_cost_ratio_sign=_sign(metrics.spread_cost_ratio),
    )


def _metrics_for(run_result: BacktestRunResult, real: bool) -> BacktestMetricsSummary:
    return compute_backtest_metrics(run_result, real_data_single_sample=real)


class RedesignSelectionStatus(str, Enum):
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    NO_CANDIDATE_SELECTED = "NO_CANDIDATE_SELECTED"


@dataclass(frozen=True)
class RedesignComparison:
    status: RedesignSelectionStatus
    selected_candidate_name: str | None
    selection_reason_safe_category: str
    baseline_validation_profit_factor: float
    baseline_validation_max_consecutive_losses: int
    train_metrics: tuple[RedesignSplitMetricsSafe, ...]
    validation_metrics: tuple[RedesignSplitMetricsSafe, ...]
    parameter_search_count: int
    selected_using: str = "TRAIN_VALIDATION_ONLY"
    oos_not_seen_before_freeze: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


_MIN_VALIDATION_PROFIT_FACTOR = 1.0


def _baseline_metrics(dataset_slice: BacktestDataset) -> BacktestMetricsSummary:
    policy = build_candidate_exit_policy_profiles()["CANDIDATE_MEDIUM_BALANCED"]
    run_result = run_synthetic_backtest(
        dataset=dataset_slice, exit_policy=policy, spread_included=True
    )
    return _metrics_for(run_result, not dataset_slice.synthetic_fixture)


def compare_redesign_candidates_train_validation(
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    candidates: tuple[RedesignCandidate, ...] | None = None,
) -> RedesignComparison:
    """Compare redesign candidates on train+validation only. OOS untouched.

    Selection is strict and conservative: a candidate must reach validation
    profit factor > 1.0 with non-negative expectancy, a sufficient trade
    count, and no worse max-consecutive-losses than the baseline. The best
    eligible validation profit factor wins (deterministic tie-break).
    """

    candidate_set = candidates or build_default_redesign_candidates()
    splits = build_redesign_split_datasets(dataset, split)
    train_ds = splits["TRAIN"]
    validation_ds = splits["VALIDATION"]
    real = not dataset.synthetic_fixture

    baseline_val = _baseline_metrics(validation_ds)
    train_views: list[RedesignSplitMetricsSafe] = [
        _view("BASELINE", "TRAIN", _baseline_metrics(train_ds))
    ]
    validation_views: list[RedesignSplitMetricsSafe] = [
        _view("BASELINE", "VALIDATION", baseline_val)
    ]

    eligible: list[tuple[str, BacktestMetricsSummary]] = []
    for candidate in candidate_set:
        train_metrics = _metrics_for(
            run_redesign_backtest(dataset=train_ds, candidate=candidate), real
        )
        val_metrics = _metrics_for(
            run_redesign_backtest(dataset=validation_ds, candidate=candidate), real
        )
        train_views.append(_view(candidate.candidate_name, "TRAIN", train_metrics))
        validation_views.append(
            _view(candidate.candidate_name, "VALIDATION", val_metrics)
        )
        if (
            val_metrics.trade_count >= MINIMUM_TRADE_COUNT_FOR_EVALUATION
            and val_metrics.profit_factor > _MIN_VALIDATION_PROFIT_FACTOR
            and val_metrics.expectancy >= 0
            and val_metrics.max_consecutive_losses
            <= baseline_val.max_consecutive_losses
        ):
            eligible.append((candidate.candidate_name, val_metrics))

    parameter_search_count = len(candidate_set)
    if not eligible:
        return RedesignComparison(
            status=RedesignSelectionStatus.NO_CANDIDATE_SELECTED,
            selected_candidate_name=None,
            selection_reason_safe_category="NO_CANDIDATE_MEETS_SELECTION_CRITERIA",
            baseline_validation_profit_factor=round(baseline_val.profit_factor, 4),
            baseline_validation_max_consecutive_losses=(
                baseline_val.max_consecutive_losses
            ),
            train_metrics=tuple(train_views),
            validation_metrics=tuple(validation_views),
            parameter_search_count=parameter_search_count,
        )

    eligible.sort(
        key=lambda item: (
            -item[1].profit_factor,
            item[1].max_consecutive_losses,
            item[0],
        )
    )
    return RedesignComparison(
        status=RedesignSelectionStatus.CANDIDATE_SELECTED,
        selected_candidate_name=eligible[0][0],
        selection_reason_safe_category=(
            "VALIDATION_PROFIT_FACTOR_ABOVE_ONE_WITHOUT_WORSE_RISK"
        ),
        baseline_validation_profit_factor=round(baseline_val.profit_factor, 4),
        baseline_validation_max_consecutive_losses=(
            baseline_val.max_consecutive_losses
        ),
        train_metrics=tuple(train_views),
        validation_metrics=tuple(validation_views),
        parameter_search_count=parameter_search_count,
    )


@dataclass(frozen=True)
class FrozenRedesignCandidate:
    candidate: RedesignCandidate
    rule_version: str
    selection_reason_safe_category: str
    validation_profit_factor: float
    selected_using: str = "TRAIN_VALIDATION_ONLY"
    oos_not_seen_before_freeze: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def freeze_redesign_candidate(
    comparison: RedesignComparison,
    candidates: tuple[RedesignCandidate, ...] | None = None,
) -> FrozenRedesignCandidate | None:
    if comparison.status is not RedesignSelectionStatus.CANDIDATE_SELECTED:
        return None
    candidate_set = candidates or build_default_redesign_candidates()
    by_name = {c.candidate_name: c for c in candidate_set}
    selected = by_name[comparison.selected_candidate_name]
    validation_pf = next(
        view.profit_factor_rounded
        for view in comparison.validation_metrics
        if view.candidate_name == selected.candidate_name
    )
    return FrozenRedesignCandidate(
        candidate=selected,
        rule_version=REDESIGN_RULE_VERSION,
        selection_reason_safe_category=comparison.selection_reason_safe_category,
        validation_profit_factor=validation_pf,
    )


class RedesignOosResultCategory(str, Enum):
    OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW = (
        "OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW"
    )
    OOS_DEGRADED_REJECT_CANDIDATE = "OOS_DEGRADED_REJECT_CANDIDATE"
    OOS_INSUFFICIENT_TRADES = "OOS_INSUFFICIENT_TRADES"
    OOS_NOT_RUN_NO_CANDIDATE = "OOS_NOT_RUN_NO_CANDIDATE"


_OOS_DEGRADATION_FLOOR = 0.80
_MIN_OOS_PROFIT_FACTOR = 1.0

_EXIT_REASONS = (
    BacktestExitReason.EXIT_TAKE_PROFIT,
    BacktestExitReason.EXIT_STOP_LOSS,
    BacktestExitReason.EXIT_MAX_HOLD,
    BacktestExitReason.EXIT_OPPOSITE_SIGNAL,
    BacktestExitReason.EXIT_END_OF_WINDOW,
)


@dataclass(frozen=True)
class RedesignOosEvaluation:
    result_category: RedesignOosResultCategory
    oos_metrics: RedesignSplitMetricsSafe | None
    exit_reason_distribution: tuple[tuple[str, int], ...]
    evaluated_once: bool
    retuned_after_oos: bool = False
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_redesign_candidate_on_oos_once(
    dataset: BacktestDataset,
    split: ChronologicalSplit,
    frozen: FrozenRedesignCandidate | None,
) -> RedesignOosEvaluation:
    """Evaluate the frozen redesign candidate on OOS exactly once. No retuning."""

    if frozen is None:
        return RedesignOosEvaluation(
            result_category=RedesignOosResultCategory.OOS_NOT_RUN_NO_CANDIDATE,
            oos_metrics=None,
            exit_reason_distribution=(),
            evaluated_once=False,
        )
    oos_ds = build_redesign_split_datasets(dataset, split)["OOS"]
    run_result = run_redesign_backtest(dataset=oos_ds, candidate=frozen.candidate)
    metrics = _metrics_for(run_result, not oos_ds.synthetic_fixture)
    view = _view(frozen.candidate.candidate_name, "OOS", metrics)
    exit_counts = {
        reason.value: sum(
            1 for t in run_result.trades if t.exit_reason_safe_label is reason
        )
        for reason in _EXIT_REASONS
    }
    exit_distribution = tuple(
        (label, count) for label, count in sorted(exit_counts.items()) if count
    )
    if metrics.trade_count < MINIMUM_TRADE_COUNT_FOR_EVALUATION:
        category = RedesignOosResultCategory.OOS_INSUFFICIENT_TRADES
    elif metrics.profit_factor >= max(
        _MIN_OOS_PROFIT_FACTOR,
        frozen.validation_profit_factor * _OOS_DEGRADATION_FLOOR,
    ):
        category = RedesignOosResultCategory.OOS_INITIAL_PASSED_FOR_FURTHER_REVIEW
    else:
        category = RedesignOosResultCategory.OOS_DEGRADED_REJECT_CANDIDATE
    return RedesignOosEvaluation(
        result_category=category,
        oos_metrics=view,
        exit_reason_distribution=exit_distribution,
        evaluated_once=True,
    )
