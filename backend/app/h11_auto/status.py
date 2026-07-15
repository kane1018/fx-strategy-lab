"""Safe read-only status projection for a separate H11 auto surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.h11_auto.report import H11AutoReportStatus, summarize_h11_auto_state


class AutoProjectionState(str, Enum):
    OFF = "OFF"
    IDLE_FAKE_ONLY = "IDLE_FAKE_ONLY"
    ACTIVE_FAKE_ONLY = "ACTIVE_FAKE_ONLY"
    HALTED_OPERATOR_REVIEW_REQUIRED = "HALTED_OPERATOR_REVIEW_REQUIRED"


@dataclass(frozen=True)
class H11AutoStatusProjection:
    state: AutoProjectionState
    phase: str
    cycle_count: int
    entry_attempts: int
    exit_attempts: int
    active_cycles: int
    halt_latched: bool
    halt_reason_code: str
    journal_valid: bool
    last_updated_at_utc: str
    generation_label: str
    strategy_version: str
    selected_horizon: str
    risk_policy_label: str
    dead_man_policy_label: str
    actual_transport_present: bool = False
    actual_post_allowed: bool = False
    broker_read_allowed: bool = False
    broker_write_allowed: bool = False
    credential_read_allowed: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


def project_h11_auto_status(state_path: Path) -> H11AutoStatusProjection:
    report = summarize_h11_auto_state(state_path)
    if report.report_status is H11AutoReportStatus.STATE_MISSING:
        state = AutoProjectionState.OFF
    elif report.halted_cycle_count:
        state = AutoProjectionState.HALTED_OPERATOR_REVIEW_REQUIRED
    elif report.active_cycle_count:
        state = AutoProjectionState.ACTIVE_FAKE_ONLY
    else:
        state = AutoProjectionState.IDLE_FAKE_ONLY
    return H11AutoStatusProjection(
        state=state,
        phase="PHASE_B_FAKE_ONLY_NO_POST",
        cycle_count=report.cycle_count,
        entry_attempts=report.entry_attempt_count,
        exit_attempts=report.exit_attempt_count,
        active_cycles=report.active_cycle_count,
        halt_latched=report.halted_cycle_count > 0,
        halt_reason_code=report.latest_halt_reason_code,
        journal_valid=report.journal_valid,
        last_updated_at_utc=report.last_updated_at_utc,
        generation_label=report.generation_label,
        strategy_version=report.strategy_version,
        selected_horizon=report.selected_horizon,
        risk_policy_label=report.risk_policy_label,
        dead_man_policy_label=report.dead_man_policy_label,
    )
