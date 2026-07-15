const MARKET_RENDER_INTERVAL_MS = 1000;
const SIGNAL_SETTLE_DELAY_MS = 3000;
const FORMAL_REFRESH_RECHECK_MS = 10000;
const FORMAL_REFRESH_MAX_RECHECKS = 3;
const PUBLIC_TICKER_WS = "wss://forex-api.coin.z.com/ws/public/v1";

const state = {
  selected: "10m",
  signals: [],
  realtimeEstimates: [],
  realtimeCollection: null,
  realtimeHorizon: "10m",
  signalSeries: { "10m": [], "30m": [], "24h": [], realtime: { "10m": [], "30m": [] } },
  currentTab: "signal",
  validationHorizon: "overall",
  realtimeValidationHorizon: "10m",
  validationData: null,
  exitPlans: { "10m": null, "30m": null },
  exitSignals: { "10m": null, "30m": null },
  actualPositions: [],
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
  formalRefreshRechecks: 0,
  refreshInFlight: false,
  realtimeInFlight: false,
  lastRealtimeSampleSecond: null,
  exitStatusInFlight: false,
  brokerSyncInFlight: false,
  brokerSnapshotRevision: 0,
  lastExitRefreshSecond: null,
  lastBrokerSyncSecond: null,
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

function signalAgeOffsetSeconds(key) {
  if (["10m", "30m"].includes(key)) return 60;
  if (key === "24h") return 3600;
  return 0;
}

function signalAgeLabel(value, key) {
  const fallback = key === "realtime" ? "最終推定 —" : "確定足 —";
  if (!value) return fallback;
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return fallback;
  const seconds = Math.max(
    0,
    Math.floor((Date.now() - parsed - signalAgeOffsetSeconds(key) * 1000) / 1000),
  );
  return key === "realtime" ? `最終推定 ${seconds}秒前` : `確定足 ${seconds}秒前`;
}

function signalAgeMarkup(signal, key, compact = false) {
  return `<span class="signal-age ${compact ? "compact" : ""}" data-signal-age="${key}" data-signal-time="${escapeHtml(signal.origin_time_utc || "")}">${signalAgeLabel(signal.origin_time_utc, key)}</span>`;
}

function updateSignalAges() {
  document.querySelectorAll("[data-signal-age]").forEach((node) => {
    node.textContent = signalAgeLabel(node.dataset.signalTime, node.dataset.signalAge);
  });
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
  const estimate = realtimeByHorizon(state.realtimeHorizon);
  return {
    horizon: "realtime",
    horizon_label: "毎秒推定",
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
  if (key === "realtime") {
    const label = state.realtimeHorizon === "30m" ? "30分" : "10分";
    return `非正式・検証前 · ${label}方向の毎秒ローリング推定`;
  }
  return key === "24h" ? "方向参考 · H11 v2" : "正式シグナル · SHORT v1";
}

function realtimeProgress() {
  const stored = state.realtimeCollection?.stored_sample_count ?? 0;
  const coverage = state.realtimeCollection?.recent_coverage_seconds ?? 0;
  const remaining = Math.max(0, 31 * 60 - coverage);
  if (state.realtimeCollection?.tick_native_window_ready) return "1秒ローリング窓 準備完了";
  if (remaining < 60) return `1秒データ ${stored.toLocaleString("ja-JP")}件 · 最終確認中`;
  return `1秒データ ${stored.toLocaleString("ja-JP")}件 · native窓まで約${Math.ceil(remaining / 60)}分`;
}

function signalSeriesFor(key) {
  if (key === "realtime") return state.signalSeries.realtime[state.realtimeHorizon] || [];
  return state.signalSeries[key] || [];
}

function signalSparkline(key, compact = false) {
  const points = signalSeriesFor(key)
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

function realtimeHorizonControl(compact = false) {
  return `<div class="realtime-horizon-switch ${compact ? "compact" : ""}" role="group" aria-label="毎秒推定の予測時間">
    <span>予測時間</span>
    <button type="button" data-realtime-horizon="10m" class="${state.realtimeHorizon === "10m" ? "active" : ""}" aria-pressed="${state.realtimeHorizon === "10m"}">10分</button>
    <button type="button" data-realtime-horizon="30m" class="${state.realtimeHorizon === "30m" ? "active" : ""}" aria-pressed="${state.realtimeHorizon === "30m"}">30分</button>
  </div>`;
}

function mainCard(signal, key) {
  const width = signal.p_up == null ? 0 : Math.round(signal.p_up * 100);
  const cardTitle = key === "realtime" ? signal.horizon_label : `${signal.horizon_label}の方向`;
  const recordLabel =
    key === "realtime"
      ? `${realtimeModeLabel(realtimeByHorizon(state.realtimeHorizon))} · ${realtimeProgress()}`
      : signal.recorded_mode === "PROSPECTIVE"
        ? "前向き記録"
        : signal.recorded_mode === "REPLAYED_AFTER_MATURITY"
          ? "成熟後記録"
          : "未記録";
  return `
    <div class="card-top"><span class="horizon-label">${escapeHtml(cardTitle)}</span><span class="model-tag">${signalModelLabel(key)}</span></div>
    ${signalAgeMarkup(signal, key)}
    ${key === "realtime" ? realtimeHorizonControl() : ""}
    <div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(directionDisplay[signal.direction] || signal.direction)}</div>
    <div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇確率</span><span class="probability-label">下降 ${percent(signal.p_down)}</span></div>
    <div class="probability-bar" aria-label="上昇確率 ${width}%"><span style="width:${width}%"></span></div>
    <div class="reason">${escapeHtml(signal.reason)}</div>
    ${signalCardControl(key)}
    ${signalSparkline(key)}
    <div class="meta-line"><span>観測 ${jst(signal.origin_time_utc)} JST</span><span>判定基準 Buy 58% / Sell 42%</span><span>${escapeHtml(recordLabel)}</span></div>`;
}

function smallCard(signal, key) {
  return `<article class="signal-small">
    <button class="signal-card-select" type="button" data-signal-key="${key}" aria-label="${escapeHtml(signal.horizon_label)}を大きく表示">
      <div class="card-top"><span class="horizon-label">${escapeHtml(signal.horizon_label)}</span><span class="swap-hint">メイン表示</span></div>
      ${signalAgeMarkup(signal, key, true)}
      <div class="small-signal-summary"><div class="direction ${directionClass[signal.direction] || "unknown"}">${escapeHtml(directionDisplay[signal.direction] || signal.direction)}</div><div class="probability-row"><span class="probability-value">${percent(signal.p_up)}</span><span class="probability-label">上昇</span></div></div>
      ${signalSparkline(key, true)}
    </button>
    ${key === "realtime" ? realtimeHorizonControl(true) : ""}
    ${signalCardControl(key, true)}
  </article>`;
}

function cardActionState(key) {
  if (key === "24h") {
    return {
      exitLabel: "出口対象外",
      exitReason: "24時間モデルは相場方向の参考表示です",
      positions: [],
    };
  }
  if (key === "realtime") {
    return {
      exitLabel: "出口対象外",
      exitReason: "毎秒推定は非正式の研究表示です",
      positions: [],
    };
  }
  if (!state.brokerSync.configured) {
    return {
      exitLabel: "出口: 同期未設定",
      exitReason: "実建玉を確認するread-only同期が未設定です",
      positions: [],
    };
  }
  if (state.brokerSync.status !== "SYNCED") {
    return {
      exitLabel: "出口: 同期要確認",
      exitReason: "latestExecutions / openPositionsの正常同期を待っています",
      positions: [],
    };
  }
  if (!state.actualPositions.length) {
    return {
      exitLabel: "出口: 実建玉なし",
      exitReason: "GMO FXの現在建玉はありません",
      positions: [],
    };
  }
  const priority = {
    STOP_LOSS_REACHED: 100,
    TAKE_PROFIT_REACHED: 95,
    TIME_EXIT_DUE: 90,
    PRICE_UNKNOWN: 80,
    MODEL_STOP_CANDIDATE: 70,
    FORMAL_SIGNAL_UNKNOWN: 60,
    MODEL_EDGE_WARNING: 50,
    CONTINUE_POSITION: 10,
  };
  const positions = state.actualPositions
    .map((position) => ({ position, exit: position.exit_signals?.[key] }))
    .filter((item) => item.exit)
    .sort((left, right) => (priority[right.exit.code] || 0) - (priority[left.exit.code] || 0));
  const primary = positions[0];
  return {
    exitLabel: `出口: ${primary?.exit.label || "確認中"}`,
    exitReason: primary?.exit.reason || "実建玉の出口条件を確認しています",
    positions,
    exitSignal: primary?.exit || null,
  };
}

function brokerPlanLabel(sync = {}) {
  const labels = {
    WAITING_FOR_OPEN: "約定同期: 新規約定待ち",
    AMBIGUOUS_OPEN: "約定同期: 新規約定を特定不可",
    LINKED: "約定同期: 新規約定反映済み",
    PARTIALLY_CLOSED: "約定同期: 一部決済",
    RECHECK_REQUIRED: "約定同期: 要確認",
    CLOSED: "約定同期: 決済反映済み",
    NOT_TRACKED: "約定同期: 未追跡",
  };
  return labels[sync.state] || "約定同期: 確認中";
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
  const details = action.positions
    .map(({ position, exit }) => {
      const side = position.side === "BUY" ? "Buy" : "Sell";
      const time = exit.remaining_seconds == null ? "時刻不明" : remainingTime(exit.remaining_seconds);
      return `<small>${side} · ${Number(position.remaining_size || 0).toLocaleString("ja-JP")}通貨 · Entry ${quote(position.average_entry_price)} · ${escapeHtml(exit.label)} · ${time}</small>`;
    })
    .join("");
  return `<div class="signal-card-control actual-position-control ${compact ? "compact" : ""} ${escapeHtml(action.exitSignal?.tone || "neutral")}">
    <div class="signal-card-exit" title="${escapeHtml(action.exitReason)}">
      <strong>${escapeHtml(action.exitLabel)}</strong>
      <span>${escapeHtml(action.exitReason)}</span>
      ${details}
    </div>
  </div>`;
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
  document.querySelectorAll("[data-realtime-horizon]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      state.realtimeHorizon = button.dataset.realtimeHorizon;
      renderSignals();
    });
  });
  updateSignalAges();
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
  state.formalRefreshRechecks = 0;
  const now = Date.now();
  const nextMinute = (Math.floor(now / 60000) + 1) * 60000;
  state.nextSignalRefreshAt = nextMinute + SIGNAL_SETTLE_DELAY_MS;
  state.signalTimer = window.setTimeout(async () => {
    await refreshFormalSignal();
  }, Math.max(250, state.nextSignalRefreshAt - now));
}

