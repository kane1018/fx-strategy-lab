"""No-POST readiness aggregation for the future controlled entry POST gate.

Combines the four no-POST boundaries (sealed credential presence, ephemeral
entry permit, runtime safe-read gate, entry transport availability) into a
single readiness classification.

Critical invariant: even when every fake boundary is fully satisfied, this
summary NEVER authorizes a real POST. ``actual_entry_POST_allowed`` is
hardcoded false, ``entry_post_execution_gate_is_separate_step`` is true, and
``__bool__`` stays false. Reaching a real POST additionally requires a real
transport implementation, real credential actual-use approval, an operator
sign-off recorded per the resume design, and the 2026-07-06 incident being
formally remediated -- none of which this summary can grant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_live_entry_post_permit import GmoEntryPostPermit
from app.services.gmo_live_entry_transport import GmoEntryTransport
from app.services.gmo_live_runtime_safe_read import GmoRuntimeSafeReadGateResult
from app.services.gmo_live_sealed_credential_provider import (
    GmoSealedCredentialPresence,
)


class GmoEntryActualPostReadinessStatus(str, Enum):
    BLOCKED_BY_CREDENTIAL_BOUNDARY = "BLOCKED_BY_CREDENTIAL_BOUNDARY"
    BLOCKED_BY_HARD_GUARD_PERMIT = "BLOCKED_BY_HARD_GUARD_PERMIT"
    BLOCKED_BY_RUNTIME_SAFE_READ = "BLOCKED_BY_RUNTIME_SAFE_READ"
    BLOCKED_BY_TRANSPORT = "BLOCKED_BY_TRANSPORT"
    NO_POST_FOUNDATION_READY_STILL_NOT_ACTUAL_POST_ALLOWED = (
        "NO_POST_FOUNDATION_READY_STILL_NOT_ACTUAL_POST_ALLOWED"
    )


@dataclass(frozen=True)
class GmoEntryActualPostGateReadinessSummary:
    status: GmoEntryActualPostReadinessStatus
    no_post_foundation_ready: bool
    blocked_reasons: tuple[str, ...]
    credential_present_safe_boolean: bool
    credential_actual_use_ready: bool
    permit_usable_for_one_entry_post: bool
    runtime_safe_read_ready: bool
    entry_transport_available_fake_only: bool
    production_real_transport_implemented: bool
    actual_entry_POST_allowed: bool = False
    entry_post_execution_gate_is_separate_step: bool = True
    ai_trade_decision_performed: bool = False
    operator_confirmation_substituted: bool = False

    def __bool__(self) -> bool:
        return False


def build_gmo_entry_actual_post_gate_readiness_summary(
    *,
    credential_presence: GmoSealedCredentialPresence,
    permit: GmoEntryPostPermit,
    runtime_gate: GmoRuntimeSafeReadGateResult,
    entry_transport: GmoEntryTransport,
) -> GmoEntryActualPostGateReadinessSummary:
    """Aggregate the four no-POST boundaries; never authorize a real POST."""

    blocked_reasons: list[str] = []

    credential_ready = (
        credential_presence.credential_present_safe_boolean
        and credential_presence.credential_actual_use_ready
    )
    if not credential_ready:
        blocked_reasons.append("CREDENTIAL_ACTUAL_USE_BOUNDARY_NOT_READY")

    permit_usable = permit.usable_for_one_entry_post
    if not permit_usable:
        blocked_reasons.append("ENTRY_POST_PERMIT_NOT_USABLE")

    if not runtime_gate.ready:
        blocked_reasons.append("RUNTIME_SAFE_READ_GATE_NOT_READY")

    # A real transport is never treated as "available" in a no-POST step;
    # only a fake transport counts as the no-POST foundation being present.
    # The production real transport is unimplemented by design, so this is
    # always false here (kept explicit to force re-review if that changes).
    production_real_transport_implemented = False
    entry_transport_available_fake_only = not getattr(
        entry_transport, "is_real_transport", False
    )
    if not entry_transport_available_fake_only:
        blocked_reasons.append("ENTRY_TRANSPORT_REAL_FORBIDDEN_IN_NO_POST")

    # The production real transport is unimplemented by design; record it as a
    # standing blocker toward an actual POST regardless of fake readiness.
    blocked_reasons.append("PRODUCTION_REAL_ENTRY_TRANSPORT_NOT_IMPLEMENTED")

    no_post_foundation_ready = (
        credential_ready
        and permit_usable
        and runtime_gate.ready
        and entry_transport_available_fake_only
    )

    if not credential_ready:
        status = GmoEntryActualPostReadinessStatus.BLOCKED_BY_CREDENTIAL_BOUNDARY
    elif not permit_usable:
        status = GmoEntryActualPostReadinessStatus.BLOCKED_BY_HARD_GUARD_PERMIT
    elif not runtime_gate.ready:
        status = GmoEntryActualPostReadinessStatus.BLOCKED_BY_RUNTIME_SAFE_READ
    elif not entry_transport_available_fake_only:
        status = GmoEntryActualPostReadinessStatus.BLOCKED_BY_TRANSPORT
    else:
        status = (
            GmoEntryActualPostReadinessStatus
            .NO_POST_FOUNDATION_READY_STILL_NOT_ACTUAL_POST_ALLOWED
        )

    return GmoEntryActualPostGateReadinessSummary(
        status=status,
        no_post_foundation_ready=no_post_foundation_ready,
        blocked_reasons=tuple(blocked_reasons),
        credential_present_safe_boolean=(
            credential_presence.credential_present_safe_boolean
        ),
        credential_actual_use_ready=credential_presence.credential_actual_use_ready,
        permit_usable_for_one_entry_post=permit_usable,
        runtime_safe_read_ready=runtime_gate.ready,
        entry_transport_available_fake_only=entry_transport_available_fake_only,
        production_real_transport_implemented=production_real_transport_implemented,
        actual_entry_POST_allowed=False,
        entry_post_execution_gate_is_separate_step=True,
        ai_trade_decision_performed=False,
        operator_confirmation_substituted=False,
    )
