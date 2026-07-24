"""H-11 v4 unattended live orchestration (fake-only, unwired).

The thin, sequential bridge between the six-condition unattended proof
constructor (``confirm_v4_unattended_authorization_once``) and the
proof-accepting G013 entry-cycle driver
(``run_g013_actual_canary_after_unattended_authorization``).  It adds no
decision logic and no state of its own beyond the credential/client guard
and the notification wiring below — every other gate it relies on lives,
unchanged and already reviewed, inside the functions it calls.

``notification_ready`` (design doc §9.2 item 4, §14, §15) is no longer a
caller-supplied claim: it is derived here, fresh, via
``unattended_live_notification_channel_ready`` from caller-supplied real
transports — a cheap, no-I/O structural signal (design doc §14.5 Option
A). The actual real send happens separately, exactly once, before the
driver is called, via ``H11V4EnabledDualRouteNotifier``. A failed send is
itself a fail-closed condition: the daily authorization is already
consumed by that point, so this aborts rather than proceeding to the
driver.

**What the ``UNATTENDED_LIVE_ENTRY_ATTEMPTED`` send does NOT yet
guarantee (design doc §15.5, a known, accepted residual gap, not
resolved by this module):** it fires once this module's six coarse
conditions have passed and the daily authorization is consumed — not
once a permit is actually minted or an order actually reaches the
broker. The driver still has several of its own fail-closed gates left
to clear after this point (session consume/exact-binding/clean-main
re-checks, signal-postable, two dead-man-heartbeat waits) before
``issue_v4_gmo_actual_activation_permit`` ever runs, and most of those
are reported by the CLI as routine "not yet" rather than a distinct
abort. Reading this event as "an order was attempted" overstates what
it means today; it means "the six-condition gate cleared." Narrowing
this gap (e.g. moving the notify seam, or distinguishing the driver's
own pre-permit gates in the CLI's abort handling) is out of scope for
this module and the driver remains untouched by design.

``entry_gate_blocked_reasons`` remains a caller-supplied, unverifiable
claim at this layer (design doc §9.2 item 4): the CLI wiring slice
derives it from real same-cycle evaluations (§13) — never hardcode
``()`` the way this module's own tests do for fake-only isolation.

This module deliberately never references the phrase-based confirmation
functions (``confirm_v4_major_incident_resume_exact``/
``confirm_v4_current_turn_exact``), ``bind_v4_gmo_actual_runtime``,
``issue_v4_gmo_actual_activation_permit``,
``V4GmoKeychainCredentialPair``, or ``V4GmoHttpxPrivateTransport`` — the
own-source AST test pins this, discharging design doc §10.3's
bypass-prevention obligation. ``credential_pair``/``client``/
``notification_primary``/``notification_secondary`` are all required
with no default of any kind; no real Keychain access or real transport
construction exists here, and nothing is wired into any runtime, CLI, or
scheduler.
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
    confirm_v4_unattended_authorization_once,
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
from app.services.h11_v4_unattended_live_entry_notification import (
    H11V4EnabledDualRouteNotifier,
    unattended_live_notification_channel_ready,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import V4HeartbeatChainStore
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
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
    """Run at most one unattended entry cycle: verify, notify, mint, then drive.

    Sequence (§15.1, nothing else added or reordered vs. §11.6):

    1. Fail-closed runtime guard that ``credential_pair``/``client`` are not
       ``None`` — deliberately redundant with the driver's own identical
       guard, so neither layer depends on the other for this property.
    2. Derive ``notification_ready`` via
       ``unattended_live_notification_channel_ready`` from the
       caller-supplied real transports — cheap, no-I/O.
    3. ``confirm_v4_unattended_authorization_once`` with ``session.intent``,
       the caller-supplied stores, and the derived ``notification_ready``.
       This re-verifies all six conditions fresh, consumes the operator's
       daily authorization as its first write, and mints the
       resume/current-turn proof pair — or raises with nothing minted.
    4. Once proofs are minted (authorization already consumed), send the
       one real notification via ``H11V4EnabledDualRouteNotifier`` — if it
       reports ``halt_required``, raise here; the driver is never called.
    5. ``run_g013_actual_canary_after_unattended_authorization`` with those
       proofs, the session, and the caller-supplied
       ``credential_pair``/``client``.  Its internal sequence (session
       consume/refresh → permit → bind → entry cycle → monitor-to-flat) is
       unchanged from its own review.

    Known, accepted cost (§10.3/§11.6/§15.1): the daily authorization is
    consumed at step 3, so a failure at step 4 or step 5 burns the day with
    no entry — the track-wide fail-closed preference over any
    double-issuance risk.
    """

    if credential_pair is None or client is None:
        raise V4UnattendedLiveOrchestrationError(
            "UNATTENDED_ORCHESTRATION_CREDENTIAL_OR_CLIENT_REQUIRED"
        )
    notification_ready = unattended_live_notification_channel_ready(
        primary=notification_primary, secondary=notification_secondary
    )
    resume_proof, confirmation_proof = confirm_v4_unattended_authorization_once(
        intent=session.intent,
        state_root=state_root,
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man_store,
        heartbeat_chain_store=heartbeat_chain_store,
        notification_ready=notification_ready,
        entry_gate_blocked_reasons=entry_gate_blocked_reasons,
        now_utc=now_utc,
    )
    notification_result = H11V4EnabledDualRouteNotifier(
        primary=notification_primary, secondary=notification_secondary
    ).notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    if notification_result.halt_required:
        raise V4UnattendedLiveOrchestrationError(
            "UNATTENDED_ORCHESTRATION_NOTIFICATION_SEND_FAILED"
        )
    return run_g013_actual_canary_after_unattended_authorization(
        session=session,
        resume_proof=resume_proof,
        confirmation_proof=confirmation_proof,
        credential_pair=credential_pair,
        client=client,
    )
