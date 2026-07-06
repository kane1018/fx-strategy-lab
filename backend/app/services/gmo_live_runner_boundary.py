"""GMO live runner/service boundary adapter and no-POST hook summary inputs.

This module composes the GMO live kill-switch and live-enable policy into a
single adapter result used by safety review and no-POST wiring.

`bot_service` and `automation_service` now call the no-POST hook helper during
their entry paths so this summary can be observed without touching broker
transport or private API execution.
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
from app.services.risk_service import (
    GmoLiveReadinessShadowInput,
    evaluate_gmo_live_readiness_shadow,
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


@dataclass(frozen=True)
class GmoLiveServiceBoundarySummary:
    """The exact shape consumed by `bot_service` / `AutomationRunner` to decide
    no-POST GMO readiness.

    The summary is intentionally fail-closed and does not carry broker result
    payloads, credentials, or raw identifiers.
    """

    runner_summary: GmoLiveRunnerBoundaryResult
    service_hook_wired: bool = False
    service_hook_wired_into_bot_service: bool = False
    service_hook_wired_into_automation_runner: bool = False
    readiness_shadow_entry_allowed: bool = False
    readiness_shadow_settlement_allowed: bool = False
    readiness_shadow_blocked_reasons: tuple[str, ...] = ()


def build_gmo_live_service_boundary_summary(
    boundary_input: GmoLiveRunnerBoundaryInput | None = None,
) -> GmoLiveServiceBoundarySummary:
    """Service-facing hook wrapping `build_gmo_live_runner_boundary_summary`.

    Never calls `GmoFxBroker.market_order` or `official_settlement_order`,
    never imports `bot_service` or `automation_service`, never touches a
    real HTTP client, credential, or `.env`.
    """
    boundary_snapshot = boundary_input or GmoLiveRunnerBoundaryInput()
    shadow_summary = evaluate_gmo_live_readiness_shadow(
        GmoLiveReadinessShadowInput(
            risk_config=boundary_snapshot.risk_config,
            live_enable_policy_input=boundary_snapshot.live_enable_policy_input,
            kill_switch_state=boundary_snapshot.kill_switch_state,
            generic_close_attempt_detected=False,
            settlement_side_docs_status_classified=boundary_snapshot.settlement_side_docs_status_classified,
            paper_evidence_safe_label_present=True,
            operator_live_enable_declared=True,
        )
    )
    return GmoLiveServiceBoundarySummary(
        runner_summary=build_gmo_live_runner_boundary_summary(boundary_snapshot),
        readiness_shadow_entry_allowed=shadow_summary.entry_shadow_allowed,
        readiness_shadow_settlement_allowed=shadow_summary.settlement_shadow_allowed,
        readiness_shadow_blocked_reasons=shadow_summary.blocked_reasons,
    )


def build_gmo_live_service_no_post_hook_summary(
    boundary_input: GmoLiveRunnerBoundaryInput | None = None,
    *,
    invoked_from_bot_service: bool = False,
    invoked_from_automation_runner: bool = False,
) -> GmoLiveServiceBoundarySummary:
    """Build the no-POST service hook summary for a concrete caller.

    This helper is intended for service wiring that is still in safety-only mode:
    it only flips ``service_hook_wired`` / caller-specific flags so the caller can
    prove where the hook is currently attached without changing any downstream
    gate values.
    """
    base_summary = build_gmo_live_service_boundary_summary(boundary_input)
    return GmoLiveServiceBoundarySummary(
        runner_summary=base_summary.runner_summary,
        readiness_shadow_entry_allowed=base_summary.readiness_shadow_entry_allowed,
        readiness_shadow_settlement_allowed=base_summary.readiness_shadow_settlement_allowed,
        readiness_shadow_blocked_reasons=base_summary.readiness_shadow_blocked_reasons,
        service_hook_wired=True,
        service_hook_wired_into_bot_service=invoked_from_bot_service,
        service_hook_wired_into_automation_runner=invoked_from_automation_runner,
    )
