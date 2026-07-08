"""Strategy evaluation hardening (no-POST, deterministic, aggregate-only).

The single-shot freeze->OOS protocol accepted a candidate on validation that
then failed once out-of-sample. That is exactly the false-positive risk a
rigorous evaluation must control. This module replaces "one OOS look" with a
much stronger battery, all read-only over the operator's local CSV dataset:

1. Walk-forward (rolling out-of-sample): evaluate a fixed candidate over many
   consecutive OOS windows and measure how often its edge actually persists,
   not whether it worked once.
2. Cost sensitivity: repeat the walk-forward at several spread-cost
   multipliers; a real edge must survive higher assumed costs.
3. Random-entry benchmark: run a deterministic pseudo-random entry through
   the SAME exits, so we can tell whether the entry rule adds information or
   whether the result is explained by the exit/position structure alone.
4. Combined robustness verdict per candidate.

Everything is deterministic (a fixed LCG, never the `random` module), never
touches a broker/network/credential surface, and reports only safe labels,
safe counts, and aggregate metrics. Nothing here is ever a performance proof
or a live permission: ``performance_proof_status`` / ``live_ready`` stay
false and results are never truthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_strategy_backtest_dataset import BacktestDataset
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    BacktestRunResult,
    BacktestTradeEvent,
    GmoBacktestRunStatus,
    build_candidate_exit_policy_profiles,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_backtest_metrics import (
    BacktestMetricsSummary,
    compute_backtest_metrics,
)
from app.services.gmo_strategy_redesign import (
    REDESIGN_SLICE_LEAD_IN_BARS,
    RedesignCandidate,
    RedesignExitConfig,
    build_default_redesign_candidates,
    compute_redesign_features,
    run_redesign_backtest,
)

BASELINE_RUNNER_NAME = "BASELINE"
RANDOM_BENCHMARK_RUNNER_NAME = "RANDOM_ENTRY_BENCHMARK"
DEFAULT_COST_MULTIPLIERS = (1.0, 1.5, 2.0)
DEFAULT_WALK_FORWARD_WINDOW_BARS = 2000
DEFAULT_MAX_WINDOWS = 12
DEFAULT_MIN_TRADES_PER_WINDOW = 15
# A candidate is walk-forward robust only if it clears this share of the
# qualifying windows, and cost-robust if it still does at 1.5x cost.
_ROBUST_PASS_RATE = 0.60
_COST_ROBUST_MULTIPLIER = 1.5
_BEATS_RANDOM_MARGIN = 0.05
_LCG_SEED = 2_463_534_242


# ---------------------------------------------------------------------------
# Walk-forward windows (chronological, no leakage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WalkForwardWindow:
    """One rolling OOS window: [traded_start, traded_end) plus indicator lead."""

    index: int
    slice_start: int
    traded_start: int
    traded_end: int

    def __bool__(self) -> bool:
        return False


def build_walk_forward_windows(
    total_bars: int,
    *,
    window_bars: int = DEFAULT_WALK_FORWARD_WINDOW_BARS,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
    max_windows: int = DEFAULT_MAX_WINDOWS,
) -> tuple[WalkForwardWindow, ...]:
    """Consecutive, non-overlapping OOS windows with an indicator lead-in.

    Window i trades bars [lead + i*window_bars, lead + (i+1)*window_bars); its
    slice includes the preceding ``lead`` bars purely as indicator warmup
    (that is standard lookback, not leakage -- no future bar is ever used).
    """

    if window_bars <= 0 or lead < 0:
        return ()
    windows: list[WalkForwardWindow] = []
    index = 0
    while len(windows) < max_windows:
        traded_start = lead + index * window_bars
        traded_end = traded_start + window_bars
        if traded_end > total_bars:
            break
        windows.append(
            WalkForwardWindow(
                index=index,
                slice_start=traded_start - lead,
                traded_start=traded_start,
                traded_end=traded_end,
            )
        )
        index += 1
    return tuple(windows)


def _window_slice(
    dataset: BacktestDataset, window: WalkForwardWindow, *, lead: int
) -> BacktestDataset:
    return BacktestDataset(
        symbol_safe_label=dataset.symbol_safe_label,
        timeframe_safe_label=dataset.timeframe_safe_label,
        candles=dataset.candles[window.slice_start : window.traded_end],
        spreads=dataset.spreads[window.slice_start : window.traded_end],
        sessions=dataset.sessions[window.slice_start : window.traded_end],
        warmup_bars=lead,
        synthetic_fixture=dataset.synthetic_fixture,
        validated_operator_local_csv=dataset.validated_operator_local_csv,
    )


# ---------------------------------------------------------------------------
# Deterministic random-entry benchmark (fixed LCG; never the random module)
# ---------------------------------------------------------------------------


@dataclass
class _OpenBenchmarkTrade:
    side: str
    entry_close: float
    entry_bar: int
    spread_cost: float
    tp_distance: float
    sl_distance: float


def run_random_entry_backtest(
    *,
    dataset: BacktestDataset,
    exit_config: RedesignExitConfig,
    spread_included: bool = True,
    spread_cost_multiplier: float = 1.0,
    seed: int = _LCG_SEED,
) -> BacktestRunResult:
    """Same ATR exits, but entry side chosen by a fixed deterministic LCG.

    Enters (when flat) on a fixed cadence with a pseudo-random long/short
    side, sized by the same ATR-relative exits. Reproducible for any seed;
    used only to benchmark whether a real entry rule adds information.
    """

    candles = dataset.candles
    closes = [c.close_value for c in candles]
    highs = [c.high_value for c in candles]
    lows = [c.low_value for c in candles]
    from app.services.gmo_strategy_redesign import RedesignFeatureConfig

    feature_config = RedesignFeatureConfig()
    trades: list[BacktestTradeEvent] = []
    open_trade: _OpenBenchmarkTrade | None = None
    state = seed & 0x7FFFFFFF

    def _next_bit() -> int:
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return (state >> 16) & 1

    def _close(*, reason: BacktestExitReason, exit_price: float, bar: int) -> None:
        nonlocal open_trade
        assert open_trade is not None
        direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
        pnl = (exit_price - open_trade.entry_close) * direction - open_trade.spread_cost
        trades.append(
            BacktestTradeEvent(
                trade_index=len(trades),
                side_safe_label=open_trade.side,
                entry_signal_safe_label="RANDOM_ENTRY",
                exit_reason_safe_label=reason,
                hold_duration_bars=bar - open_trade.entry_bar,
                synthetic_pnl_value=pnl,
                synthetic_spread_cost_value=open_trade.spread_cost,
                spread_included=spread_included,
                synthetic_fixture=dataset.synthetic_fixture,
            )
        )
        open_trade = None

    last_index = len(candles) - 1
    for bar_index in range(dataset.warmup_bars, len(candles)):
        candle = candles[bar_index]
        features = compute_redesign_features(
            closes=closes, highs=highs, lows=lows, index=bar_index,
            config=feature_config,
        )
        if open_trade is not None:
            direction = 1.0 if open_trade.side == "PAPER_LONG" else -1.0
            hit_sl = (
                candle.low_value <= open_trade.entry_close - open_trade.sl_distance
                if direction > 0
                else candle.high_value >= open_trade.entry_close + open_trade.sl_distance
            )
            hit_tp = (
                candle.high_value >= open_trade.entry_close + open_trade.tp_distance
                if direction > 0
                else candle.low_value <= open_trade.entry_close - open_trade.tp_distance
            )
            held = bar_index - open_trade.entry_bar
            if hit_sl:
                _close(
                    reason=BacktestExitReason.EXIT_STOP_LOSS,
                    exit_price=open_trade.entry_close - direction * open_trade.sl_distance,
                    bar=bar_index,
                )
            elif hit_tp:
                _close(
                    reason=BacktestExitReason.EXIT_TAKE_PROFIT,
                    exit_price=open_trade.entry_close + direction * open_trade.tp_distance,
                    bar=bar_index,
                )
            elif held >= exit_config.max_hold_bars:
                _close(
                    reason=BacktestExitReason.EXIT_MAX_HOLD,
                    exit_price=candle.close_value,
                    bar=bar_index,
                )
            continue

        # Flat: enter every few bars on a deterministic pseudo-random side.
        if not features.ready or features.atr_like <= 0:
            continue
        if bar_index % 4 != 0:  # fixed cadence to bound trade frequency
            continue
        side = "PAPER_LONG" if _next_bit() else "PAPER_SHORT"
        spread_record = dataset.spreads[bar_index]
        spread_cost = (
            (spread_record.spread_value or 0.0) * spread_cost_multiplier
            if spread_included
            else 0.0
        )
        open_trade = _OpenBenchmarkTrade(
            side=side,
            entry_close=candle.close_value,
            entry_bar=bar_index,
            spread_cost=spread_cost,
            tp_distance=exit_config.tp_atr_mult * features.atr_like,
            sl_distance=exit_config.sl_atr_mult * features.atr_like,
        )

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
        signal_distribution=(),
        category_distribution=(),
        block_reason_distribution=(),
        spread_included=spread_included,
        synthetic_fixture_only=dataset.synthetic_fixture,
        real_data_used=not dataset.synthetic_fixture,
    )


# ---------------------------------------------------------------------------
# Per-runner walk-forward summary
# ---------------------------------------------------------------------------


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


@dataclass(frozen=True)
class WindowResultSafe:
    window_index: int
    trade_count: int
    profit_factor_rounded: float
    expectancy_sign: str
    qualified: bool
    passed: bool

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class WalkForwardSummary:
    runner_name: str
    cost_multiplier: float
    window_count: int
    qualified_window_count: int
    passed_window_count: int
    pass_rate_rounded: float
    median_profit_factor_rounded: float
    window_results: tuple[WindowResultSafe, ...]
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def _metrics(run_result: BacktestRunResult, real: bool) -> BacktestMetricsSummary:
    return compute_backtest_metrics(run_result, real_data_single_sample=real)


def run_walk_forward_for_candidate(
    dataset: BacktestDataset,
    candidate: RedesignCandidate,
    windows: tuple[WalkForwardWindow, ...],
    *,
    cost_multiplier: float = 1.0,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
    min_trades_per_window: int = DEFAULT_MIN_TRADES_PER_WINDOW,
) -> WalkForwardSummary:
    """Rolling-OOS summary for one redesign candidate at one cost level."""

    real = not dataset.synthetic_fixture
    results: list[WindowResultSafe] = []
    qualified_pfs: list[float] = []
    for window in windows:
        run_result = run_redesign_backtest(
            dataset=_window_slice(dataset, window, lead=lead),
            candidate=candidate,
            spread_cost_multiplier=cost_multiplier,
        )
        metrics = _metrics(run_result, real)
        qualified = metrics.trade_count >= min_trades_per_window
        passed = qualified and metrics.profit_factor > 1.0 and metrics.expectancy >= 0
        if qualified:
            qualified_pfs.append(metrics.profit_factor)
        results.append(
            WindowResultSafe(
                window_index=window.index,
                trade_count=metrics.trade_count,
                profit_factor_rounded=round(metrics.profit_factor, 4),
                expectancy_sign=(
                    "NEGATIVE" if metrics.expectancy < 0 else "NON_NEGATIVE"
                ),
                qualified=qualified,
                passed=passed,
            )
        )
    qualified_count = sum(1 for r in results if r.qualified)
    passed_count = sum(1 for r in results if r.passed)
    pass_rate = passed_count / qualified_count if qualified_count else 0.0
    return WalkForwardSummary(
        runner_name=candidate.candidate_name,
        cost_multiplier=cost_multiplier,
        window_count=len(results),
        qualified_window_count=qualified_count,
        passed_window_count=passed_count,
        pass_rate_rounded=round(pass_rate, 4),
        median_profit_factor_rounded=round(_median(qualified_pfs), 4),
        window_results=tuple(results),
    )


def run_walk_forward_for_baseline(
    dataset: BacktestDataset,
    windows: tuple[WalkForwardWindow, ...],
    *,
    cost_multiplier: float = 1.0,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
    min_trades_per_window: int = DEFAULT_MIN_TRADES_PER_WINDOW,
) -> WalkForwardSummary:
    """Rolling-OOS summary for the old-engine baseline at one cost level."""

    real = not dataset.synthetic_fixture
    policy = build_candidate_exit_policy_profiles()["CANDIDATE_MEDIUM_BALANCED"]
    results: list[WindowResultSafe] = []
    qualified_pfs: list[float] = []
    for window in windows:
        run_result = run_synthetic_backtest(
            dataset=_window_slice(dataset, window, lead=lead),
            exit_policy=policy,
            spread_included=True,
            spread_cost_multiplier=cost_multiplier,
        )
        metrics = _metrics(run_result, real)
        qualified = metrics.trade_count >= min_trades_per_window
        passed = qualified and metrics.profit_factor > 1.0 and metrics.expectancy >= 0
        if qualified:
            qualified_pfs.append(metrics.profit_factor)
        results.append(
            WindowResultSafe(
                window_index=window.index,
                trade_count=metrics.trade_count,
                profit_factor_rounded=round(metrics.profit_factor, 4),
                expectancy_sign=(
                    "NEGATIVE" if metrics.expectancy < 0 else "NON_NEGATIVE"
                ),
                qualified=qualified,
                passed=passed,
            )
        )
    qualified_count = sum(1 for r in results if r.qualified)
    passed_count = sum(1 for r in results if r.passed)
    pass_rate = passed_count / qualified_count if qualified_count else 0.0
    return WalkForwardSummary(
        runner_name=BASELINE_RUNNER_NAME,
        cost_multiplier=cost_multiplier,
        window_count=len(results),
        qualified_window_count=qualified_count,
        passed_window_count=passed_count,
        pass_rate_rounded=round(pass_rate, 4),
        median_profit_factor_rounded=round(_median(qualified_pfs), 4),
        window_results=tuple(results),
    )


def run_walk_forward_for_random_benchmark(
    dataset: BacktestDataset,
    windows: tuple[WalkForwardWindow, ...],
    exit_config: RedesignExitConfig,
    *,
    cost_multiplier: float = 1.0,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
    min_trades_per_window: int = DEFAULT_MIN_TRADES_PER_WINDOW,
) -> WalkForwardSummary:
    """Rolling-OOS summary for the deterministic random-entry benchmark."""

    real = not dataset.synthetic_fixture
    results: list[WindowResultSafe] = []
    qualified_pfs: list[float] = []
    for window in windows:
        run_result = run_random_entry_backtest(
            dataset=_window_slice(dataset, window, lead=lead),
            exit_config=exit_config,
            spread_cost_multiplier=cost_multiplier,
            seed=_LCG_SEED + window.index,
        )
        metrics = _metrics(run_result, real)
        qualified = metrics.trade_count >= min_trades_per_window
        passed = qualified and metrics.profit_factor > 1.0 and metrics.expectancy >= 0
        if qualified:
            qualified_pfs.append(metrics.profit_factor)
        results.append(
            WindowResultSafe(
                window_index=window.index,
                trade_count=metrics.trade_count,
                profit_factor_rounded=round(metrics.profit_factor, 4),
                expectancy_sign=(
                    "NEGATIVE" if metrics.expectancy < 0 else "NON_NEGATIVE"
                ),
                qualified=qualified,
                passed=passed,
            )
        )
    qualified_count = sum(1 for r in results if r.qualified)
    passed_count = sum(1 for r in results if r.passed)
    pass_rate = passed_count / qualified_count if qualified_count else 0.0
    return WalkForwardSummary(
        runner_name=RANDOM_BENCHMARK_RUNNER_NAME,
        cost_multiplier=cost_multiplier,
        window_count=len(results),
        qualified_window_count=qualified_count,
        passed_window_count=passed_count,
        pass_rate_rounded=round(pass_rate, 4),
        median_profit_factor_rounded=round(_median(qualified_pfs), 4),
        window_results=tuple(results),
    )


# ---------------------------------------------------------------------------
# Combined per-candidate robustness verdict
# ---------------------------------------------------------------------------


class RobustnessVerdictCategory(str, Enum):
    ROBUST_CANDIDATE_FOR_PAPER_FORWARD = "ROBUST_CANDIDATE_FOR_PAPER_FORWARD"
    NOT_ROBUST_REJECT = "NOT_ROBUST_REJECT"
    INSUFFICIENT_WINDOWS = "INSUFFICIENT_WINDOWS"


@dataclass(frozen=True)
class CandidateRobustnessVerdict:
    candidate_name: str
    verdict: RobustnessVerdictCategory
    base_cost_pass_rate: float
    base_cost_median_pf: float
    stressed_cost_pass_rate: float
    robust_across_walk_forward: bool
    robust_to_cost: bool
    beats_random: bool
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class EvaluationHardeningReport:
    window_count: int
    window_bars: int
    cost_multipliers: tuple[float, ...]
    baseline_base_cost_pass_rate: float
    random_base_cost_pass_rate: float
    verdicts: tuple[CandidateRobustnessVerdict, ...]
    any_robust_candidate: bool
    overall_conclusion_safe_label: str
    performance_proof_status: bool = False
    live_ready: bool = False
    real_data_used: bool = True

    def __bool__(self) -> bool:
        return False


def evaluate_candidate_robustness(
    dataset: BacktestDataset,
    *,
    candidates: tuple[RedesignCandidate, ...] | None = None,
    window_bars: int = DEFAULT_WALK_FORWARD_WINDOW_BARS,
    max_windows: int = DEFAULT_MAX_WINDOWS,
    cost_multipliers: tuple[float, ...] = DEFAULT_COST_MULTIPLIERS,
    lead: int = REDESIGN_SLICE_LEAD_IN_BARS,
) -> EvaluationHardeningReport:
    """Full robustness battery over all candidates. Aggregate-only, no-POST."""

    candidate_set = candidates or build_default_redesign_candidates()
    windows = build_walk_forward_windows(
        len(dataset.candles), window_bars=window_bars, lead=lead,
        max_windows=max_windows,
    )
    base_cost = cost_multipliers[0] if cost_multipliers else 1.0
    stress_cost = next(
        (c for c in cost_multipliers if c >= _COST_ROBUST_MULTIPLIER), base_cost
    )

    baseline_base = run_walk_forward_for_baseline(
        dataset, windows, cost_multiplier=base_cost, lead=lead
    )
    # Random benchmark uses each candidate's own exit config; summarize the
    # random pass rate with a representative exit config (the first candidate's).
    representative_exit = candidate_set[0].exit_config if candidate_set else None
    random_base = (
        run_walk_forward_for_random_benchmark(
            dataset, windows, representative_exit, cost_multiplier=base_cost, lead=lead
        )
        if representative_exit is not None
        else None
    )
    random_base_median = (
        random_base.median_profit_factor_rounded if random_base is not None else 0.0
    )

    verdicts: list[CandidateRobustnessVerdict] = []
    for candidate in candidate_set:
        base = run_walk_forward_for_candidate(
            dataset, candidate, windows, cost_multiplier=base_cost, lead=lead
        )
        stressed = run_walk_forward_for_candidate(
            dataset, candidate, windows, cost_multiplier=stress_cost, lead=lead
        )
        random_for_exit = run_walk_forward_for_random_benchmark(
            dataset, windows, candidate.exit_config, cost_multiplier=base_cost,
            lead=lead,
        )
        robust_wf = (
            base.qualified_window_count >= 3
            and base.pass_rate_rounded >= _ROBUST_PASS_RATE
        )
        robust_cost = stressed.pass_rate_rounded >= _ROBUST_PASS_RATE
        beats_random = (
            base.median_profit_factor_rounded
            > random_for_exit.median_profit_factor_rounded + _BEATS_RANDOM_MARGIN
        )
        if base.qualified_window_count < 3:
            verdict = RobustnessVerdictCategory.INSUFFICIENT_WINDOWS
        elif robust_wf and robust_cost and beats_random:
            verdict = RobustnessVerdictCategory.ROBUST_CANDIDATE_FOR_PAPER_FORWARD
        else:
            verdict = RobustnessVerdictCategory.NOT_ROBUST_REJECT
        verdicts.append(
            CandidateRobustnessVerdict(
                candidate_name=candidate.candidate_name,
                verdict=verdict,
                base_cost_pass_rate=base.pass_rate_rounded,
                base_cost_median_pf=base.median_profit_factor_rounded,
                stressed_cost_pass_rate=stressed.pass_rate_rounded,
                robust_across_walk_forward=robust_wf,
                robust_to_cost=robust_cost,
                beats_random=beats_random,
            )
        )

    any_robust = any(
        v.verdict is RobustnessVerdictCategory.ROBUST_CANDIDATE_FOR_PAPER_FORWARD
        for v in verdicts
    )
    conclusion = (
        "ROBUST_CANDIDATE_FOUND_PAPER_FORWARD_NEXT"
        if any_robust
        else "NO_ROBUST_EDGE_ACROSS_WALK_FORWARD_AND_COST_STRESS"
    )
    return EvaluationHardeningReport(
        window_count=len(windows),
        window_bars=window_bars,
        cost_multipliers=cost_multipliers,
        baseline_base_cost_pass_rate=baseline_base.pass_rate_rounded,
        random_base_cost_pass_rate=random_base_median,
        verdicts=tuple(verdicts),
        any_robust_candidate=any_robust,
        overall_conclusion_safe_label=conclusion,
        real_data_used=not dataset.synthetic_fixture,
    )
