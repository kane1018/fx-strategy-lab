"""Safe one-shot projection of Phase B budget and dead-man state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
    evaluate_risk_before_entry,
)


@dataclass(frozen=True)
class H11AutoRuntimeStatusProjection:
    risk_stop_state: str
    entry_allowed_by_risk: bool
    risk_blocked_reasons: tuple[str, ...]
    entries_today: int
    consecutive_losses: int
    daily_limit_reached: bool
    monthly_limit_reached: bool
    consecutive_limit_reached: bool
    discipline_violation_count: int
    dead_man_alive: bool
    dead_man_reason: str
    heartbeat_age_seconds: float | None
    halt_required: bool
    actual_post_allowed: bool = False
    broker_read_allowed: bool = False
    broker_write_allowed: bool = False
    credential_read_allowed: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


def project_runtime_safety_status(
    *,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    cycle_day_jst: str,
    now_utc: datetime,
) -> H11AutoRuntimeStatusProjection:
    state = risk_store.load()
    gate = evaluate_risk_before_entry(
        state=state,
        policy=risk_policy,
        cycle_day_jst=cycle_day_jst,
    )
    dead_man = dead_man_store.evaluate(now_utc=now_utc)
    return H11AutoRuntimeStatusProjection(
        risk_stop_state=gate.stop_state.value,
        entry_allowed_by_risk=gate.allowed,
        risk_blocked_reasons=gate.blocked_reasons,
        entries_today=state.entries_today,
        consecutive_losses=state.consecutive_losses,
        daily_limit_reached=(
            state.daily_loss_jpy_internal >= risk_policy.daily_loss_limit_jpy
        ),
        monthly_limit_reached=(
            state.monthly_loss_jpy_internal >= risk_policy.monthly_loss_limit_jpy
        ),
        consecutive_limit_reached=(
            state.consecutive_losses >= risk_policy.maximum_consecutive_losses
        ),
        discipline_violation_count=state.discipline_violation_count,
        dead_man_alive=dead_man.alive,
        dead_man_reason=dead_man.reason_safe_label,
        heartbeat_age_seconds=dead_man.heartbeat_age_seconds,
        halt_required=(
            gate.stop_state is not AutoRiskStopState.ACTIVE
            or dead_man.halt_required
        ),
    )
