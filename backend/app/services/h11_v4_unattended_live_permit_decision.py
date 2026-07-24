"""H-11 v4 unattended live permit-issuance decision layer (fake-only, unwired).

Composes the six approved conditions of the Phase 4 design (§3.2, operator
decisions §3.4) into one pure decision:

1. operator daily authorization artifact (``h11_v4_unattended_live_authorization``)
2. the existing entry gates, expressed here as an already-computed tuple of
   blocked reasons from the caller's preflight/signal evaluation
3. the persistent realized-P&L risk gate (existing, reused unchanged:
   ``app.h11_auto.runtime_safety.evaluate_risk_before_entry``)
4. supervisor heartbeat recency (existing ``DeadManResult``) and continuity
   (``h11_v4_unattended_live_heartbeat_chain``)
5. the operator persistent HALT, which in this design is the existing
   latch-only ``AutoRiskStopState.KILLED`` (``engage_risk_kill``) surfacing
   through the risk gate's ``PERSISTENT_RISK_STOPPED`` reason AND through
   this layer's own independent stop-state check
   (``PERSISTENT_RISK_STOP_STATE_NOT_ACTIVE``, which blocks on any latched
   stop state regardless of the gate's ``allowed`` flag) -- no separate HALT
   store is duplicated here
6. notification readiness, fail-closed: not ready means no permit

This function performs no I/O and **never issues a permit**. Its output is a
typed decision whose live/permit fields are pinned false and cannot be
constructed otherwise. Turning an allowed decision into an actual
``issue_v4_gmo_actual_activation_permit`` call requires a future, separately
authorized wiring step (including consuming the one-use authorization marker),
plus proof constructors that do not exist yet -- deliberately, so this layer
cannot place an order no matter what its inputs claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManResult,
    PhaseBRiskGateResult,
)
from app.services.h11_v4_unattended_live_authorization import (
    V4UnattendedLiveAuthorizationCheck,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainAssessment,
)

_JST = ZoneInfo("Asia/Tokyo")


class V4UnattendedLivePermitDecisionError(RuntimeError):
    """Fail-closed decision error containing safe labels only."""


@dataclass(frozen=True)
class V4UnattendedPermitDecision:
    allowed: bool
    blocked_reasons: tuple[str, ...]
    trading_day_jst: str
    permit_issued: bool = False
    broker_post_authorized: bool = False
    actual_post_count: int = 0
    credential_read_performed: bool = False
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool or type(self.blocked_reasons) is not tuple:
            raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_INVALID")
        for reason in self.blocked_reasons:
            _validate_safe_reason(reason)
        if self.allowed and self.blocked_reasons:
            raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_INCONSISTENT")
        if not self.allowed and not self.blocked_reasons:
            raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_INCONSISTENT")
        if (
            self.permit_issued is not False
            or self.broker_post_authorized is not False
            or type(self.actual_post_count) is not int
            or self.actual_post_count != 0
            or self.credential_read_performed is not False
            or self.broker_read_performed is not False
            or self.broker_write_performed is not False
            or self.live_ready is not False
            or self.unattended_live_supported is not False
        ):
            raise V4UnattendedLivePermitDecisionError(
                "PERMIT_DECISION_CANNOT_CLAIM_LIVE_ACTIVITY"
            )

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "blocked_reasons": list(self.blocked_reasons),
            "trading_day_jst": self.trading_day_jst,
            "permit_issued": False,
            "broker_post_authorized": False,
            "actual_post_count": 0,
            "credential_read_performed": False,
            "broker_read_performed": False,
            "broker_write_performed": False,
            "live_ready": False,
            "unattended_live_supported": False,
        }

    def __bool__(self) -> bool:
        return False


def decide_unattended_permit_issuance(
    *,
    authorization: V4UnattendedLiveAuthorizationCheck,
    risk_gate: PhaseBRiskGateResult,
    dead_man: DeadManResult,
    heartbeat_chain: V4HeartbeatChainAssessment,
    notification_ready: bool,
    entry_gate_blocked_reasons: tuple[str, ...],
    now_utc: datetime,
) -> V4UnattendedPermitDecision:
    """Evaluate all six approved conditions; every failure is fail-closed.

    ``entry_gate_blocked_reasons`` is the already-computed outcome of the
    existing signal/market/quote/spread/account preflight gates -- this layer
    trusts their evaluation but never their absence: the caller must pass the
    actual tuple, and any non-empty tuple blocks.
    """

    if (
        type(authorization) is not V4UnattendedLiveAuthorizationCheck
        or type(risk_gate) is not PhaseBRiskGateResult
        or type(dead_man) is not DeadManResult
        or type(heartbeat_chain) is not V4HeartbeatChainAssessment
        or type(notification_ready) is not bool
        or type(entry_gate_blocked_reasons) is not tuple
    ):
        raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_INPUT_INVALID")
    if now_utc.tzinfo is None:
        raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_CLOCK_INVALID")
    for reason in entry_gate_blocked_reasons:
        _validate_safe_reason(reason)

    reasons: list[str] = []
    if not authorization.authorized:
        reasons.append("OPERATOR_DAILY_AUTHORIZATION_NOT_CLEAR")
        reasons.extend(authorization.blocked_reasons)
    today_jst = now_utc.astimezone(_JST).date().isoformat()
    if authorization.trading_day_jst != today_jst:
        # Defense-in-depth: a stale check object from a previous day must not
        # authorize today even if its own flags claim it is clear.
        reasons.append("OPERATOR_AUTHORIZATION_DAY_STALE")
    if not risk_gate.allowed:
        # Unconditional sentinel: a blocked risk gate must block this decision
        # even if its own reasons tuple is (inconsistently) empty. Without
        # this, a hand-built PhaseBRiskGateResult(allowed=False,
        # blocked_reasons=()) would contribute nothing and fail OPEN --
        # exactly the operator-KILL bypass an independent Safety review
        # demonstrated (2026-07-24 VETO, fixed here).
        reasons.append("PERSISTENT_RISK_GATE_NOT_CLEAR")
        reasons.extend(risk_gate.blocked_reasons)
    if (
        type(risk_gate.stop_state) is not AutoRiskStopState
        or risk_gate.stop_state is not AutoRiskStopState.ACTIVE
    ):
        # Defense-in-depth independent of `allowed`: a latched stop state
        # blocks even when paired with a forged/inconsistent allowed=True.
        reasons.append("PERSISTENT_RISK_STOP_STATE_NOT_ACTIVE")
    if not dead_man.alive:
        reasons.append("DEAD_MAN_NOT_ALIVE")
        _validate_safe_reason(dead_man.reason_safe_label)
        reasons.append(dead_man.reason_safe_label)
    if dead_man.halt_required is not False:
        # Same inconsistency class: halt_required must independently block
        # even if paired with alive=True in a crafted result.
        reasons.append("DEAD_MAN_HALT_REQUIRED")
    if not heartbeat_chain.continuously_healthy:
        _validate_safe_reason(heartbeat_chain.reason_safe_label)
        reasons.append(heartbeat_chain.reason_safe_label)
    if notification_ready is not True:
        reasons.append("NOTIFICATION_PATH_NOT_READY")
    reasons.extend(entry_gate_blocked_reasons)
    return V4UnattendedPermitDecision(
        allowed=not reasons,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        trading_day_jst=today_jst,
    )


def _validate_safe_reason(reason: str) -> None:
    if (
        not isinstance(reason, str)
        or not reason
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
            for character in reason
        )
    ):
        raise V4UnattendedLivePermitDecisionError("PERMIT_DECISION_REASON_INVALID")
