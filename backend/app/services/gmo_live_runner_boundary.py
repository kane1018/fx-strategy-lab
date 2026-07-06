"""GMO live runner/bot-service boundary: adapter skeleton, not wired in yet.

`bot_service.start_bot` already hard-blocks any mode outside
`{"demo", "practice"}`, and `automation_service.AutomationRunner` is tightly
coupled to `OandaBroker` and SQLAlchemy-backed DB models
(`AutoTradeState`, `OrderLog`, `Signal`). Rewiring either of those files to
call into GMO live policy would mean touching the real, currently-working
automation loop -- out of scope for a no-POST safety Step. This module
instead provides a standalone adapter that composes the GMO live kill switch
and live enable policy into a single "would a runner be allowed to start GMO
live entry/settlement" summary.

This module is not imported by `bot_service.py` or `automation_service.py`
in this Step. That connection is deliberately deferred to a separate, later
Step so the real automation loop is not touched as a side effect of adding a
safety policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    GmoLiveRiskConfig,
    evaluate_gmo_live_enable_policy,
    evaluate_gmo_live_kill_switch,
)


@dataclass(frozen=True)
class GmoLiveRunnerBoundaryInput:
    process_just_started: bool = True
    risk_config: GmoLiveRiskConfig = GmoLiveRiskConfig()
    live_enable_policy_input: GmoLiveEnablePolicyInput = GmoLiveEnablePolicyInput()
    kill_switch_state: GmoLiveKillSwitchState = GmoLiveKillSwitchState()
    settlement_side_docs_status_classified: bool = False


@dataclass(frozen=True)
class GmoLiveRunnerBoundaryResult:
    runner_may_start_gmo_live_entry: bool
    runner_may_start_gmo_live_settlement: bool
    process_start_default_off_enforced: bool
    blocked_reasons: tuple[str, ...]
    settlement_blocked_reasons: tuple[str, ...]
    wired_into_bot_service: bool = False
    wired_into_automation_runner: bool = False


def build_gmo_live_runner_boundary_summary(
    boundary_input: GmoLiveRunnerBoundaryInput | None = None,
) -> GmoLiveRunnerBoundaryResult:
    """Compute whether a runner/bot-service COULD start GMO live entry or
    settlement, without starting anything.

    Never calls a real HTTP client, never imports bot_service or
    automation_service, and never calls any GmoFxBroker order-write method.
    """
    snapshot = boundary_input or GmoLiveRunnerBoundaryInput()
    reasons: list[str] = []
    if snapshot.process_just_started:
        reasons.append("PROCESS_START_DEFAULT_OFF")
    if not snapshot.risk_config.gmo_live_enabled:
        reasons.append("GMO_LIVE_ENABLED_FALSE")

    live_enable_result = evaluate_gmo_live_enable_policy(snapshot.live_enable_policy_input)
    if not live_enable_result.live_enable_ready:
        reasons.append("LIVE_ENABLE_POLICY_NOT_READY")

    kill_switch_decision = evaluate_gmo_live_kill_switch(snapshot.kill_switch_state)
    if not kill_switch_decision.entry_allowed:
        reasons.append("KILL_SWITCH_TRIGGERED")

    entry_blocked = bool(reasons)

    settlement_reasons = list(reasons)
    if not snapshot.settlement_side_docs_status_classified:
        settlement_reasons.append("SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED")
    if not kill_switch_decision.settlement_allowed:
        settlement_reasons.append("KILL_SWITCH_SETTLEMENT_BLOCKED")
    settlement_blocked = bool(settlement_reasons)

    return GmoLiveRunnerBoundaryResult(
        runner_may_start_gmo_live_entry=not entry_blocked,
        runner_may_start_gmo_live_settlement=not settlement_blocked,
        process_start_default_off_enforced=snapshot.process_just_started,
        blocked_reasons=tuple(reasons),
        settlement_blocked_reasons=tuple(dict.fromkeys(settlement_reasons)),
    )
