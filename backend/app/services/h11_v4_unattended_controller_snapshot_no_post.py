"""Assemble one conservative unattended-controller snapshot with no I/O."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.h11_auto.runtime_safety import PhaseBRiskPolicy, PhaseBRiskState
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    V4BoundAccountSnapshotEvidenceNoPost,
    V4BoundAccountSnapshotEvidenceNoPostError,
    validate_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_commissioning_no_post import (
    V4CommissioningArtifact,
    V4PredecessorCanaryCompletionArtifact,
    V4ShadowEvidenceArtifact,
)
from app.services.h11_v4_unattended_integrated_controller_no_post import (
    V4IntegratedControllerSnapshot,
    build_integrated_controller_evidence,
)
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmCheck

_SCHEMA = "H11_V4_UNATTENDED_CONTROLLER_OFFLINE_SNAPSHOT_NO_POST_V1"
_ZERO_DIGEST = "sha256:" + ("0" * 64)


class V4UnattendedControllerSnapshotNoPostError(ValueError):
    """Fixed safe failure for invalid local source binding."""


@dataclass(frozen=True)
class V4UnattendedControllerOfflineSources:
    reviewed_files_digest: str
    generation: V4GmoFrozenGeneration
    risk_policy: PhaseBRiskPolicy
    risk_state: PhaseBRiskState
    arm_check: V4UnattendedLiveArmCheck
    commissioning_artifact: V4CommissioningArtifact
    commissioning_shadow: V4ShadowEvidenceArtifact
    predecessor_completion: V4PredecessorCanaryCompletionArtifact
    account_snapshot_evidence: V4BoundAccountSnapshotEvidenceNoPost | None = None


def assemble_offline_controller_snapshot_no_post(
    *,
    sources: V4UnattendedControllerOfflineSources,
    now_utc: datetime,
) -> V4IntegratedControllerSnapshot:
    """Bind local artifacts while fixing unavailable live facts to safe values."""

    _validate_sources(sources, now_utc=now_utc)
    generation = sources.generation
    observed = now_utc.astimezone(UTC)
    cycle_binding = _cycle_binding(
        generation_digest=generation.digest,
        observed_at_utc=observed,
    )
    account_evidence = sources.account_snapshot_evidence
    if account_evidence is None:
        account_snapshot_known = False
        account_flat = False
        active_orders_zero = False
        account_snapshot_evidence_digest = _ZERO_DIGEST
    else:
        try:
            validate_bound_account_snapshot_evidence_no_post(
                account_evidence,
                expected_reviewed_files_digest=sources.reviewed_files_digest,
                expected_generation_digest=generation.digest,
                expected_cycle_binding_digest=cycle_binding,
                now_utc=observed,
            )
        except V4BoundAccountSnapshotEvidenceNoPostError as error:
            raise V4UnattendedControllerSnapshotNoPostError(
                "OFFLINE_CONTROLLER_ACCOUNT_SNAPSHOT_INVALID"
            ) from error
        account_snapshot_known = True
        account_flat = account_evidence.account_flat
        active_orders_zero = account_evidence.active_orders_zero
        account_snapshot_evidence_digest = account_evidence.artifact_digest
    evidence = build_integrated_controller_evidence(
        reviewed_files_digest=sources.reviewed_files_digest,
        generation_digest=generation.digest,
        cycle_binding_digest=cycle_binding,
        expected_cycle_binding_digest=cycle_binding,
        protection_cycle_binding_digest=cycle_binding,
        scheduled_exit_cycle_binding_digest=cycle_binding,
        expected_risk_policy_digest=sources.risk_policy.digest,
        arm_reviewed_files_digest=sources.arm_check.reviewed_files_digest,
        arm_generation_digest=sources.arm_check.generation_digest,
        arm_armed=sources.arm_check.armed,
        process_lock_clear=False,
        persistent_halt_clear=True,
        dead_man_clear=False,
        heartbeat_chain_clear=False,
        notification_ready=False,
        market_open=False,
        formal_signal_actionable=False,
        quote_fresh=False,
        spread_within_limit=False,
        account_snapshot_known=account_snapshot_known,
        account_flat=account_flat,
        active_orders_zero=active_orders_zero,
        exact_protection_confirmed=False,
        protection_observed_current=False,
        position_ownership_confirmed=False,
        scheduled_exit_due=False,
        transport_action_pending=False,
        result_unknown=False,
        daily_entry_count=sources.risk_state.entries_today,
        daily_loss_jpy=sources.risk_state.daily_loss_jpy_internal,
        monthly_loss_jpy=sources.risk_state.monthly_loss_jpy_internal,
        consecutive_losses=sources.risk_state.consecutive_losses,
        observed_at_utc=observed.isoformat(),
        valid_until_utc=(observed + timedelta(seconds=60)).isoformat(),
        account_snapshot_evidence_digest=account_snapshot_evidence_digest,
    )
    return V4IntegratedControllerSnapshot(
        reviewed_files_digest=sources.reviewed_files_digest,
        generation_digest=generation.digest,
        cycle_binding_digest=cycle_binding,
        expected_cycle_binding_digest=cycle_binding,
        risk_policy=sources.risk_policy,
        expected_risk_policy_digest=sources.risk_policy.digest,
        commissioning_artifact=sources.commissioning_artifact,
        commissioning_shadow=sources.commissioning_shadow,
        predecessor_completion=sources.predecessor_completion,
        account_snapshot_evidence=account_evidence,
        evidence=evidence,
    )


def _validate_sources(
    sources: V4UnattendedControllerOfflineSources,
    *,
    now_utc: datetime,
) -> None:
    if (
        type(sources) is not V4UnattendedControllerOfflineSources
        or type(sources.generation) is not V4GmoFrozenGeneration
        or type(sources.risk_policy) is not PhaseBRiskPolicy
        or type(sources.risk_state) is not PhaseBRiskState
        or type(sources.arm_check) is not V4UnattendedLiveArmCheck
        or type(sources.commissioning_artifact) is not V4CommissioningArtifact
        or type(sources.commissioning_shadow) is not V4ShadowEvidenceArtifact
        or type(sources.predecessor_completion)
        is not V4PredecessorCanaryCompletionArtifact
        or (
            sources.account_snapshot_evidence is not None
            and type(sources.account_snapshot_evidence)
            is not V4BoundAccountSnapshotEvidenceNoPost
        )
    ):
        raise V4UnattendedControllerSnapshotNoPostError(
            "OFFLINE_CONTROLLER_SOURCE_TYPE_INVALID"
        )
    if now_utc.tzinfo is None:
        raise V4UnattendedControllerSnapshotNoPostError(
            "OFFLINE_CONTROLLER_CLOCK_INVALID"
        )
    if (
        sources.generation.implementation_digest != sources.reviewed_files_digest
        or sources.generation.risk_policy_digest != sources.risk_policy.digest
        or sources.risk_state.policy_digest != sources.risk_policy.digest
        or sources.arm_check.generation_digest != sources.generation.digest
        or sources.arm_check.reviewed_files_digest != sources.reviewed_files_digest
        or sources.commissioning_artifact.generation_label
        != sources.generation.generation_label
        or sources.commissioning_artifact.reviewed_files_digest
        != sources.reviewed_files_digest
        or sources.commissioning_artifact.generation_digest
        != sources.generation.digest
        or sources.commissioning_artifact.shadow_evidence_digest
        != sources.commissioning_shadow.artifact_digest
        or sources.commissioning_artifact.shadow_reviewed_files_digest
        != sources.reviewed_files_digest
        or sources.commissioning_artifact.shadow_generation_digest
        != sources.generation.digest
        or sources.commissioning_shadow.reviewed_files_digest
        != sources.reviewed_files_digest
        or sources.commissioning_shadow.generation_digest
        != sources.generation.digest
        or sources.commissioning_artifact.prior_canary_generation_label
        != sources.predecessor_completion.prior_canary_generation_label
        or sources.commissioning_artifact.prior_canary_generation_digest
        != sources.predecessor_completion.prior_canary_generation_digest
        or sources.commissioning_artifact.prior_canary_handoff_digest
        != sources.predecessor_completion.artifact_digest
        or sources.commissioning_artifact.prior_canary_reconciliation_artifact_digest
        != sources.predecessor_completion.reconciliation_passed_marker_digest
    ):
        raise V4UnattendedControllerSnapshotNoPostError(
            "OFFLINE_CONTROLLER_SOURCE_BINDING_INVALID"
        )


def controller_cycle_binding_no_post(
    *, generation_digest: str, observed_at_utc: datetime
) -> str:
    payload = json.dumps(
        {
            "schema": _SCHEMA,
            "generation_digest": generation_digest,
            "observed_minute_utc": observed_at_utc.replace(
                second=0, microsecond=0
            ).isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


_cycle_binding = controller_cycle_binding_no_post
