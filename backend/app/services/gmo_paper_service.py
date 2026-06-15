"""Replay GMO Public klines through the existing strategy as PAPER trades.

No real orders, no Private API, no broker order call. Given a list of candles
(e.g. fetched read-only from GMO Public API), this opens/closes VIRTUAL positions
and persists them as PaperTrade rows under a PaperTradeSession so that
performance_service.paper_performance can aggregate them. Completed (closed)
trades count toward strategy stats; a still-open final position is recorded
separately as an open paper position (unrealized).

This module is pure simulation over provided candles: it never performs network
or broker I/O itself.
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import PaperTrade, PaperTradeSession
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig, StrategyType
from app.services.market_data_service import candles_to_frame, pip_size
from app.services.paper_trade_service import _pnl
from app.strategies import StrategySignal, evaluate_strategy
from app.strategies.rsi_reversal import calculate_rsi


def _close_trade(
    session: PaperTradeSession,
    symbol: str,
    execution: ExecutionConfig,
    position: dict[str, Any],
    exit_price: float,
    exit_reason: str,
    closed_at: datetime,
) -> PaperTrade:
    pnl = (
        _pnl(symbol, position["side"], position["entry_price"], exit_price, position["units"])
        - execution.commission_per_trade
    )
    session.balance += pnl
    session.realized_pnl += pnl
    return PaperTrade(
        session_id=session.id,
        symbol=symbol,
        side=position["side"],
        status="closed",
        units=position["units"],
        entry_price=position["entry_price"],
        current_price=exit_price,
        exit_price=exit_price,
        stop_loss=position["stop_loss"],
        take_profit=position["take_profit"],
        unrealized_pnl=0,
        realized_pnl=round(pnl, 4),
        entry_reason=position["entry_reason"],
        exit_reason=exit_reason,
        opened_at=position["opened_at"],
        closed_at=closed_at,
    )


# Paper-trade-only exit policies (analysis A/B; never wired into a live strategy).
EXIT_POLICIES = (
    "baseline",  # current behavior: opposite signal closes the position
    "no_opposite_signal_exit",  # ignore opposite-signal exits; only SL/TP (+ end-of-data)
    "min_hold_30m_before_opposite_exit",  # allow opposite-signal exit only after 30 min
    "time_stop_30m",  # baseline exits + force-exit after 30 min held
    "time_stop_60m",  # baseline exits + force-exit after 60 min held
)


def _opposite_exit_allowed(exit_policy: str, opened_at: datetime, now: datetime) -> bool:
    if exit_policy == "no_opposite_signal_exit":
        return False
    if exit_policy == "min_hold_30m_before_opposite_exit":
        return (now - opened_at).total_seconds() >= 30 * 60
    return True  # baseline / time_stop_* keep the baseline opposite-signal behavior


def _time_stop_minutes(exit_policy: str) -> int | None:
    return {"time_stop_30m": 30, "time_stop_60m": 60}.get(exit_policy)


def adx_series(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Wilder ADX over the frame's OHLC (period fixed at 14; not optimized)."""
    high, low, close = frame["high"], frame["low"], frame["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index
    )
    atr = true_range.ewm(alpha=1 / period, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.fillna(0).ewm(alpha=1 / period, adjust=False).mean().to_numpy()


def _precompute_rsi_signals(frame: pd.DataFrame, config: StrategyConfig) -> list[StrategySignal]:
    """Exact per-bar rsi_reversal signals, vectorized (O(n)).

    EWM(adjust=False) is causal, so the full-series RSI at row j equals the RSI
    that evaluate_strategy(frame.iloc[:j+1]) would compute. So signal-at-prefix
    [:i] (latest row i-1) compares rsi[i-2] vs rsi[i-1] — identical to the per-bar
    path, just without recomputing on every bar.
    """
    rsi = calculate_rsi(frame["close"], config.rsi_period).to_numpy()
    oversold, overbought = config.oversold, config.overbought
    out: list[StrategySignal] = [StrategySignal("hold", "warmup")] * len(frame)
    for i in range(config.rsi_period + 2, len(frame)):
        prev, cur = float(rsi[i - 2]), float(rsi[i - 1])
        if prev > oversold and cur <= oversold:
            out[i] = StrategySignal("buy", f"RSI({config.rsi_period})={cur:.1f}<= {oversold}")
        elif prev < overbought and cur >= overbought:
            out[i] = StrategySignal("sell", f"RSI({config.rsi_period})={cur:.1f}>= {overbought}")
        else:
            out[i] = StrategySignal("hold", f"RSI({config.rsi_period})={cur:.1f}")
    return out


def replay_paper_trades(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    strategy: StrategyConfig,
    execution: ExecutionConfig,
    source: str = "gmo_public_kline",
    exit_policy: str = "baseline",
    force_close_at_end: bool = False,
    fast_signals: bool = False,
    entry_adx_max: float | None = None,
) -> dict[str, Any]:
    if len(candles) < 3:
        raise ValueError("リプレイに必要な足が不足しています（3本以上必要）")
    if exit_policy not in EXIT_POLICIES:
        raise ValueError(f"未対応のexit_policyです: {exit_policy}")
    frame = candles_to_frame(candles)
    pip = pip_size(symbol)
    friction = pip * (execution.spread_pips / 2 + execution.slippage_pips)
    time_stop_min = _time_stop_minutes(exit_policy)
    # Exact vectorized signals (RSI only) keep long continuous replays O(n).
    precomputed = (
        _precompute_rsi_signals(frame, strategy)
        if fast_signals and strategy.strategy_type == StrategyType.RSI_REVERSAL
        else None
    )
    # Regime filter (entry-only): block NEW entries when ADX >= entry_adx_max.
    adx = adx_series(frame) if entry_adx_max is not None else None

    session = PaperTradeSession(
        status="running",
        symbol=symbol,
        timeframe=timeframe,
        strategy_type=strategy.strategy_type.value,
        config_json={
            "source": source,
            "bars": len(candles),
            "exit_policy": exit_policy,
            "strategy": strategy.model_dump(mode="json"),
            "execution": execution.model_dump(mode="json"),
        },
        initial_balance=execution.initial_capital,
        balance=execution.initial_capital,
    )
    db.add(session)
    db.flush()

    position: dict[str, Any] | None = None
    completed = 0
    skipped_entries = 0
    signal_counts = {"buy": 0, "sell": 0, "hold": 0}

    for index in range(2, len(frame)):
        row = frame.iloc[index]
        timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime()
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close_price = float(row["close"])
        signal = (
            precomputed[index]
            if precomputed is not None
            else evaluate_strategy(frame.iloc[:index], strategy)
        )
        signal_counts[signal.action] = signal_counts.get(signal.action, 0) + 1

        # Close on an opposite signal at the next bar's open (no look-ahead),
        # subject to the exit policy under test.
        if (
            position
            and signal.action in {"buy", "sell"}
            and signal.action != position["side"]
            and _opposite_exit_allowed(exit_policy, position["opened_at"], timestamp)
        ):
            exit_price = (
                open_price - friction if position["side"] == "buy" else open_price + friction
            )
            db.add(
                _close_trade(
                    session, symbol, execution, position, exit_price,
                    f"反対シグナル: {signal.reason}", timestamp,
                )
            )
            completed += 1
            position = None

        # Open a virtual position at the bar open if flat and signalled.
        # Gate on the ADX of the last COMPLETED bar (index-1) to avoid look-ahead,
        # matching the signal's information set.
        adx_blocks_entry = (
            adx is not None
            and not np.isnan(adx[index - 1])
            and adx[index - 1] >= entry_adx_max
        )
        if not position and signal.action in {"buy", "sell"} and adx_blocks_entry:
            skipped_entries += 1  # regime filter: strong trend -> skip new entry
        elif not position and signal.action in {"buy", "sell"}:
            side = signal.action
            entry = open_price + friction if side == "buy" else open_price - friction
            units = min(execution.fixed_units or 1000, session.balance * execution.leverage / entry)
            stop_distance = execution.stop_loss_pips * pip
            take_distance = execution.take_profit_pips * pip
            stop = entry - stop_distance if side == "buy" else entry + stop_distance
            take = entry + take_distance if side == "buy" else entry - take_distance
            max_risk = abs(_pnl(symbol, side, entry, stop, units))
            if units > 0 and max_risk <= session.balance * execution.max_loss_percent / 100:
                position = {
                    "side": side,
                    "entry_price": entry,
                    "units": units,
                    "stop_loss": stop,
                    "take_profit": take,
                    "entry_reason": signal.reason,
                    "opened_at": timestamp,
                }

        # Intrabar SL/TP via high/low; stop is checked first (conservative).
        if position:
            exit_raw: float | None = None
            reason = ""
            if position["side"] == "buy":
                if low <= position["stop_loss"]:
                    exit_raw, reason = position["stop_loss"], "損切り到達"
                elif high >= position["take_profit"]:
                    exit_raw, reason = position["take_profit"], "利確到達"
            else:
                if high >= position["stop_loss"]:
                    exit_raw, reason = position["stop_loss"], "損切り到達"
                elif low <= position["take_profit"]:
                    exit_raw, reason = position["take_profit"], "利確到達"
            if exit_raw is not None:
                exit_price = (
                    exit_raw - friction if position["side"] == "buy" else exit_raw + friction
                )
                db.add(
                    _close_trade(
                        session, symbol, execution, position, exit_price, reason, timestamp
                    )
                )
                completed += 1
                position = None

        # Time stop: exit at this bar's close once max hold elapsed (SL/TP take priority).
        if position and time_stop_min is not None:
            held = (timestamp - position["opened_at"]).total_seconds() / 60
            if held >= time_stop_min:
                exit_price = (
                    close_price - friction if position["side"] == "buy" else close_price + friction
                )
                db.add(
                    _close_trade(
                        session, symbol, execution, position, exit_price,
                        f"時間ストップ{time_stop_min}分", timestamp,
                    )
                )
                completed += 1
                position = None

    open_position_count = 0
    if position:
        last_close = float(frame.iloc[-1]["close"])
        last_ts = pd.Timestamp(frame.iloc[-1]["timestamp"]).to_pydatetime()
        if force_close_at_end:
            # Close the final position at the last close so it counts as completed
            # (used for fair exit-policy A/B; reason is identifiable for distortion checks).
            exit_price = (
                last_close - friction if position["side"] == "buy" else last_close + friction
            )
            db.add(
                _close_trade(
                    session, symbol, execution, position, exit_price,
                    "データ終了強制クローズ", last_ts,
                )
            )
            completed += 1
        else:
            # Default: leave the final position OPEN as an unrealized paper position.
            unrealized = _pnl(
                symbol, position["side"], position["entry_price"], last_close, position["units"]
            )
            db.add(
                PaperTrade(
                    session_id=session.id,
                    symbol=symbol,
                    side=position["side"],
                    status="open",
                    units=position["units"],
                    entry_price=position["entry_price"],
                    current_price=last_close,
                    stop_loss=position["stop_loss"],
                    take_profit=position["take_profit"],
                    unrealized_pnl=round(unrealized, 4),
                    entry_reason=position["entry_reason"],
                    opened_at=position["opened_at"],
                )
            )
            open_position_count = 1

    session.status = "stopped"
    session.stopped_at = datetime.utcnow()
    db.commit()
    return {
        "session_id": session.id,
        "bars": len(candles),
        "completed_trades": completed,
        "skipped_entries": skipped_entries,
        "open_position_count": open_position_count,
        "signal_counts": signal_counts,
    }
