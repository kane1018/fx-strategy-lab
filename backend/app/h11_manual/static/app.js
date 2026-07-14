const MARKET_RENDER_INTERVAL_MS = 1000;
const SIGNAL_SETTLE_DELAY_MS = 3000;
const PUBLIC_TICKER_WS = "wss://forex-api.coin.z.com/ws/public/v1";

const state = {
  selected: "10m",
  signals: [],
  realtimeEstimates: [],
  realtimeCollection: null,
  signalSeries: { "10m": [], "30m": [], "24h": [], realtime: [] },
  currentTab: "signal",
  validationHorizon: "10m",
  realtimeValidationHorizon: "10m",
  validationData: null,
  exitPlans: { "10m": null, "30m": null },
  exitSignals: { "10m": null, "30m": null },
  openPositionCount: 0,
  brokerSync: { status: "NOT_CONFIGURED", configured: false, open_position_count: null },
  chartTimeframe: "1m",
  candles: [],
  live: {
    bid: null,
    ask: null,
    marketTime: null,
    receivedAt: null,
    marketStatus: null,
  },
  websocket: null,
  reconnectAttempt: 0,
  reconnectTimer: null,
  renderTimer: null,
  signalTimer: null,
  nextSignalRefreshAt: null,
  refreshInFlight: false,
  realtimeInFlight: false,
  lastRealtimeSampleSecond: null,
  exitStatusInFlight: false,
  brokerSyncInFlight: false,
  lastExitRefreshSecond: null,
  lastBrokerSyncSecond: null,
  tradeStartInFlight: false,
  calculatorPriceEdited: false,
  calculatorDirectionEdited: false,
};

const formalHorizonOrder = ["10m", "30m", "24h"];
const signalOrder = ["10m", "30m", "24h", "realtime"];
const directionClass = {
  "買い": "buy",
  "売り": "sell",
  "見送り": "no-trade",
  "判定不可": "unknown",
};
const directionDisplay = {
  "買い": "Buy",
  "売り": "Sell",
  "見送り": "Stay",
  "判定不可": "Unknown",
};
const chartLabels = { "1m": "1分足", "10m": "10分足", "30m": "30分足", "1h": "1時間足" };

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>'"]/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char],
  );
}

function percent(value) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

function jst(value, includeSeconds = true) {
  if (!value) return "—";
  const options = {
    timeZone: "Asia/Tokyo",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  };
  if (includeSeconds) options.second = "2-digit";
  return new Intl.DateTimeFormat("ja-JP", options).format(new Date(value));
}

function signalByHorizon(horizon) {
  return state.signals.find((item) => item.horizon === horizon) || {
    horizon,
    horizon_label: { "10m": "10分", "30m": "30分", "24h": "24時間" }[horizon],
    direction: "判定不可",
    p_up: null,
    p_down: null,
    reason: "データを読み込めません",
    status: "BLOCKED",
  };
}

function realtimeByHorizon(horizon) {
  return state.realtimeEstimates.find((item) => item.horizon === horizon) || null;
}

function realtimeModeLabel(estimate) {
  if (!estimate) return "1秒データを待機中";
  if (estimate.estimate_mode === "TICK_NATIVE_ROLLING_60S") return "1秒データのみで計算";
  if (estimate.estimate_mode === "M1_BOOTSTRAP_ROLLING_60S") return "M1履歴を併用・蓄積中";
  return "推定準備中";
}

function displaySignal(key) {
  if (key !== "realtime") return signalByHorizon(key);
  const estimate = realtimeByHorizon("10m");
  return {
    horizon: "realtime",
    horizon_label: "毎秒ローリング",
    direction: estimate?.direction || "判定不可",
    p_up: estimate?.p_up ?? null,
    p_down: estimate?.p_down ?? null,
    reason: estimate?.reason || "Public tickerの1秒サンプルを準備しています",
    origin_time_utc: estimate?.estimate_time_utc ?? null,
    status: estimate ? "OK" : "BLOCKED",
    recorded_mode: "REALTIME_ESTIMATE_NOT_FORMAL",
    forecast_id: null,
  };
}

function signalModelLabel(key) {
  if (key === "realtime") return "非正式・検証前 · 10分方向の毎秒推定";
  return `正式シグナル · ${key === "24h" ? "H11 v2" : "SHORT v1"}`;
}

function realtimeProgress() {
  const stored = state.realtimeCollection?.stored_sample_count ?? 0;
  const coverage = state.realtimeCollection?.recent_coverage_seconds ?? 0;
  const remaining = Math.max(0, 31 * 60 - coverage);
  return state.realtimeCollection?.tick_native_window_ready
    ? "1秒ローリング窓 準備完了"
    : `1秒データ ${stored.toLocaleString("ja-JP")}件 · native窓まで約${Math.ceil(remaining / 60)}分`;
}

function signalSparkline(key, compact = false) {
  const points = (state.signalSeries[key] || [])
    .map((item) => Number(item.p_up))
    .filter(Number.isFinite)
    .slice(compact ? -45 : -120);
  if (!points.length) {
    return `<div class="signal-chart empty ${compact ? "compact" : ""}">確率履歴を蓄積中</div>`;
  }
  const x = (index) => (points.length === 1 ? 50 : (index / (points.length - 1)) * 100);
  const y = (value) => 34 - Math.max(0, Math.min(1, value)) * 32;
  const polyline = points.map((value, index) => `${x(index).toFixed(2)},${y(value).toFixed(2)}`).join(" ");
  const latest = Math.round(points[points.length - 1] * 100);
  return `<div class="signal-chart ${compact ? "compact" : ""}" aria-label="上昇確率の履歴・最新${latest}%">
    <svg class="signal-sparkline" viewBox="0 0 100 36" preserveAspectRatio="none" role="img">
      <line class="threshold buy-threshold" x1="0" y1="${y(0.58)}" x2="100" y2="${y(0.58)}"></line>
      <line class="threshold midpoint" x1="0" y1="${y(0.5)}" x2="100" y2="${y(0.5)}"></line>
      <line class="threshold sell-threshold" x1="0" y1="${y(0.42)}" x2="100" y2="${y(0.42)}"></line>
      <polyline points="${polyline}"></polyline>
    </svg>
    <span>上昇確率の推移</span>
  </div>`;
}

