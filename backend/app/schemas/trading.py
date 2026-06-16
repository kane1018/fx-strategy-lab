from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class StrategyType(StrEnum):
    MOVING_AVERAGE_CROSS = "moving_average_cross"
    RSI_REVERSAL = "rsi_reversal"
    BREAKOUT = "breakout"
    BOLLINGER_REVERSION = "bollinger_reversion"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


class StrategyConfig(BaseModel):
    strategy_type: StrategyType = StrategyType.MOVING_AVERAGE_CROSS
    short_period: int = Field(default=10, ge=2, le=200)
    long_period: int = Field(default=30, ge=3, le=500)
    rsi_period: int = Field(default=14, ge=2, le=100)
    oversold: float = Field(default=30, ge=1, le=49)
    overbought: float = Field(default=70, ge=51, le=99)
    breakout_period: int = Field(default=20, ge=2, le=200)
    bollinger_period: int = Field(default=20, ge=2, le=200)
    bollinger_sigma: float = Field(default=2.0, gt=0, le=5)

    @model_validator(mode="after")
    def validate_periods(self) -> "StrategyConfig":
        if self.short_period >= self.long_period:
            raise ValueError("short_period must be less than long_period")
        if self.oversold >= self.overbought:
            raise ValueError("oversold must be less than overbought")
        return self


class ExecutionConfig(BaseModel):
    initial_capital: float = Field(default=1_000_000, gt=0)
    fixed_units: float | None = Field(default=1000, gt=0)
    risk_percent: float = Field(default=1, gt=0, le=5)
    stop_loss_pips: float = Field(default=30, gt=0)
    take_profit_pips: float = Field(default=60, gt=0)
    max_loss_percent: float = Field(default=2, gt=0, le=10)
    spread_pips: float = Field(default=1.2, ge=0, le=20)
    commission_per_trade: float = Field(default=0, ge=0)
    slippage_pips: float = Field(default=0.2, ge=0, le=20)
    leverage: float = Field(default=25, ge=1, le=100)


class BacktestRequest(BaseModel):
    symbol: str = "USD_JPY"
    timeframe: str = "H1"
    start: datetime
    end: datetime
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    candles: list[Candle] | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "BacktestRequest":
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class TradeResult(BaseModel):
    symbol: str
    side: Side
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    units: float
    pnl: float
    entry_reason: str
    exit_reason: str


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float


class ChartPoint(Candle):
    signal: Literal["buy", "sell", "exit"] | None = None


class BacktestMetrics(BaseModel):
    total_pnl: float
    return_percent: float
    win_rate: float
    trade_count: int
    average_win: float
    average_loss: float
    profit_factor: float | None
    max_drawdown: float
    max_drawdown_percent: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    margin_call_triggered: bool


class BacktestResponse(BaseModel):
    run_id: int
    metrics: BacktestMetrics
    equity_curve: list[EquityPoint]
    chart: list[ChartPoint]
    trades: list[TradeResult]
    warnings: list[str]


class PaperSessionRequest(BaseModel):
    symbol: str = "USD_JPY"
    timeframe: str = "M5"
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


class PaperTickRequest(BaseModel):
    price: float | None = Field(default=None, gt=0)


class SignalMonitorRequest(BaseModel):
    symbol: str = "USD_JPY"
    timeframe: str = "M5"
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


class RiskConfig(BaseModel):
    max_daily_loss: float = Field(default=100, gt=0)
    max_loss_per_trade: float = Field(default=25, gt=0)
    max_positions: int = Field(default=1, ge=1, le=10)
    max_units: float = Field(default=1000, gt=0)
    max_consecutive_losses: int = Field(default=3, ge=1, le=20)
    max_spread_pips: float = Field(default=3, gt=0)
    avoid_news_minutes: int = Field(default=30, ge=0, le=180)


class OrderRequest(BaseModel):
    client_order_id: str = Field(min_length=8, max_length=100)
    mode: Literal["demo", "practice", "live"] = "demo"
    symbol: str = "USD_JPY"
    side: Side
    units: float = Field(gt=0)
    current_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    spread_pips: float = Field(default=1, ge=0)
    estimated_loss: float = Field(gt=0)
    admin_live_enabled: bool = False
    confirmation_text: str = ""
    manual_stop_available: bool = True
    logs_enabled: bool = True
    api_connection_ok: bool = False
    high_impact_news_active: bool = False


class OrderSubmission(BaseModel):
    request: OrderRequest
    risk: RiskConfig = Field(default_factory=RiskConfig)


class CloseOrderRequest(BaseModel):
    exit_price: float = Field(gt=0)


class BotStartRequest(BaseModel):
    mode: Literal["demo", "practice", "live"] = "demo"


class AutoTradeConfig(BaseModel):
    symbol: str = "USD_JPY"
    timeframe: str = "M5"
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    interval_seconds: int = Field(default=30, ge=5, le=3600)


class ApiMessage(BaseModel):
    message: str
    data: dict[str, Any] | None = None
