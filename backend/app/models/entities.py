from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class UserSettings(Base):
    __tablename__ = "user_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    default_symbol: Mapped[str] = mapped_column(String(20), default="USD_JPY")
    default_timeframe: Mapped[str] = mapped_column(String(10), default="H1")
    live_trading_ui_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    live_confirmation_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logs_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    strategy_type: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    strategy_type: Mapped[str] = mapped_column(String(40))
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(10))
    entry_time: Mapped[datetime] = mapped_column(DateTime)
    exit_time: Mapped[datetime] = mapped_column(DateTime)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    units: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    entry_reason: Mapped[str] = mapped_column(Text)
    exit_reason: Mapped[str] = mapped_column(Text)


class PaperTradeSession(Base):
    __tablename__ = "paper_trade_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="stopped")
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    strategy_type: Mapped[str] = mapped_column(String(40))
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    initial_balance: Mapped[float] = mapped_column(Float)
    balance: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("paper_trade_sessions.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open")
    units: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_reason: Mapped[str] = mapped_column(Text)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    strategy_name: Mapped[str] = mapped_column(String(80))
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    risk_percent: Mapped[float] = mapped_column(Float)
    notice: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BotStatus(Base):
    __tablename__ = "bot_status"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="demo")
    status: Mapped[str] = mapped_column(String(30), default="stopped")
    manual_stop_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BotLog(Base):
    __tablename__ = "bot_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AutoTradeState(Base):
    __tablename__ = "auto_trade_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    environment: Mapped[str] = mapped_column(String(20), default="practice")
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_signal_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_risk_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_fill_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    current_positions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    last_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_price_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_balance_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_cycle_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class RiskSettings(Base):
    __tablename__ = "risk_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    max_daily_loss: Mapped[float] = mapped_column(Float, default=100)
    max_loss_per_trade: Mapped[float] = mapped_column(Float, default=25)
    max_positions: Mapped[int] = mapped_column(Integer, default=1)
    max_units: Mapped[float] = mapped_column(Float, default=1000)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=3)
    max_spread_pips: Mapped[float] = mapped_column(Float, default=3)
    avoid_news_minutes: Mapped[int] = mapped_column(Integer, default=30)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    broker_name: Mapped[str] = mapped_column(String(40), default="demo")
    environment: Mapped[str] = mapped_column(String(20), default="demo")
    account_ref: Mapped[str] = mapped_column(String(100), default="local-demo")
    api_connection_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    last_connection_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class OrderLog(Base):
    __tablename__ = "order_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(10))
    units: Mapped[float] = mapped_column(Float)
    requested_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    risk_check_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(20), default="error")
    message: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
