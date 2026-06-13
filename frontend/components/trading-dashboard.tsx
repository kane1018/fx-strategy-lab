"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api } from "@/lib/api";
import { validateStrategy } from "@/lib/validation";
import type {
  BacktestResponse,
  AutomationStatus,
  BotStatus,
  ExecutionConfig,
  OrderRecord,
  PaperSnapshot,
  SignalRecord,
  StrategyConfig,
  StrategyType
} from "@/types/trading";
import { MetricCard } from "./metric-card";
import { StatusPill } from "./status-pill";

const symbols = ["USD_JPY", "EUR_USD", "GBP_JPY", "AUD_JPY"];
const timeframes = ["M1", "M5", "M15", "H1", "H4", "D"];
const strategyNames: Record<StrategyType, string> = {
  moving_average_cross: "移動平均クロス",
  rsi_reversal: "RSI逆張り",
  breakout: "ブレイクアウト"
};

const defaultStrategy: StrategyConfig = {
  strategy_type: "moving_average_cross",
  short_period: 10,
  long_period: 30,
  rsi_period: 14,
  oversold: 30,
  overbought: 70,
  breakout_period: 20
};

const defaultExecution: ExecutionConfig = {
  initial_capital: 1_000_000,
  fixed_units: 1000,
  risk_percent: 1,
  stop_loss_pips: 30,
  take_profit_pips: 60,
  max_loss_percent: 2,
  spread_pips: 1.2,
  commission_per_trade: 0,
  slippage_pips: 0.2,
  leverage: 25
};

function isoDate(daysAgo: number) {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

function money(value: number) {
  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0
  }).format(value);
}

