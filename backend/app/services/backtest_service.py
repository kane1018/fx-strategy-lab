from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.models import BacktestRun, BacktestTrade
from app.schemas.trading import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    ChartPoint,
    EquityPoint,
    Side,
    TradeResult,
)
from app.services.market_data_service import candles_to_frame, generate_demo_candles, pip_size
from app.strategies import evaluate_strategy


@dataclass
class OpenPosition:
    side: Side
    entry_time: datetime
    entry_price: float
    units: float
    stop_loss: float
    take_profit: float
    entry_reason: str


def _price_pnl(symbol: str, side: Side, entry: float, exit_price: float, units: float) -> float:
    price_delta = exit_price - entry if side == Side.BUY else entry - exit_price
    # P&L is quoted approximately in account currency for an explainable MVP.
    conversion = 1 / exit_price if symbol.endswith("JPY") else 1
    return price_delta * units * conversion


def _entry_price(close: float, side: Side, pip: float, spread: float, slippage: float) -> float:
    friction = pip * (spread / 2 + slippage)
    return close + friction if side == Side.BUY else close - friction


def _exit_price(raw_price: float, side: Side, pip: float, spread: float, slippage: float) -> float:
    friction = pip * (spread / 2 + slippage)
    return raw_price - friction if side == Side.BUY else raw_price + friction


def _position_units(request: BacktestRequest, equity: float, entry: float) -> float:
    execution = request.execution
    if execution.fixed_units:
        requested_units = execution.fixed_units
    else:
        risk_amount = equity * execution.risk_percent / 100
        stop_distance = execution.stop_loss_pips * pip_size(request.symbol)
        requested_units = risk_amount / max(stop_distance, 1e-9)
    max_by_margin = equity * execution.leverage / entry
    return max(0, min(requested_units, max_by_margin))


def _metrics(
    initial: float,
    equity: list[EquityPoint],
    trades: list[TradeResult],
    margin: bool,
) -> BacktestMetrics:
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    final_equity = equity[-1].equity if equity else initial
    peak = initial
    max_drawdown = 0.0
    max_drawdown_percent = 0.0
    for point in equity:
        peak = max(peak, point.equity)
        drawdown = peak - point.equity
        max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_percent = max(max_drawdown_percent, drawdown / peak * 100 if peak else 0)

    consecutive_wins = consecutive_losses = max_wins = max_losses = 0
    for trade in trades:
        if trade.pnl > 0:
            consecutive_wins += 1
            consecutive_losses = 0
        elif trade.pnl < 0:
            consecutive_losses += 1
            consecutive_wins = 0
        max_wins = max(max_wins, consecutive_wins)
        max_losses = max(max_losses, consecutive_losses)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return BacktestMetrics(
        total_pnl=round(final_equity - initial, 2),
        return_percent=round((final_equity / initial - 1) * 100, 3),
        win_rate=round(len(wins) / len(trades) * 100, 2) if trades else 0,
        trade_count=len(trades),
        average_win=round(sum(wins) / len(wins), 2) if wins else 0,
        average_loss=round(sum(losses) / len(losses), 2) if losses else 0,
        profit_factor=round(gross_profit / gross_loss, 3) if gross_loss else None,
        max_drawdown=round(max_drawdown, 2),
        max_drawdown_percent=round(max_drawdown_percent, 3),
        max_consecutive_wins=max_wins,
        max_consecutive_losses=max_losses,
        margin_call_triggered=margin,
    )


