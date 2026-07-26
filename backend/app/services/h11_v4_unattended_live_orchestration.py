"""Persistent-arm bridge to the reviewed G013 entry-cycle driver.

The constructor re-reads persistent arm and every existing runtime gate before
minting one-use proofs. The driver receives a mandatory MARKET-only boundary
callback. After attempt and risk persistence, that callback re-reads arm and
sends ``UNATTENDED_LIVE_ENTRY_ATTEMPT_RESERVED`` on both routes before HTTP.
OFF or either notification failure produces no broker write and the
coordinated path latches HALT.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx

from app.h11_auto.runtime_safety import (
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.h11_auto.v4_gmo_canary_activation import (
    confirm_v4_persistent_arm_authorization_once as confirm_v4_unattended_authorization_once,
)
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair
from app.services.h11_v4_gmo_g013_canary import (
    V4GmoG013CanaryResult,
    V4GmoG013PreparedSession,
    run_g013_actual_canary_after_unattended_authorization,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4EmailTransport,
    H11V4NotificationEvent,
    H11V4PushoverTransport,
)
from app.services.h11_v4_unattended_live_arm_state import (
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_entry_notification import (
    H11V4EnabledDualRouteNotifier,
    unattended_live_notification_channel_ready,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import V4HeartbeatChainStore
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_live_arm_state_path,
)


class V4UnattendedLiveOrchestrationError(RuntimeError):
    """Fixed safe orchestration failure containing safe labels only."""


def run_unattended_live_entry_cycle_once(
    *,
    session: V4GmoG013PreparedSession,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    heartbeat_chain_store: V4HeartbeatChainStore,
    notification_primary: H11V4PushoverTransport,
    notification_secondary: H11V4EmailTransport,
    entry_gate_blocked_reasons: tuple[str, ...],
    credential_pair: V4GmoSealedCredentialPair,
    client: httpx.Client,
    now_utc: datetime,
) -> V4GmoG013CanaryResult:
    """Run one bounded cycle under persistent arm and fresh runtime gates."""

    if credential_pair is None or client is None:
        raise V4UnattendedLiveOrchestrationError(
            "UNATTENDED_ORCHESTRATION_CREDENTIAL_OR_CLIENT_REQUIRED"
        )
    notification_ready = unattended_live_notification_channel_ready(
        primary=notification_primary, secondary=notification_secondary
    )
    reviewed_files_digest = session.generation.implementation_digest
    resume_proof, confirmation_proof = confirm_v4_unattended_authorization_once(
        intent=session.intent,
        expected_reviewed_files_digest=reviewed_files_digest,
        state_root=state_root,
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man_store,
        heartbeat_chain_store=heartbeat_chain_store,
        notification_ready=notification_ready,
        entry_gate_blocked_reasons=entry_gate_blocked_reasons,
        now_utc=now_utc,
    )
    notifier = H11V4EnabledDualRouteNotifier(
        primary=notification_primary, secondary=notification_secondary
    )

    def _final_market_boundary() -> None:
        arm = V4UnattendedLiveArmStore(
            v4_unattended_live_arm_state_path(
                state_root=state_root,
                generation_digest=session.intent.generation_digest,
            )
        ).check(
            expected_generation_digest=session.intent.generation_digest,
            expected_reviewed_files_digest=reviewed_files_digest,
        )
        if not arm.armed:
            raise V4UnattendedLiveOrchestrationError(
                "UNATTENDED_ORCHESTRATION_FINAL_ARM_NOT_CLEAR"
            )
        notification_result = notifier.notify_once(
            H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPT_RESERVED
        )
        if (
            notification_result.halt_required
            or not notification_result.primary_ready
            or not notification_result.secondary_ready
        ):
            raise V4UnattendedLiveOrchestrationError(
                "UNATTENDED_ORCHESTRATION_NOTIFICATION_SEND_FAILED"
            )

    return run_g013_actual_canary_after_unattended_authorization(
        session=session,
        resume_proof=resume_proof,
        confirmation_proof=confirmation_proof,
        credential_pair=credential_pair,
        client=client,
        before_market_transport=_final_market_boundary,
    )