function mainCard(signal, key) {
  const width = signal.p_up == null ? 0 : Math.round(signal.p_up * 100);
  const recordLabel =
    key === "realtime"
      ? `${realtimeModeLabel(realtimeByHorizon("10m"))} · ${realtimeProgress()}`
      : signal.recorded_mode === "PROSPECTIVE"
        ? "前向き記録"
        : signal.recorded_mode === "REPLAYED_AFTER_MATURITY"
          ? "成熟後記録"
          : "未記録";
  return `
    <div class="card-top"><span class="horizon-label">${escapeHtml(signal.horizon_label)}の方向</span><span class="model-tag">${signalModelLabel(key)}</span></div>
    <div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(directionDisplay[signal.direction] || signal.direction)}</div>
    <div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇確率</span><span class="probability-label">下降 ${percent(signal.p_down)}</span></div>
    <div class="probability-bar" aria-label="上昇確率 ${width}%"><span style="width:${width}%"></span></div>
    <div class="reason">${escapeHtml(signal.reason)}</div>
    ${signalCardControl(key)}
    ${signalSparkline(key)}
    <div class="meta-line"><span>観測 ${jst(signal.origin_time_utc)} JST</span><span>閾値 Buy 58% / Sell 42%</span><span>${escapeHtml(recordLabel)}</span></div>`;
}

function smallCard(signal, key) {
  return `<article class="signal-small">
    <button class="signal-card-select" type="button" data-signal-key="${key}" aria-label="${escapeHtml(signal.horizon_label)}を大きく表示">
      <div class="card-top"><span class="horizon-label">${escapeHtml(signal.horizon_label)}</span><span class="swap-hint">クリックで切替</span></div>
      <div class="small-signal-summary"><div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(directionDisplay[signal.direction] || signal.direction)}</div><div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇</span></div></div>
      ${signalSparkline(key, true)}
    </button>
    ${signalCardControl(key, true)}
  </article>`;
}

function quickExitContext(key = state.selected) {
  const signal = displaySignal(key);
  const supported = ["10m", "30m"].includes(key);
  const directional = ["買い", "売り"].includes(signal.direction);
  const quoteAge = state.live.receivedAt == null ? Infinity : Date.now() - state.live.receivedAt;
  const referencePrice = signal.direction === "買い" ? state.live.ask : state.live.bid;
  return {
    signal,
    eligible:
      supported &&
      directional &&
      Boolean(signal.forecast_id) &&
      signal.recorded_mode === "PROSPECTIVE" &&
      Number.isFinite(referencePrice) &&
      quoteAge <= 15000 &&
      state.brokerSync.configured &&
      state.brokerSync.status === "SYNCED" &&
      !state.exitPlans[key],
  };
}

function cardActionState(key) {
  const signal = displaySignal(key);
  if (key === "24h") {
    return {
      label: "参考表示・取引対象外",
      enabled: false,
      exitLabel: "出口対象外",
      exitReason: "24時間モデルは相場方向の参考表示です",
    };
  }
  if (key === "realtime") {
    return {
      label: "検証前・取引対象外",
      enabled: false,
      exitLabel: "出口対象外",
      exitReason: "毎秒ローリングは非正式推定です",
    };
  }
  const active = state.exitPlans[key];
  if (active) {
    const exitSignal = state.exitSignals[key];
    return {
      label: "出口シグナル稼働中",
      enabled: false,
      exitLabel: `出口: ${exitSignal?.label || "確認中"}`,
      exitReason: exitSignal?.reason || "出口条件を確認しています",
      active,
      exitSignal,
    };
  }
  if (state.tradeStartInFlight) {
    return { label: "開始中…", enabled: false, exitLabel: "出口: 開始処理中", exitReason: "二重操作を防止しています" };
  }
  const context = quickExitContext(key);
  if (context.eligible) {
    return {
      label: `${directionDisplay[signal.direction]}で取引開始`,
      enabled: true,
      exitLabel: "出口: 建玉なし",
      exitReason: "開始後、このカードへ出口シグナルを表示 · SL15 / TP22.5",
    };
  }
  if (signal.direction === "見送り") {
    return { label: "取引開始（Stay）", enabled: false, exitLabel: "出口: 建玉なし", exitReason: "方向条件を満たしていません" };
  }
  if (!['買い', '売り'].includes(signal.direction)) {
    return { label: "取引開始（判定待ち）", enabled: false, exitLabel: "出口: 建玉なし", exitReason: "正式方向を確認できません" };
  }
  if (!state.brokerSync.configured) {
    return {
      label: "取引開始（同期未設定）",
      enabled: false,
      exitLabel: "Broker同期: 未設定",
      exitReason: "read-only credentialをKeychainへ設定すると有効になります",
    };
  }
  if (state.brokerSync.status !== "SYNCED") {
    return {
      label: "取引開始（同期確認待ち）",
      enabled: false,
      exitLabel: "Broker同期: 要確認",
      exitReason: "latestExecutions / openPositionsの正常同期を待っています",
    };
  }
  return {
    label: "取引開始（価格待ち）",
    enabled: false,
    exitLabel: "出口: 建玉なし",
    exitReason: "前向き記録と15秒以内のPublic価格が必要です",
  };
}

function brokerPlanLabel(sync = {}) {
  const labels = {
    WAITING_FOR_OPEN: "Broker: OPEN約定待ち",
    AMBIGUOUS_OPEN: "Broker: OPEN照合不明",
    LINKED: "Broker: OPEN照合済み",
    PARTIALLY_CLOSED: "Broker: 部分決済",
    RECHECK_REQUIRED: "Broker: 同期要確認",
    CLOSED: "Broker: CLOSE反映済み",
    NOT_TRACKED: "Broker: 未追跡",
  };
  return labels[sync.state] || "Broker: 確認中";
}

