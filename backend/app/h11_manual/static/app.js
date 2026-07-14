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
  activeExitPlan: null,
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
  lastExitRefreshSecond: null,
  decisionInFlight: false,
};

const formalHorizonOrder = ["10m", "30m", "24h"];
const signalOrder = ["10m", "30m", "24h", "realtime"];
const directionClass = {
  "買い": "buy",
  "売り": "sell",
  "見送り": "no-trade",
  "判定不可": "unknown",
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
    <div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(signal.direction)}</div>
    <div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇確率</span><span class="probability-label">下降 ${percent(signal.p_down)}</span></div>
    <div class="probability-bar" aria-label="上昇確率 ${width}%"><span style="width:${width}%"></span></div>
    <div class="reason">${escapeHtml(signal.reason)}</div>
    ${signalSparkline(key)}
    <div class="meta-line"><span>観測 ${jst(signal.origin_time_utc)} JST</span><span>閾値 買い58% / 売り42%</span><span>${escapeHtml(recordLabel)}</span></div>`;
}

function smallCard(signal, key) {
  return `<button class="signal-small" type="button" data-signal-key="${key}" aria-label="${escapeHtml(signal.horizon_label)}を大きく表示">
    <div class="card-top"><span class="horizon-label">${escapeHtml(signal.horizon_label)}</span><span class="swap-hint">クリックで切替</span></div>
    <div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(signal.direction)}</div>
    <div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇</span></div>
    ${signalSparkline(key, true)}
  </button>`;
}

function quickExitContext() {
  const signal = displaySignal(state.selected);
  const supported = ["10m", "30m"].includes(state.selected);
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
      !state.activeExitPlan,
  };
}

function updateQuickExitAction() {
  const button = document.querySelector("#trade-and-exit-button");
  const guidance = document.querySelector("#quick-exit-guidance");
  if (!button || !guidance) return;
  const context = quickExitContext();
  if (state.decisionInFlight) {
    button.textContent = "開始中…";
    button.disabled = true;
    button.classList.remove("quick-ready");
    guidance.textContent = "取引記録と出口計画を固定しています";
  } else if (state.activeExitPlan) {
    button.textContent = "出口管理中";
    button.disabled = true;
    button.classList.remove("quick-ready");
    guidance.textContent = "進行中の出口計画があります。出口シグナルを確認してください";
  } else if (context.eligible) {
    button.textContent = "取引した＋出口開始";
    button.disabled = false;
    button.classList.add("quick-ready");
    guidance.textContent = "1クリックで最新Public価格から固定SL 15 / TP 22.5 pipsを開始します";
  } else {
    button.textContent = "取引した";
    button.disabled = false;
    button.classList.remove("quick-ready");
    guidance.textContent = "ワンクリック開始は正式10分/30分の買い・売りと15秒以内の価格が必要です";
  }
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
  if (age <= 15000) updateRealtimeEstimate();
  if (["signal", "exit"].includes(state.currentTab)) refreshExitStatusOncePerSecond();
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

async function recordDecision(decision) {
  if (state.decisionInFlight) return;
  state.decisionInFlight = true;
  updateQuickExitAction();
  const isRealtime = state.selected === "realtime";
  const horizon = isRealtime ? "10m" : state.selected;
  const signal = isRealtime ? displaySignal("realtime") : signalByHorizon(horizon);
  try {
    await request("/api/manual/decisions", {
      method: "POST",
      body: JSON.stringify({
        horizon,
        decision,
        forecast_id: isRealtime ? null : signal.forecast_id,
        note: isRealtime ? "REALTIME_ESTIMATE_NON_FORMAL" : "",
      }),
    });
    showNotice(`${signal.horizon_label}を「${decision}」として記録しました。`);
    if (decision === "取引した") {
      const quick = quickExitContext();
      if (quick.eligible) {
        try {
          const data = await request("/api/manual/exit-plan/quick-start", {
            method: "POST",
            body: JSON.stringify({
              forecast_id: quick.signal.forecast_id,
              horizon: quick.signal.horizon,
              direction: quick.signal.direction,
            }),
          });
          renderExitPlan(data);
          showNotice(
            "取引記録と出口管理を開始しました。固定SL 15 / TP 22.5 pipsを監視します。",
          );
          return;
        } catch (error) {
          await switchTab("exit");
          prepareExitForm(horizon);
          showNotice(
            `ワンクリック開始できませんでした。実約定価格を確認してください: ${error.message}`,
            "error",
          );
          return;
        }
      }
      await switchTab("exit");
      prepareExitForm(horizon);
    }
  } catch (error) {
    showNotice(`記録できませんでした: ${error.message}`, "error");
  } finally {
    state.decisionInFlight = false;
    updateQuickExitAction();
  }
}

function prepareExitForm(requestedHorizon = state.selected) {
  const horizon = ["24h", "realtime"].includes(requestedHorizon) ? "10m" : requestedHorizon;
  const signal = signalByHorizon(horizon);
  document.querySelector("#exit-horizon").value = horizon;
  document.querySelector("#exit-forecast-id").value = signal.forecast_id || "";
  document.querySelector("#exit-origin").textContent = `${jst(signal.origin_time_utc)} JST`;
  const target = signal.origin_time_utc
    ? new Date(new Date(signal.origin_time_utc).getTime() + Number.parseInt(horizon, 10) * 60000)
    : null;
  document.querySelector("#exit-target").textContent = target ? `${jst(target.toISOString())} JST` : "—";
  const directionInput = document.querySelector("#exit-direction");
  directionInput.value = ["買い", "売り"].includes(signal.direction) ? signal.direction : "";
  const referencePrice = directionInput.value === "買い" ? state.live.ask : state.live.bid;
  if (referencePrice != null) document.querySelector("#exit-entry").value = referencePrice.toFixed(3);
  updateExitContractPrices();
}

function updateExitContractPrices() {
  const direction = document.querySelector("#exit-direction")?.value;
  const entry = Number(document.querySelector("#exit-entry")?.value);
  const stopPips = Number(document.querySelector("#exit-stop-pips")?.value);
  const takePips = Number(document.querySelector("#exit-take-pips")?.value);
  if (![entry, stopPips, takePips].every(Number.isFinite) || !["買い", "売り"].includes(direction)) {
    document.querySelector("#exit-stop-price").textContent = "—";
    document.querySelector("#exit-take-price").textContent = "—";
    return null;
  }
  const sign = direction === "買い" ? 1 : -1;
  const stop = entry - sign * stopPips * 0.01;
  const take = entry + sign * takePips * 0.01;
  document.querySelector("#exit-stop-price").textContent = stop.toFixed(3);
  document.querySelector("#exit-take-price").textContent = take.toFixed(3);
  return { stop, take };
}

async function openExitPlan(event) {
  event.preventDefault();
  const prices = updateExitContractPrices();
  const forecastId = document.querySelector("#exit-forecast-id").value;
  if (!prices || !forecastId) {
    showNotice("方向・価格・有効な正式シグナルを確認してください。", "error");
    return;
  }
  try {
    const data = await request("/api/manual/exit-plan", {
      method: "POST",
      body: JSON.stringify({
        forecast_id: forecastId,
        horizon: document.querySelector("#exit-horizon").value,
        direction: document.querySelector("#exit-direction").value,
        entry_price: Number(document.querySelector("#exit-entry").value),
        stop_loss_price: prices.stop,
        take_profit_price: prices.take,
      }),
    });
    state.activeExitPlan = data.active;
    renderExitPlan(data);
    showNotice("固定SL・固定TP・time exitの出口計画を開始しました。");
  } catch (error) {
    showNotice(`出口計画を開始できませんでした: ${error.message}`, "error");
  }
}

function remainingTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function renderExitSignal(data) {
  const signal = data.exit_signal || {
    label: "判定不可",
    tone: "unknown",
    reason: "出口シグナルを確認できません",
  };
  const active = data.active;
  const strip = document.querySelector("#exit-signal-strip");
  strip.className = `exit-signal-strip ${signal.tone || "neutral"}`;
  document.querySelector("#exit-signal-label").textContent = signal.label;
  document.querySelector("#exit-position-label").textContent = active
    ? `${active.direction} · ${active.horizon} · 手動登録建玉`
    : "手動登録建玉なし";
  document.querySelector("#exit-signal-reason").textContent = signal.reason;
}

function renderExitPlan(data) {
  const active = data.active;
  const exitSignal = data.exit_signal || { label: "判定不可", tone: "unknown", reason: "確認できません" };
  state.activeExitPlan = active;
  renderExitSignal(data);
  const form = document.querySelector("#exit-plan-form");
  form.classList.toggle("hidden", Boolean(active));
  const panel = document.querySelector("#active-exit-plan");
  if (!active) {
    panel.className = "panel empty-state";
    panel.innerHTML = "進行中の出口計画はありません";
  } else {
    const alerts = [
      active.stop_reached ? "損切り価格到達" : null,
      active.take_profit_reached ? "利益確定価格到達" : null,
      active.time_exit_due ? "予測対象時刻到達" : null,
    ].filter(Boolean);
    panel.className = `panel active-exit-card ${alerts.length ? "exit-due" : ""}`;
    panel.innerHTML = `<div class="exit-card-head"><div><p class="eyebrow">ACTIVE MANUAL PLAN</p><h2>${escapeHtml(active.direction)} · ${escapeHtml(active.horizon)}</h2></div><span class="exit-state ${escapeHtml(exitSignal.tone)}">${escapeHtml(exitSignal.label)}</span></div>
      <div class="active-exit-signal"><span>POSITION-AWARE EXIT SIGNAL</span><strong>${escapeHtml(exitSignal.label)}</strong><p>${escapeHtml(exitSignal.reason)}</p></div>
      <div class="exit-live-grid"><div><span>現在価格</span><strong>${quote(active.current_price)}</strong></div><div><span>残り時間</span><strong>${remainingTime(active.remaining_seconds)}</strong></div><div><span>時間切れ</span><strong>${jst(active.target_time_utc)} JST</strong></div></div>
      <div class="exit-levels"><div><span>エントリー</span><strong>${quote(active.entry_price)}</strong></div><div><span>損切り</span><strong>${quote(active.stop_loss_price)}</strong></div><div><span>利益確定</span><strong>${quote(active.take_profit_price)}</strong></div></div>
      <div class="exit-alerts">${alerts.length ? alerts.map((item) => `<span>${escapeHtml(item)}</span>`).join("") : "固定条件の到達を監視しています"}</div>
      <div class="exit-actions"><button type="button" data-exit-reason="損切り">損切りで終了</button><button type="button" data-exit-reason="利益確定">利益確定で終了</button><button type="button" data-exit-reason="時間切れ">時間切れで終了</button><button type="button" data-exit-reason="手動終了">手動終了</button><button type="button" data-exit-reason="異常終了">異常終了</button></div>
      <p class="exit-footnote">表示と記録のみです。brokerの建玉確認・自動決済は行いません。</p>`;
    panel.querySelectorAll("[data-exit-reason]").forEach((button) => {
      button.addEventListener("click", () => closeExitPlan(button.dataset.exitReason));
    });
  }
  const history = data.history || [];
  const historyElement = document.querySelector("#exit-history");
  historyElement.className = "table-wrap";
  historyElement.innerHTML = renderTable(
    history,
    [
      ["entry_time_utc", "開始", jst],
      ["horizon", "時間軸"],
      ["direction", "方向"],
      ["entry_price", "Entry", quote],
      ["exit_price", "Exit", quote],
      ["exit_reason", "終了理由"],
      ["status", "状態"],
    ],
    "出口履歴はまだありません",
  );
  updateQuickExitAction();
}

async function loadExitPlan() {
  if (state.exitStatusInFlight) return;
  state.exitStatusInFlight = true;
  try {
    renderExitPlan(await request("/api/manual/exit-plan"));
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
}

async function closeExitPlan(reason) {
  const active = state.activeExitPlan;
  if (!active) return;
  const livePrice = active.direction === "買い" ? state.live.bid : state.live.ask;
  const exitPrice = livePrice ?? active.current_price;
  if (exitPrice == null) {
    showNotice("終了価格を確認できません。Public tickerを確認してください。", "error");
    return;
  }
  try {
    const data = await request("/api/manual/exit-plan/close", {
      method: "POST",
      body: JSON.stringify({ reason, exit_price: exitPrice }),
    });
    renderExitPlan(data);
    prepareExitForm();
    showNotice(`出口計画を「${reason}」として記録しました。`);
  } catch (error) {
    showNotice(`出口を記録できませんでした: ${error.message}`, "error");
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
      ["direction", "方向"],
      ["p_up", "上昇確率", percent],
      ["recorded_mode", "記録方式"],
      ["outcome_up", "結果", (value) => (value == null ? "未確定" : value ? "上昇" : "下降")],
    ],
    "予測履歴はまだありません",
  );
  document.querySelector("#decision-table").className = "table-wrap";
  document.querySelector("#decision-table").innerHTML = renderTable(
    data.operator_decisions,
    [
      ["recorded_at_utc", "記録時刻", jst],
      ["horizon", "時間軸"],
      ["decision", "選択"],
      ["note", "メモ"],
    ],
    "手動記録はまだありません",
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
  if (tab === "exit") {
    prepareExitForm();
    await loadExitPlan();
  }
  if (tab === "validation") await loadValidation();
  if (tab === "signal") drawChart();
}

function calculate(event) {
  event.preventDefault();
  const direction = document.querySelector("#calc-direction").value;
  const entry = Number(document.querySelector("#calc-entry").value);
  const slPips = Number(document.querySelector("#calc-sl").value);
  const tpPips = Number(document.querySelector("#calc-tp").value);
  const size = Number(document.querySelector("#calc-size").value);
  const cost = Number(document.querySelector("#calc-cost").value);
  const pip = 0.01;
  const sign = direction === "buy" ? 1 : -1;
  const stop = entry - sign * slPips * pip;
  const take = entry + sign * tpPips * pip;
  const maxLoss = (slPips + 2 * cost) * pip * size;
  const targetGain = Math.max(0, tpPips - 2 * cost) * pip * size;
  document.querySelector("#calculator-result").className = "panel result-panel";
  document.querySelector("#calculator-result").innerHTML = `<div class="result-item"><span>損切り価格</span><strong>${stop.toFixed(3)}</strong></div><div class="result-item"><span>利益確定価格</span><strong>${take.toFixed(3)}</strong></div><div class="result-item"><span>最大損失目安</span><strong>¥${Math.round(maxLoss).toLocaleString("ja-JP")}</strong></div><div class="result-item"><span>利益目安</span><strong>¥${Math.round(targetGain).toLocaleString("ja-JP")}</strong></div>`;
}

async function initialize() {
  const current = await loadCurrent();
  await loadSignalSeries();
  await loadChart();
  await loadExitPlan();
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
  document.querySelectorAll("[data-decision]").forEach((item) => {
    item.addEventListener("click", () => recordDecision(item.dataset.decision));
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
  document.querySelector("#exit-plan-form").addEventListener("submit", openExitPlan);
  document.querySelector("#exit-horizon").addEventListener("change", (event) => {
    prepareExitForm(event.target.value);
  });
  ["#exit-direction", "#exit-entry", "#exit-stop-pips", "#exit-take-pips"].forEach(
    (selector) => document.querySelector(selector).addEventListener("input", updateExitContractPrices),
  );
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