function expectedCompletedM1OriginMs(now = Date.now()) {
  return (Math.floor(now / 60000) - 1) * 60000;
}

function formalSignalsIncludeLatestCompletedM1() {
  const expected = expectedCompletedM1OriginMs();
  return ["10m", "30m"].every((horizon) => {
    const origin = Date.parse(signalByHorizon(horizon).origin_time_utc || "");
    return Number.isFinite(origin) && origin >= expected;
  });
}

function scheduleFormalRefreshRecheck() {
  if (state.signalTimer) window.clearTimeout(state.signalTimer);
  state.nextSignalRefreshAt = Date.now() + FORMAL_REFRESH_RECHECK_MS;
  state.signalTimer = window.setTimeout(async () => {
    await refreshFormalSignal();
  }, FORMAL_REFRESH_RECHECK_MS);
}

async function refreshFormalSignal() {
  await refreshData({ auto: true });
  if (formalSignalsIncludeLatestCompletedM1()) {
    state.formalRefreshRechecks = 0;
    scheduleSignalRefresh();
    return;
  }
  if (
    state.live.marketStatus !== "CLOSE" &&
    state.formalRefreshRechecks < FORMAL_REFRESH_MAX_RECHECKS
  ) {
    state.formalRefreshRechecks += 1;
    setUpdateStatus(`確定足の公開反映を再確認中 (${state.formalRefreshRechecks}/${FORMAL_REFRESH_MAX_RECHECKS})`, "loading");
    scheduleFormalRefreshRecheck();
    return;
  }
  state.formalRefreshRechecks = 0;
  scheduleSignalRefresh();
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
  updateSignalAges();
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
    ["10m", "30m"].forEach((horizon) => {
      const estimate = realtimeByHorizon(horizon);
      if (estimate?.p_up == null || !estimate?.estimate_time_utc) return;
      const series = state.signalSeries.realtime[horizon];
      const point = { time_utc: estimate.estimate_time_utc, p_up: estimate.p_up };
      if (series.at(-1)?.time_utc === point.time_utc) series[series.length - 1] = point;
      else series.push(point);
      state.signalSeries.realtime[horizon] = series.slice(-120);
    });
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

function remainingTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function applyExitPlanStatus(data, { allowBrokerSnapshot = true } = {}) {
  state.exitPlans = { "10m": null, "30m": null };
  state.exitSignals = { "10m": null, "30m": null };
  (data.active_plans || []).forEach((item) => {
    state.exitPlans[item.plan.horizon] = item.plan;
    state.exitSignals[item.plan.horizon] = item.exit_signal;
  });
  if (allowBrokerSnapshot) {
    state.actualPositions = data.actual_positions || [];
    if (data.broker_sync) applyBrokerSyncOverview(data.broker_sync);
  }
  renderSignals();
}

function applyBrokerSyncOverview(data) {
  state.brokerSync = { ...state.brokerSync, ...data };
  const brokerCount = document.querySelector("#broker-position-count");
  brokerCount.textContent = data.open_position_count == null ? "—" : String(data.open_position_count);
  const syncLabel = document.querySelector("#broker-sync-label");
  const syncDot = document.querySelector("#broker-sync-dot");
  if (data.status === "SYNCED") {
    syncLabel.textContent = `建玉同期 ${jst(data.last_success_at_utc)} JST`;
    syncDot.className = "status-dot";
  } else if (data.status === "NOT_CONFIGURED") {
    syncLabel.textContent = "建玉同期 未設定";
    syncDot.className = "status-dot loading";
  } else {
    syncLabel.textContent = "建玉同期 要確認";
    syncDot.className = "status-dot error";
  }
}

function applyBrokerSync(data) {
  state.brokerSnapshotRevision += 1;
  applyBrokerSyncOverview(data);
  state.exitPlans = { "10m": null, "30m": null };
  state.exitSignals = { "10m": null, "30m": null };
  (data.active_plans || []).forEach((item) => {
    state.exitPlans[item.plan.horizon] = item.plan;
    state.exitSignals[item.plan.horizon] = item.exit_signal;
  });
  state.actualPositions = data.actual_positions || [];
  const closeEvent = (data.events || []).find((event) => event.type === "CLOSE_APPLIED");
  const openEvent = (data.events || []).find((event) => event.type === "OPEN_LINKED");
  if (closeEvent) showNotice("手動CLOSE約定を検知し、出口表示とポジション履歴へ反映しました。");
  else if (openEvent) showNotice("手動OPEN約定を検知し、実建玉の出口シグナルを開始しました。");
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
  const requestedBrokerSnapshotRevision = state.brokerSnapshotRevision;
  try {
    const data = await request("/api/manual/exit-plan");
    applyExitPlanStatus(data, {
      allowBrokerSnapshot: requestedBrokerSnapshotRevision === state.brokerSnapshotRevision,
    });
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
}

function positionStatusLabel(value) {
  return {
    OPEN: "保有中",
    PARTIALLY_CLOSED: "一部決済",
    CLOSED: "決済済み",
    RECHECK_REQUIRED: "要確認",
  }[value] || value;
}

async function loadPositionHistory() {
  const data = await request("/api/manual/positions?limit=100");
  if (data.broker_sync) applyBrokerSyncOverview(data.broker_sync);
  document.querySelector("#position-table").className = "table-wrap";
  document.querySelector("#position-table").innerHTML = renderTable(
    data.positions,
    [
      ["status", "状態", positionStatusLabel],
      ["side", "方向", (value) => value === "BUY" ? "Buy" : "Sell"],
      ["opened_at_utc", "OPEN時刻", jst],
      ["entry_size", "当初数量", (value) => `${Number(value || 0).toLocaleString("ja-JP")}通貨`],
      ["remaining_size", "現在数量", (value) => `${Number(value || 0).toLocaleString("ja-JP")}通貨`],
      ["average_entry_price", "平均約定価格", quote],
      ["closed_at_utc", "CLOSE時刻", jst],
      ["average_close_price", "平均決済価格", quote],
    ],
    data.broker_sync?.status === "SYNCED"
      ? "同期済みのポジション履歴はまだありません"
      : "Broker read-only同期後にポジション履歴を表示します",
  );
}

function metric(value) {
  return value == null ? "—" : Number(value).toFixed(4);
}

function percent1(value) {
  return value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
}

function interval95(low, high) {
  return low == null || high == null ? "—" : `${percent1(low)}–${percent1(high)}`;
}

function renderActionBreakdown(diagnostics) {
  const root = document.querySelector("#action-breakdown-cards");
  const breakdown = diagnostics?.action_breakdown;
  if (!root || !breakdown) return;
  const buy = breakdown.items.buy;
  const sell = breakdown.items.sell;
  const stay = breakdown.items.stay;
  const isOverall = state.validationHorizon === "overall";
  const overlapRows = (item, stayMode = false) => isOverall
    ? `<div class="confidence-row"><dt>非重複・95%区間</dt><dd>時間軸別で確認</dd></div>`
    : stayMode
      ? `<div><dt>非重複N</dt><dd>${item.non_overlapping_n}件</dd></div>
        <div><dt>非重複 上昇／下降</dt><dd>${percent1(item.non_overlapping_realized_up_rate)}／${percent1(item.non_overlapping_realized_down_rate)}</dd></div>
        <div class="confidence-row"><dt>上昇 95%区間</dt><dd>${interval95(item.up_wilson_low, item.up_wilson_high)}</dd></div>
        <div class="confidence-row"><dt>下降 95%区間</dt><dd>${interval95(item.down_wilson_low, item.down_wilson_high)}</dd></div>`
      : `<div><dt>非重複N</dt><dd>${item.non_overlapping_n}件</dd></div>
        <div><dt>非重複一致率</dt><dd>${percent1(item.non_overlapping_direction_accuracy)}</dd></div>
        <div class="confidence-row"><dt>95%区間</dt><dd>${interval95(item.wilson_low, item.wilson_high)}</dd></div>`;
  const directionalCard = (key, label, metricLabel, item) => `
    <article class="action-metric-card ${key}">
      <div class="action-card-head"><strong>${label}</strong><span>${metricLabel}</span></div>
      <div class="action-primary-rate">${percent1(item.direction_accuracy)}<small>全件</small></div>
      <dl>
        <div><dt>対象数</dt><dd>${item.sample_n}件</dd></div>
        <div><dt>対象率</dt><dd>${percent1(item.coverage)}</dd></div>
        ${overlapRows(item)}
      </dl>
    </article>`;
  root.innerHTML = `
    ${directionalCard("buy", "Buy", "上昇一致率", buy)}
    ${directionalCard("sell", "Sell", "下降一致率", sell)}
    <article class="action-metric-card stay">
      <div class="action-card-head"><strong>Stay</strong><span>実現方向</span></div>
      <div class="stay-direction-rates">
        <div><small>上昇</small><strong>${percent1(stay.realized_up_rate)}</strong></div>
        <div><small>下降</small><strong>${percent1(stay.realized_down_rate)}</strong></div>
      </div>
      <dl>
        <div><dt>対象数</dt><dd>${stay.sample_n}件</dd></div>
        <div><dt>対象率</dt><dd>${percent1(stay.coverage)}</dd></div>
        ${overlapRows(stay, true)}
      </dl>
    </article>`;
}

function renderValidationDiagnostics() {
  const diagnostics = state.validationData?.metrics?.diagnostics?.[state.validationHorizon];
  if (!diagnostics) return;
  renderActionBreakdown(diagnostics);
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
    threshold.innerHTML = `<table><thead><tr><th>買い／売り基準</th><th>全件N</th><th>対象率</th><th>全件精度</th><th>非重複N</th><th>非重複精度</th><th>95%区間</th></tr></thead><tbody>${rows
      .map(
        (row) => `<tr class="${row.is_current_v1 ? "threshold-current" : ""}"><td>${Math.round(row.buy_threshold * 100)}%／${Math.round(row.sell_threshold * 100)}%${row.is_current_v1 ? " · 現行v1" : ""}</td><td>${row.sample_n}</td><td>${percent1(row.coverage)}</td><td>${percent1(row.direction_accuracy)}</td><td>${row.non_overlapping_n == null ? "—" : row.non_overlapping_n}</td><td>${percent1(row.non_overlapping_accuracy)}</td><td>${row.wilson_low == null ? "—" : `${percent1(row.wilson_low)}–${percent1(row.wilson_high)}`}</td></tr>`,
      )
      .join("")}</tbody></table>`;
  }
  document.querySelectorAll("[data-validation-horizon]").forEach((button) => {
    button.classList.toggle("active", button.dataset.validationHorizon === state.validationHorizon);
  });
  const scope = state.validationHorizon === "overall"
    ? `全時間軸 · PROSPECTIVE ${diagnostics.raw_resolved_n}件。全体は時間軸を横断するため、非重複率と95%区間は時間軸別で確認します。`
    : `${signalByHorizon(state.validationHorizon).horizon_label} · PROSPECTIVE ${diagnostics.raw_resolved_n}件 · 非重複 ${diagnostics.non_overlapping_n}件。`;
  document.querySelector("#threshold-policy-note").textContent =
    `対象: ${scope}58%／42%はSHORT v1で固定し、診断結果から自動変更しません。`;
}

function renderRealtimeValidationDiagnostics() {
  const root = state.validationData?.realtime_rolling;
  const selected = root?.horizons?.[state.realtimeValidationHorizon];
  if (!root || !selected) return;
  const raw = selected.raw_metrics;
  const independent = selected.non_overlapping_metrics;
  const cards = [
    ["記録予測", selected.forecast_n, "1秒ごとの全件数"],
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
      ["sample_n", "毎秒N"],
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
    ? `<table><thead><tr><th>買い／売り基準</th><th>毎秒N</th><th>対象率</th><th>毎秒精度</th><th>非重複N</th><th>非重複精度</th><th>95%区間</th></tr></thead><tbody>${rows
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
    `対象: ${state.realtimeValidationHorizon} · 毎秒Brier ${metric(raw.brier)}（0.5基準比 ${metric(raw.brier_improvement_vs_0_5)}）· 非重複Brier ${metric(independent.brier)}。毎秒の全件行は互いに重なるため、独立標本ではありません。対象BIDは目標時刻から15秒以内だけを採用し、遅延時は欠測に固定します。${modeSummary}。正式シグナルへの自動昇格・判定基準の自動変更はありません。`;
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
        `<article class="metric-card"><h2>${label}</h2><dl><div><dt>確定数</dt><dd>${item.resolved_n}</dd></div><div><dt>Brier</dt><dd>${metric(item.brier)}</dd></div><div><dt>Log loss</dt><dd>${metric(item.log_loss)}</dd></div></dl></article>`,
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
  if (tab === "history") await loadHistory();
  if (tab === "record") await loadPositionHistory();
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