function brokerPlanDetail(sync = {}) {
  if (sync.state === "PARTIALLY_CLOSED") {
    return `残 ${Number(sync.remaining_size || 0).toLocaleString("ja-JP")} / ${Number(sync.entry_size || 0).toLocaleString("ja-JP")}通貨`;
  }
  if (sync.state === "LINKED") {
    return `${Number(sync.entry_size || 0).toLocaleString("ja-JP")}通貨 · 約定価格を自動反映`;
  }
  if (sync.state === "AMBIGUOUS_OPEN") return "複数候補のため自動で紐付けていません";
  if (sync.state === "RECHECK_REQUIRED") return "推測で決済扱いにせず確認待ちで停止しています";
  return "手動OPEN/CLOSEをread-only GETで確認します";
}

function signalCardControl(key, compact = false) {
  const action = cardActionState(key);
  if (action.active) {
    const active = action.active;
    const broker = active.broker_sync || {};
    return `<div class="signal-card-control card-position-control ${compact ? "compact" : ""} ${escapeHtml(action.exitSignal?.tone || "neutral")}">
      <div class="signal-card-exit" title="${escapeHtml(action.exitReason)}">
        <strong>${escapeHtml(action.exitLabel)}</strong>
        <span>${escapeHtml(action.exitReason)}</span>
        <small>${escapeHtml(directionDisplay[active.direction] || active.direction)} · ${escapeHtml(active.horizon)} · Entry ${quote(active.entry_price)} · SL ${quote(active.stop_loss_price)} · TP ${quote(active.take_profit_price)} · ${remainingTime(active.remaining_seconds)}</small>
      </div>
      <div class="broker-card-state ${escapeHtml((broker.state || "").toLowerCase())}" title="${escapeHtml(brokerPlanDetail(broker))}">
        <strong>${escapeHtml(brokerPlanLabel(broker))}</strong>
        <span>${escapeHtml(brokerPlanDetail(broker))}</span>
      </div>
    </div>`;
  }
  return `<div class="signal-card-control ${compact ? "compact" : ""}">
    <div class="signal-card-exit" title="${escapeHtml(action.exitReason)}"><strong data-card-exit-label="${key}">${escapeHtml(action.exitLabel)}</strong><span data-card-exit-reason="${key}">${escapeHtml(action.exitReason)}</span></div>
    <button type="button" data-trade-start="${key}" ${action.enabled ? "" : "disabled"}>${escapeHtml(action.label)}</button>
  </div>`;
}

function updateQuickExitAction() {
  document.querySelectorAll("[data-trade-start]").forEach((button) => {
    const key = button.dataset.tradeStart;
    const action = cardActionState(key);
    button.textContent = action.label;
    button.disabled = !action.enabled;
    button.classList.toggle("quick-ready", action.enabled);
    const label = document.querySelector(`[data-card-exit-label="${key}"]`);
    const reason = document.querySelector(`[data-card-exit-reason="${key}"]`);
    if (label) label.textContent = action.exitLabel;
    if (reason) reason.textContent = action.exitReason;
  });
}

function renderSignals() {
  const selected = displaySignal(state.selected);
  document.querySelector("#main-signal").innerHTML = mainCard(selected, state.selected);
  document.querySelector("#sub-signals").innerHTML = signalOrder
    .filter((key) => key !== state.selected)
    .map((key) => smallCard(displaySignal(key), key))
    .join("");
  document.querySelectorAll("[data-signal-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selected = button.dataset.signalKey;
      renderSignals();
    });
  });
  document.querySelectorAll("[data-trade-start]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.tradeStart;
      state.selected = key;
      renderSignals();
      await startTrade(key);
    });
  });
  updateQuickExitAction();
}

function setUpdateStatus(text, type = "ok") {
  document.querySelector("#updated-at").textContent = text;
  document.querySelector("#update-dot").className = `status-dot ${type === "ok" ? "" : type}`;
}

function showNotice(text, type = "info") {
  const notice = document.querySelector("#notice");
  notice.textContent = text;
  notice.className = `notice ${type === "error" ? "error" : ""}`;
}

function hideNotice() {
  document.querySelector("#notice").classList.add("hidden");
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      message = (await response.json()).detail || message;
    } catch (_) {
      // Keep the sanitized HTTP fallback.
    }
    throw new Error(message);
  }
  return response.json();
}

async function loadCurrent() {
  setUpdateStatus("シグナル読み込み中", "loading");
  try {
    const data = await request("/api/manual/current");
    state.signals = data.signals;
    renderSignals();
    setUpdateStatus(`シグナル更新 ${jst(data.updated_at_utc)} JST`);
    if (data.signals.some((signal) => signal.status === "BLOCKED")) {
      showNotice("短期シグナルを初期化しています。完了まで画面を開いたままお待ちください。");
    } else {
      hideNotice();
    }
    return data;
  } catch (error) {
    setUpdateStatus("シグナル読み込み失敗", "error");
    showNotice(error.message, "error");
    renderSignals();
    return null;
  }
}

async function loadSignalSeries() {
  try {
    const data = await request("/api/manual/signal-series?limit=120");
    formalHorizonOrder.forEach((horizon) => {
      state.signalSeries[horizon] = data.series[horizon] || [];
    });
    renderSignals();
  } catch (_) {
    // Current values remain usable when stored probability history is unavailable.
  }
}

async function refreshData({ auto = false } = {}) {
  if (state.refreshInFlight) return null;
  state.refreshInFlight = true;
  const button = document.querySelector("#refresh-button");
  button.disabled = true;
  button.textContent = auto ? "確定足更新中…" : "更新中…";
  if (auto) document.querySelector("#next-signal-update").textContent = "シグナル更新中";
  setUpdateStatus("M1確定足を更新中", "loading");
  try {
    const data = await request(`/api/manual/refresh?force=${auto ? "false" : "true"}`, {
      method: "POST",
    });
    state.signals = data.signals;
    renderSignals();
    await loadSignalSeries();
    await loadChart();
    setUpdateStatus(`シグナル更新 ${jst(data.updated_at_utc)} JST`);
    const refreshStatus = data.refresh?.status;
    if (data.signals.some((signal) => signal.status === "BLOCKED")) {
      showNotice("必要な確定足またはモデルがまだ揃っていません。次回の毎分更新で再確認します。");
    } else if (!auto && refreshStatus === "UPDATED") {
      showNotice("確定足とシグナルを更新しました。");
    } else {
      hideNotice();
    }
    return data;
  } catch (error) {
    setUpdateStatus("確定足更新失敗", "error");
    showNotice(`更新できませんでした: ${error.message}`, "error");
    return null;
  } finally {
    state.refreshInFlight = false;
    button.disabled = false;
    button.textContent = "データを更新";
  }
}

