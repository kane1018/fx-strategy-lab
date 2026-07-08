"""Gotobi / Tokyo-fixing drift hypothesis (backtest-only, deterministic, no-POST).

A NEW, non-technical-indicator hypothesis with a real economic mechanism:
Japanese importers settle USD payments on "gotobi" days (dates ending in 5 or
0), so banks buy USD into the 9:55 JST Tokyo fixing (TTM). Academic work
(Ref. NBER w22820; arXiv 2301.13204, co-authored with GMO Gaika-ex) reports
that USD/JPY tends to drift UP from ~03:00 JST toward 9:55 JST on gotobi days.

This module PRE-REGISTERS one fixed rule and evaluates it honestly:

  * Effective gotobi day = base day in {5,10,15,20,25,30}; if that date is not
    a Japanese BANK business day (weekend / national holiday / year-end bank
    closure), settlement is brought forward to the PRECEDING bank business day.
  * On each effective gotobi day: go LONG USD/JPY at the ~03:00 JST bar close,
    exit at the ~09:55 JST bar close (a fixed time window; no TP/SL).

Because a naive positive result is easy to fool oneself with, the effect is
judged against FOUR controls, all net of realistic cost (0.5 pip/side slippage
+ spread, 2.0x cost stress):
  1. Non-gotobi control: the same window on non-gotobi days must NOT do as well.
  2. Day-label permutation p90: random same-size day subsets (many seeds).
  3. Sign-permutation p90: the same gotobi days with randomized direction.
  4. Temporal stability: the edge must hold in both halves of the sample.

Everything is deterministic (a fixed LCG, never the `random` module), never
touches a broker / network / credential surface, reports only safe labels,
safe counts, and aggregate ratios (profit factor, win rate, sign labels), and
is never a performance proof or a live permission: ``performance_proof_status``
/ ``live_ready`` stay false and results are never truthy. The calendar is a
static, auditable table covering only the span the local datasets cover; no
data is fetched.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum

from app.services.gmo_strategy_backtest_dataset import BacktestDataset
from app.services.gmo_strategy_backtest_engine import (
    BacktestExitReason,
    BacktestRunResult,
    BacktestTradeEvent,
    GmoBacktestRunStatus,
)

# ---------------------------------------------------------------------------
# Japanese bank-business-day calendar (static, auditable, no fetch)
# ---------------------------------------------------------------------------
# National holidays incl. substitute days, PLUS the year-end/new-year bank
# closure (Dec 31, Jan 2, Jan 3; Jan 1 is itself a national holiday). Source:
# Japanese Cabinet Office national-holiday list. Only the span our USD/JPY
# datasets cover (2025-04 .. 2026-07) is encoded; extend deliberately if the
# data range grows.
_JP_BANK_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2025, 4, 29),  # Showa Day
        date(2025, 5, 3),  # Constitution Memorial Day
        date(2025, 5, 4),  # Greenery Day
        date(2025, 5, 5),  # Children's Day
        date(2025, 5, 6),  # Substitute holiday
        date(2025, 7, 21),  # Marine Day
        date(2025, 8, 11),  # Mountain Day
        date(2025, 9, 15),  # Respect-for-the-Aged Day
        date(2025, 9, 23),  # Autumnal Equinox Day
        date(2025, 10, 13),  # Sports Day
        date(2025, 11, 3),  # Culture Day
        date(2025, 11, 23),  # Labor Thanksgiving Day
        date(2025, 11, 24),  # Substitute holiday
        date(2025, 12, 31),  # Year-end bank closure
        date(2026, 1, 1),  # New Year's Day
        date(2026, 1, 2),  # New-year bank closure
        date(2026, 1, 3),  # New-year bank closure
        date(2026, 1, 12),  # Coming-of-Age Day
        date(2026, 2, 11),  # National Foundation Day
        date(2026, 2, 23),  # The Emperor's Birthday
        date(2026, 3, 20),  # Vernal Equinox Day
        date(2026, 4, 29),  # Showa Day
        date(2026, 5, 3),  # Constitution Memorial Day
        date(2026, 5, 4),  # Greenery Day
        date(2026, 5, 5),  # Children's Day
        date(2026, 5, 6),  # Substitute holiday
        date(2026, 7, 20),  # Marine Day
    }
)

# "go-to-bi" settlement days: dates ending in 5 (5/15/25) plus the 0-ending
# days. Per the frozen pre-registration the "0"/30 slot is the true MONTH-END
# (末日 = the last calendar day), so a 31-day month uses the 31st (its real
# bank settlement day), not the 30th, and February uses the 28th/29th.
_GOTOBI_FIXED_DAYS = (5, 10, 15, 20, 25)


def is_jp_bank_business_day(day: date) -> bool:
    """Weekday and not a Japanese bank holiday (within the encoded span)."""

    return day.weekday() < 5 and day not in _JP_BANK_HOLIDAYS


def _preceding_business_day(day: date) -> date:
    cursor = day
    for _ in range(14):
        cursor = cursor - timedelta(days=1)
        if is_jp_bank_business_day(cursor):
            return cursor
    return cursor


def effective_gotobi_dates(start: date, end: date) -> frozenset[date]:
    """Bank-business-day-adjusted gotobi dates within ``[start, end]``.

    If a base gotobi date is not a bank business day, the settlement demand is
    brought forward to the preceding bank business day (that is when the FX
    flow actually appears).
    """

    out: set[date] = set()
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        last_day = _calendar.monthrange(year, month)[1]
        for day_num in (*_GOTOBI_FIXED_DAYS, last_day):  # 5/10/15/20/25 + 末日
            base_date = date(year, month, day_num)
            effective = (
                base_date
                if is_jp_bank_business_day(base_date)
                else _preceding_business_day(base_date)
            )
            if start <= effective <= end:
                out.add(effective)
        month += 1
        if month > 12:
            year += 1
            month = 1
    return frozenset(out)


# ---------------------------------------------------------------------------
# Pre-registered entry/exit window (JST minutes since midnight)
# ---------------------------------------------------------------------------
DEFAULT_ENTRY_JST_MINUTE = 3 * 60  # 03:00 JST -- drift onset per the literature
DEFAULT_EXIT_JST_MINUTE = 9 * 60 + 55  # 09:55 JST -- the Tokyo fixing (TTM)
# If the first tradeable bar of the day starts this many minutes past the entry
# target, the market was closed at 03:00 JST (e.g. Monday pre-open) and the day
# is skipped rather than entered at a fabricated price.
_ENTRY_LATENESS_TOLERANCE_MINUTES = 90

_LCG_SEED = 2_463_534_242
_TIMEFRAME_BAR_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}


class GotobiDayFilter(str, Enum):
    GOTOBI = "GOTOBI"
    NON_GOTOBI = "NON_GOTOBI"


def _bar_jst(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC) + timedelta(hours=9)


def _bar_minutes(dataset: BacktestDataset) -> int:
    mapped = _TIMEFRAME_BAR_MINUTES.get(dataset.timeframe_safe_label)
    if mapped:
        return mapped
    diffs = [
        (dataset.candles[i + 1].timestamp - dataset.candles[i].timestamp)
        // 1000
        // 60
        for i in range(min(50, len(dataset.candles) - 1))
    ]
    positive = [d for d in diffs if d > 0]
    return min(positive) if positive else 60


@dataclass(frozen=True)
class _DayTrade:
    day: date
    is_gotobi: bool
    entry_index: int
    exit_index: int


def _valid_day_trades(
    dataset: BacktestDataset,
    *,
    entry_jst_minute: int,
    exit_jst_minute: int,
) -> tuple[tuple[_DayTrade, ...], int]:
    """All JST dates that have a valid ~entry and ~exit bar. Returns the trades
    plus the count of gotobi days skipped for lack of a valid entry bar."""

    width = _bar_minutes(dataset)
    candles = dataset.candles
    by_date: dict[date, list[int]] = {}
    for i, candle in enumerate(candles):
        by_date.setdefault(_bar_jst(candle.timestamp).date(), []).append(i)

    span_start = min(by_date) if by_date else date(2000, 1, 1)
    span_end = max(by_date) if by_date else date(2000, 1, 1)
    gotobi = effective_gotobi_dates(span_start, span_end)

    trades: list[_DayTrade] = []
    skipped_gotobi = 0
    for day in sorted(by_date):
        indices = by_date[day]
        entry_index = None
        for i in indices:
            jst = _bar_jst(candles[i].timestamp)
            close_minute = jst.hour * 60 + jst.minute + width
            if close_minute >= entry_jst_minute:
                entry_index = i
                entry_close_minute = close_minute
                break
        if entry_index is None:
            if day in gotobi:
                skipped_gotobi += 1
            continue
        if entry_close_minute - entry_jst_minute > _ENTRY_LATENESS_TOLERANCE_MINUTES:
            if day in gotobi:
                skipped_gotobi += 1
            continue
        exit_index = None
        for i in indices:
            if i <= entry_index:
                continue
            jst = _bar_jst(candles[i].timestamp)
            close_minute = jst.hour * 60 + jst.minute + width
            if close_minute >= exit_jst_minute:
                exit_index = i
                break
        if exit_index is None:
            if day in gotobi:
                skipped_gotobi += 1
            continue
        trades.append(
            _DayTrade(
                day=day,
                is_gotobi=day in gotobi,
                entry_index=entry_index,
                exit_index=exit_index,
            )
        )
    return tuple(trades), skipped_gotobi


def _trade_pnl(
    dataset: BacktestDataset,
    day_trade: _DayTrade,
    *,
    long: bool,
    spread_included: bool,
    spread_cost_multiplier: float,
    slippage_price_per_side: float,
) -> tuple[float, float]:
    """Return ``(pnl, spread_cost)`` for one day trade. Candles are BID.

    Spread is charged on the leg that CROSSES it (leg-level, per the frozen
    pre-registration): a long buys at ASK on entry (charge the entry-bar
    spread) and sells at BID on exit (no extra); a short sells at BID on entry
    (no extra) and buys at ASK on exit (charge the exit-bar spread). Slippage
    is charged on both fills.
    """

    direction = 1.0 if long else -1.0
    entry_close = dataset.candles[day_trade.entry_index].close_value
    exit_close = dataset.candles[day_trade.exit_index].close_value
    crossing_index = day_trade.entry_index if long else day_trade.exit_index
    spread = (
        (dataset.spreads[crossing_index].spread_value or 0.0)
        if spread_included
        else 0.0
    )
    spread_cost = spread * spread_cost_multiplier
    pnl = (
        (exit_close - entry_close) * direction
        - spread_cost
        - 2.0 * slippage_price_per_side
    )
    return pnl, spread_cost


def run_gotobi_backtest(
    *,
    dataset: BacktestDataset,
    day_filter: GotobiDayFilter = GotobiDayFilter.GOTOBI,
    entry_jst_minute: int = DEFAULT_ENTRY_JST_MINUTE,
    exit_jst_minute: int = DEFAULT_EXIT_JST_MINUTE,
    direction_long: bool = True,
    spread_included: bool = True,
    spread_cost_multiplier: float = 1.0,
    slippage_price_per_side: float = 0.0,
    randomize_side_seed: int | None = None,
) -> BacktestRunResult:
    """Run the pre-registered gotobi window over one dataset. No retry paths."""

    all_trades, _ = _valid_day_trades(
        dataset, entry_jst_minute=entry_jst_minute, exit_jst_minute=exit_jst_minute
    )
    want_gotobi = day_filter is GotobiDayFilter.GOTOBI
    selected = [t for t in all_trades if t.is_gotobi == want_gotobi]

    state = (randomize_side_seed or 0) & 0x7FFFFFFF

    def _next_long() -> bool:
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return bool((state >> 16) & 1)

    events: list[BacktestTradeEvent] = []
    for day_trade in selected:
        long = _next_long() if randomize_side_seed is not None else direction_long
        pnl, spread_cost = _trade_pnl(
            dataset, day_trade, long=long, spread_included=spread_included,
            spread_cost_multiplier=spread_cost_multiplier,
            slippage_price_per_side=slippage_price_per_side,
        )
        events.append(
            BacktestTradeEvent(
                trade_index=len(events),
                side_safe_label="PAPER_LONG" if long else "PAPER_SHORT",
                entry_signal_safe_label="GOTOBI_FIX_DRIFT",
                exit_reason_safe_label=BacktestExitReason.EXIT_MAX_HOLD,
                hold_duration_bars=day_trade.exit_index - day_trade.entry_index,
                synthetic_pnl_value=pnl,
                synthetic_spread_cost_value=spread_cost,
                spread_included=spread_included,
                synthetic_fixture=dataset.synthetic_fixture,
            )
        )
    return BacktestRunResult(
        status=GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED,
        blocked_reasons=(),
        bars_processed=len(dataset.candles),
        trades=tuple(events),
        signal_distribution=(("GOTOBI_FIX_DRIFT", len(events)),),
        category_distribution=(),
        block_reason_distribution=(),
        spread_included=spread_included,
        synthetic_fixture_only=dataset.synthetic_fixture,
        real_data_used=not dataset.synthetic_fixture,
    )


# ---------------------------------------------------------------------------
# Honest evaluation: controls, permutations, cost stress, temporal stability
# ---------------------------------------------------------------------------
DEFAULT_STANDARD_SLIPPAGE_PRICE_PER_SIDE = 0.005  # 0.5 pip USD/JPY
DEFAULT_COST_MULTIPLIERS = (1.0, 1.5, 2.0)
DEFAULT_PERMUTATION_SEED_COUNT = 500
_BENCHMARK_PERCENTILE = 0.90
# Frozen pre-registration min-sample: gotobi >= 90 trades, split into >= 3
# chronological blocks each with >= 25 trades; below this the outcome is
# INSUFFICIENT (never a pass).
_MIN_GOTOBI_TRADES = 90
_STABILITY_BLOCKS = 3
_MIN_TRADES_PER_BLOCK = 25

VERDICT_PASSED = "RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD"
VERDICT_NOT_ROBUST = "GOTOBI_EFFECT_NOT_ROBUST_REJECT"
VERDICT_INSUFFICIENT = "INSUFFICIENT_GOTOBI_SAMPLE"


def _profit_factor(pnls: list[float]) -> float:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    if not wins:
        return 0.0
    if not losses:
        return 99.0
    return sum(wins) / abs(sum(losses))


def _win_rate(pnls: list[float]) -> float:
    return (sum(1 for p in pnls if p > 0) / len(pnls)) if pnls else 0.0


def _expectancy(pnls: list[float]) -> float:
    return (sum(pnls) / len(pnls)) if pnls else 0.0


def _sign(value: float) -> str:
    return "NON_NEGATIVE" if value >= 0 else "NEGATIVE"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int(pct * (len(ordered) - 1))]


def _lcg_order(n_total: int, seed: int) -> list[int]:
    state = seed & 0x7FFFFFFF
    order = list(range(n_total))
    for i in range(n_total - 1, 0, -1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


@dataclass(frozen=True)
class GotobiLegSafe:
    label: str
    trade_count: int
    profit_factor_rounded: float
    win_rate_rounded: float
    expectancy_sign: str

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class GotobiEvaluationReport:
    timeframe_safe_label: str
    entry_jst_hhmm: str
    exit_jst_hhmm: str
    slippage_price_per_side: float
    stress_cost_multiplier: float
    effective_gotobi_trade_count: int
    skipped_gotobi_day_count: int
    gotobi: GotobiLegSafe
    non_gotobi: GotobiLegSafe
    gotobi_cost_stressed: GotobiLegSafe
    label_permutation_p90_pf: float  # plain (secondary reference)
    weekday_stratified_label_permutation_p90_pf: float  # primary control
    sign_permutation_p90_pf: float
    block_pf_rounded: tuple[float, ...]
    block_trade_counts: tuple[int, ...]
    beats_non_gotobi_control: bool
    beats_label_permutation: bool  # plain (secondary reference)
    beats_weekday_stratified_label: bool  # primary control
    beats_sign_permutation: bool
    survives_cost_stress: bool
    stable_across_blocks: bool
    robust_verdict_safe_label: str
    performance_proof_status: bool = False
    live_ready: bool = False
    real_data_used: bool = True

    def __bool__(self) -> bool:
        return False


def _leg(label: str, pnls: list[float]) -> GotobiLegSafe:
    return GotobiLegSafe(
        label=label,
        trade_count=len(pnls),
        profit_factor_rounded=round(_profit_factor(pnls), 4),
        win_rate_rounded=round(_win_rate(pnls), 4),
        expectancy_sign=_sign(_expectancy(pnls)),
    )


def evaluate_gotobi_effect(
    dataset: BacktestDataset,
    *,
    entry_jst_minute: int = DEFAULT_ENTRY_JST_MINUTE,
    exit_jst_minute: int = DEFAULT_EXIT_JST_MINUTE,
    slippage_price_per_side: float = DEFAULT_STANDARD_SLIPPAGE_PRICE_PER_SIDE,
    cost_multipliers: tuple[float, ...] = DEFAULT_COST_MULTIPLIERS,
    permutation_seed_count: int = DEFAULT_PERMUTATION_SEED_COUNT,
) -> GotobiEvaluationReport:
    """Judge the pre-registered gotobi window against four controls, net of
    realistic cost. Aggregate-only, deterministic, no-POST. Never truthy."""

    base_cost = cost_multipliers[0] if cost_multipliers else 1.0
    stress_cost = max(cost_multipliers) if cost_multipliers else base_cost

    all_trades, skipped = _valid_day_trades(
        dataset, entry_jst_minute=entry_jst_minute, exit_jst_minute=exit_jst_minute
    )
    gotobi_trades = [t for t in all_trades if t.is_gotobi]
    non_gotobi_trades = [t for t in all_trades if not t.is_gotobi]

    def long_pnls(trades: list[_DayTrade], cost: float) -> list[float]:
        return [
            _trade_pnl(
                dataset, t, long=True, spread_included=True,
                spread_cost_multiplier=cost,
                slippage_price_per_side=slippage_price_per_side,
            )[0]
            for t in trades
        ]

    def short_pnls(trades: list[_DayTrade], cost: float) -> list[float]:
        return [
            _trade_pnl(
                dataset, t, long=False, spread_included=True,
                spread_cost_multiplier=cost,
                slippage_price_per_side=slippage_price_per_side,
            )[0]
            for t in trades
        ]

    gotobi_long_base = long_pnls(gotobi_trades, base_cost)
    gotobi_short_base = short_pnls(gotobi_trades, base_cost)
    non_gotobi_long_base = long_pnls(non_gotobi_trades, base_cost)
    gotobi_long_stress = long_pnls(gotobi_trades, stress_cost)
    all_long_base = gotobi_long_base + non_gotobi_long_base

    gotobi_leg = _leg("GOTOBI", gotobi_long_base)
    non_gotobi_leg = _leg("NON_GOTOBI", non_gotobi_long_base)
    stressed_leg = _leg("GOTOBI_COST_STRESSED", gotobi_long_stress)

    gotobi_pf = gotobi_leg.profit_factor_rounded
    n_goto = len(gotobi_trades)

    # (secondary) plain day-label permutation: random same-size subsets.
    label_pfs: list[float] = []
    if all_long_base and n_goto:
        for seed in range(permutation_seed_count):
            order = _lcg_order(len(all_long_base), _LCG_SEED + seed * 100003 + 11)
            label_pfs.append(_profit_factor([all_long_base[i] for i in order[:n_goto]]))
    label_p90 = round(_percentile(label_pfs, _BENCHMARK_PERCENTILE), 4)

    # (primary) weekday-stratified label permutation: sample same per-weekday
    # counts as gotobi, from all valid days -> controls gotobi's weekday skew.
    all_long_ordered = long_pnls(all_trades, base_cost)
    by_weekday: dict[int, list[float]] = {}
    for trade, pnl in zip(all_trades, all_long_ordered, strict=True):
        by_weekday.setdefault(trade.day.weekday(), []).append(pnl)
    gotobi_weekday_counts: dict[int, int] = {}
    for trade in gotobi_trades:
        wd = trade.day.weekday()
        gotobi_weekday_counts[wd] = gotobi_weekday_counts.get(wd, 0) + 1
    strat_pfs: list[float] = []
    if n_goto:
        for seed in range(permutation_seed_count):
            sample: list[float] = []
            for wd, cnt in sorted(gotobi_weekday_counts.items()):
                pool = by_weekday.get(wd, [])
                if not pool:
                    continue
                if len(pool) <= cnt:
                    sample.extend(pool)
                else:
                    order = _lcg_order(len(pool), _LCG_SEED + seed * 100003 + wd * 7 + 3)
                    sample.extend(pool[i] for i in order[:cnt])
            strat_pfs.append(_profit_factor(sample))
    strat_p90 = round(_percentile(strat_pfs, _BENCHMARK_PERCENTILE), 4)

    # Sign-permutation: same gotobi days, randomized direction.
    sign_pfs: list[float] = []
    for seed in range(permutation_seed_count):
        state = (_LCG_SEED + seed * 100003 + 7) & 0x7FFFFFFF
        pnls: list[float] = []
        for k in range(n_goto):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            long = bool((state >> 16) & 1)
            pnls.append(gotobi_long_base[k] if long else gotobi_short_base[k])
        sign_pfs.append(_profit_factor(pnls))
    sign_p90 = round(_percentile(sign_pfs, _BENCHMARK_PERCENTILE), 4)

    # Temporal stability: N chronological blocks, each must have PF > 1.
    ordered = sorted(range(n_goto), key=lambda k: gotobi_trades[k].day)
    block_pfs: list[float] = []
    block_counts: list[int] = []
    for b in range(_STABILITY_BLOCKS):
        lo = b * n_goto // _STABILITY_BLOCKS
        hi = (b + 1) * n_goto // _STABILITY_BLOCKS
        block = [gotobi_long_base[k] for k in ordered[lo:hi]]
        block_pfs.append(round(_profit_factor(block), 4))
        block_counts.append(len(block))

    beats_control = gotobi_pf > max(1.0, non_gotobi_leg.profit_factor_rounded)
    beats_label = gotobi_pf > label_p90  # secondary
    beats_stratified = gotobi_pf > strat_p90  # primary
    beats_sign = gotobi_pf > sign_p90
    survives_cost = (
        stressed_leg.profit_factor_rounded > 1.0
        and stressed_leg.expectancy_sign == "NON_NEGATIVE"
    )
    stable = all(pf > 1.0 for pf in block_pfs)

    enough = (
        n_goto >= _MIN_GOTOBI_TRADES
        and all(c >= _MIN_TRADES_PER_BLOCK for c in block_counts)
    )
    robust = (
        enough
        and beats_control
        and beats_stratified
        and beats_sign
        and survives_cost
        and stable
    )
    if not enough:
        verdict = VERDICT_INSUFFICIENT
    elif robust:
        verdict = VERDICT_PASSED
    else:
        verdict = VERDICT_NOT_ROBUST

    return GotobiEvaluationReport(
        timeframe_safe_label=dataset.timeframe_safe_label,
        entry_jst_hhmm=f"{entry_jst_minute // 60:02d}:{entry_jst_minute % 60:02d}",
        exit_jst_hhmm=f"{exit_jst_minute // 60:02d}:{exit_jst_minute % 60:02d}",
        slippage_price_per_side=slippage_price_per_side,
        stress_cost_multiplier=stress_cost,
        effective_gotobi_trade_count=n_goto,
        skipped_gotobi_day_count=skipped,
        gotobi=gotobi_leg,
        non_gotobi=non_gotobi_leg,
        gotobi_cost_stressed=stressed_leg,
        label_permutation_p90_pf=label_p90,
        weekday_stratified_label_permutation_p90_pf=strat_p90,
        sign_permutation_p90_pf=sign_p90,
        block_pf_rounded=tuple(block_pfs),
        block_trade_counts=tuple(block_counts),
        beats_non_gotobi_control=beats_control,
        beats_label_permutation=beats_label,
        beats_weekday_stratified_label=beats_stratified,
        beats_sign_permutation=beats_sign,
        survives_cost_stress=survives_cost,
        stable_across_blocks=stable,
        robust_verdict_safe_label=verdict,
        real_data_used=not dataset.synthetic_fixture,
    )
