"""H-11 v2 Stage 1 daily paper engine (no-POST, paper positions only).

Runs one Stage 1 evaluation per invocation (manual daily batch; resident
processes and cron stay forbidden until a Stage 3 policy step):

1. If a paper position is open, settle it against the H1 bars observed since
   entry using the frozen exit contract — SL / TP / 24h timeout only.
2. If flat and every frozen gate passes, evaluate the v2 prediction at the
   latest completed bar and open at most one paper position.

Paper fills use the frozen friction model (0.5 pip/side). All money numbers
are PAPER JPY amounts on the frozen fixed size (10,000 currency units).
State and journal live under the gitignored market_data/ directory; stdout
prints safe aggregates only. Nothing here touches broker/private surfaces.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from app.services.h11_preview_adapter import map_h11_prediction_to_preview
from app.services.h11_stage1_paper_wiring import (
    PER_TRADE_MAX_LOSS_BOUND_JPY,
    H11Stage1Session,
    H11Stage1StopState,
)
from app.strategies.h11_regime_moe import (
    H11_V2_CONFIG_HASH,
    H11V2Parameters,
    compute_features,
    predict_h11_v2,
)

# Frozen execution contract (v2 spec inherits v1 §4/§5).
POSITION_SIZE_UNITS = 10_000
PIP_JPY = 0.01  # USD/JPY pip in price units
FRICTION_PIPS_PER_SIDE = 0.5
SL_ATR_MULTIPLIER = 1.5
TP_R_MULTIPLE = 1.5
MAX_HOLDING_BARS = 24
JST_OFFSET = timedelta(hours=9)

# Operational layer (2026-07-14 amendment; NOT part of the frozen model spec):
# entry evaluation is code-gated to fixed JST hour slots covering the Tokyo,
# London, and New York sessions. Off-schedule manual runs still settle open
# positions (settlement is path-independent of run timing) but never evaluate
# a new entry -- this structurally removes human-timed sampling bias
# (e.g. running the batch only after seeing a large move). Duplicate runs
# inside the same slot are also skipped once the latest bar was evaluated.
ENTRY_EVAL_SLOTS_JST = (10, 16, 22)


def entry_evaluation_gate(
    now_jst: datetime,
    last_entry_eval_bar_utc: str | None,
    latest_bar_utc: str,
) -> str:
    """Return a skip reason, or "" when entry evaluation may proceed."""

    if now_jst.hour not in ENTRY_EVAL_SLOTS_JST:
        return "OFF_SCHEDULE_RUN"
    if last_entry_eval_bar_utc == latest_bar_utc:
        return "BAR_ALREADY_EVALUATED"
    return ""


@dataclass
class Stage1OpenPosition:
    direction: str  # "PAPER_LONG" / "PAPER_SHORT"
    entry_time_utc: str
    entry_price: float
    sl_price: float
    tp_price: float
    expiry_time_utc: str


@dataclass
class Stage1PersistentState:
    stage1_started_at_utc: str
    stop_state: str = H11Stage1StopState.ACTIVE.value
    kill_switch_on: bool = False
    stopped_at_utc: str | None = None
    monthly_loss_jpy: int = 0
    daily_loss_jpy: int = 0
    consecutive_losses: int = 0
    trades_today: int = 0
    current_day: str | None = None
    current_month: str | None = None
    closed_trades: int = 0
    discipline_violations: list[str] | None = None
    open_position: dict | None = None
    # Last H1 bar (UTC ISO) whose entry decision was evaluated. Used by
    # entry_evaluation_gate to skip duplicate evaluations within a slot.
    # Optional with default None so pre-amendment state files keep loading.
    last_entry_eval_bar_utc: str | None = None


def load_state(path: Path, now_utc: datetime) -> Stage1PersistentState:
    if path.exists():
        return Stage1PersistentState(**json.loads(path.read_text()))
    return Stage1PersistentState(
        stage1_started_at_utc=now_utc.isoformat(timespec="seconds"),
        discipline_violations=[],
    )


def save_state(path: Path, state: Stage1PersistentState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2))


def session_from_state(state: Stage1PersistentState) -> H11Stage1Session:
    session = H11Stage1Session()
    session.stop_state = H11Stage1StopState(state.stop_state)
    session.kill_switch_on = state.kill_switch_on
    session.discipline_violation_log = list(state.discipline_violations or [])
    session._monthly_loss_jpy = state.monthly_loss_jpy
    session._daily_loss_jpy = state.daily_loss_jpy
    session._consecutive_losses = state.consecutive_losses
    session._trades_today = state.trades_today
    if state.current_day:
        session._current_day = tuple(int(x) for x in state.current_day.split("-"))
    if state.current_month:
        session._current_month = tuple(int(x) for x in state.current_month.split("-"))
    if state.stopped_at_utc:
        session._stopped_at = datetime.fromisoformat(state.stopped_at_utc) + JST_OFFSET
    return session


def state_from_session(
    state: Stage1PersistentState, session: H11Stage1Session
) -> Stage1PersistentState:
    state.stop_state = session.stop_state.value
    state.kill_switch_on = session.kill_switch_on
    state.discipline_violations = list(session.discipline_violation_log)
    state.monthly_loss_jpy = session._monthly_loss_jpy
    state.daily_loss_jpy = session._daily_loss_jpy
    state.consecutive_losses = session._consecutive_losses
    state.trades_today = session._trades_today
    if session._current_day:
        state.current_day = "-".join(str(x) for x in session._current_day)
    if session._current_month:
        state.current_month = "-".join(str(x) for x in session._current_month)
    state.stopped_at_utc = (
        (session._stopped_at - JST_OFFSET).isoformat(timespec="seconds")
        if session._stopped_at
        else None
    )
    return state


def _friction(price_move_sign: int) -> float:
    """Signed friction applied against the trader on each side."""

    return price_move_sign * FRICTION_PIPS_PER_SIDE * PIP_JPY


def paper_pnl_jpy(direction: str, entry_price: float, exit_price: float) -> int:
    """Frozen friction model: 0.5 pip/side against the trade, fixed size."""

    if direction == "PAPER_LONG":
        effective = (exit_price - _friction(1)) - (entry_price + _friction(1))
    else:
        effective = (entry_price - _friction(1)) - (exit_price + _friction(1))
    return int(round(effective * POSITION_SIZE_UNITS))


def settle_position(
    position: Stage1OpenPosition,
    bar_times_utc: list[datetime],
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> tuple[str, float] | None:
    """Return (exit_route, exit_price) using bars strictly after entry.

    Both-sides-hit in one bar resolves to SL (conservative). Timeout settles
    at the expiry bar close. None = position stays open.
    """

    entry_time = datetime.fromisoformat(position.entry_time_utc)
    expiry_time = datetime.fromisoformat(position.expiry_time_utc)
    long = position.direction == "PAPER_LONG"
    for i, bar_time in enumerate(bar_times_utc):
        if bar_time <= entry_time:
            continue
        sl_hit = low[i] <= position.sl_price if long else high[i] >= position.sl_price
        tp_hit = high[i] >= position.tp_price if long else low[i] <= position.tp_price
        if sl_hit:
            return ("PAPER_EXIT_SL", position.sl_price)
        if tp_hit:
            return ("PAPER_EXIT_TP", position.tp_price)
        if bar_time >= expiry_time:
            return ("PAPER_EXIT_TIMEOUT", float(close[i]))
    return None


def build_entry_decision(
    parameters: H11V2Parameters,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    hour_jst: np.ndarray,
    spread_wide: np.ndarray,
    bar_times_utc: list[datetime],
) -> dict:
    """Evaluate v2 at the latest completed bar; return a safe decision dict."""

    features = compute_features(open_, high, low, close, hour_jst, spread_wide)
    row = len(close) - 1
    if not features.eligible[row]:
        return {"action": "NO_ENTRY", "reason": "FEATURES_NOT_ELIGIBLE"}
    prediction = predict_h11_v2(
        parameters, features.expert_features[row], features.regime_axes[row]
    )
    decision = map_h11_prediction_to_preview(
        prediction, expected_config_hash=H11_V2_CONFIG_HASH
    )
    signal = decision.signal.value
    if signal not in ("AUTO_PREVIEW_SIGNAL_BUY", "AUTO_PREVIEW_SIGNAL_SELL"):
        return {
            "action": "NO_ENTRY",
            "reason": decision.reason.value,
            "p_up": None if prediction.p_up is None else round(prediction.p_up, 3),
        }

    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))),
    )
    atr_24 = float(np.mean(tr[row - 23 : row + 1]))
    sl_width = SL_ATR_MULTIPLIER * atr_24
    worst_loss_jpy = sl_width * POSITION_SIZE_UNITS + 2 * FRICTION_PIPS_PER_SIDE * PIP_JPY * (
        POSITION_SIZE_UNITS
    )
    if worst_loss_jpy > PER_TRADE_MAX_LOSS_BOUND_JPY:
        return {"action": "NO_ENTRY", "reason": "PER_TRADE_BOUND_WOULD_EXCEED"}

    entry_price = float(close[row])
    long = signal == "AUTO_PREVIEW_SIGNAL_BUY"
    sl_price = entry_price - sl_width if long else entry_price + sl_width
    tp_price = (
        entry_price + TP_R_MULTIPLE * sl_width
        if long
        else entry_price - TP_R_MULTIPLE * sl_width
    )
    entry_time = bar_times_utc[row]
    return {
        "action": "ENTER",
        "reason": decision.reason.value,
        "p_up": round(prediction.p_up, 3),
        "position": Stage1OpenPosition(
            direction="PAPER_LONG" if long else "PAPER_SHORT",
            entry_time_utc=entry_time.isoformat(timespec="seconds"),
            entry_price=entry_price,
            sl_price=round(sl_price, 4),
            tp_price=round(tp_price, 4),
            expiry_time_utc=(entry_time + timedelta(hours=MAX_HOLDING_BARS)).isoformat(
                timespec="seconds"
            ),
        ),
    }