function scheduleSignalRefresh() {
  if (state.signalTimer) window.clearTimeout(state.signalTimer);
  const now = Date.now();
  const nextMinute = (Math.floor(now / 60000) + 1) * 60000;
  state.nextSignalRefreshAt = nextMinute + SIGNAL_SETTLE_DELAY_MS;
  state.signalTimer = window.setTimeout(async () => {
    await refreshData({ auto: true });
    scheduleSignalRefresh();
  }, Math.max(250, state.nextSignalRefreshAt - now));
}

function setMarketStatus(text, stateClass = "") {
  document.querySelector("#market-status").textContent = text;
  document.querySelector("#market-status-dot").className = `market-status-dot ${stateClass}`;
}

function connectTicker() {
  if (state.websocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(state.websocket.readyState)) {
    return;
  }
  setMarketStatus("Public ticker接続中");
  const socket = new WebSocket(PUBLIC_TICKER_WS);
  state.websocket = socket;
  socket.addEventListener("open", () => {
    state.reconnectAttempt = 0;
    setMarketStatus("live受信中", "connected");
    socket.send(JSON.stringify({ command: "subscribe", channel: "ticker", symbol: "USD_JPY" }));
  });
  socket.addEventListener("message", (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.symbol !== "USD_JPY") return;
      const bid = Number(payload.bid);
      const ask = Number(payload.ask);
      if (!Number.isFinite(bid) || !Number.isFinite(ask) || ask < bid) return;
      state.live = {
        bid,
        ask,
        marketTime: payload.timestamp || new Date().toISOString(),
        receivedAt: Date.now(),
        marketStatus: payload.status || null,
      };
    } catch (_) {
      // Ignore malformed public messages and retain the last valid tick.
    }
  });
  socket.addEventListener("error", () => {
    setMarketStatus("ticker接続エラー", "error");
  });
  socket.addEventListener("close", () => {
    if (state.websocket !== socket) return;
    state.websocket = null;
    state.reconnectAttempt += 1;
    const delay = Math.min(5000 * 2 ** (state.reconnectAttempt - 1), 30000);
    setMarketStatus(`再接続待機 ${Math.round(delay / 1000)}秒`, "error");
    state.reconnectTimer = window.setTimeout(connectTicker, delay);
  });
}

function quote(value) {
  return value == null ? "—" : Number(value).toFixed(3);
}

function renderMarket() {
  const age = state.live.receivedAt == null ? Infinity : Date.now() - state.live.receivedAt;
  document.querySelector("#live-bid").textContent = quote(state.live.bid);
  document.querySelector("#live-ask").textContent = quote(state.live.ask);
  document.querySelector("#live-spread").textContent =
    state.live.bid == null || state.live.ask == null
      ? "—"
      : `${((state.live.ask - state.live.bid) / 0.01).toFixed(1)} pips`;
  document.querySelector("#live-time").textContent = jst(state.live.marketTime);
  if (age <= 15000) {
    setMarketStatus(state.live.marketStatus === "CLOSE" ? "市場CLOSE" : "live受信中", "connected");
  } else if (state.websocket?.readyState === WebSocket.OPEN) {
    setMarketStatus("価格更新待機中");
  }
  if (state.nextSignalRefreshAt) {
    const remaining = Math.max(0, state.nextSignalRefreshAt - Date.now());
    document.querySelector("#next-signal-update").textContent =
      `次回シグナル更新まで ${Math.ceil(remaining / 1000)}秒`;
  }
  drawChart();
  updateQuickExitAction();
  if (state.currentTab === "calculator" && !state.calculatorPriceEdited) syncCalculatorQuote();
  if (age <= 15000) updateRealtimeEstimate();
  if (state.currentTab === "signal") refreshExitStatusOncePerSecond();
}

async function updateRealtimeEstimate() {
  if (state.realtimeInFlight || state.live.bid == null || state.live.ask == null) return;
  const currentSecond = Math.floor(Date.now() / 1000);
  if (state.lastRealtimeSampleSecond === currentSecond) return;
  state.lastRealtimeSampleSecond = currentSecond;
  state.realtimeInFlight = true;
  try {
    const data = await request("/api/manual/realtime-estimate", {
      method: "POST",
      body: JSON.stringify({
        bid: state.live.bid,
        ask: state.live.ask,
        market_time_utc: state.live.marketTime,
      }),
    });
    state.realtimeEstimates = data.estimates;
    state.realtimeCollection = data.collection;
    const estimate = realtimeByHorizon("10m");
    if (estimate?.p_up != null && estimate?.estimate_time_utc) {
      const series = state.signalSeries.realtime;
      const point = { time_utc: estimate.estimate_time_utc, p_up: estimate.p_up };
      if (series.at(-1)?.time_utc === point.time_utc) series[series.length - 1] = point;
      else series.push(point);
      state.signalSeries.realtime = series.slice(-120);
    }
    renderSignals();
  } catch (_) {
    // Formal signals remain visible; transient realtime estimation failures stay isolated.
  } finally {
    state.realtimeInFlight = false;
  }
}

async function loadChart() {
  try {
    const data = await request(`/api/manual/chart?timeframe=${state.chartTimeframe}&limit=180`);
    state.candles = data.candles.map((candle) => ({
      time_utc: candle.time_utc,
      open: Number(candle.open),
      high: Number(candle.high),
      low: Number(candle.low),
      close: Number(candle.close),
    }));
    document.querySelector("#chart-timeframe-label").textContent = chartLabels[state.chartTimeframe];
    drawChart();
  } catch (error) {
    state.candles = [];
    document.querySelector("#chart-empty").textContent = `チャートを読み込めません: ${error.message}`;
    document.querySelector("#chart-empty").classList.remove("hidden");
  }
}

