"""H-11 v3 persistent runtime safety primitives (no-POST).

Provides the pieces that can be completed before actual activation:

- append-only, hash-linked safe-category journal;
- persistent budget/stop/kill ledger using the frozen H-11 limits;
- fail-closed boot reconciliation over sanitized broker-state labels;
- fake-only notification boundary.

No network, broker, credential, environment, sender, or hard-guard allow path
exists here. Runtime files are local artifacts and must stay gitignored.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from app.services.h11_stage1_paper_wiring import (
    BUDGET_RELOAD_COOLING_DAYS,
    DAILY_MAX_LOSS_JPY,
    MAX_CONSECUTIVE_LOSSES_STOP,
    MAX_TRADES_PER_DAY,
    MONTHLY_MAX_LOSS_JPY,
    PER_TRADE_MAX_LOSS_BOUND_JPY,
)
from app.services.h11_v3_ifdoco_profile import H11_V3_CONFIG_HASH
from app.services.h11_v3_observed_live_state import H11V3ObservedState


class H11V3RuntimeSafetyError(RuntimeError):
    """Fail-closed error that never carries a raw broker value or ID."""


class H11V3JournalEvent(str, Enum):
    BOOT_RECONCILED = "BOOT_RECONCILED"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    ENTRY_ATTEMPT_STARTED = "ENTRY_ATTEMPT_STARTED"
    ENTRY_ACCEPTED_SAFE = "ENTRY_ACCEPTED_SAFE"
    PROTECTION_RECONCILED = "PROTECTION_RECONCILED"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    SETTLEMENT_ATTEMPT_STARTED = "SETTLEMENT_ATTEMPT_STARTED"
    FLAT_RECONCILED = "FLAT_RECONCILED"
    RISK_STOPPED = "RISK_STOPPED"
    NOTIFICATION_FAILED = "NOTIFICATION_FAILED"
    HALTED = "HALTED"


@dataclass(frozen=True)
class H11V3SafeJournalRecord:
    sequence: int
    config_hash: str
    cycle_day_jst: str
    event_category: str
    state_safe_label: str
    previous_digest: str
    digest: str

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3SafeJournalSummary:
    valid: bool
    record_count: int
    event_distribution: tuple[tuple[str, int], ...]
    final_state_safe_label: str
    actual_post_count: int = 0
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


class H11V3SafeJournal:
    """Minimal local JSONL journal containing safe labels and digests only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(
        self,
        *,
        cycle_day_jst: str,
        event: H11V3JournalEvent,
        state: H11V3ObservedState,
    ) -> H11V3SafeJournalRecord:
        _validate_day(cycle_day_jst)
        records = self.read_verified()
        previous_digest = records[-1].digest if records else "GENESIS"
        payload = {
            "sequence": len(records) + 1,
            "config_hash": H11_V3_CONFIG_HASH,
            "cycle_day_jst": cycle_day_jst,
            "event_category": event.value,
            "state_safe_label": state.value,
            "previous_digest": previous_digest,
        }
        digest = _journal_digest(payload)
        record = H11V3SafeJournalRecord(**payload, digest=digest)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def read_verified(self) -> tuple[H11V3SafeJournalRecord, ...]:
        if not self.path.exists():
            return ()
        records: list[H11V3SafeJournalRecord] = []
        previous_digest = "GENESIS"
        for expected_sequence, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            try:
                payload = json.loads(line)
                record = H11V3SafeJournalRecord(**payload)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise H11V3RuntimeSafetyError("safe journal is malformed") from error
            digest_payload = {
                "sequence": record.sequence,
                "config_hash": record.config_hash,
                "cycle_day_jst": record.cycle_day_jst,
                "event_category": record.event_category,
                "state_safe_label": record.state_safe_label,
                "previous_digest": record.previous_digest,
            }
            if (
                record.sequence != expected_sequence
                or record.config_hash != H11_V3_CONFIG_HASH
                or record.previous_digest != previous_digest
                or record.digest != _journal_digest(digest_payload)
            ):
                raise H11V3RuntimeSafetyError("safe journal verification failed")
            try:
                _validate_day(record.cycle_day_jst)
                H11V3JournalEvent(record.event_category)
                H11V3ObservedState(record.state_safe_label)
            except (H11V3RuntimeSafetyError, ValueError) as error:
                raise H11V3RuntimeSafetyError(
                    "safe journal contains an unsupported safe label"
                ) from error
            records.append(record)
            previous_digest = record.digest
        return tuple(records)

    def summary(self) -> H11V3SafeJournalSummary:
        records = self.read_verified()
        counts: dict[str, int] = {}
        for record in records:
            counts[record.event_category] = counts.get(record.event_category, 0) + 1
        return H11V3SafeJournalSummary(
            valid=True,
            record_count=len(records),
            event_distribution=tuple(sorted(counts.items())),
            final_state_safe_label=records[-1].state_safe_label if records else "EMPTY",
        )