export function TradingDashboard() {
  const [activePhase, setActivePhase] = useState(1);
  const [symbol, setSymbol] = useState("USD_JPY");
  const [timeframe, setTimeframe] = useState("H1");
  const [start, setStart] = useState(isoDate(180));
  const [end, setEnd] = useState(isoDate(0));
  const [strategy, setStrategy] = useState(defaultStrategy);
  const [execution, setExecution] = useState(defaultExecution);
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [paper, setPaper] = useState<PaperSnapshot | null>(null);
  const [monitorId, setMonitorId] = useState<string | null>(null);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [orderResult, setOrderResult] = useState<Record<string, unknown> | null>(
    null
  );
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [automation, setAutomation] = useState<AutomationStatus | null>(null);
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [brokerOk, setBrokerOk] = useState(false);
  const [practiceOk, setPracticeOk] = useState(false);
  const [liveUiEnabled, setLiveUiEnabled] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const sharedRequest = useMemo(
    () => ({ symbol, timeframe, strategy, execution }),
    [symbol, timeframe, strategy, execution]
  );

  useEffect(() => {
    api<AutomationStatus>("/api/automation/status")
      .then((status) => {
        setAutomation(status);
        setBotStatus(status.bot);
      })
      .catch(() => {
        // The main error banner is reserved for explicit user actions.
      });
  }, []);

  useEffect(() => {
    if (!automation?.enabled) return;
    const timer = window.setInterval(() => {
      api<AutomationStatus>("/api/automation/status")
        .then((status) => {
          setAutomation(status);
          setBotStatus(status.bot);
        })
        .catch((caught: unknown) => {
          setError(caught instanceof Error ? caught.message : "状態取得に失敗しました");
        });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [automation?.enabled]);

  async function act(task: () => Promise<void>) {
    setLoading(true);
    setError("");
    try {
      await task();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "処理に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  const runBacktest = () =>
    act(async () => {
      const validationError = validateStrategy(strategy);
      if (validationError) {
        throw new Error(validationError);
      }
      const result = await api<BacktestResponse>("/api/backtests", {
        method: "POST",
        body: JSON.stringify({
          ...sharedRequest,
          start: `${start}T00:00:00`,
          end: `${end}T23:59:59`
        })
      });
      setBacktest(result);
    });

  const startPaper = () =>
    act(async () => {
      const result = await api<PaperSnapshot>("/api/paper/sessions", {
        method: "POST",
        body: JSON.stringify(sharedRequest)
      });
      setPaper(result);
    });

  const tickPaper = () =>
    paper &&
    act(async () => {
      setPaper(
        await api<PaperSnapshot>(`/api/paper/sessions/${paper.id}/tick`, {
          method: "POST",
          body: JSON.stringify({})
        })
      );
    });

  const stopPaper = () =>
    paper &&
    act(async () => {
      setPaper(
        await api<PaperSnapshot>(`/api/paper/sessions/${paper.id}/stop`, {
          method: "POST",
          body: "{}"
        })
      );
    });

  const toggleMonitor = () =>
    act(async () => {
      if (monitorId) {
        await api(`/api/signals/monitors/${monitorId}/stop`, {
          method: "POST",
          body: "{}"
        });
        setMonitorId(null);
      } else {
        const result = await api<{ monitor_id: string }>(
          "/api/signals/monitors",
          { method: "POST", body: JSON.stringify(sharedRequest) }
        );
        setMonitorId(result.monitor_id);
      }
    });

  const checkSignal = () =>
    monitorId &&
    act(async () => {
      await api(`/api/signals/monitors/${monitorId}/evaluate`, {
        method: "POST",
        body: "{}"
      });
      setSignals(await api<SignalRecord[]>("/api/signals"));
    });

  const testBroker = () =>
    act(async () => {
      const result = await api<{ ok: boolean }>("/api/broker/connection-test", {
        method: "POST",
        body: "{}"
      });
      setBrokerOk(result.ok);
      setBotStatus(await api<BotStatus>("/api/bot/status"));
      setOrders(await api<OrderRecord[]>("/api/orders"));
    });

  const testPracticeBroker = () =>
    act(async () => {
      const result = await api<{ ok: boolean; message: string }>(
        "/api/broker/connection-test?mode=practice",
        { method: "POST", body: "{}" }
      );
      setPracticeOk(result.ok);
      if (!result.ok) throw new Error(result.message);
    });

  const startPracticeAutomation = () =>
    act(async () => {
      const status = await api<AutomationStatus>("/api/automation/start", {
        method: "POST",
        body: JSON.stringify({
          ...sharedRequest,
          risk: {
            max_daily_loss: 100,
            max_loss_per_trade: 25,
            max_positions: 1,
            max_units: 1000,
            max_consecutive_losses: 3,
            max_spread_pips: 3,
            avoid_news_minutes: 30
          },
          interval_seconds: 30
        })
      });
      setAutomation(status);
      setBotStatus(status.bot);
      setPracticeOk(true);
    });

  const runPracticeCycle = () =>
    act(async () => {
      const status = await api<AutomationStatus>("/api/automation/cycle", {
        method: "POST",
        body: "{}"
      });
      setAutomation(status);
      setBotStatus(status.bot);
      setOrders(await api<OrderRecord[]>("/api/orders"));
    });

  const stopPracticeAutomation = () =>
    act(async () => {
      const status = await api<AutomationStatus>("/api/automation/stop", {
        method: "POST",
        body: "{}"
      });
      setAutomation(status);
      setBotStatus(status.bot);
    });

  const startDemoBot = () =>
    act(async () => {
      setBotStatus(
        await api<BotStatus>("/api/bot/start", {
          method: "POST",
          body: JSON.stringify({ mode: "demo" })
        })
      );
    });

  const stopDemoBot = () =>
    act(async () => {
      setBotStatus(
        await api<BotStatus>("/api/bot/stop", {
          method: "POST",
          body: "{}"
        })
      );
    });

  const submitDemoOrder = (mode: "demo" | "live") =>
    act(async () => {
      const price = paper?.current_price ?? 157;
      const pip = symbol.endsWith("JPY") ? 0.01 : 0.0001;
      const result = await api<Record<string, unknown>>("/api/orders", {
        method: "POST",
        body: JSON.stringify({
          request: {
            client_order_id: `WEB-${Date.now()}`,
            mode,
            symbol,
            side: "buy",
            units: execution.fixed_units,
            current_price: price,
            stop_loss: price - execution.stop_loss_pips * pip,
            take_profit: price + execution.take_profit_pips * pip,
            spread_pips: execution.spread_pips,
            estimated_loss: 10,
            admin_live_enabled: liveUiEnabled,
            confirmation_text: confirmation,
            manual_stop_available: true,
            logs_enabled: true,
            api_connection_ok: brokerOk,
            high_impact_news_active: false
          },
          risk: {
            max_daily_loss: 100,
            max_loss_per_trade: 25,
            max_positions: 1,
            max_units: 1000,
            max_consecutive_losses: 3,
            max_spread_pips: 3,
            avoid_news_minutes: 30
          }
        })
      });
      setOrderResult(result);
      setBotStatus(await api<BotStatus>("/api/bot/status"));
      setOrders(await api<OrderRecord[]>("/api/orders"));
    });

  const closeDemoPosition = (order: OrderRecord) =>
    act(async () => {
      const exitPrice = paper?.current_price ?? order.filled_price ?? 157;
      setOrderResult(
        await api<Record<string, unknown>>(`/api/orders/${order.id}/close`, {
          method: "POST",
          body: JSON.stringify({ exit_price: exitPrice })
        })
      );
      setOrders(await api<OrderRecord[]>("/api/orders"));
    });

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">PERSONAL STRATEGY WORKSPACE</p>
          <h1>FX Strategy Lab</h1>
        </div>
        <div className="safety-badge">
          <span>LIVE TRADING</span>
          <strong>LOCKED</strong>
        </div>
      </header>

      <section className="hero">
        <div>
          <span className="phase-label">安全優先の段階運用</span>
          <h2>仮説を、記録できる判断へ。</h2>
          <p>
            過去検証からデモ注文まで、同じ戦略ロジックで追跡します。
            実資金ブローカーはこのMVPでは接続されません。
          </p>
        </div>
        <div className="hero-status">
          <StatusPill status={botStatus?.status ?? paper?.status ?? "stopped"} />
          <small>現在のBot状態</small>
        </div>
      </section>

      <nav className="phase-nav" aria-label="開発フェーズ">
        {[
          ["01", "バックテスト"],
          ["02", "ペーパートレード"],
          ["03", "シグナル通知"],
          ["04", "デモ注文・安全設定"]
        ].map(([number, label], index) => (
          <button
            key={number}
            className={activePhase === index + 1 ? "active" : ""}
            onClick={() => setActivePhase(index + 1)}
          >
            <span>{number}</span>
            {label}
          </button>
        ))}
      </nav>

      {error && <div className="error-banner">{error}</div>}

      <div className="workspace">
        <aside className="control-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">STRATEGY CONFIG</p>
              <h3>検証条件</h3>
            </div>
            <span className="saved-dot">● 保存対象</span>
          </div>
          <div className="form-grid">
            <label>
              通貨ペア
              <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
                {symbols.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              時間足
              <select
                value={timeframe}
                onChange={(event) => setTimeframe(event.target.value)}
              >
                {timeframes.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            {activePhase === 1 && (
              <>
                <label>
                  開始日
                  <input
                    type="date"
                    value={start}
                    onChange={(event) => setStart(event.target.value)}
                  />
                </label>
                <label>
                  終了日
                  <input
                    type="date"
                    value={end}
                    onChange={(event) => setEnd(event.target.value)}
                  />
                </label>
              </>
            )}
          </div>
          <label>
            戦略
            <select
              value={strategy.strategy_type}
              onChange={(event) =>
                setStrategy({
                  ...strategy,
                  strategy_type: event.target.value as StrategyType
                })
              }
            >
              {Object.entries(strategyNames).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <div className="parameter-box">
            {strategy.strategy_type === "moving_average_cross" && (
              <div className="form-grid">
                <NumberField
                  label="短期MA"
                  value={strategy.short_period}
                  onChange={(short_period) => setStrategy({ ...strategy, short_period })}
                />
                <NumberField
                  label="長期MA"
                  value={strategy.long_period}
                  onChange={(long_period) => setStrategy({ ...strategy, long_period })}
                />
              </div>
            )}
            {strategy.strategy_type === "rsi_reversal" && (
              <div className="form-grid">
                <NumberField
                  label="RSI期間"
                  value={strategy.rsi_period}
                  onChange={(rsi_period) => setStrategy({ ...strategy, rsi_period })}
                />
                <NumberField
                  label="売られすぎ"
                  value={strategy.oversold}
                  onChange={(oversold) => setStrategy({ ...strategy, oversold })}
                />
                <NumberField
                  label="買われすぎ"
                  value={strategy.overbought}
                  onChange={(overbought) => setStrategy({ ...strategy, overbought })}
                />
              </div>
            )}
            {strategy.strategy_type === "breakout" && (
              <NumberField
                label="参照期間"
                value={strategy.breakout_period}
                onChange={(breakout_period) =>
                  setStrategy({ ...strategy, breakout_period })
                }
              />
            )}
          </div>

          <div className="form-grid">
            <NumberField
              label="初期資金"
              value={execution.initial_capital}
              onChange={(initial_capital) =>
                setExecution({ ...execution, initial_capital })
              }
            />
            <NumberField
              label="取引数量"
              value={execution.fixed_units}
              onChange={(fixed_units) => setExecution({ ...execution, fixed_units })}
            />
            <NumberField
              label="損切り (pips)"
              value={execution.stop_loss_pips}
              onChange={(stop_loss_pips) =>
                setExecution({ ...execution, stop_loss_pips })
              }
            />
            <NumberField
              label="利確 (pips)"
              value={execution.take_profit_pips}
              onChange={(take_profit_pips) =>
                setExecution({ ...execution, take_profit_pips })
              }
            />
            <NumberField
              label="最大損失率 (%)"
              value={execution.max_loss_percent}
              step={0.1}
              onChange={(max_loss_percent) =>
                setExecution({ ...execution, max_loss_percent })
              }
            />
            <NumberField
              label="レバレッジ"
              value={execution.leverage}
              onChange={(leverage) => setExecution({ ...execution, leverage })}
            />
          </div>
          <details>
            <summary>約定コスト設定</summary>
            <div className="form-grid detail-grid">
              <NumberField
                label="スプレッド (pips)"
                value={execution.spread_pips}
                step={0.1}
                onChange={(spread_pips) =>
                  setExecution({ ...execution, spread_pips })
                }
              />
              <NumberField
                label="スリッページ (pips)"
                value={execution.slippage_pips}
                step={0.1}
                onChange={(slippage_pips) =>
                  setExecution({ ...execution, slippage_pips })
                }
              />
              <NumberField
                label="手数料 / 取引"
                value={execution.commission_per_trade}
                onChange={(commission_per_trade) =>
                  setExecution({ ...execution, commission_per_trade })
                }
              />
            </div>
          </details>
        </aside>

        <section className="result-panel">
          {activePhase === 1 && (
            <BacktestView
              result={backtest}
              loading={loading}
              onRun={runBacktest}
            />
          )}
          {activePhase === 2 && (
            <PaperView
              snapshot={paper}
              loading={loading}
              onStart={startPaper}
              onTick={tickPaper}
              onStop={stopPaper}
            />
          )}
          {activePhase === 3 && (
            <SignalView
              monitorId={monitorId}
              signals={signals}
              loading={loading}
              onToggle={toggleMonitor}
              onCheck={checkSignal}
            />
          )}
          {activePhase === 4 && (
            <BrokerView
              brokerOk={brokerOk}
              practiceOk={practiceOk}
              botStatus={botStatus}
              automation={automation}
              orders={orders}
              orderResult={orderResult}
              liveUiEnabled={liveUiEnabled}
              confirmation={confirmation}
              loading={loading}
              onTest={testBroker}
              onPracticeTest={testPracticeBroker}
              onPracticeStart={startPracticeAutomation}
              onPracticeCycle={runPracticeCycle}
              onPracticeStop={stopPracticeAutomation}
              onStartBot={startDemoBot}
              onStopBot={stopDemoBot}
              onDemo={() => submitDemoOrder("demo")}
              onLive={() => submitDemoOrder("live")}
              onClose={closeDemoPosition}
              onLiveToggle={setLiveUiEnabled}
              onConfirmation={setConfirmation}
            />
          )}
        </section>
      </div>
    </main>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step = 1
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
}) {
  return (
    <label>
      {label}
      <input
        type="number"
        value={value}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <span>DATA</span>
      <h3>まだ結果はありません</h3>
      <p>{text}</p>
    </div>
  );
}

function BacktestView({
  result,
  loading,
  onRun
}: {
  result: BacktestResponse | null;
  loading: boolean;
  onRun: () => void;
}) {
  return (
    <>
      <div className="result-heading">
        <div>
          <p className="eyebrow">PHASE 01</p>
          <h3>バックテスト結果</h3>
        </div>
        <button className="primary-button" disabled={loading} onClick={onRun}>
          {loading ? "検証中..." : "バックテスト実行"}
        </button>
      </div>
      {!result ? (
        <EmptyState text="左の条件を設定して、バックテストを実行してください。" />
      ) : (
        <>
          <div className="metrics-grid">
            <MetricCard
              label="総損益"
              value={money(result.metrics.total_pnl)}
              tone={result.metrics.total_pnl >= 0 ? "positive" : "negative"}
            />
            <MetricCard
              label="損益率"
              value={`${result.metrics.return_percent.toFixed(2)}%`}
            />
            <MetricCard
              label="勝率"
              value={`${result.metrics.win_rate.toFixed(1)}%`}
            />
            <MetricCard label="取引回数" value={`${result.metrics.trade_count}`} />
            <MetricCard
              label="PF"
              value={result.metrics.profit_factor?.toFixed(2) ?? "∞"}
            />
            <MetricCard
              label="最大DD"
              value={`${result.metrics.max_drawdown_percent.toFixed(2)}%`}
              tone="negative"
            />
            <MetricCard
              label="最大連勝"
              value={`${result.metrics.max_consecutive_wins}`}
            />
            <MetricCard
              label="最大連敗"
              value={`${result.metrics.max_consecutive_losses}`}
            />
          </div>
          <div className="chart-card">
            <h4>エクイティカーブ</h4>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={result.equity_curve}>
                <defs>
                  <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2ec4a6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#2ec4a6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1e3540" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={["auto", "auto"]} tick={{ fill: "#78909c" }} />
                <Tooltip />
                <Area
                  dataKey="equity"
                  stroke="#2ec4a6"
                  fill="url(#equityFill)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-card">
            <h4>価格・売買ポイント</h4>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={result.chart}>
                <CartesianGrid stroke="#1e3540" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={["auto", "auto"]} tick={{ fill: "#78909c" }} />
                <Tooltip />
                <Line
                  dataKey="close"
                  stroke="#d7e1e6"
                  dot={(props) => {
                    const signal = result.chart[props.index]?.signal;
                    if (!signal) return <></>;
                    const color =
                      signal === "buy"
                        ? "#2ec4a6"
                        : signal === "sell"
                          ? "#ff6b6b"
                          : "#f4c95d";
                    return (
                      <circle
                        cx={props.cx}
                        cy={props.cy}
                        r={4}
                        fill={color}
                        stroke="none"
                      />
                    );
                  }}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <TradeTable trades={result.trades} />
          <div className="warning-list">
            {result.warnings.map((warning) => (
              <p key={warning}>注意: {warning}</p>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function TradeTable({ trades }: { trades: BacktestResponse["trades"] }) {
  return (
    <div className="table-card">
      <h4>取引履歴</h4>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>日時</th>
              <th>方向</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>損益</th>
              <th>エントリー理由</th>
              <th>決済理由</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, index) => (
              <tr key={`${trade.entry_time}-${index}`}>
                <td>{new Date(trade.entry_time).toLocaleString("ja-JP")}</td>
                <td className={trade.side}>{trade.side.toUpperCase()}</td>
                <td>{trade.entry_price.toFixed(5)}</td>
                <td>{trade.exit_price.toFixed(5)}</td>
                <td className={trade.pnl >= 0 ? "profit" : "loss"}>
                  {money(trade.pnl)}
                </td>
                <td>{trade.entry_reason}</td>
                <td>{trade.exit_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PaperView({
  snapshot,
  loading,
  onStart,
  onTick,
  onStop
}: {
  snapshot: PaperSnapshot | null;
  loading: boolean;
  onStart: () => void;
  onTick: () => void;
  onStop: () => void;
}) {
  return (
    <>
      <div className="result-heading">
        <div>
          <p className="eyebrow">PHASE 02</p>
          <h3>ペーパートレード</h3>
        </div>
        <div className="button-row">
          <button className="primary-button" disabled={loading} onClick={onStart}>
            開始
          </button>
          <button disabled={!snapshot || loading} onClick={onTick}>
            価格更新・判定
          </button>
          <button
            className="danger-button"
            disabled={!snapshot || loading}
            onClick={onStop}
          >
            手動停止
          </button>
        </div>
      </div>
      {!snapshot ? (
        <EmptyState text="仮想資金のみで戦略をリアルタイム相当に検証します。" />
      ) : (
        <>
          <div className="session-strip">
            <StatusPill status={snapshot.status} />
            <span>Session #{snapshot.id}</span>
            <span>
              現在価格: {snapshot.current_price?.toFixed(5) ?? "更新待ち"}
            </span>
          </div>
          <div className="metrics-grid">
            <MetricCard label="仮想資金" value={money(snapshot.balance)} />
            <MetricCard label="Equity" value={money(snapshot.equity)} />
            <MetricCard
              label="含み損益"
              value={money(snapshot.unrealized_pnl)}
              tone={snapshot.unrealized_pnl >= 0 ? "positive" : "negative"}
            />
            <MetricCard label="確定損益" value={money(snapshot.realized_pnl)} />
            <MetricCard label="本日の取引" value={`${snapshot.today_trade_count}`} />
            <MetricCard label="本日の最大損失" value={money(snapshot.today_max_loss)} />
          </div>
          <div className="log-box">
            <span>直近の戦略判定</span>
            <strong>{snapshot.last_signal?.action ?? "待機中"}</strong>
            <p>{snapshot.last_signal?.reason ?? "価格更新後に表示されます。"}</p>
          </div>
          <div className="table-card">
            <h4>保有中の仮想ポジション</h4>
            {snapshot.open_positions.length ? (
              snapshot.open_positions.map((trade) => (
                <div className="position-row" key={trade.id}>
                  <b className={trade.side}>{trade.side.toUpperCase()}</b>
                  <span>{trade.units.toFixed(0)} units</span>
                  <span>Entry {trade.entry_price.toFixed(5)}</span>
                  <span>SL {trade.stop_loss.toFixed(5)}</span>
                  <span>TP {trade.take_profit.toFixed(5)}</span>
                  <strong>{money(trade.unrealized_pnl)}</strong>
                </div>
              ))
            ) : (
              <p className="muted">現在ポジションはありません。</p>
            )}
          </div>
        </>
      )}
    </>
  );
}

function SignalView({
  monitorId,
  signals,
  loading,
  onToggle,
  onCheck
}: {
  monitorId: string | null;
  signals: SignalRecord[];
  loading: boolean;
  onToggle: () => void;
  onCheck: () => void;
}) {
  return (
    <>
      <div className="result-heading">
        <div>
          <p className="eyebrow">PHASE 03</p>
          <h3>シグナル監視</h3>
        </div>
        <div className="button-row">
          <button className="primary-button" disabled={loading} onClick={onToggle}>
            {monitorId ? "監視OFF" : "監視ON"}
          </button>
          <button disabled={!monitorId || loading} onClick={onCheck}>
            今すぐ判定
          </button>
        </div>
      </div>
      <div className="session-strip">
        <StatusPill status={monitorId ? "running" : "stopped"} />
        <span>{monitorId ? `Monitor ${monitorId.slice(0, 8)}` : "監視停止中"}</span>
      </div>
      {signals.length ? (
        <div className="signal-list">
          {signals.map((signal) => (
            <article key={signal.id}>
              <div>
                <span className={`signal-side ${signal.side}`}>{signal.side}</span>
                <h4>
                  {signal.symbol} / {signal.timeframe}
                </h4>
                <p>{signal.reason}</p>
              </div>
              <dl>
                <div>
                  <dt>価格</dt>
                  <dd>{signal.price.toFixed(5)}</dd>
                </div>
                <div>
                  <dt>SL</dt>
                  <dd>{signal.stop_loss.toFixed(5)}</dd>
                </div>
                <div>
                  <dt>TP</dt>
                  <dd>{signal.take_profit.toFixed(5)}</dd>
                </div>
                <div>
                  <dt>Risk</dt>
                  <dd>{signal.risk_percent}%</dd>
                </div>
              </dl>
              <small>{signal.notice}</small>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState text="条件成立時の通知は画面とDBへ記録されます。" />
      )}
    </>
  );
}

function BrokerView({
  brokerOk,
  practiceOk,
  botStatus,
  automation,
  orders,
  orderResult,
  liveUiEnabled,
  confirmation,
  loading,
  onTest,
  onPracticeTest,
  onPracticeStart,
  onPracticeCycle,
  onPracticeStop,
  onStartBot,
  onStopBot,
  onDemo,
  onLive,
  onClose,
  onLiveToggle,
  onConfirmation
}: {
  brokerOk: boolean;
  practiceOk: boolean;
  botStatus: BotStatus | null;
  automation: AutomationStatus | null;
  orders: OrderRecord[];
  orderResult: Record<string, unknown> | null;
  liveUiEnabled: boolean;
  confirmation: string;
  loading: boolean;
  onTest: () => void;
  onPracticeTest: () => void;
  onPracticeStart: () => void;
  onPracticeCycle: () => void;
  onPracticeStop: () => void;
  onStartBot: () => void;
  onStopBot: () => void;
  onDemo: () => void;
  onLive: () => void;
  onClose: (order: OrderRecord) => void;
  onLiveToggle: (value: boolean) => void;
  onConfirmation: (value: string) => void;
}) {
  return (
    <>
      <div className="result-heading">
        <div>
          <p className="eyebrow">PHASE 04</p>
          <h3>デモ注文・安全設定</h3>
        </div>
        <button disabled={loading} onClick={onTest}>
          デモ接続テスト
        </button>
      </div>
      <div className={`connection-card ${brokerOk ? "ok" : ""}`}>
        <span>DEMO BROKER</span>
        <strong>{brokerOk ? "CONNECTED" : "NOT TESTED"}</strong>
        <p>ローカルのデモブローカーです。外部口座や実資金には接続しません。</p>
      </div>
      <div className="session-strip">
        <StatusPill status={botStatus?.status ?? "stopped"} />
        <span>{botStatus?.stop_reason ?? "デモBotは明示的な開始操作が必要です"}</span>
        <div className="button-row">
          <button
            disabled={!brokerOk || loading}
            className="primary-button"
            onClick={onStartBot}
          >
            デモBot開始
          </button>
          <button
            disabled={loading}
            className="danger-button"
            onClick={onStopBot}
          >
            Bot手動停止
          </button>
        </div>
      </div>
      <div className="risk-grid">
        {[
          "1日の最大損失: ¥100",
          "1回の最大損失: ¥25",
          "最大ポジション: 1",
          "最大数量: 1,000",
          "連敗停止: 3",
          "最大スプレッド: 3 pips",
          "二重注文ID: 拒否",
          "約定未確認: 緊急停止"
        ].map((item) => (
          <span key={item}>✓ {item}</span>
        ))}
      </div>
      <div className="button-row">
        <button
          className="primary-button"
          disabled={!brokerOk || botStatus?.status !== "running" || loading}
          onClick={onDemo}
        >
          デモ成行注文をテスト
        </button>
      </div>
      <div className="live-lock">
        <div className="live-lock-heading">
          <div>
            <span>実資金モード</span>
            <strong>常時ブロック</strong>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={liveUiEnabled}
              onChange={(event) => onLiveToggle(event.target.checked)}
            />
            <i />
          </label>
        </div>
        <p>
          UI確認をONにしても、環境変数、確認文言、API接続、ログ、リスク設定、
          実ブローカー実装の全条件が必要です。このMVPは実ブローカー未実装のため必ず拒否します。
        </p>
        <label>
          確認文言
          <input
            value={confirmation}
            placeholder="LIVE TRADING ENABLED"
            onChange={(event) => onConfirmation(event.target.value)}
          />
        </label>
        <button className="danger-button" disabled={loading} onClick={onLive}>
          ライブ注文ガードを検証
        </button>
      </div>
      <div className="table-card">
        <h4>デモ注文・ポジション履歴</h4>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>通貨</th>
                <th>方向</th>
                <th>数量</th>
                <th>状態</th>
                <th>約定価格</th>
                <th>損益</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td>
                  <td>{order.symbol}</td>
                  <td>{order.side}</td>
                  <td>{order.units}</td>
                  <td>{order.status}</td>
                  <td>{order.filled_price?.toFixed(5) ?? "-"}</td>
                  <td>
                    {order.realized_pnl == null ? "-" : money(order.realized_pnl)}
                  </td>
                  <td>
                    <button
                      disabled={
                        order.mode !== "demo" ||
                        order.status !== "filled" ||
                        loading
                      }
                      onClick={() => onClose(order)}
                    >
                      デモ決済
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className={`connection-card practice-card ${practiceOk ? "ok" : ""}`}>
        <span>OANDA PRACTICE AUTOMATION</span>
        <strong>
          {automation?.enabled
            ? "AUTO TRADE ON"
            : practiceOk
              ? "CONNECTED / OFF"
              : "NOT CONNECTED"}
        </strong>
        <p>
          価格取得、戦略判定、リスク判定、SL/TP付き注文、約定確認、
          ポジション監視、反対シグナル決済を30秒周期で実行します。
        </p>
        <div className="button-row">
          <button disabled={loading} onClick={onPracticeTest}>
            practice接続テスト
          </button>
          <button
            className="primary-button"
            disabled={!practiceOk || automation?.enabled || loading}
            onClick={onPracticeStart}
          >
            practice自動売買ON
          </button>
          <button
            disabled={!automation?.enabled || loading}
            onClick={onPracticeCycle}
          >
            1サイクル確認
          </button>
          <button
            className="danger-button"
            disabled={!automation?.enabled || loading}
            onClick={onPracticeStop}
          >
            practice自動売買停止
          </button>
        </div>
      </div>
      <div className="automation-grid">
        <MetricCard
          label="自動売買"
          value={automation?.enabled ? "ON" : "OFF"}
          tone={automation?.enabled ? "positive" : "neutral"}
        />
        <MetricCard label="環境" value={automation?.environment ?? "practice"} />
        <MetricCard
          label="Bot状態"
          value={automation?.bot.status ?? botStatus?.status ?? "stopped"}
        />
        <MetricCard
          label="最終注文ID"
          value={automation?.last_order_id || "-"}
        />
      </div>
      <div className="automation-detail">
        <dl>
          <div>
            <dt>Live注文</dt>
            <dd>BLOCKED</dd>
          </div>
          <div>
            <dt>最終シグナル</dt>
            <dd>
              {automation?.last_signal.action ?? "-"}{" "}
              {automation?.last_signal.reason ?? ""}
            </dd>
          </div>
          <div>
            <dt>最終リスク判定</dt>
            <dd>
              {automation?.last_risk.allowed == null
                ? "-"
                : automation.last_risk.allowed
                  ? "許可"
                  : `拒否: ${automation.last_risk.reasons?.join(", ")}`}
            </dd>
          </div>
          <div>
            <dt>最終約定確認</dt>
            <dd>
              {automation?.last_fill.status ?? "-"}{" "}
              {automation?.last_fill.fill_transaction_id ?? ""}
            </dd>
          </div>
          <div>
            <dt>停止理由</dt>
            <dd>{automation?.bot.stop_reason ?? "-"}</dd>
          </div>
          <div>
            <dt>最終価格取得</dt>
            <dd>{automation?.last_price_at ?? "-"}</dd>
          </div>
          <div>
            <dt>最終残高取得</dt>
            <dd>{automation?.last_balance_at ?? "-"}</dd>
          </div>
        </dl>
      </div>
      <div className="table-card">
        <h4>OANDA practice 現在ポジション</h4>
        {automation?.current_positions.length ? (
          automation.current_positions.map((position) => (
            <div
              className="position-row"
              key={`${position.symbol}-${position.side}`}
            >
              <b className={position.side}>{position.side.toUpperCase()}</b>
              <span>{position.symbol}</span>
              <span>{position.units} units</span>
              <span>平均 {position.average_price}</span>
              <strong>{position.unrealized_pnl}</strong>
            </div>
          ))
        ) : (
          <p className="muted">practiceポジションはありません。</p>
        )}
      </div>
      {orderResult && (
        <pre className="result-json">{JSON.stringify(orderResult, null, 2)}</pre>
      )}
    </>
  );
}