function chartIntervalMinutes() {
  return { "1m": 1, "10m": 10, "30m": 30, "1h": 60 }[state.chartTimeframe];
}

function candlesWithLiveTick() {
  const candles = state.candles.map((candle) => ({ ...candle }));
  if (state.live.bid == null) return candles;
  const intervalMs = chartIntervalMinutes() * 60000;
  const tickTime = Date.parse(state.live.marketTime || "") || Date.now();
  const bucket = Math.floor(tickTime / intervalMs) * intervalMs;
  const bucketIso = new Date(bucket).toISOString();
  const last = candles[candles.length - 1];
  const lastBucket = last ? Math.floor(Date.parse(last.time_utc) / intervalMs) * intervalMs : null;
  if (last && lastBucket === bucket) {
    last.high = Math.max(last.high, state.live.bid);
    last.low = Math.min(last.low, state.live.bid);
    last.close = state.live.bid;
  } else if (!last || bucket > lastBucket) {
    const open = last?.close ?? state.live.bid;
    candles.push({
      time_utc: bucketIso,
      open,
      high: Math.max(open, state.live.bid),
      low: Math.min(open, state.live.bid),
      close: state.live.bid,
    });
  }
  return candles;
}

function drawChart() {
  const canvas = document.querySelector("#price-chart");
  if (!canvas) return;
  const context = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = "#06101d";
  context.fillRect(0, 0, width, height);

  const candles = candlesWithLiveTick().slice(-90);
  const empty = document.querySelector("#chart-empty");
  if (!candles.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  const margin = { top: 16, right: 72, bottom: 28, left: 14 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  let minimum = Math.min(...candles.map((candle) => candle.low));
  let maximum = Math.max(...candles.map((candle) => candle.high));
  const padding = Math.max((maximum - minimum) * 0.08, 0.002);
  minimum -= padding;
  maximum += padding;
  const priceY = (price) => margin.top + ((maximum - price) / (maximum - minimum)) * plotHeight;
  const step = plotWidth / candles.length;
  const candleWidth = Math.max(2, Math.min(10, step * 0.62));

  context.strokeStyle = "rgba(70, 94, 126, .30)";
  context.fillStyle = "#6f849f";
  context.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
  context.lineWidth = 1;
  for (let index = 0; index <= 4; index += 1) {
    const y = margin.top + (plotHeight * index) / 4;
    const price = maximum - ((maximum - minimum) * index) / 4;
    context.beginPath();
    context.moveTo(margin.left, y);
    context.lineTo(width - margin.right, y);
    context.stroke();
    context.fillText(price.toFixed(3), width - margin.right + 9, y + 4);
  }

  candles.forEach((candle, index) => {
    const x = margin.left + step * index + step / 2;
    const rising = candle.close >= candle.open;
    const color = rising ? "#2dd4bf" : "#fb7185";
    context.strokeStyle = color;
    context.fillStyle = color;
    context.beginPath();
    context.moveTo(x, priceY(candle.high));
    context.lineTo(x, priceY(candle.low));
    context.stroke();
    const top = Math.min(priceY(candle.open), priceY(candle.close));
    const bodyHeight = Math.max(1, Math.abs(priceY(candle.open) - priceY(candle.close)));
    context.fillRect(x - candleWidth / 2, top, candleWidth, bodyHeight);
  });

  const latest = candles[candles.length - 1];
  const latestY = priceY(latest.close);
  context.strokeStyle = "rgba(96, 165, 250, .85)";
  context.setLineDash([4, 4]);
  context.beginPath();
  context.moveTo(margin.left, latestY);
  context.lineTo(width - margin.right, latestY);
  context.stroke();
  context.setLineDash([]);
  context.fillStyle = "#60a5fa";
  context.fillText(latest.close.toFixed(3), width - margin.right + 9, latestY + 4);

  const timeIndices = [0, Math.floor((candles.length - 1) / 2), candles.length - 1];
  context.fillStyle = "#6f849f";
  timeIndices.forEach((index) => {
    const candle = candles[index];
    const x = margin.left + step * index + step / 2;
    const label = new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(candle.time_utc));
    context.fillText(label, Math.max(margin.left, x - 18), height - 8);
  });
}

async function startTrade(signalKey = state.selected) {
  if (state.tradeStartInFlight) return;
  state.tradeStartInFlight = true;
  updateQuickExitAction();
  try {
    const quick = quickExitContext(signalKey);
    if (!quick.eligible) {
      showNotice(
        "取引開始を記録できません。正式10分/30分の買い・売りと15秒以内の価格を確認してください。",
        "error",
      );
      return;
    }
    const data = await request("/api/manual/exit-plan/quick-start", {
      method: "POST",
      body: JSON.stringify({
        forecast_id: quick.signal.forecast_id,
        horizon: quick.signal.horizon,
        direction: quick.signal.direction,
      }),
    });
    applyExitPlanStatus(data);
    showNotice("TRADE_STARTEDを記録し、出口シグナルを開始しました。");
  } catch (error) {
    showNotice(`取引開始と出口シグナルを開始できませんでした: ${error.message}`, "error");
  } finally {
    state.tradeStartInFlight = false;
    updateQuickExitAction();
  }
}

function remainingTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function applyExitPlanStatus(data) {
  state.exitPlans = { "10m": null, "30m": null };
  state.exitSignals = { "10m": null, "30m": null };
  (data.active_plans || []).forEach((item) => {
    state.exitPlans[item.plan.horizon] = item.plan;
    state.exitSignals[item.plan.horizon] = item.exit_signal;
  });
  state.openPositionCount = Number(data.open_position_count) || 0;
  document.querySelector("#open-position-count").textContent = String(state.openPositionCount);
  if (data.broker_sync) applyBrokerSyncOverview(data.broker_sync);
  renderSignals();
}

function applyBrokerSyncOverview(data) {
  state.brokerSync = { ...state.brokerSync, ...data };
  const brokerCount = document.querySelector("#broker-position-count");
  brokerCount.textContent = data.open_position_count == null ? "—" : String(data.open_position_count);
  const syncLabel = document.querySelector("#broker-sync-label");
  const syncDot = document.querySelector("#broker-sync-dot");
  if (data.status === "SYNCED") {
    syncLabel.textContent = `同期 ${jst(data.last_success_at_utc)} JST`;
    syncDot.className = "status-dot";
  } else if (data.status === "NOT_CONFIGURED") {
    syncLabel.textContent = "Broker同期 未設定";
    syncDot.className = "status-dot loading";
  } else {
    syncLabel.textContent = "Broker同期 要確認";
    syncDot.className = "status-dot error";
  }
}

function applyBrokerSync(data) {
  applyBrokerSyncOverview(data);
  state.exitPlans = { "10m": null, "30m": null };
  state.exitSignals = { "10m": null, "30m": null };
  (data.active_plans || []).forEach((item) => {
    state.exitPlans[item.plan.horizon] = item.plan;
    state.exitSignals[item.plan.horizon] = item.exit_signal;
  });
  state.openPositionCount = (data.active_plans || []).length;
  document.querySelector("#open-position-count").textContent = String(state.openPositionCount);
  const closeEvent = (data.events || []).find((event) => event.type === "CLOSE_APPLIED");
  const openEvent = (data.events || []).find((event) => event.type === "OPEN_LINKED");
  if (closeEvent) showNotice("手動CLOSE約定を検知し、カードと取引記録へ反映しました。");
  else if (openEvent) showNotice("手動OPEN約定を検知し、実約定価格と数量をカードへ反映しました。");
  renderSignals();
}

async function loadBrokerSync() {
  if (state.brokerSyncInFlight) return;
  state.brokerSyncInFlight = true;
  try {
    applyBrokerSync(await request("/api/manual/broker-sync"));
  } catch (error) {
    state.brokerSync = { ...state.brokerSync, status: "ERROR" };
    applyBrokerSyncOverview(state.brokerSync);
    showNotice(`Broker read-only同期を確認できませんでした: ${error.message}`, "error");
  } finally {
    state.brokerSyncInFlight = false;
  }
}

async function loadExitPlan() {
  if (state.exitStatusInFlight) return;
  state.exitStatusInFlight = true;
  try {
    applyExitPlanStatus(await request("/api/manual/exit-plan"));
  } catch (error) {
    showNotice(`出口計画を読み込めませんでした: ${error.message}`, "error");
  } finally {
    state.exitStatusInFlight = false;
  }
}

function refreshExitStatusOncePerSecond() {
  const second = Math.floor(Date.now() / 1000);
  if (state.lastExitRefreshSecond === second) return;
  state.lastExitRefreshSecond = second;
  loadExitPlan();
  if (second % 5 === 0 && state.lastBrokerSyncSecond !== second) {
    state.lastBrokerSyncSecond = second;
    loadBrokerSync();
  }
}

function renderTable(rows, columns, emptyText) {
  if (!rows.length) return `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
  return `<table><thead><tr>${columns.map(([_, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([key, _, format]) => `<td>${escapeHtml(format ? format(row[key], row) : row[key] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

async function loadHistory() {
  const data = await request("/api/manual/history?limit=100");
  document.querySelector("#history-table").className = "table-wrap";
  document.querySelector("#history-table").innerHTML = renderTable(
    data.forecasts,
    [
      ["origin_time_utc", "観測時刻", jst],
      ["horizon", "時間軸"],
      ["direction", "方向", (value) => directionDisplay[value] || value],
      ["p_up", "上昇確率", percent],
      ["recorded_mode", "記録方式"],
      ["outcome_up", "結果", (value) => (value == null ? "未確定" : value ? "上昇" : "下降")],
    ],
    "予測履歴はまだありません",
  );
  document.querySelector("#decision-table").className = "table-wrap";
  document.querySelector("#decision-table").innerHTML = renderTable(
    data.signal_actions,
    [
      ["recorded_at_utc", "記録時刻", jst],
      ["horizon", "時間軸"],
      ["action", "状態", (value) => value === "TRADE_STARTED" ? "取引開始" : "取引開始記録なし"],
      ["note", "メモ"],
    ],
    "取引記録はまだありません",
  );
}

function metric(value) {
  return value == null ? "—" : Number(value).toFixed(4);
}

function percent1(value) {
  return value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
}

function renderValidationDiagnostics() {
  const diagnostics = state.validationData?.metrics?.diagnostics?.[state.validationHorizon];
  if (!diagnostics) return;
  const calibration = document.querySelector("#calibration-table");
  calibration.className = "table-wrap";
  calibration.innerHTML = renderTable(
    diagnostics.calibration_bands,
    [
      ["label", "予測帯"],
      ["sample_n", "全件N"],
      ["non_overlapping_n", "非重複N"],
      ["mean_p_up", "平均予測", percent1],
      ["realized_up_rate", "実現上昇率", percent1],
      ["calibration_gap", "校正差", percent1],
    ],
    "この時間軸の確定結果はまだありません",
  );
  const rows = diagnostics.threshold_curve;
  const threshold = document.querySelector("#threshold-table");
  threshold.className = "table-wrap";
  if (!rows.length) {
    threshold.innerHTML = '<div class="empty-state">この時間軸の確定結果はまだありません</div>';
  } else {
    threshold.innerHTML = `<table><thead><tr><th>買い／売り基準</th><th>全件N</th><th>Coverage</th><th>全件精度</th><th>非重複N</th><th>非重複精度</th><th>95%区間</th></tr></thead><tbody>${rows
      .map(
        (row) => `<tr class="${row.is_current_v1 ? "threshold-current" : ""}"><td>${Math.round(row.buy_threshold * 100)}%／${Math.round(row.sell_threshold * 100)}%${row.is_current_v1 ? " · 現行v1" : ""}</td><td>${row.sample_n}</td><td>${percent1(row.coverage)}</td><td>${percent1(row.direction_accuracy)}</td><td>${row.non_overlapping_n}</td><td>${percent1(row.non_overlapping_accuracy)}</td><td>${row.wilson_low == null ? "—" : `${percent1(row.wilson_low)}–${percent1(row.wilson_high)}`}</td></tr>`,
      )
      .join("")}</tbody></table>`;
  }
  document.querySelectorAll("[data-validation-horizon]").forEach((button) => {
    button.classList.toggle("active", button.dataset.validationHorizon === state.validationHorizon);
  });
  document.querySelector("#threshold-policy-note").textContent =
    `対象: ${signalByHorizon(state.validationHorizon).horizon_label} · PROSPECTIVE ${diagnostics.raw_resolved_n}件 · 非重複 ${diagnostics.non_overlapping_n}件。58%／42%はSHORT v1で固定し、診断結果から自動変更しません。`;
}

function renderRealtimeValidationDiagnostics() {
  const root = state.validationData?.realtime_rolling;
  const selected = root?.horizons?.[state.realtimeValidationHorizon];
  if (!root || !selected) return;
  const raw = selected.raw_metrics;
  const independent = selected.non_overlapping_metrics;
  const cards = [
    ["記録予測", selected.forecast_n, "1秒ごとのraw件数"],
    ["結果確定", selected.resolved_n, `照合率 ${percent1(selected.target_resolution_coverage)}`],
    ["非重複N", independent.resolved_n, `${state.realtimeValidationHorizon}間隔で抽出`],
    ["対象価格欠測", selected.target_price_missing_n, "目標時刻+15秒超"],
  ];
  document.querySelector("#realtime-validation-cards").innerHTML = cards
    .map(
      ([label, value, note]) =>
        `<article class="metric-card"><h2>${label}</h2><dl><div><dt>件数</dt><dd>${value}</dd></div><div><dt>説明</dt><dd>${note}</dd></div></dl></article>`,
    )
    .join("");

  document.querySelector("#realtime-calibration-table").className = "table-wrap";
  document.querySelector("#realtime-calibration-table").innerHTML = renderTable(
    selected.calibration_bands,
    [
      ["label", "予測帯"],
      ["sample_n", "raw N"],
      ["non_overlapping_n", "非重複N"],
      ["mean_p_up", "平均予測", percent1],
      ["realized_up_rate", "実現上昇率", percent1],
      ["calibration_gap", "校正差", percent1],
    ],
    "この時間軸の確定結果はまだありません",
  );
  const threshold = document.querySelector("#realtime-threshold-table");
  const rows = selected.threshold_curve;
  threshold.className = "table-wrap";
  threshold.innerHTML = rows.length
    ? `<table><thead><tr><th>買い／売り基準</th><th>raw N</th><th>Coverage</th><th>raw精度</th><th>非重複N</th><th>非重複精度</th><th>95%区間</th></tr></thead><tbody>${rows
        .map(
          (row) => `<tr class="${row.is_current_v1 ? "threshold-current" : ""}"><td>${Math.round(row.buy_threshold * 100)}%／${Math.round(row.sell_threshold * 100)}%</td><td>${row.sample_n}</td><td>${percent1(row.coverage)}</td><td>${percent1(row.direction_accuracy)}</td><td>${row.non_overlapping_n}</td><td>${percent1(row.non_overlapping_accuracy)}</td><td>${row.wilson_low == null ? "—" : `${percent1(row.wilson_low)}–${percent1(row.wilson_high)}`}</td></tr>`,
        )
        .join("")}</tbody></table>`
    : '<div class="empty-state">この時間軸の確定結果はまだありません</div>';
  document.querySelectorAll("[data-realtime-validation-horizon]").forEach((button) => {
    button.classList.toggle(
      "active",
      button.dataset.realtimeValidationHorizon === state.realtimeValidationHorizon,
    );
  });
  const modeSummary = selected.estimate_modes.length
    ? selected.estimate_modes.map((item) => `${item.estimate_mode}: ${item.forecast_n}件`).join(" / ")
    : "予測待ち";
  document.querySelector("#realtime-validation-note").textContent =
    `対象: ${state.realtimeValidationHorizon} · raw Brier ${metric(raw.brier)}（0.5基準比 ${metric(raw.brier_improvement_vs_0_5)}）· 非重複 Brier ${metric(independent.brier)}。rawの毎秒行は独立標本ではありません。対象BIDは目標時刻から15秒以内だけを採用し、遅延時は欠測に固定します。${modeSummary}。正式シグナルへの自動昇格・閾値自動変更はありません。`;
}

async function loadValidation() {
  const data = await request("/api/manual/validation");
  state.validationData = data;
  const items = [
    ["overall", "全体", data.metrics.overall],
    ...formalHorizonOrder.map((horizon) => [
      horizon,
      signalByHorizon(horizon).horizon_label,
      data.metrics.horizons[horizon],
    ]),
  ];
  document.querySelector("#validation-cards").innerHTML = items
    .map(
      ([_, label, item]) =>
        `<article class="metric-card"><h2>${label}</h2><dl><div><dt>確定数</dt><dd>${item.resolved_n}</dd></div><div><dt>Brier</dt><dd>${metric(item.brier)}</dd></div><div><dt>Log loss</dt><dd>${metric(item.log_loss)}</dd></div><div><dt>方向精度</dt><dd>${item.accuracy == null ? "—" : percent(item.accuracy)}</dd></div></dl></article>`,
    )
    .join("");
  renderValidationDiagnostics();
  renderRealtimeValidationDiagnostics();
}

async function switchTab(tab) {
  state.currentTab = tab;
  document.querySelectorAll(".screen").forEach((screen) => {
    screen.classList.toggle("active-screen", screen.id === tab);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.tab === tab);
  });
  if (tab === "history" || tab === "record") await loadHistory();
  if (tab === "validation") await loadValidation();
  if (tab === "calculator") prepareCalculator();
  if (tab === "signal") drawChart();
}

function calculatorFormalSignal() {
  const horizon = ["10m", "30m"].includes(state.selected) ? state.selected : "10m";
  return signalByHorizon(horizon);
}

function syncCalculatorQuote() {
  const directionInput = document.querySelector("#calc-direction");
  const entryInput = document.querySelector("#calc-entry");
  const context = document.querySelector("#calc-signal-context");
  const signal = calculatorFormalSignal();
  const formalDirection = signal.direction === "買い" ? "buy" : signal.direction === "売り" ? "sell" : "";
  if (!state.calculatorDirectionEdited && directionInput.value !== formalDirection) {
    directionInput.value = formalDirection;
    state.calculatorPriceEdited = false;
  }
  const direction = directionInput.value;
  const quoteAge = state.live.receivedAt == null ? Infinity : Date.now() - state.live.receivedAt;
  const price = direction === "buy" ? state.live.ask : direction === "sell" ? state.live.bid : null;
  const fresh = Number.isFinite(price) && quoteAge >= -5000 && quoteAge <= 15000;
  if (!state.calculatorPriceEdited) entryInput.value = fresh ? Number(price).toFixed(3) : "";
  const signalText = ["買い", "売り"].includes(signal.direction)
    ? `${signal.horizon_label}正式シグナル: ${signal.direction}`
    : `${signal.horizon_label}正式シグナル: ${signal.direction}`;
  const priceText = !direction
    ? "方向を選択するとPublic ASK/BIDを反映"
    : fresh
      ? `Public ${direction === "buy" ? "ASK" : "BID"}を自動反映`
      : "15秒以内のPublic価格なし・手入力可能";
  context.textContent = `${signalText} · ${priceText}`;
}

function prepareCalculator() {
  const signal = calculatorFormalSignal();
  const directionInput = document.querySelector("#calc-direction");
  state.calculatorDirectionEdited = false;
  state.calculatorPriceEdited = false;
  directionInput.value = signal.direction === "買い" ? "buy" : signal.direction === "売り" ? "sell" : "";
  document.querySelector("#calc-entry").value = "";
  document.querySelector("#calc-size").value = "0";
  document.querySelector("#calculator-result").className = "panel result-panel empty-state";
  document.querySelector("#calculator-result").textContent =
    "許容損失額を入力して「数量と価格を計算」を押してください";
  syncCalculatorQuote();
}

function calculate(event) {
  event.preventDefault();
  const direction = document.querySelector("#calc-direction").value;
  const entry = Number(document.querySelector("#calc-entry").value);
  const slPips = Number(document.querySelector("#calc-sl").value);
  const tpPips = Number(document.querySelector("#calc-tp").value);
  const allowedLoss = Number(document.querySelector("#calc-max-loss").value);
  const cost = Number(document.querySelector("#calc-cost").value);
  const pip = 0.01;
  const lossPerUnit = (slPips + 2 * cost) * pip;
  const size = Math.floor(allowedLoss / lossPerUnit / 1000) * 1000;
  const result = document.querySelector("#calculator-result");
  if (!direction || !Number.isFinite(entry) || entry <= 0 || !Number.isFinite(size) || size < 1000) {
    document.querySelector("#calc-size").value = "0";
    result.className = "panel result-panel empty-state";
    result.textContent = "方向・価格を確認してください。許容損失額が1,000通貨分より小さい場合も計算できません。";
    return;
  }
  document.querySelector("#calc-size").value = String(size);
  const sign = direction === "buy" ? 1 : -1;
  const stop = entry - sign * slPips * pip;
  const take = entry + sign * tpPips * pip;
  const maxLoss = lossPerUnit * size;
  const targetGain = Math.max(0, tpPips - 2 * cost) * pip * size;
  result.className = "panel result-panel";
  result.innerHTML = `<div class="result-item"><span>逆算数量</span><strong>${size.toLocaleString("ja-JP")}通貨</strong></div><div class="result-item"><span>損切り価格</span><strong>${stop.toFixed(3)}</strong></div><div class="result-item"><span>利益確定価格</span><strong>${take.toFixed(3)}</strong></div><div class="result-item"><span>最大損失目安</span><strong>¥${Math.round(maxLoss).toLocaleString("ja-JP")}</strong></div><div class="result-item"><span>利益目安</span><strong>¥${Math.round(targetGain).toLocaleString("ja-JP")}</strong></div><p class="result-note">許容損失 ¥${Math.round(allowedLoss).toLocaleString("ja-JP")}以内になるよう1,000通貨単位で切り下げています。注文は送信されません。</p>`;
}

async function initialize() {
  const current = await loadCurrent();
  await loadSignalSeries();
  await loadChart();
  await loadExitPlan();
  await loadBrokerSync();
  connectTicker();
  scheduleSignalRefresh();
  renderMarket();
  state.renderTimer = window.setInterval(renderMarket, MARKET_RENDER_INTERVAL_MS);
  if (current?.signals?.slice(0, 2).some((signal) => signal.status === "BLOCKED")) {
    await refreshData({ auto: true });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-tab]").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      switchTab(item.dataset.tab);
    });
  });
  document.querySelectorAll("[data-chart-timeframe]").forEach((item) => {
    item.addEventListener("click", async () => {
      state.chartTimeframe = item.dataset.chartTimeframe;
      document.querySelectorAll("[data-chart-timeframe]").forEach((button) => {
        button.classList.toggle("active", button === item);
      });
      await loadChart();
    });
  });
  document.querySelector("#refresh-button").addEventListener("click", () => {
    refreshData({ auto: false });
  });
  document.querySelector("#calculator-form").addEventListener("submit", calculate);
  document.querySelector("#calc-direction").addEventListener("change", () => {
    state.calculatorDirectionEdited = true;
    state.calculatorPriceEdited = false;
    syncCalculatorQuote();
  });
  document.querySelector("#calc-entry").addEventListener("input", () => {
    state.calculatorPriceEdited = true;
  });
  document.querySelectorAll("[data-validation-horizon]").forEach((button) => {
    button.addEventListener("click", () => {
      state.validationHorizon = button.dataset.validationHorizon;
      renderValidationDiagnostics();
    });
  });
  document.querySelectorAll("[data-realtime-validation-horizon]").forEach((button) => {
    button.addEventListener("click", () => {
      state.realtimeValidationHorizon = button.dataset.realtimeValidationHorizon;
      renderRealtimeValidationDiagnostics();
    });
  });
  window.addEventListener("resize", drawChart);
  window.addEventListener("beforeunload", () => {
    if (state.websocket) state.websocket.close();
    if (state.reconnectTimer) window.clearTimeout(state.reconnectTimer);
    if (state.renderTimer) window.clearInterval(state.renderTimer);
    if (state.signalTimer) window.clearTimeout(state.signalTimer);
  });
  initialize();
});
