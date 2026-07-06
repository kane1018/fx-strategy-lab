"""No-POST typed permit and actual-gate readiness helpers for GMO live.

This module keeps runtime-state classification strictly to safe labels/counts and
typed objects. It intentionally does not carry raw credentials, raw ids, or
network/request payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_live_credential_boundary import GmoLiveCredentialBoundary
from app.services.gmo_live_pre_actual_readiness import (
    GmoCloseOrderSideSemanticsStatus,
    GmoPreActualSupportAnswerStatus,
    normalize_support_answer_status,
)
from app.services.gmo_live_runner_boundary import GmoLiveRunnerBoundaryResult
from app.services.risk_service import GmoLiveReadinessShadowResult


class GmoPermitKind(str, Enum):
    """Permit families for typed one-time execution classification."""

    ENTRY = "ENTRY"
    OFFICIAL_SETTLEMENT = "OFFICIAL_SETTLEMENT"


class GmoPermitStatus(str, Enum):
    """Stable labels for why a typed permit is blocked."""

    READY = "READY"
    BLOCKED_BY_OPERATOR_CONFIRMATION = "BLOCKED_BY_OPERATOR_CONFIRMATION"
    BLOCKED_BY_RUNTIME_POSITION_STATE = "BLOCKED_BY_RUNTIME_POSITION_STATE"
    BLOCKED_BY_PENDING_ORDER_CONFLICT = "BLOCKED_BY_PENDING_ORDER_CONFLICT"
    BLOCKED_BY_POST_LIMIT = "BLOCKED_BY_POST_LIMIT"
    BLOCKED_BY_SETTLEMENT_POST_NOT_ALLOWED = (
        "BLOCKED_BY_SETTLEMENT_POST_NOT_ALLOWED"
    )
    BLOCKED_BY_ENTRY_POST_NOT_ALLOWED = "BLOCKED_BY_ENTRY_POST_NOT_ALLOWED"
    BLOCKED_BY_GUARD_SETTINGS = "BLOCKED_BY_GUARD_SETTINGS"
    BLOCKED_BY_RETRY_REPOST = "BLOCKED_BY_RETRY_REPOST"
    BLOCKED_BY_MANUAL_INTERVENTION = "BLOCKED_BY_MANUAL_INTERVENTION"


@dataclass(frozen=True)
class GmoLiveEntryPermit:
    """Typed one-time permit for entry execution.

    `__bool__` remains false to avoid permit objects becoming an allow-bridge.
    """

    permit_kind: GmoPermitKind
    permit_status: GmoPermitStatus
    permit_ready: bool
    operator_signal_safe_label_exists: bool
    pre_entry_open_positions_count: int
    pre_entry_active_or_pending_order_conflict_count: int
    max_entry_post_count: int
    settlement_post_not_allowed: bool
    retry_allowed: bool
    repost_allowed: bool
    manual_intervention_performed: bool
    max_entry_post_limit: int = 1

    def __bool__(self) -> bool:
        return False

    @property
    def has_entry_preconditions(self) -> bool:
        return (
            self.permit_ready
            and self.operator_signal_safe_label_exists
            and self.settlement_post_not_allowed
            and self.pre_entry_open_positions_count == 0
            and self.pre_entry_active_or_pending_order_conflict_count == 0
            and self.max_entry_post_count == self.max_entry_post_limit
            and not self.retry_allowed
            and not self.repost_allowed
            and not self.manual_intervention_performed
        )


def build_gmo_live_entry_permit(
    *,
    operator_signal_safe_label_exists: bool,
    pre_entry_open_positions_count: int,
    pre_entry_active_or_pending_order_conflict_count: int,
    max_entry_post_count: int,
    settlement_post_not_allowed: bool,
    retry_allowed: bool,
    repost_allowed: bool,
    manual_intervention_performed: bool,
    max_entry_post_limit: int = 1,
) -> GmoLiveEntryPermit:
    """Build a typed entry permit from safe runtime signals."""

    if not operator_signal_safe_label_exists:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_OPERATOR_CONFIRMATION,
            permit_ready=False,
            operator_signal_safe_label_exists=False,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if pre_entry_open_positions_count != 0:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_RUNTIME_POSITION_STATE,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if pre_entry_active_or_pending_order_conflict_count != 0:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_PENDING_ORDER_CONFLICT,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if max_entry_post_count != 1:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_POST_LIMIT,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if not settlement_post_not_allowed:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_SETTLEMENT_POST_NOT_ALLOWED,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if retry_allowed or repost_allowed:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_RETRY_REPOST,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    if manual_intervention_performed:
        return GmoLiveEntryPermit(
            permit_kind=GmoPermitKind.ENTRY,
            permit_status=GmoPermitStatus.BLOCKED_BY_MANUAL_INTERVENTION,
            permit_ready=False,
            operator_signal_safe_label_exists=True,
            pre_entry_open_positions_count=pre_entry_open_positions_count,
            pre_entry_active_or_pending_order_conflict_count=(
                pre_entry_active_or_pending_order_conflict_count
            ),
            max_entry_post_count=max_entry_post_count,
            settlement_post_not_allowed=settlement_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_entry_post_limit=max_entry_post_limit,
        )

    return GmoLiveEntryPermit(
        permit_kind=GmoPermitKind.ENTRY,
        permit_status=GmoPermitStatus.READY,
        permit_ready=True,
        operator_signal_safe_label_exists=True,
        pre_entry_open_positions_count=pre_entry_open_positions_count,
        pre_entry_active_or_pending_order_conflict_count=(
            pre_entry_active_or_pending_order_conflict_count
        ),
        max_entry_post_count=max_entry_post_count,
        settlement_post_not_allowed=settlement_post_not_allowed,
        retry_allowed=retry_allowed,
        repost_allowed=repost_allowed,
        manual_intervention_performed=manual_intervention_performed,
        max_entry_post_limit=max_entry_post_limit,
    )


@dataclass(frozen=True)
class GmoLiveSettlementPermit:
    """Typed one-time permit for settlement execution.

    This object is separate from the entry permit and is also never coerced to a
    boolean allow-bridge.
    """

    permit_kind: GmoPermitKind
    permit_status: GmoPermitStatus
    permit_ready: bool
    pre_settlement_open_positions_count: int
    pre_settlement_active_or_pending_order_conflict_count: int
    settlement_route_required: bool
    generic_close_forbidden: bool
    side_provenance_ready: bool
    side_docs_confirmed: bool
    max_settlement_post_count: int
    entry_post_not_allowed: bool = True
    retry_allowed: bool = False
    repost_allowed: bool = False
    manual_intervention_performed: bool = False
    max_settlement_post_limit: int = 1

    def __bool__(self) -> bool:
        return False

    @property
    def has_settlement_preconditions(self) -> bool:
        return (
            self.permit_ready
            and self.settlement_route_required
            and self.generic_close_forbidden
            and self.side_provenance_ready
            and self.side_docs_confirmed
            and self.pre_settlement_open_positions_count == 1
            and self.pre_settlement_active_or_pending_order_conflict_count == 0
            and self.max_settlement_post_count == self.max_settlement_post_limit
            and self.entry_post_not_allowed
            and not self.retry_allowed
            and not self.repost_allowed
            and not self.manual_intervention_performed
        )


def build_gmo_live_settlement_permit(
    *,
    pre_settlement_open_positions_count: int,
    pre_settlement_active_or_pending_order_conflict_count: int,
    settlement_route_required: bool,
    generic_close_forbidden: bool,
    side_provenance_ready: bool,
    side_docs_confirmed: bool,
    max_settlement_post_count: int,
    entry_post_not_allowed: bool,
    retry_allowed: bool,
    repost_allowed: bool,
    manual_intervention_performed: bool,
    max_settlement_post_limit: int = 1,
) -> GmoLiveSettlementPermit:
    """Build a typed settlement permit from safe signals only."""

    if not settlement_route_required:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_GUARD_SETTINGS,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=False,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if not side_docs_confirmed:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_GUARD_SETTINGS,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=False,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if not generic_close_forbidden:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_GUARD_SETTINGS,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if not side_provenance_ready:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_GUARD_SETTINGS,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=False,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if pre_settlement_open_positions_count != 1:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_RUNTIME_POSITION_STATE,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if pre_settlement_active_or_pending_order_conflict_count != 0:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_PENDING_ORDER_CONFLICT,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if max_settlement_post_count != 1:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_POST_LIMIT,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if not entry_post_not_allowed:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_ENTRY_POST_NOT_ALLOWED,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if retry_allowed or repost_allowed:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_RETRY_REPOST,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    if manual_intervention_performed:
        return GmoLiveSettlementPermit(
            permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
            permit_status=GmoPermitStatus.BLOCKED_BY_MANUAL_INTERVENTION,
            permit_ready=False,
            pre_settlement_open_positions_count=pre_settlement_open_positions_count,
            pre_settlement_active_or_pending_order_conflict_count=(
                pre_settlement_active_or_pending_order_conflict_count
            ),
            settlement_route_required=settlement_route_required,
            generic_close_forbidden=generic_close_forbidden,
            side_provenance_ready=side_provenance_ready,
            side_docs_confirmed=side_docs_confirmed,
            max_settlement_post_count=max_settlement_post_count,
            entry_post_not_allowed=entry_post_not_allowed,
            retry_allowed=retry_allowed,
            repost_allowed=repost_allowed,
            manual_intervention_performed=manual_intervention_performed,
            max_settlement_post_limit=max_settlement_post_limit,
        )

    return GmoLiveSettlementPermit(
        permit_kind=GmoPermitKind.OFFICIAL_SETTLEMENT,
        permit_status=GmoPermitStatus.READY,
        permit_ready=True,
        pre_settlement_open_positions_count=pre_settlement_open_positions_count,
        pre_settlement_active_or_pending_order_conflict_count=(
            pre_settlement_active_or_pending_order_conflict_count
        ),
        settlement_route_required=settlement_route_required,
        generic_close_forbidden=generic_close_forbidden,
        side_provenance_ready=side_provenance_ready,
        side_docs_confirmed=side_docs_confirmed,
        max_settlement_post_count=max_settlement_post_count,
        entry_post_not_allowed=entry_post_not_allowed,
        retry_allowed=retry_allowed,
        repost_allowed=repost_allowed,
        manual_intervention_performed=manual_intervention_performed,
        max_settlement_post_limit=max_settlement_post_limit,
    )


class GmoActualEntryGateReadinessStatus(str, Enum):
    ACTUAL_ENTRY_GATE_NOT_READY = "ACTUAL_ENTRY_GATE_NOT_READY"
    ACTUAL_ENTRY_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY = (
        "ACTUAL_ENTRY_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY"
    )
    ACTUAL_ENTRY_GATE_BLOCKED_BY_OPERATOR_CONFIRMATION = (
        "ACTUAL_ENTRY_GATE_BLOCKED_BY_OPERATOR_CONFIRMATION"
    )
    ACTUAL_ENTRY_GATE_DESIGN_READY_NO_POST = "ACTUAL_ENTRY_GATE_DESIGN_READY_NO_POST"


class GmoActualSettlementGateReadinessStatus(str, Enum):
    ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_DOCS = (
        "ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_DOCS"
    )
    ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SUPPORT_NOT_RECEIVED = (
        "ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SUPPORT_NOT_RECEIVED"
    )
    ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_PROVENANCE_CORRECTION_REQUIRED = (
        "ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_PROVENANCE_CORRECTION_REQUIRED"
    )
    ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY = (
        "ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY"
    )
    ACTUAL_SETTLEMENT_GATE_DESIGN_READY_NO_POST = (
        "ACTUAL_SETTLEMENT_GATE_DESIGN_READY_NO_POST"
    )


@dataclass(frozen=True)
class GmoLiveActualEntryGateReadinessSummary:
    actual_entry_gate_ready: bool
    status: GmoActualEntryGateReadinessStatus
    blocked_reasons: tuple[str, ...]
    permit: GmoLiveEntryPermit
    service_hook_wired: bool
    runner_boundary_ready: bool
    risk_shadow_entry_allowed: bool
    credential_boundary_ready: bool
    max_consecutive_losses_selected: int | None
    gmo_live_enable_policy_ready: bool


@dataclass(frozen=True)
class GmoLiveActualSettlementGateReadinessSummary:
    actual_settlement_gate_ready: bool
    status: GmoActualSettlementGateReadinessStatus
    blocked_reasons: tuple[str, ...]
    permit: GmoLiveSettlementPermit
    service_hook_wired: bool
    runner_boundary_ready: bool
    risk_shadow_settlement_allowed: bool
    credential_boundary_ready: bool
    support_answer_status: GmoPreActualSupportAnswerStatus
    settlement_side_docs_status: GmoCloseOrderSideSemanticsStatus
    side_provenance_correction_required: bool
    settlement_side_official_docs_semantics_confirmed: bool


def build_gmo_live_actual_entry_gate_readiness_summary(
    *,
    runner_summary: GmoLiveRunnerBoundaryResult,
    shadow_result: GmoLiveReadinessShadowResult,
    credential_boundary: GmoLiveCredentialBoundary,
    permit: GmoLiveEntryPermit,
    gmo_live_enable_policy_ready: bool,
    max_consecutive_losses_selected: int | None = 2,
) -> GmoLiveActualEntryGateReadinessSummary:
    """Build the entry actual-gate readiness summary.

    This remains no-POST: the summary only reflects whether the surrounding
    run/runner/shadow/permit inputs are design-ready.
    """

    blocked_reasons: list[str] = []

    if not runner_summary.runner_may_start_gmo_live_entry:
        blocked_reasons.append("runner_entry_not_ready")

    if not shadow_result.entry_shadow_allowed:
        blocked_reasons.append("risk_shadow_gate_blocked")

    if not gmo_live_enable_policy_ready:
        blocked_reasons.append("live_enable_policy_not_ready")

    if max_consecutive_losses_selected not in (2, 3):
        blocked_reasons.append("max_consecutive_losses_selection_invalid")

    if not credential_boundary.credential_boundary_ready:
        blocked_reasons.append("credential_boundary_not_ready")

    if not permit.permit_ready:
        blocked_reasons.append("entry_permit_not_ready")

    if "credential_boundary_not_ready" in blocked_reasons:
        status = (
            GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY
        )
    elif (
        "runner_entry_not_ready" in blocked_reasons
        or "entry_permit_not_ready" in blocked_reasons
    ):
        status = (
            GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_BLOCKED_BY_OPERATOR_CONFIRMATION
        )
    elif blocked_reasons:
        status = GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_NOT_READY
    else:
        status = GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_DESIGN_READY_NO_POST

    return GmoLiveActualEntryGateReadinessSummary(
        actual_entry_gate_ready=not blocked_reasons,
        status=status,
        blocked_reasons=tuple(blocked_reasons),
        permit=permit,
        service_hook_wired=True,
        runner_boundary_ready=runner_summary.runner_may_start_gmo_live_entry,
        risk_shadow_entry_allowed=shadow_result.entry_shadow_allowed,
        credential_boundary_ready=credential_boundary.credential_boundary_ready,
        max_consecutive_losses_selected=max_consecutive_losses_selected,
        gmo_live_enable_policy_ready=gmo_live_enable_policy_ready,
    )


def _settlement_side_provenance_is_ready(
    side_status: GmoCloseOrderSideSemanticsStatus,
    support_status: GmoPreActualSupportAnswerStatus,
) -> bool:
    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED:
        return False
    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED:
        return False
    if support_status is (
        GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
    ):
        return (
            side_status
            is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE
        )
    if support_status is (
        GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE
    ):
        return (
            side_status
            is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE
        )

    return (
        side_status is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE
    )


def _settlement_side_docs_confirmed(
    side_status: GmoCloseOrderSideSemanticsStatus,
) -> bool:
    return side_status not in (
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED,
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS,
    )


def build_gmo_live_actual_settlement_gate_readiness_summary(
    *,
    runner_summary: GmoLiveRunnerBoundaryResult,
    shadow_result: GmoLiveReadinessShadowResult,
    credential_boundary: GmoLiveCredentialBoundary,
    permit: GmoLiveSettlementPermit,
    support_answer_status: GmoPreActualSupportAnswerStatus | str,
    settlement_side_status: GmoCloseOrderSideSemanticsStatus,
    max_consecutive_losses_selected: int | None = 2,
) -> GmoLiveActualSettlementGateReadinessSummary:
    """Build the settlement actual-gate readiness summary.

    This no-POST summary never raises and never decides allow/deny for any
    production request.
    """

    support_status = normalize_support_answer_status(support_answer_status)
    blocked_reasons: list[str] = []

    if not runner_summary.runner_may_start_gmo_live_settlement:
        blocked_reasons.append("runner_settlement_not_ready")

    if not shadow_result.settlement_shadow_allowed:
        blocked_reasons.append("risk_shadow_settlement_blocked")

    if max_consecutive_losses_selected not in (2, 3):
        blocked_reasons.append("max_consecutive_losses_selection_invalid")

    if not credential_boundary.credential_boundary_ready:
        blocked_reasons.append("credential_boundary_not_ready")

    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED:
        blocked_reasons.append("support_answer_not_received")

    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED:
        blocked_reasons.append("support_answer_unsafe_raw_text")

    if support_status in {
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_AMBIGUOUS,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_CONFLICTING,
    }:
        blocked_reasons.append("settlement_side_docs_ambiguous")

    if settlement_side_status in {
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED,
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS,
    }:
        blocked_reasons.append("settlement_side_docs_not_ready")

    if not permit.permit_ready:
        blocked_reasons.append("settlement_permit_not_ready")

    if support_status is (
        GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE
    ):
        blocked_reasons.append("settlement_side_provenance_correction_required")

    side_provenance_correction_required = (
        settlement_side_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE
        or (
            support_status
            is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
        )
    )

    if "credential_boundary_not_ready" in blocked_reasons:
        status = (
            GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY
        )
    elif "support_answer_not_received" in blocked_reasons:
        status = (
            GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SUPPORT_NOT_RECEIVED
        )
    elif "settlement_side_provenance_correction_required" in blocked_reasons:
        status = (
            GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_PROVENANCE_CORRECTION_REQUIRED
        )
    elif blocked_reasons:
        status = (
            GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_DOCS
        )
    else:
        status = (
            GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_DESIGN_READY_NO_POST
        )

    return GmoLiveActualSettlementGateReadinessSummary(
        actual_settlement_gate_ready=not blocked_reasons,
        status=status,
        blocked_reasons=tuple(blocked_reasons),
        permit=permit,
        service_hook_wired=True,
        runner_boundary_ready=runner_summary.runner_may_start_gmo_live_settlement,
        risk_shadow_settlement_allowed=shadow_result.settlement_shadow_allowed,
        credential_boundary_ready=credential_boundary.credential_boundary_ready,
        support_answer_status=support_status,
        settlement_side_docs_status=settlement_side_status,
        side_provenance_correction_required=side_provenance_correction_required,
        settlement_side_official_docs_semantics_confirmed=_settlement_side_docs_confirmed(
            settlement_side_status,
        ),
    )
