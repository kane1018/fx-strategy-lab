"""No-POST tests for the gotobi / Tokyo-fixing hypothesis module (synthetic)."""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime, timedelta

from app.services import gmo_strategy_gotobi as module
from app.services.gmo_strategy_backtest_dataset import (
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
)
from app.services.gmo_strategy_gotobi import (
    DEFAULT_EXIT_JST_MINUTE,
    GotobiDayFilter,
    effective_gotobi_dates,
    evaluate_gotobi_effect,
    is_jp_bank_business_day,
    run_gotobi_backtest,
)

_BASE = 150.0
_EPOCH_2025 = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)


def _synthetic_year(
    *,
    gotobi_step: float = 0.10,
    months: int = 12,
    spread: float = 0.002,
) -> BacktestDataset:
    """Weekday H1 bars for 2025 (no weekend bars). On effective gotobi JST
    dates the close steps UP by ``gotobi_step`` from 09:00 JST onward, so a
    03:00->~09:55 long books ~+step; non-gotobi days are flat (small cost loss).
    """

    end = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=months * 31)
    gotobi = effective_gotobi_dates(date(2025, 1, 1), end.date())
    candles, spreads, sessions = [], [], []
    hours = int((end - _EPOCH_2025).total_seconds() // 3600)
    for h in range(hours):
        utc = _EPOCH_2025 + timedelta(hours=h)
        jst = utc + timedelta(hours=9)
        if jst.weekday() >= 5:  # no weekend bars (market closed)
            continue
        ts = int(utc.timestamp() * 1000)
        jst_min = jst.hour * 60 + jst.minute
        up = jst.date() in gotobi and jst_min >= 9 * 60
        close = _BASE + (gotobi_step if up else 0.0)
        candles.append(
            BacktestCandleRecord(
                timestamp=ts,
                symbol_safe_label="USD_JPY",
                timeframe_safe_label="H1",
                open_value=close,
                high_value=close + 0.01,
                low_value=close - 0.01,
                close_value=close,
            )
        )
        spreads.append(
            BacktestSpreadRecord(
                timestamp=ts,
                symbol_safe_label="USD_JPY",
                spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL,
                spread_value=spread,
            )
        )
        sessions.append(
            BacktestSessionRecord(
                timestamp=ts,
                session_safe_label=SessionAllowedSafeLabel.SESSION_ALLOWED,
            )
        )
    return BacktestDataset(
        symbol_safe_label="USD_JPY",
        timeframe_safe_label="H1",
        candles=tuple(candles),
        spreads=tuple(spreads),
        sessions=tuple(sessions),
        synthetic_fixture=False,
    )


class TestGotobiCalendar:
    def test_bank_business_day(self) -> None:
        assert is_jp_bank_business_day(date(2025, 5, 2)) is True  # Fri
        assert is_jp_bank_business_day(date(2025, 5, 10)) is False  # Sat
        assert is_jp_bank_business_day(date(2025, 5, 5)) is False  # Children's Day

    def test_effective_dates_shift_to_preceding_business_day(self) -> None:
        may = effective_gotobi_dates(date(2025, 5, 1), date(2025, 5, 31))
        # 5th=Children's holiday->2nd; 10th=Sat->9th; 25th=Sun->23rd.
        assert may == frozenset(
            {
                date(2025, 5, 2),
                date(2025, 5, 9),
                date(2025, 5, 15),
                date(2025, 5, 20),
                date(2025, 5, 23),
                date(2025, 5, 30),
            }
        )

    def test_february_thirty_slot_uses_last_day(self) -> None:
        feb = effective_gotobi_dates(date(2026, 2, 1), date(2026, 2, 28))
        # Feb has no 30th; the month-end slot is the last day (28th, Sat)
        # -> preceding business day 27th (Fri).
        assert date(2026, 2, 27) in feb
        assert all(d.month == 2 for d in feb)

    def test_month_end_uses_31st_when_business_day(self) -> None:
        # July 2025: the 31st is a Thursday (bank business day), so the
        # month-end slot is the 31st, NOT the 30th.
        july = effective_gotobi_dates(date(2025, 7, 1), date(2025, 7, 31))
        assert date(2025, 7, 31) in july
        assert date(2025, 7, 30) not in july


class TestGotobiRunner:
    def test_gotobi_long_is_profitable_on_engineered_drift(self) -> None:
        ds = _synthetic_year()
        result = run_gotobi_backtest(dataset=ds, day_filter=GotobiDayFilter.GOTOBI)
        assert len(result.trades) >= 30
        pnls = [t.synthetic_pnl_value for t in result.trades]
        assert sum(1 for p in pnls if p > 0) / len(pnls) > 0.9
        assert result.real_data_used is True
        assert bool(result) is False

    def test_non_gotobi_control_is_not_profitable(self) -> None:
        ds = _synthetic_year()
        result = run_gotobi_backtest(
            dataset=ds, day_filter=GotobiDayFilter.NON_GOTOBI
        )
        pnls = [t.synthetic_pnl_value for t in result.trades]
        assert all(p <= 0 for p in pnls)  # flat days lose only the spread/slip

    def test_sign_randomization_is_deterministic(self) -> None:
        ds = _synthetic_year()
        a = run_gotobi_backtest(dataset=ds, randomize_side_seed=42)
        b = run_gotobi_backtest(dataset=ds, randomize_side_seed=42)
        assert [t.side_safe_label for t in a.trades] == [
            t.side_safe_label for t in b.trades
        ]

    def test_leg_level_spread_charges_the_crossing_side(self) -> None:
        # entry-bar spread 0.002, exit-bar spread 0.010: a long crosses on
        # entry (0.002), a short crosses on exit (0.010).
        candles, spreads, sessions = [], [], []
        for i, sp in enumerate((0.002, 0.010)):
            candles.append(
                BacktestCandleRecord(
                    timestamp=int(_EPOCH_2025.timestamp() * 1000) + i,
                    symbol_safe_label="USD_JPY", timeframe_safe_label="M5",
                    open_value=_BASE, high_value=_BASE, low_value=_BASE,
                    close_value=_BASE,
                )
            )
            spreads.append(
                BacktestSpreadRecord(
                    timestamp=int(_EPOCH_2025.timestamp() * 1000) + i,
                    symbol_safe_label="USD_JPY",
                    spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL,
                    spread_value=sp,
                )
            )
            sessions.append(
                BacktestSessionRecord(
                    timestamp=int(_EPOCH_2025.timestamp() * 1000) + i,
                    session_safe_label=SessionAllowedSafeLabel.SESSION_ALLOWED,
                )
            )
        ds = BacktestDataset(
            symbol_safe_label="USD_JPY", timeframe_safe_label="M5",
            candles=tuple(candles), spreads=tuple(spreads),
            sessions=tuple(sessions), synthetic_fixture=False,
        )
        dt = module._DayTrade(
            day=date(2025, 1, 6), is_gotobi=True, entry_index=0, exit_index=1
        )
        _, long_cost = module._trade_pnl(
            ds, dt, long=True, spread_included=True,
            spread_cost_multiplier=1.0, slippage_price_per_side=0.0,
        )
        _, short_cost = module._trade_pnl(
            ds, dt, long=False, spread_included=True,
            spread_cost_multiplier=1.0, slippage_price_per_side=0.0,
        )
        assert round(long_cost, 6) == 0.002  # entry-bar spread
        assert round(short_cost, 6) == 0.010  # exit-bar spread

    def test_missing_0300_bar_day_is_skipped_not_fabricated(self) -> None:
        # One Monday gotobi date (2025-06-30) with bars only from 07:00 JST on.
        day_utc = datetime(2025, 6, 29, 21, 0, tzinfo=UTC)  # 06:00 JST Mon 6/30
        candles, spreads, sessions = [], [], []
        for h in range(6):  # 06:00..11:00 JST -- no 03:00 bar
            utc = day_utc + timedelta(hours=h)
            ts = int(utc.timestamp() * 1000)
            candles.append(
                BacktestCandleRecord(
                    timestamp=ts, symbol_safe_label="USD_JPY",
                    timeframe_safe_label="H1", open_value=_BASE,
                    high_value=_BASE + 0.01, low_value=_BASE - 0.01,
                    close_value=_BASE,
                )
            )
            spreads.append(
                BacktestSpreadRecord(
                    timestamp=ts, symbol_safe_label="USD_JPY",
                    spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL,
                    spread_value=0.002,
                )
            )
            sessions.append(
                BacktestSessionRecord(
                    timestamp=ts,
                    session_safe_label=SessionAllowedSafeLabel.SESSION_ALLOWED,
                )
            )
        ds = BacktestDataset(
            symbol_safe_label="USD_JPY", timeframe_safe_label="H1",
            candles=tuple(candles), spreads=tuple(spreads),
            sessions=tuple(sessions), synthetic_fixture=False,
        )
        assert date(2025, 6, 30) in effective_gotobi_dates(
            date(2025, 6, 30), date(2025, 6, 30)
        )
        result = run_gotobi_backtest(dataset=ds, day_filter=GotobiDayFilter.GOTOBI)
        assert len(result.trades) == 0  # no valid 03:00 entry -> no fabricated fill


class TestGotobiEvaluation:
    def test_engineered_effect_is_robust_under_all_controls(self) -> None:
        report = evaluate_gotobi_effect(_synthetic_year(months=20))
        assert report.effective_gotobi_trade_count >= 90
        assert report.gotobi.profit_factor_rounded > report.non_gotobi.profit_factor_rounded
        assert report.beats_non_gotobi_control is True
        assert report.beats_label_permutation is True  # secondary
        assert report.beats_weekday_stratified_label is True  # primary
        assert report.beats_sign_permutation is True
        assert report.survives_cost_stress is True
        assert report.stable_across_blocks is True
        assert len(report.block_pf_rounded) == 3
        assert all(c >= 25 for c in report.block_trade_counts)
        assert report.robust_verdict_safe_label == (
            "RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD"
        )
        assert report.performance_proof_status is False
        assert report.live_ready is False
        assert bool(report) is False

    def test_is_deterministic(self) -> None:
        ds = _synthetic_year(months=8)
        assert evaluate_gotobi_effect(ds) == evaluate_gotobi_effect(ds)

    def test_small_sample_is_withheld_not_endorsed(self) -> None:
        report = evaluate_gotobi_effect(_synthetic_year(months=2))
        assert report.effective_gotobi_trade_count < 90
        assert report.robust_verdict_safe_label == "INSUFFICIENT_GOTOBI_SAMPLE"

    def test_exit_defaults_are_the_tokyo_fix(self) -> None:
        assert DEFAULT_EXIT_JST_MINUTE == 9 * 60 + 55


class TestModuleIsolation:
    def test_no_network_broker_env_or_random_module(self) -> None:
        source = inspect.getsource(module)
        for token in (
            "httpx", "requests", "urllib", "live_order_once",
            "live_verification", "os.environ", "getenv", "/private/v1",
            "import random", "random.random", "random.randint",
            "profitable", "winning strategy",
        ):
            assert token not in source

    def test_results_are_never_a_performance_proof(self) -> None:
        report = evaluate_gotobi_effect(_synthetic_year(months=2))
        assert report.performance_proof_status is False
        assert report.live_ready is False
