"""Disabled H-11 v3 actual-transport boundary for review (no-POST).

This module proves the intended IFDOCO production boundary shape without
binding a sender, HTTP client, credential, environment source, or hard-guard
allow. Activation is deliberately unconstructible and the send method always
raises. A separate actual activation step must replace this disabled boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.private_api.order_builders import (
    GMO_FX_IFDOCO_ORDER_PATH,
    REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
    GmoFxPrivateRequestPlanSafeSummary,
)
from app.services.h11_v3_ifdoco_profile import H11_V3_CONFIG_HASH


class H11V3DisabledActualBoundaryError(RuntimeError):
    """Fail-closed boundary error; never carries a request, value, or ID."""


class H11V3ActualActivation:
    """Unconstructible until the separately authorized actual activation step."""

    def __init__(self) -> None:
        raise H11V3DisabledActualBoundaryError(
            "H-11 v3 actual activation is not constructible in V3_BUILD_NO_POST"
        )


@dataclass(frozen=True)
class H11V3ActualBoundaryReviewInput:
    plan_summary: GmoFxPrivateRequestPlanSafeSummary
    expected_config_hash: str
    persistent_lock_ready: bool = False
    intent_first_ready: bool = False
    risk_stop_ready: bool = False
    boot_reconcile_ready: bool = False
    notification_dead_man_ready: bool = False
    server_side_oco_spec_ready: bool = False
    broker_native_expiry_confirmed: bool = False
    partial_fill_policy_ready: bool = False
    sealed_credential_boundary_reviewed: bool = False


@dataclass(frozen=True)
class H11V3ActualBoundaryReview:
    structural_review_ready: bool
    blocked_reasons: tuple[str, ...]
    request_kind_safe_label: str
    route_safe_label: str
    actual_transport_bound: bool = False
    sender_bound: bool = False
    credential_value_present: bool = False
    hard_guard_allow_resolved: bool = False
    allow_bridge_present: bool = False
    actual_post_allowed: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3DisabledIfdocoTransport:
    """Reviewed future shape; permanently unable to send in this phase."""

    plan_summary: GmoFxPrivateRequestPlanSafeSummary
    activation: H11V3ActualActivation | None = None
    is_real_transport: bool = True

    def send_ifdoco_once_sanitized(self) -> None:
        if self.plan_summary.request_kind != REQUEST_KIND_IFDOCO_PROTECTED_ENTRY:
            raise H11V3DisabledActualBoundaryError(
                "disabled v3 boundary accepts IFDOCO protected-entry plans only"
            )
        if self.plan_summary.path != GMO_FX_IFDOCO_ORDER_PATH:
            raise H11V3DisabledActualBoundaryError(
                "disabled v3 boundary rejects non-IFDOCO routes"
            )
        if not isinstance(self.activation, H11V3ActualActivation):
            raise H11V3DisabledActualBoundaryError(
                "disabled v3 transport has no actual activation or sender binding"
            )
        raise H11V3DisabledActualBoundaryError(
            "disabled v3 transport cannot send in V3_BUILD_NO_POST"
        )

    def __bool__(self) -> bool:
        return False


def review_h11_v3_disabled_actual_boundary(
    review_input: H11V3ActualBoundaryReviewInput,
) -> H11V3ActualBoundaryReview:
    reasons: list[str] = []
    summary = review_input.plan_summary
    if summary.request_kind != REQUEST_KIND_IFDOCO_PROTECTED_ENTRY:
        reasons.append("IFDOCO_PROTECTED_ENTRY_KIND_REQUIRED")
    if summary.path != GMO_FX_IFDOCO_ORDER_PATH:
        reasons.append("IFDOCO_ROUTE_REQUIRED")
    if summary.body_field_count not in {8, 9}:
        reasons.append("IFDOCO_BODY_FIELD_SHAPE_MISMATCH")
    if review_input.expected_config_hash != H11_V3_CONFIG_HASH:
        reasons.append("V3_CONFIG_HASH_MISMATCH")
    checks = (
        (review_input.persistent_lock_ready, "PERSISTENT_LOCK_NOT_READY"),
        (review_input.intent_first_ready, "INTENT_FIRST_NOT_READY"),
        (review_input.risk_stop_ready, "RISK_STOP_NOT_READY"),
        (review_input.boot_reconcile_ready, "BOOT_RECONCILE_NOT_READY"),
        (
            review_input.notification_dead_man_ready,
            "NOTIFICATION_DEAD_MAN_NOT_READY",
        ),
        (review_input.server_side_oco_spec_ready, "SERVER_SIDE_OCO_SPEC_NOT_READY"),
        (
            review_input.broker_native_expiry_confirmed,
            "BROKER_NATIVE_EXPIRY_NOT_CONFIRMED",
        ),
        (review_input.partial_fill_policy_ready, "PARTIAL_FILL_POLICY_NOT_READY"),
        (
            review_input.sealed_credential_boundary_reviewed,
            "SEALED_CREDENTIAL_BOUNDARY_NOT_REVIEWED",
        ),
    )
    reasons.extend(reason for ready, reason in checks if not ready)
    return H11V3ActualBoundaryReview(
        structural_review_ready=not reasons,
        blocked_reasons=tuple(reasons),
        request_kind_safe_label=summary.request_kind,
        route_safe_label=summary.path,
    )