def run_backtest(db: Session, request: BacktestRequest) -> BacktestResponse:
    candles = request.candles or generate_demo_candles(
        request.symbol, request.timeframe, request.start, request.end
    )
    frame = candles_to_frame(candles)
    pip = pip_size(request.symbol)
    equity_value = request.execution.initial_capital
    equity_curve: list[EquityPoint] = []
    trades: list[TradeResult] = []
    chart_frame = frame.tail(500)
    chart: list[ChartPoint] = [
        ChartPoint(
            timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            signal=None,
        )
        for _, row in chart_frame.iterrows()
    ]
    chart_index = {point.timestamp: index for index, point in enumerate(chart)}
    position: OpenPosition | None = None
    margin_call_triggered = False

    for index in range(2, len(frame)):
        row = frame.iloc[index]
        timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime()
        open_price = float(row["open"])
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])

        # Signals are calculated only from completed candles. Execution occurs at the
        # following candle's open, avoiding same-close fills and look-ahead bias.
        signal = evaluate_strategy(frame.iloc[:index], request.strategy)
        if position and signal.action in {"buy", "sell"} and signal.action != position.side.value:
            exit_price = _exit_price(
                open_price,
                position.side,
                pip,
                request.execution.spread_pips,
                request.execution.slippage_pips,
            )
            pnl = (
                _price_pnl(
                    request.symbol,
                    position.side,
                    position.entry_price,
                    exit_price,
                    position.units,
                )
                - request.execution.commission_per_trade
            )
            equity_value += pnl
            trades.append(
                TradeResult(
                    symbol=request.symbol,
                    side=position.side,
                    entry_time=position.entry_time,
                    exit_time=timestamp,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    units=position.units,
                    pnl=round(pnl, 2),
                    entry_reason=position.entry_reason,
                    exit_reason=f"反対シグナル: {signal.reason}",
                )
            )
            if timestamp in chart_index:
                chart[chart_index[timestamp]].signal = "exit"
            position = None

        if not position and signal.action in {"buy", "sell"}:
            side = Side(signal.action)
            entry = _entry_price(
                open_price,
                side,
                pip,
                request.execution.spread_pips,
                request.execution.slippage_pips,
            )
            units = _position_units(request, equity_value, entry)
            if units > 0:
                stop_distance = request.execution.stop_loss_pips * pip
                take_distance = request.execution.take_profit_pips * pip
                stop = entry - stop_distance if side == Side.BUY else entry + stop_distance
                take = entry + take_distance if side == Side.BUY else entry - take_distance
                max_risk = abs(_price_pnl(request.symbol, side, entry, stop, units))
                if max_risk <= equity_value * request.execution.max_loss_percent / 100:
                    position = OpenPosition(
                        side=side,
                        entry_time=timestamp,
                        entry_price=entry,
                        units=units,
                        stop_loss=stop,
                        take_profit=take,
                        entry_reason=signal.reason,
                    )
                    if timestamp in chart_index:
                        chart[chart_index[timestamp]].signal = side.value

        if position:
            exit_raw: float | None = None
            exit_reason = ""
            if position.side == Side.BUY:
                if low <= position.stop_loss:
                    exit_raw, exit_reason = position.stop_loss, "損切り到達"
                elif high >= position.take_profit:
                    exit_raw, exit_reason = position.take_profit, "利確到達"
            else:
                if high >= position.stop_loss:
                    exit_raw, exit_reason = position.stop_loss, "損切り到達"
                elif low <= position.take_profit:
                    exit_raw, exit_reason = position.take_profit, "利確到達"

            if exit_raw is not None:
                exit_price = _exit_price(
                    exit_raw,
                    position.side,
                    pip,
                    request.execution.spread_pips,
                    request.execution.slippage_pips,
                )
                pnl = (
                    _price_pnl(
                        request.symbol,
                        position.side,
                        position.entry_price,
                        exit_price,
                        position.units,
                    )
                    - request.execution.commission_per_trade
                )
                equity_value += pnl
                trades.append(
                    TradeResult(
                        symbol=request.symbol,
                        side=position.side,
                        entry_time=position.entry_time,
                        exit_time=timestamp,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        units=position.units,
                        pnl=round(pnl, 2),
                        entry_reason=position.entry_reason,
                        exit_reason=exit_reason,
                    )
                )
                if timestamp in chart_index:
                    chart[chart_index[timestamp]].signal = "exit"
                position = None

        unrealized = 0.0
        if position:
            unrealized = _price_pnl(
                request.symbol, position.side, position.entry_price, close, position.units
            )
        current_equity = equity_value + unrealized
        equity_curve.append(EquityPoint(timestamp=timestamp, equity=round(current_equity, 2)))
        if current_equity <= request.execution.initial_capital / request.execution.leverage:
            margin_call_triggered = True
            break

    if position:
        last = frame.iloc[-1]
        timestamp = pd.Timestamp(last["timestamp"]).to_pydatetime()
        exit_price = _exit_price(
            float(last["close"]),
            position.side,
            pip,
            request.execution.spread_pips,
            request.execution.slippage_pips,
        )
        pnl = (
            _price_pnl(
                request.symbol, position.side, position.entry_price, exit_price, position.units
            )
            - request.execution.commission_per_trade
        )
        equity_value += pnl
        trades.append(
            TradeResult(
                symbol=request.symbol,
                side=position.side,
                entry_time=position.entry_time,
                exit_time=timestamp,
                entry_price=position.entry_price,
                exit_price=exit_price,
                units=position.units,
                pnl=round(pnl, 2),
                entry_reason=position.entry_reason,
                exit_reason="検証期間終了",
            )
        )
        equity_curve.append(EquityPoint(timestamp=timestamp, equity=round(equity_value, 2)))

    metrics = _metrics(
        request.execution.initial_capital, equity_curve, trades, margin_call_triggered
    )
    run = BacktestRun(
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_type=request.strategy.strategy_type.value,
        request_json=request.model_dump(mode="json", exclude={"candles"}),
        metrics_json=metrics.model_dump(mode="json"),
    )
    db.add(run)
    db.flush()
    for trade in trades:
        db.add(
            BacktestTrade(
                run_id=run.id,
                symbol=trade.symbol,
                side=trade.side.value,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                units=trade.units,
                pnl=trade.pnl,
                entry_reason=trade.entry_reason,
                exit_reason=trade.exit_reason,
            )
        )
    db.commit()
    warnings = [
        "デモ生成価格による検証です。実データ接続後に再検証してください。",
        "同一足で損切りと利確の両方に到達した場合は、保守的に損切りを優先します。",
        "バックテスト結果は将来の利益を保証しません。",
    ]
    return BacktestResponse(
        run_id=run.id,
        metrics=metrics,
        equity_curve=equity_curve[-1000:],
        chart=chart,
        trades=trades,
        warnings=warnings,
    )