class H11V3RiskStopState(str, Enum):
    ACTIVE = "ACTIVE"
    STOPPED_DAILY_BUDGET = "STOPPED_DAILY_BUDGET"
    STOPPED_MONTHLY_BUDGET = "STOPPED_MONTHLY_BUDGET"
    STOPPED_CONSECUTIVE_LOSSES = "STOPPED_CONSECUTIVE_LOSSES"
    KILLED = "KILLED"


@dataclass
class H11V3RiskPersistentState:
    config_hash: str = H11_V3_CONFIG_HASH
    stop_state: str = H11V3RiskStopState.ACTIVE.value
    current_day_jst: str | None = None
    current_month_jst: str | None = None
    daily_loss_jpy: int = 0
    monthly_loss_jpy: int = 0
    consecutive_losses: int = 0
    entries_today: int = 0
    stopped_on_jst: str | None = None
    discipline_violation_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3RiskGateResult:
    allowed: bool
    stop_state: H11V3RiskStopState
    blocked_reasons: tuple[str, ...]
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


class H11V3RiskStore:
    """Atomic persistent risk state; caller must hold the cycle process lock."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> H11V3RiskPersistentState:
        if not self.path.exists():
            return H11V3RiskPersistentState()
        try:
            state = H11V3RiskPersistentState(
                **json.loads(self.path.read_text(encoding="utf-8"))
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise H11V3RuntimeSafetyError("risk state is malformed") from error
        if state.config_hash != H11_V3_CONFIG_HASH:
            raise H11V3RuntimeSafetyError("risk state config hash mismatch")
        try:
            H11V3RiskStopState(state.stop_state)
        except ValueError as error:
            raise H11V3RuntimeSafetyError("risk stop state is unsupported") from error
        return state

    def save(self, state: H11V3RiskPersistentState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(state), sort_keys=True, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self.path)


def evaluate_h11_v3_risk_before_entry(
    *, state: H11V3RiskPersistentState,
    cycle_day_jst: str,
) -> H11V3RiskGateResult:
    current_day = _validate_day(cycle_day_jst)
    _roll_risk_calendar(state, current_day)
    reasons: list[str] = []
    stop_state = H11V3RiskStopState(state.stop_state)
    if stop_state is not H11V3RiskStopState.ACTIVE:
        reasons.append("RISK_SESSION_STOPPED")
    if state.entries_today >= MAX_TRADES_PER_DAY:
        reasons.append("MAX_ENTRIES_PER_DAY_REACHED")
    if state.daily_loss_jpy >= DAILY_MAX_LOSS_JPY:
        reasons.append("DAILY_LOSS_LIMIT_REACHED")
    if state.monthly_loss_jpy >= MONTHLY_MAX_LOSS_JPY:
        reasons.append("MONTHLY_LOSS_LIMIT_REACHED")
    if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES_STOP:
        reasons.append("CONSECUTIVE_LOSS_LIMIT_REACHED")
    return H11V3RiskGateResult(
        allowed=not reasons,
        stop_state=H11V3RiskStopState(state.stop_state),
        blocked_reasons=tuple(reasons),
    )


def record_h11_v3_entry_attempt(
    *, state: H11V3RiskPersistentState, cycle_day_jst: str
) -> None:
    gate = evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst=cycle_day_jst
    )
    if not gate.allowed:
        raise H11V3RuntimeSafetyError("entry attempt blocked by persistent risk gate")
    state.entries_today += 1


def record_h11_v3_closed_result(
    *,
    state: H11V3RiskPersistentState,
    cycle_day_jst: str,
    pnl_jpy_internal: int,
) -> H11V3RiskStopState:
    """Record an internal result without returning or logging the value."""

    current_day = _validate_day(cycle_day_jst)
    _roll_risk_calendar(state, current_day)
    loss = max(0, -pnl_jpy_internal)
    if loss > PER_TRADE_MAX_LOSS_BOUND_JPY:
        state.discipline_violation_count += 1
        state.stop_state = H11V3RiskStopState.KILLED.value
        state.stopped_on_jst = cycle_day_jst
        return H11V3RiskStopState.KILLED
    if loss:
        state.daily_loss_jpy += loss
        state.monthly_loss_jpy += loss
        state.consecutive_losses += 1
    else:
        state.consecutive_losses = 0

    if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES_STOP:
        _enter_risk_stop(
            state, H11V3RiskStopState.STOPPED_CONSECUTIVE_LOSSES, cycle_day_jst
        )
    elif state.monthly_loss_jpy >= MONTHLY_MAX_LOSS_JPY:
        _enter_risk_stop(
            state, H11V3RiskStopState.STOPPED_MONTHLY_BUDGET, cycle_day_jst
        )
    elif state.daily_loss_jpy >= DAILY_MAX_LOSS_JPY:
        _enter_risk_stop(
            state, H11V3RiskStopState.STOPPED_DAILY_BUDGET, cycle_day_jst
        )
    return H11V3RiskStopState(state.stop_state)


def engage_h11_v3_kill(
    *, state: H11V3RiskPersistentState, cycle_day_jst: str
) -> None:
    _validate_day(cycle_day_jst)
    _enter_risk_stop(state, H11V3RiskStopState.KILLED, cycle_day_jst)


def operator_reload_h11_v3_risk(
    *,
    state: H11V3RiskPersistentState,
    reload_day_jst: str,
    postmortem_complete: bool,
    review_approved: bool,
) -> bool:
    reload_day = _validate_day(reload_day_jst)
    stop_state = H11V3RiskStopState(state.stop_state)
    if stop_state not in {
        H11V3RiskStopState.STOPPED_MONTHLY_BUDGET,
        H11V3RiskStopState.STOPPED_CONSECUTIVE_LOSSES,
    }:
        return False
    if not postmortem_complete or not review_approved or state.stopped_on_jst is None:
        return False
    stopped_day = _validate_day(state.stopped_on_jst)
    if (reload_day - stopped_day).days < BUDGET_RELOAD_COOLING_DAYS:
        return False
    if (reload_day.year, reload_day.month) == (stopped_day.year, stopped_day.month):
        return False
    state.stop_state = H11V3RiskStopState.ACTIVE.value
    state.daily_loss_jpy = 0
    state.monthly_loss_jpy = 0
    state.consecutive_losses = 0
    state.entries_today = 0
    state.stopped_on_jst = None
    state.current_day_jst = reload_day.isoformat()
    state.current_month_jst = reload_day.strftime("%Y-%m")
    return True


class H11V3BrokerCycleSafeStatus(str, Enum):
    FLAT_CLEAR = "FLAT_CLEAR"
    PROTECTED_PENDING = "PROTECTED_PENDING"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class H11V3FillCompletenessStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class H11V3ProtectionChildrenStatus(str, Enum):
    BOTH_ACTIVE = "BOTH_ACTIVE"
    ONE_OR_MORE_MISSING = "ONE_OR_MORE_MISSING"
    UNKNOWN = "UNKNOWN"


class H11V3PendingExpiryStatus(str, Enum):
    CONFIRMED_WITHIN_SIGNAL_WINDOW = "CONFIRMED_WITHIN_SIGNAL_WINDOW"
    EXCEEDS_SIGNAL_WINDOW = "EXCEEDS_SIGNAL_WINDOW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class H11V3PostEntryReconcileInput:
    fill_status: H11V3FillCompletenessStatus = H11V3FillCompletenessStatus.UNKNOWN
    protection_status: H11V3ProtectionChildrenStatus = (
        H11V3ProtectionChildrenStatus.UNKNOWN
    )
    pending_expiry_status: H11V3PendingExpiryStatus = H11V3PendingExpiryStatus.UNKNOWN
    safe_read_performed: bool = False
    safe_read_fresh: bool = False


@dataclass(frozen=True)
class H11V3PostEntryReconcileResult:
    protected_position_ready: bool
    halt_required: bool
    reasons: tuple[str, ...]
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_entry_post_allowed: bool = False
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_h11_v3_post_entry_reconcile(
    snapshot: H11V3PostEntryReconcileInput,
) -> H11V3PostEntryReconcileResult:
    reasons: list[str] = []
    if not snapshot.safe_read_performed or not snapshot.safe_read_fresh:
        reasons.append("POST_ENTRY_SAFE_READ_MISSING_OR_STALE")
    if snapshot.fill_status is not H11V3FillCompletenessStatus.FULL:
        reasons.append(f"ENTRY_FILL_{snapshot.fill_status.value}_HALT")
    if snapshot.protection_status is not H11V3ProtectionChildrenStatus.BOTH_ACTIVE:
        reasons.append(f"PROTECTION_CHILDREN_{snapshot.protection_status.value}_HALT")
    if snapshot.pending_expiry_status is not (
        H11V3PendingExpiryStatus.CONFIRMED_WITHIN_SIGNAL_WINDOW
    ):
        reasons.append(f"PENDING_EXPIRY_{snapshot.pending_expiry_status.value}_HALT")
    return H11V3PostEntryReconcileResult(
        protected_position_ready=not reasons,
        halt_required=bool(reasons),
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class H11V3BootReconcileInput:
    local_state: H11V3ObservedState
    broker_status: H11V3BrokerCycleSafeStatus = H11V3BrokerCycleSafeStatus.UNKNOWN
    safe_read_performed: bool = False
    safe_read_fresh: bool = False


@dataclass(frozen=True)
class H11V3BootReconcileResult:
    reconciled: bool
    reason_safe_label: str
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_h11_v3_boot_reconcile(
    snapshot: H11V3BootReconcileInput,
) -> H11V3BootReconcileResult:
    if not snapshot.safe_read_performed or not snapshot.safe_read_fresh:
        return H11V3BootReconcileResult(False, "BOOT_SAFE_READ_MISSING_OR_STALE")
    expected = {
        H11V3ObservedState.READY: {H11V3BrokerCycleSafeStatus.FLAT_CLEAR},
        H11V3ObservedState.FLAT_RECONCILED: {H11V3BrokerCycleSafeStatus.FLAT_CLEAR},
        H11V3ObservedState.PROTECTED_ORDER_ACTIVE: {
            H11V3BrokerCycleSafeStatus.PROTECTED_PENDING
        },
        H11V3ObservedState.POSITION_PROTECTED: {
            H11V3BrokerCycleSafeStatus.POSITION_PROTECTED
        },
    }
    if snapshot.broker_status in expected.get(snapshot.local_state, set()):
        return H11V3BootReconcileResult(True, "BOOT_RECONCILED_SAFE")
    return H11V3BootReconcileResult(False, "BOOT_STATE_MISMATCH_OR_UNKNOWN")


class H11V3NotificationCategory(str, Enum):
    ENTRY_ATTEMPTED = "ENTRY_ATTEMPTED"
    PROTECTION_CONFIRMED = "PROTECTION_CONFIRMED"
    FLAT_CONFIRMED = "FLAT_CONFIRMED"
    UNKNOWN_HALTED = "UNKNOWN_HALTED"
    RISK_STOPPED = "RISK_STOPPED"
    DEAD_MAN_HALTED = "DEAD_MAN_HALTED"


class H11V3Notifier(Protocol):
    external_send: bool

    def notify(self, category: H11V3NotificationCategory) -> bool: ...


@dataclass
class H11V3FakeNotifier:
    external_send: bool = False
    fail: bool = False
    categories: list[H11V3NotificationCategory] | None = None

    def notify(self, category: H11V3NotificationCategory) -> bool:
        if self.categories is None:
            self.categories = []
        if self.fail:
            return False
        self.categories.append(category)
        return True

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3DeadManPersistentState:
    config_hash: str = H11_V3_CONFIG_HASH
    last_heartbeat_utc: str | None = None

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3DeadManResult:
    alive: bool
    halt_required: bool
    reason_safe_label: str
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


class H11V3DeadManStore:
    """Persistent heartbeat with no process-control or external-send surface."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def heartbeat(self, *, heartbeat_utc: datetime) -> None:
        if heartbeat_utc.tzinfo is None:
            raise H11V3RuntimeSafetyError("dead-man heartbeat must be timezone-aware")
        normalized = heartbeat_utc.astimezone(UTC)
        state = H11V3DeadManPersistentState(
            last_heartbeat_utc=normalized.isoformat(timespec="seconds")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(state), sort_keys=True, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self.path)

    def evaluate(
        self, *, now_utc: datetime, maximum_age_seconds: int
    ) -> H11V3DeadManResult:
        if now_utc.tzinfo is None or maximum_age_seconds <= 0:
            return H11V3DeadManResult(False, True, "DEAD_MAN_INPUT_INVALID")
        if not self.path.exists():
            return H11V3DeadManResult(False, True, "DEAD_MAN_HEARTBEAT_MISSING")
        try:
            state = H11V3DeadManPersistentState(
                **json.loads(self.path.read_text(encoding="utf-8"))
            )
            if state.config_hash != H11_V3_CONFIG_HASH or state.last_heartbeat_utc is None:
                raise ValueError
            heartbeat = datetime.fromisoformat(state.last_heartbeat_utc)
            if heartbeat.tzinfo is None:
                raise ValueError
            heartbeat = heartbeat.astimezone(UTC)
        except (TypeError, ValueError, json.JSONDecodeError):
            return H11V3DeadManResult(False, True, "DEAD_MAN_STATE_INVALID")
        age_seconds = (now_utc.astimezone(UTC) - heartbeat).total_seconds()
        if age_seconds < 0:
            return H11V3DeadManResult(False, True, "DEAD_MAN_HEARTBEAT_FROM_FUTURE")
        if age_seconds > maximum_age_seconds:
            return H11V3DeadManResult(False, True, "DEAD_MAN_HEARTBEAT_STALE")
        return H11V3DeadManResult(True, False, "DEAD_MAN_ALIVE")


def _roll_risk_calendar(state: H11V3RiskPersistentState, current_day: date) -> None:
    day_text = current_day.isoformat()
    month_text = current_day.strftime("%Y-%m")
    if state.current_day_jst != day_text:
        state.current_day_jst = day_text
        state.daily_loss_jpy = 0
        state.entries_today = 0
        if state.stop_state == H11V3RiskStopState.STOPPED_DAILY_BUDGET.value:
            state.stop_state = H11V3RiskStopState.ACTIVE.value
            state.stopped_on_jst = None
    if state.current_month_jst != month_text:
        state.current_month_jst = month_text
        state.monthly_loss_jpy = 0


def _enter_risk_stop(
    state: H11V3RiskPersistentState,
    stop_state: H11V3RiskStopState,
    cycle_day_jst: str,
) -> None:
    state.stop_state = stop_state.value
    state.stopped_on_jst = cycle_day_jst


def _validate_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise H11V3RuntimeSafetyError("invalid JST day") from error


def _journal_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()
