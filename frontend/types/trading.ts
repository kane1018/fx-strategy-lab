export type StrategyType =
  | "moving_average_cross"
  | "rsi_reversal"
  | "breakout";

export interface StrategyConfig {
  strategy_type: StrategyType;
  short_period: number;
  long_period: number;
  rsi_period: number;
  oversold: number;
  overbought: number;
  breakout_period: number;
}

export interface ExecutionConfig {
  initial_capital: number;
  fixed_units: number;
  risk_percent: number;
  stop_loss_pips: number;
  take_profit_pips: number;
  max_loss_percent: number;
  spread_pips: number;
  commission_per_trade: number;
  slippage_pips: number;
  leverage: number;
}

export interface TradeResult {
  symbol: string;
  side: "buy" | "sell";
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  units: number;
  pnl: number;
  entry_reason: string;
  exit_reason: string;
}

export interface BacktestResponse {
  run_id: number;
  metrics: {
    total_pnl: number;
    return_percent: number;
    win_rate: number;
    trade_count: number;
    average_win: number;
    average_loss: number;
    profit_factor: number | null;
    max_drawdown: number;
    max_drawdown_percent: number;
    max_consecutive_wins: number;
    max_consecutive_losses: number;
    margin_call_triggered: boolean;
  };
  equity_curve: Array<{ timestamp: string; equity: number }>;
  chart: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    signal: "buy" | "sell" | "exit" | null;
  }>;
  trades: TradeResult[];
  warnings: string[];
}

export interface PaperSnapshot {
  id: number;
  status: string;
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  today_trade_count: number;
  today_max_loss: number;
  current_price?: number;
  last_signal?: { action: string; reason: string };
  error_message?: string;
  open_positions: PaperTrade[];
  trades: PaperTrade[];
}

export interface PaperTrade {
  id: number;
  side: string;
  status: string;
  units: number;
  entry_price: number;
  current_price: number;
  stop_loss: number;
  take_profit: number;
  unrealized_pnl: number;
  realized_pnl: number | null;
  entry_reason: string;
  exit_reason: string | null;
}

export interface SignalRecord {
  id: number;
  symbol: string;
  timeframe: string;
  strategy_name: string;
  side: string;
  price: number;
  stop_loss: number;
  take_profit: number;
  reason: string;
  risk_percent: number;
  notice: string;
  created_at: string;
}

export interface BotStatus {
  mode: string;
  status: string;
  manual_stop_active: boolean;
  stop_reason: string | null;
}

export interface AutomationStatus {
  enabled: boolean;
  environment: string;
  last_signal: {
    action?: string;
    reason?: string;
    price?: number;
    created_at?: string;
  };
  last_risk: {
    allowed?: boolean;
    reasons?: string[];
    units?: number;
    estimated_loss?: number;
  };
  last_order_id: string | null;
  last_fill: {
    accepted?: boolean;
    status?: string;
    fill_transaction_id?: string;
    filled_price?: number;
    reasons?: string[];
  };
  current_positions: Array<{
    symbol: string;
    side: string;
    units: number;
    average_price: number;
    unrealized_pnl: number;
  }>;
  last_price_at: string | null;
  last_balance_at: string | null;
  last_cycle_at: string | null;
  consecutive_failures: number;
  bot: BotStatus;
}

export interface OrderRecord {
  id: number;
  client_order_id: string;
  broker_order_id: string | null;
  mode: string;
  symbol: string;
  side: string;
  units: number;
  status: string;
  reason: string;
  filled_price: number | null;
  realized_pnl: number | null;
  created_at: string;
}
