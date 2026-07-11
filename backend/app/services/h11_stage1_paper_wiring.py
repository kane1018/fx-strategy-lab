"""H-11 v2 Stage 1 paper wiring (fake-transport-only, no-POST, fail-closed).

Wires the frozen H-11 v2 prediction contract through the preview adapter into
the existing paper auto-cycle runner, and enforces the frozen budget / stop
criteria as CODE CONSTANTS (ACTIVE policy §4: not runtime-configurable).

Frozen contract sources:
- docs/STRATEGY_H11_V2_TREND_SINGLE_EXPERT_SPEC_FREEZE_NO_POST_20260711.md
- docs/OPERATOR_SELECTED_HYPOTHESIS_POLICY_REVISION_NO_POST.md §4/§5/§8

Scope: Stage 1 paper only. No real transport, no broker surface, no POST,
no credential, no operator-owned labels. Budget stops are terminal until the
coded reload conditions are met (same-month reload is impossible by code).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import (
    FakePaperCycleTransport,
    GmoPaperAutoCycleResult,
    PaperCycleTransport,
    PaperMarketScenarioSafeInput,
    run_gmo_paper_auto_cycle_once,
)
from app.services.h11_preview_adapter import (
    H11PreviewDecision,
    map_h11_prediction_to_preview,
)
from app.strategies.h11_regime_moe import H11_V2_CONFIG_HASH, H11Prediction

# --- Frozen budget contract (operator-approved §8 values; JPY, sanitized) ---
MONTHLY_MAX_LOSS_JPY = 50_000
DAILY_MAX_LOSS_JPY = 10_000
PER_TRADE_MAX_LOSS_BOUND_JPY = 5_000
MAX_CONSECUTIVE_LOSSES_STOP = 5
MAX_TRADES_PER_DAY = 1
BUDGET_RELOAD_COOLING_DAYS = 14  # minimum cooling before any reload

# --- Frozen trading-hours contract (spec §4) ---
BLOCKED_HOURS_JST = frozenset({5, 6, 7, 8})  # outside 9:00-翌5:00 JST quote window
FRIDAY_ENTRY_CUTOFF_HOUR_JST = 21  # no new entries Fri >= 21:00 JST
WEEKDAY_FRIDAY = 4
WEEKEND_DAYS = frozenset({5, 6})


class H11Stage1StopState(str, Enum):
    ACTIVE = "ACTIVE"
    STOPPED_DAILY_BUDGET = "STOPPED_DAILY_BUDGET"
    STOPPED_MONTHLY_BUDGET = "STOPPED_MONTHLY_BUDGET"
    STOPPED_CONSECUTIVE_LOSSES = "STOPPED_CONSECUTIVE_LOSSES"
    KILLED = "KILLED"


class H11Stage1BlockReason(str, Enum):
    KILL_SWITCH_ON = "KILL_SWITCH_ON"
    SESSION_STOPPED = "SESSION_STOPPED"
    OUTSIDE_TRADING_HOURS = "OUTSIDE_TRADING_HOURS"
    WEEKEND_BLOCKED = "WEEKEND_BLOCKED"
    FRIDAY_LATE_ENTRY_BLOCKED = "FRIDAY_LATE_ENTRY_BLOCKED"
    EVENT_EXCLUSION_WINDOW = "EVENT_EXCLUSION_WINDOW"
    MAX_TRADES_PER_DAY_REACHED = "MAX_TRADES_PER_DAY_REACHED"
    PREVIEW_NOT_ACTIONABLE = "PREVIEW_NOT_ACTIONABLE"


class H11Stage1CycleStatus(str, Enum):
    CYCLE_RAN = "CYCLE_RAN"
    BLOCKED_PRE_CYCLE = "BLOCKED_PRE_CYCLE"
    NO_ORDER_HOLD = "NO_ORDER_HOLD"
    NO_ORDER_UNKNOWN_BLOCKED = "NO_ORDER_UNKNOWN_BLOCKED"


@dataclass(frozen=True)
class H11Stage1CycleResult:
    """Safe labels / counts only. Never truthy; never an execution permission."""

    status: H11Stage1CycleStatus
    stop_state: H11Stage1StopState
    preview_decision: H11PreviewDecision | None
    paper_cycle_result: GmoPaperAutoCycleResult | None
    blocked_reasons: tuple[str, ...] = ()
    discipline_violations: tuple[str, ...] = ()
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    execution_permission: bool = False

    def __bool__(self) -> bool:
        return False


class H11Stage1Session:
    """Mutable Stage 1 ledger: budgets, stops, kill. All thresholds frozen.

    A triggered stop is terminal for the session until ``operator_reload`` is
    called; ``operator_reload`` is refused inside the same calendar month and
    inside the cooling window (ACTIVE policy §4 予算再装填).
    """

    def __init__(self) -> None:
        self.stop_state = H11Stage1StopState.ACTIVE
        self.kill_switch_on = False
        self.discipline_violation_log: list[str] = []
        self._monthly_loss_jpy = 0
        self._daily_loss_jpy = 0
        self._consecutive_losses = 0
        self._trades_today = 0
        self._current_day: tuple[int, int, int] | None = None
        self._current_month: tuple[int, int] | None = None
        self._stopped_at: datetime | None = None

    # -- internal calendars ------------------------------------------------
    def _roll_calendar(self, now_jst: datetime) -> None:
        day = (now_jst.year, now_jst.month, now_jst.day)
        month = (now_jst.year, now_jst.month)
        if self._current_day != day:
            self._current_day = day
            self._daily_loss_jpy = 0
            self._trades_today = 0
            # A daily stop expires with the day; monthly/consecutive stops do not.
            if self.stop_state is H11Stage1StopState.STOPPED_DAILY_BUDGET:
                self.stop_state = H11Stage1StopState.ACTIVE
                self._stopped_at = None
        if self._current_month != month:
            self._current_month = month
            # A monthly stop does NOT auto-resume on month rollover; it requires
            # operator_reload (post-mortem + cooling + review window). The loss
            # figure that triggered the stop must survive the rollover too, or
            # the post-mortem loses its evidence -- only reset while ACTIVE.
            if self.stop_state is H11Stage1StopState.ACTIVE:
                self._monthly_loss_jpy = 0

    def _enter_stop(self, state: H11Stage1StopState, now_jst: datetime) -> None:
        self.stop_state = state
        self._stopped_at = now_jst

    # -- pre-trade gates -----------------------------------------------------
    def pre_trade_gate_reasons(
        self, now_jst: datetime, event_exclusion_active: bool
    ) -> tuple[str, ...]:
        self._roll_calendar(now_jst)
        reasons: list[str] = []
        if self.kill_switch_on:
            reasons.append(H11Stage1BlockReason.KILL_SWITCH_ON.value)
        if self.stop_state is not H11Stage1StopState.ACTIVE:
            reasons.append(H11Stage1BlockReason.SESSION_STOPPED.value)
        if now_jst.weekday() in WEEKEND_DAYS:
            reasons.append(H11Stage1BlockReason.WEEKEND_BLOCKED.value)
        if now_jst.hour in BLOCKED_HOURS_JST:
            reasons.append(H11Stage1BlockReason.OUTSIDE_TRADING_HOURS.value)
        if (
            now_jst.weekday() == WEEKDAY_FRIDAY
            and now_jst.hour >= FRIDAY_ENTRY_CUTOFF_HOUR_JST
        ):
            reasons.append(H11Stage1BlockReason.FRIDAY_LATE_ENTRY_BLOCKED.value)
        if event_exclusion_active:
            reasons.append(H11Stage1BlockReason.EVENT_EXCLUSION_WINDOW.value)
        if self._trades_today >= MAX_TRADES_PER_DAY:
            reasons.append(H11Stage1BlockReason.MAX_TRADES_PER_DAY_REACHED.value)
        return tuple(reasons)

    # -- one wired cycle ------------------------------------------------------
    def run_stage1_cycle_once(
        self,
        *,
        prediction: H11Prediction,
        now_jst: datetime,
        event_exclusion_active: bool,
        scenario: PaperMarketScenarioSafeInput,
        entry_transport: PaperCycleTransport | None = None,
        settlement_transport: PaperCycleTransport | None = None,
    ) -> H11Stage1CycleResult:
        """prediction -> adapter(v2-pinned) -> gates -> at most one paper cycle."""

        reasons = self.pre_trade_gate_reasons(now_jst, event_exclusion_active)
        if reasons:
            return H11Stage1CycleResult(
                status=H11Stage1CycleStatus.BLOCKED_PRE_CYCLE,
                stop_state=self.stop_state,
                preview_decision=None,
                paper_cycle_result=None,
                blocked_reasons=reasons,
            )

        decision = map_h11_prediction_to_preview(
            prediction, expected_config_hash=H11_V2_CONFIG_HASH
        )
        signal_value = decision.signal.value
        if signal_value == "AUTO_PREVIEW_SIGNAL_HOLD":
            return H11Stage1CycleResult(
                status=H11Stage1CycleStatus.NO_ORDER_HOLD,
                stop_state=self.stop_state,
                preview_decision=decision,
                paper_cycle_result=None,
            )
        if signal_value == "AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED":
            return H11Stage1CycleResult(
                status=H11Stage1CycleStatus.NO_ORDER_UNKNOWN_BLOCKED,
                stop_state=self.stop_state,
                preview_decision=decision,
                paper_cycle_result=None,
                blocked_reasons=(H11Stage1BlockReason.PREVIEW_NOT_ACTIONABLE.value,),
            )

        cycle = run_gmo_paper_auto_cycle_once(
            auto_preview_signal=decision.signal,
            scenario=scenario,
            entry_transport=entry_transport or FakePaperCycleTransport(),
            settlement_transport=settlement_transport or FakePaperCycleTransport(),
        )
        if cycle.paper_entry_attempt_count > 0:
            self._trades_today += 1
        return H11Stage1CycleResult(
            status=H11Stage1CycleStatus.CYCLE_RAN,
            stop_state=self.stop_state,
            preview_decision=decision,
            paper_cycle_result=cycle,
        )

    # -- outcome ledger --------------------------------------------------------
    def record_paper_trade_outcome_jpy(
        self, net_jpy_sanitized: int, now_jst: datetime
    ) -> H11Stage1StopState:
        """Record one closed paper trade outcome and evaluate frozen stops.

        Losses accumulate gross (wins never restore budget: budget is the
        price of the experiment, not a rolling P&L). A loss beyond the
        structural per-trade bound is a discipline violation (the exit
        contract should make it impossible) and is still counted in full.
        """

        self._roll_calendar(now_jst)
        loss = max(0, -int(net_jpy_sanitized))
        if loss > PER_TRADE_MAX_LOSS_BOUND_JPY:
            self.discipline_violation_log.append("PER_TRADE_LOSS_BOUND_EXCEEDED")
        if loss > 0:
            self._daily_loss_jpy += loss
            self._monthly_loss_jpy += loss
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Priority order matches h11_v3_runtime_safety.record_h11_v3_closed_result:
        # consecutive > monthly > daily. A single elif chain means at most one
        # stop reason is ever recorded per call, deterministically, instead of
        # a later check silently overwriting an earlier one in the same call.
        if (
            self._consecutive_losses >= MAX_CONSECUTIVE_LOSSES_STOP
            and self.stop_state is H11Stage1StopState.ACTIVE
        ):
            self._enter_stop(H11Stage1StopState.STOPPED_CONSECUTIVE_LOSSES, now_jst)
        elif (
            self._monthly_loss_jpy >= MONTHLY_MAX_LOSS_JPY
            and self.stop_state is not H11Stage1StopState.STOPPED_MONTHLY_BUDGET
        ):
            self._enter_stop(H11Stage1StopState.STOPPED_MONTHLY_BUDGET, now_jst)
        elif (
            self._daily_loss_jpy >= DAILY_MAX_LOSS_JPY
            and self.stop_state is H11Stage1StopState.ACTIVE
        ):
            self._enter_stop(H11Stage1StopState.STOPPED_DAILY_BUDGET, now_jst)
        return self.stop_state

    # -- reload (coded half of ACTIVE policy §4 予算再装填) ---------------------
    def operator_reload(self, now_jst: datetime) -> bool:
        """Refuse same-month reload and reloads inside the cooling window.

        Passing this coded check is NECESSARY, not sufficient: post-mortem and
        review-window approval remain operator-side procedure (docs), and this
        method must only be called as part of that procedure.
        """

        if self.stop_state in (H11Stage1StopState.ACTIVE, H11Stage1StopState.KILLED):
            return False
        if self._stopped_at is None:
            return False
        same_month = (now_jst.year, now_jst.month) == (
            self._stopped_at.year,
            self._stopped_at.month,
        )
        cooled_days = (now_jst - self._stopped_at).days
        if same_month or cooled_days < BUDGET_RELOAD_COOLING_DAYS:
            return False
        self.stop_state = H11Stage1StopState.ACTIVE
        self._stopped_at = None
        self._monthly_loss_jpy = 0
        self._daily_loss_jpy = 0
        self._consecutive_losses = 0
        return True

    def engage_kill_switch(self) -> None:
        """Kill blocks new cycles only; it never auto-closes or auto-settles."""

        self.kill_switch_on = True
        self.stop_state = H11Stage1StopState.KILLED
