"""Finite fake-only paper runner for H11 auto Phase B."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.boundary import (
    FakeNotifier,
    FakePositionExitOutcome,
    FakePositionExitSender,
    FakeProtectedEntryOutcome,
    FakeProtectedEntrySender,
    NotificationCategory,
)
from app.h11_auto.contracts import FormalSignal, PhaseAExecutionPolicy, SignalDecision
from app.h11_auto.engine import FakeCycleStatus, H11AutoPhaseAEngine
from app.h11_auto.persistence import H11AutoProcessLock, H11AutoStateStore
from app.h11_auto.risk import PhaseASafetySnapshot, evaluate_phase_a_entry_gate
from app.h11_auto.runtime_safety import (
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
    evaluate_risk_before_entry,
    record_risk_entry_attempt,
)
from app.h11_auto.signal_adapter import adapt_sanitized_formal_signal

JST = ZoneInfo("Asia/Tokyo")


class H11AutoPaperRunnerError(RuntimeError):
    """Fail-closed bounded-run error without signal or broker values."""


class BoundedPaperRunStatus(str, Enum):
    COMPLETED_FAKE_ONLY = "COMPLETED_FAKE_ONLY"
    POSITION_PROTECTED_STOPPED = "POSITION_PROTECTED_STOPPED"
    HALTED_SAFE = "HALTED_SAFE"
    BOUNDED_LIMIT_REACHED = "BOUNDED_LIMIT_REACHED"


@dataclass(frozen=True)
class BoundedPaperRunConfig:
    maximum_signal_records: int = 100
    maximum_wall_seconds: float = 300.0
    synthetic_auto_flat: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.maximum_signal_records) is not int
            or not 1 <= self.maximum_signal_records <= 10_000
        ):
            raise H11AutoPaperRunnerError("signal record bound is invalid")
        if (
            isinstance(self.maximum_wall_seconds, bool)
            or not isinstance(self.maximum_wall_seconds, int | float)
            or not math.isfinite(self.maximum_wall_seconds)
            or not 0.1 <= self.maximum_wall_seconds <= 3_600.0
        ):
            raise H11AutoPaperRunnerError("wall-clock bound is invalid")
        if type(self.synthetic_auto_flat) is not bool:
            raise H11AutoPaperRunnerError("synthetic auto-flat flag is invalid")


@dataclass(frozen=True)
class BoundedPaperRunReport:
    status: BoundedPaperRunStatus
    input_records_seen: int
    stay_records: int
    blocked_records: int
    entry_attempts: int
    exit_attempts: int
    protected_positions: int
    flat_reconciliations: int
    halt_count: int
    process_lock_acquired: bool
    journal_valid: bool
    runtime_safety_bound: bool
    risk_stop_state: str
    dead_man_alive: bool
    notification_heartbeat_count: int
    external_notification_send_performed: bool
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    network_access_performed: bool = False
    credential_read_performed: bool = False
    resident_process: bool = False
    cron: bool = False
    actual_activation_ready: bool = False

    def __bool__(self) -> bool:
        return False


def load_sanitized_formal_signal_jsonl(
    path: Path,
    *,
    strategy_version: str,
    maximum_records: int,
) -> tuple[FormalSignal, ...]:
    """Read a local sanitized JSONL fixture; never fetch or infer signals."""

    if path.is_symlink() or not path.is_file():
        raise H11AutoPaperRunnerError("signal input must be a regular non-symlink file")
    if type(maximum_records) is not int or not 1 <= maximum_records <= 10_000:
        raise H11AutoPaperRunnerError("signal record bound is invalid")
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            raise H11AutoPaperRunnerError("signal input exceeds safe size bound")
    except OSError as error:
        raise H11AutoPaperRunnerError("signal input cannot be inspected") from error
    signals: list[FormalSignal] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if len(line.encode("utf-8")) > 65_536:
                    raise H11AutoPaperRunnerError("signal input line is too large")
                if not line.strip():
                    continue
                if len(signals) >= maximum_records:
                    raise H11AutoPaperRunnerError("signal input exceeds bounded limit")
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise H11AutoPaperRunnerError("signal input contains invalid JSON") from error
                if not isinstance(payload, dict):
                    raise H11AutoPaperRunnerError("signal input record must be an object")
                signals.append(
                    adapt_sanitized_formal_signal(
                        payload,
                        strategy_version=strategy_version,
                    )
                )
    except OSError as error:
        raise H11AutoPaperRunnerError("signal input cannot be read") from error
    return tuple(signals)


def run_bounded_paper_signals_no_post(
    *,
    signals: Iterable[FormalSignal],
    policy: PhaseAExecutionPolicy,
    state_path: Path,
    lock_path: Path,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    notifier: FakeNotifier,
    generation_label: str,
    config: BoundedPaperRunConfig | None = None,
    now_provider: Callable[[], datetime] | None = None,
    monotonic_provider: Callable[[], float] | None = None,
) -> BoundedPaperRunReport:
    """Process a finite local sequence through fake boundaries only."""

    config = config or BoundedPaperRunConfig()
    if state_path.resolve() == lock_path.resolve():
        raise H11AutoPaperRunnerError("state and lock paths must be separate")
    now = now_provider or (lambda: datetime.now(UTC))
    monotonic = monotonic_provider or time.monotonic
    start = monotonic()
    counts = {
        "seen": 0,
        "stay": 0,
        "blocked": 0,
        "entry": 0,
        "exit": 0,
        "protected": 0,
        "flat": 0,
        "halt": 0,
    }
    status = BoundedPaperRunStatus.COMPLETED_FAKE_ONLY
    store = H11AutoStateStore(state_path)
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        raise H11AutoPaperRunnerError("auto process lock is already held")
    try:
        if type(notifier) is not FakeNotifier or notifier.external_send_performed:  # noqa: E721
            raise H11AutoPaperRunnerError("paper notifier must remain fake-only")
        store.bind_run_generation(
            generation_label=generation_label,
            policy=policy,
            risk_policy_label=risk_policy.policy_label,
            risk_policy_digest=risk_policy.digest,
            dead_man_policy_label=dead_man_store.policy.policy_label,
            dead_man_policy_digest=dead_man_store.policy.digest,
        )
        risk_state = risk_store.load()
        initial_now = now()
        dead_man_store.heartbeat(heartbeat_utc=initial_now)
        entry_sender = FakeProtectedEntrySender(
            FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
        )
        exit_sender = FakePositionExitSender(FakePositionExitOutcome.ACCEPTED_AND_FLAT)
        engine = H11AutoPhaseAEngine(
            store=store,
            sender=entry_sender,
            exit_sender=exit_sender,
            notifier=notifier,
        )
        for signal in signals:
            if counts["seen"] >= config.maximum_signal_records:
                status = BoundedPaperRunStatus.BOUNDED_LIMIT_REACHED
                break
            if monotonic() - start >= config.maximum_wall_seconds:
                status = BoundedPaperRunStatus.BOUNDED_LIMIT_REACHED
                break
            counts["seen"] += 1
            cycle_now = now()
            if not notifier.notify(NotificationCategory.HEARTBEAT):
                counts["halt"] += 1
                status = BoundedPaperRunStatus.HALTED_SAFE
                break
            dead_man_store.heartbeat(heartbeat_utc=cycle_now)
            dead_man = dead_man_store.evaluate(now_utc=cycle_now)
            if not dead_man.alive:
                counts["halt"] += 1
                status = BoundedPaperRunStatus.HALTED_SAFE
                break
            safety = PhaseASafetySnapshot(
                boot_reconciled=True,
                process_lock_held=lock.held,
                data_fresh=True,
                clock_synchronized=True,
                notification_path_ready=True,
                active_intent_count=store.active_intent_count(),
                entries_today=store.entry_attempts_on_jst_day(now_utc=cycle_now),
                kill_requested=store.halt_latched(),
            )
            if signal.decision is not SignalDecision.STAY:
                risk_gate = evaluate_risk_before_entry(
                    state=risk_state,
                    policy=risk_policy,
                    cycle_day_jst=cycle_now.astimezone(JST).date().isoformat(),
                )
                if not risk_gate.allowed:
                    counts["blocked"] += 1
                    counts["halt"] += 1
                    status = BoundedPaperRunStatus.HALTED_SAFE
                    break
                phase_gate = evaluate_phase_a_entry_gate(
                    signal=signal,
                    policy=policy,
                    snapshot=safety,
                    now_utc=cycle_now,
                )
                if phase_gate.fake_cycle_allowed:
                    record_risk_entry_attempt(
                        state=risk_state,
                        policy=risk_policy,
                        cycle_day_jst=cycle_now.astimezone(JST).date().isoformat(),
                    )
                    risk_store.save(risk_state)
            result = engine.run_signal_once_synthetic(
                signal=signal,
                policy=policy,
                safety=safety,
                now_utc=cycle_now,
            )
            counts["entry"] += result.attempt_count
            if result.status is FakeCycleStatus.NO_ACTION_STAY:
                counts["stay"] += 1
                continue
            if result.status is FakeCycleStatus.BLOCKED_SAFE:
                counts["blocked"] += 1
                continue
            if result.status is FakeCycleStatus.HALTED_SAFE:
                counts["halt"] += 1
                status = BoundedPaperRunStatus.HALTED_SAFE
                break
            if result.status is FakeCycleStatus.POSITION_PROTECTED_SYNTHETIC:
                counts["protected"] += 1
                if not config.synthetic_auto_flat:
                    status = BoundedPaperRunStatus.POSITION_PROTECTED_STOPPED
                    break
                intent_id = entry_sender.calls[-1]
                exit_result = engine.complete_exit_once_synthetic(
                    intent_id=intent_id,
                    now_utc=cycle_now,
                )
                counts["exit"] += exit_result.exit_attempt_count
                if exit_result.status is FakeCycleStatus.FLAT_RECONCILED_SYNTHETIC:
                    counts["flat"] += 1
                else:
                    counts["halt"] += 1
                    status = BoundedPaperRunStatus.HALTED_SAFE
                    break
        journal_valid = store.verify_journal().valid
        final_dead_man = dead_man_store.evaluate(now_utc=now())
    finally:
        lock.release()
    return BoundedPaperRunReport(
        status=status,
        input_records_seen=counts["seen"],
        stay_records=counts["stay"],
        blocked_records=counts["blocked"],
        entry_attempts=counts["entry"],
        exit_attempts=counts["exit"],
        protected_positions=counts["protected"],
        flat_reconciliations=counts["flat"],
        halt_count=counts["halt"],
        process_lock_acquired=True,
        journal_valid=journal_valid,
        runtime_safety_bound=True,
        risk_stop_state=risk_state.stop_state,
        dead_man_alive=final_dead_man.alive,
        notification_heartbeat_count=notifier.events.count(
            NotificationCategory.HEARTBEAT
        ),
        external_notification_send_performed=notifier.external_send_performed,
    )
