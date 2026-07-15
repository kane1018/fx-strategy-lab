"""Broker-independent persistent budget and dead-man contracts for Phase B."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path


class H11AutoRuntimeSafetyError(RuntimeError):
    """Fail-closed runtime-safety error containing safe labels only."""


class AutoRiskStopState(str, Enum):
    ACTIVE = "ACTIVE"
    STOPPED_DAILY_BUDGET = "STOPPED_DAILY_BUDGET"
    STOPPED_MONTHLY_BUDGET = "STOPPED_MONTHLY_BUDGET"
    STOPPED_CONSECUTIVE_LOSSES = "STOPPED_CONSECUTIVE_LOSSES"
    KILLED = "KILLED"


@dataclass(frozen=True)
class PhaseBRiskPolicy:
    policy_label: str
    per_trade_loss_bound_jpy: int
    daily_loss_limit_jpy: int
    monthly_loss_limit_jpy: int
    maximum_consecutive_losses: int
    maximum_entries_per_day: int = 1

    def __post_init__(self) -> None:
        values = (
            self.per_trade_loss_bound_jpy,
            self.daily_loss_limit_jpy,
            self.monthly_loss_limit_jpy,
            self.maximum_consecutive_losses,
            self.maximum_entries_per_day,
        )
        if not self.policy_label.strip() or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in values
        ):
            raise H11AutoRuntimeSafetyError("risk policy is invalid")
        if not (
            self.per_trade_loss_bound_jpy <= self.daily_loss_limit_jpy
            <= self.monthly_loss_limit_jpy
        ):
            raise H11AutoRuntimeSafetyError("risk policy limits are inconsistent")
        if self.maximum_entries_per_day != 1:
            raise H11AutoRuntimeSafetyError("maximum entries per day must remain one")

    @property
    def digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class PhaseBRiskState:
    policy_digest: str
    stop_state: str = AutoRiskStopState.ACTIVE.value
    current_day_jst: str | None = None
    current_month_jst: str | None = None
    daily_loss_jpy_internal: int = 0
    monthly_loss_jpy_internal: int = 0
    consecutive_losses: int = 0
    entries_today: int = 0
    stopped_on_jst: str | None = None
    discipline_violation_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class PhaseBRiskGateResult:
    allowed: bool
    stop_state: AutoRiskStopState
    blocked_reasons: tuple[str, ...]
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


class PhaseBRiskStore:
    def __init__(self, path: Path, *, policy: PhaseBRiskPolicy) -> None:
        self.path = path
        self.policy = policy

    def load(self) -> PhaseBRiskState:
        if self.path.is_symlink():
            raise H11AutoRuntimeSafetyError("risk state path must not be a symlink")
        if not self.path.exists():
            return PhaseBRiskState(policy_digest=self.policy.digest)
        if not self.path.is_file():
            raise H11AutoRuntimeSafetyError("risk state path must be a regular file")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            state = PhaseBRiskState(**payload)
        except (OSError, TypeError, json.JSONDecodeError) as error:
            raise H11AutoRuntimeSafetyError("risk state is malformed") from error
        _validate_risk_state(state, self.policy)
        return state

    def save(self, state: PhaseBRiskState) -> None:
        _validate_risk_state(state, self.policy)
        if self.path.is_symlink():
            raise H11AutoRuntimeSafetyError("risk state path must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        if temporary.is_symlink():
            raise H11AutoRuntimeSafetyError("risk temporary path must not be a symlink")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(state), sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as error:
            raise H11AutoRuntimeSafetyError("risk state cannot be saved") from error


def evaluate_risk_before_entry(
    *,
    state: PhaseBRiskState,
    policy: PhaseBRiskPolicy,
    cycle_day_jst: str,
) -> PhaseBRiskGateResult:
    _validate_risk_state(state, policy)
    current_day = _validate_day(cycle_day_jst)
    _roll_calendar(state, current_day)
    reasons: list[str] = []
    stop = AutoRiskStopState(state.stop_state)
    if stop is not AutoRiskStopState.ACTIVE:
        reasons.append("PERSISTENT_RISK_STOPPED")
    if state.entries_today >= policy.maximum_entries_per_day:
        reasons.append("MAX_ENTRIES_PER_DAY_REACHED")
    if state.daily_loss_jpy_internal >= policy.daily_loss_limit_jpy:
        reasons.append("DAILY_LOSS_LIMIT_REACHED")
    if state.monthly_loss_jpy_internal >= policy.monthly_loss_limit_jpy:
        reasons.append("MONTHLY_LOSS_LIMIT_REACHED")
    if state.consecutive_losses >= policy.maximum_consecutive_losses:
        reasons.append("CONSECUTIVE_LOSS_LIMIT_REACHED")
    return PhaseBRiskGateResult(
        allowed=not reasons,
        stop_state=AutoRiskStopState(state.stop_state),
        blocked_reasons=tuple(reasons),
    )


def record_risk_entry_attempt(
    *, state: PhaseBRiskState, policy: PhaseBRiskPolicy, cycle_day_jst: str
) -> None:
    gate = evaluate_risk_before_entry(
        state=state,
        policy=policy,
        cycle_day_jst=cycle_day_jst,
    )
    if not gate.allowed:
        raise H11AutoRuntimeSafetyError("entry attempt blocked by persistent risk gate")
    state.entries_today += 1


def record_closed_result(
    *,
    state: PhaseBRiskState,
    policy: PhaseBRiskPolicy,
    cycle_day_jst: str,
    pnl_jpy_internal: int,
) -> AutoRiskStopState:
    if isinstance(pnl_jpy_internal, bool) or not isinstance(pnl_jpy_internal, int):
        raise H11AutoRuntimeSafetyError("closed result is invalid")
    _validate_risk_state(state, policy)
    existing_stop = AutoRiskStopState(state.stop_state)
    current_day = _validate_day(cycle_day_jst)
    _roll_calendar(state, current_day)
    loss = max(0, -pnl_jpy_internal)
    if loss > policy.per_trade_loss_bound_jpy:
        state.discipline_violation_count += 1
        _stop(state, AutoRiskStopState.KILLED, cycle_day_jst)
        return AutoRiskStopState.KILLED
    if loss > 0:
        state.daily_loss_jpy_internal += loss
        state.monthly_loss_jpy_internal += loss
        state.consecutive_losses += 1
    else:
        state.consecutive_losses = 0
    if existing_stop is not AutoRiskStopState.ACTIVE:
        return existing_stop
    if state.consecutive_losses >= policy.maximum_consecutive_losses:
        _stop(state, AutoRiskStopState.STOPPED_CONSECUTIVE_LOSSES, cycle_day_jst)
    elif state.monthly_loss_jpy_internal >= policy.monthly_loss_limit_jpy:
        _stop(state, AutoRiskStopState.STOPPED_MONTHLY_BUDGET, cycle_day_jst)
    elif state.daily_loss_jpy_internal >= policy.daily_loss_limit_jpy:
        _stop(state, AutoRiskStopState.STOPPED_DAILY_BUDGET, cycle_day_jst)
    return AutoRiskStopState(state.stop_state)


def engage_risk_kill(*, state: PhaseBRiskState, cycle_day_jst: str) -> None:
    _validate_day(cycle_day_jst)
    _stop(state, AutoRiskStopState.KILLED, cycle_day_jst)


@dataclass(frozen=True)
class DeadManPolicy:
    policy_label: str
    maximum_heartbeat_age_seconds: int

    def __post_init__(self) -> None:
        if (
            not self.policy_label.strip()
            or isinstance(self.maximum_heartbeat_age_seconds, bool)
            or not isinstance(self.maximum_heartbeat_age_seconds, int)
            or self.maximum_heartbeat_age_seconds <= 0
        ):
            raise H11AutoRuntimeSafetyError("dead-man policy is invalid")

    @property
    def digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class DeadManResult:
    alive: bool
    halt_required: bool
    reason_safe_label: str
    heartbeat_age_seconds: float | None
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


class DeadManStore:
    def __init__(self, path: Path, *, policy: DeadManPolicy) -> None:
        self.path = path
        self.policy = policy

    def heartbeat(self, *, heartbeat_utc: datetime) -> None:
        if heartbeat_utc.tzinfo is None:
            raise H11AutoRuntimeSafetyError("heartbeat must be timezone-aware")
        if self.path.is_symlink():
            raise H11AutoRuntimeSafetyError("dead-man path must not be a symlink")
        normalized = heartbeat_utc.astimezone(UTC)
        if self.path.exists():
            previous = self._load_heartbeat()
            if normalized < previous:
                raise H11AutoRuntimeSafetyError("heartbeat time must not move backwards")
        payload = {
            "policy_digest": self.policy.digest,
            "last_heartbeat_utc": normalized.isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        if temporary.is_symlink():
            raise H11AutoRuntimeSafetyError("dead-man temporary path must not be a symlink")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as error:
            raise H11AutoRuntimeSafetyError("dead-man state cannot be saved") from error

    def evaluate(self, *, now_utc: datetime) -> DeadManResult:
        if now_utc.tzinfo is None:
            return _dead("DEAD_MAN_INPUT_INVALID")
        if self.path.is_symlink() or not self.path.is_file():
            return _dead("DEAD_MAN_HEARTBEAT_MISSING")
        try:
            heartbeat = self._load_heartbeat()
        except H11AutoRuntimeSafetyError:
            return _dead("DEAD_MAN_STATE_INVALID")
        age = (
            now_utc.astimezone(UTC) - heartbeat.astimezone(UTC)
        ).total_seconds()
        if age < 0:
            return _dead("DEAD_MAN_HEARTBEAT_FROM_FUTURE", age)
        if age > self.policy.maximum_heartbeat_age_seconds:
            return _dead("DEAD_MAN_HEARTBEAT_STALE", age)
        return DeadManResult(
            alive=True,
            halt_required=False,
            reason_safe_label="DEAD_MAN_ALIVE",
            heartbeat_age_seconds=age,
        )

    def _load_heartbeat(self) -> datetime:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("policy_digest") != self.policy.digest:
                raise ValueError
            heartbeat = datetime.fromisoformat(payload["last_heartbeat_utc"])
            if heartbeat.tzinfo is None:
                raise ValueError
            return heartbeat.astimezone(UTC)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise H11AutoRuntimeSafetyError("dead-man state is invalid") from error


def _validate_risk_state(state: PhaseBRiskState, policy: PhaseBRiskPolicy) -> None:
    if state.policy_digest != policy.digest:
        raise H11AutoRuntimeSafetyError("risk state policy mismatch")
    try:
        AutoRiskStopState(state.stop_state)
    except ValueError as error:
        raise H11AutoRuntimeSafetyError("risk stop state is invalid") from error
    counters = (
        state.daily_loss_jpy_internal,
        state.monthly_loss_jpy_internal,
        state.consecutive_losses,
        state.entries_today,
        state.discipline_violation_count,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counters
    ):
        raise H11AutoRuntimeSafetyError("risk state counters are invalid")


def _roll_calendar(state: PhaseBRiskState, current_day: date) -> None:
    day_text = current_day.isoformat()
    month_text = current_day.strftime("%Y-%m")
    if state.current_day_jst != day_text:
        state.current_day_jst = day_text
        state.daily_loss_jpy_internal = 0
        state.entries_today = 0
        if state.stop_state == AutoRiskStopState.STOPPED_DAILY_BUDGET.value:
            state.stop_state = AutoRiskStopState.ACTIVE.value
            state.stopped_on_jst = None
    if state.current_month_jst != month_text:
        state.current_month_jst = month_text
        if state.stop_state == AutoRiskStopState.ACTIVE.value:
            state.monthly_loss_jpy_internal = 0


def _stop(
    state: PhaseBRiskState, stop: AutoRiskStopState, cycle_day_jst: str
) -> None:
    state.stop_state = stop.value
    state.stopped_on_jst = cycle_day_jst


def _validate_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise H11AutoRuntimeSafetyError("JST day is invalid") from error


def _dead(reason: str, age: float | None = None) -> DeadManResult:
    return DeadManResult(
        alive=False,
        halt_required=True,
        reason_safe_label=reason,
        heartbeat_age_seconds=age,
    )
