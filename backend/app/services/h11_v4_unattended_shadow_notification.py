"""H-11 v4 unattended shadow notification decision layer (fake-only, unwired).

Decides whether a shadow cycle's outcome is worth notifying about, and
performs the dedup that keeps a sticky HALT (which every subsequent cycle
re-reports) from re-notifying every cycle. It never sends anything itself --
sending goes through the existing, generic, already-reviewed
``H11V4DisabledDualRouteNotifier``, whose default (Refusing) transports
remain structurally incapable of a real send. This module is not wired into
the shadow runner CLI; that wiring, and any real Pushover/SMTP transport, are
a separate, explicitly authorized future change.
"""

from __future__ import annotations

from app.h11_auto.v4_unattended_shadow_controller import (
    V4ShadowControllerReport,
    V4ShadowDecisionStatus,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4DisabledDualRouteNotifier,
    H11V4NotificationEvent,
    H11V4NotificationResult,
)

_NOTIFY_WORTHY_STATUS_EVENTS: dict[V4ShadowDecisionStatus, H11V4NotificationEvent] = {
    V4ShadowDecisionStatus.SHADOW_HALTED: H11V4NotificationEvent.SHADOW_HALT_ENGAGED,
    V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING: (
        H11V4NotificationEvent.SHADOW_ACTIONABLE_OBSERVED
    ),
}


class V4UnattendedShadowNotificationError(RuntimeError):
    """Fixed safe notification-decision failure; messages carry safe labels only."""


def decide_shadow_notification_event(
    *,
    report: V4ShadowControllerReport,
    previous_status: V4ShadowDecisionStatus | None,
) -> H11V4NotificationEvent | None:
    """Return the event worth notifying on, or ``None`` for a routine cycle.

    Dedup is transition-based: a status is only notify-worthy the cycle it
    first appears (i.e. it differs from ``previous_status``). A sticky HALT
    that every following cycle re-reports as ``SHADOW_HALTED`` therefore
    notifies exactly once, not once per cycle. The caller supplies
    ``previous_status`` (e.g. the prior ledger row's status); this function
    performs no I/O and holds no state of its own.
    """

    if type(report) is not V4ShadowControllerReport:
        raise V4UnattendedShadowNotificationError("SHADOW_NOTIFICATION_REPORT_INVALID")
    if previous_status is not None and type(previous_status) is not V4ShadowDecisionStatus:
        raise V4UnattendedShadowNotificationError(
            "SHADOW_NOTIFICATION_PREVIOUS_STATUS_INVALID"
        )
    if report.status == previous_status:
        return None
    return _NOTIFY_WORTHY_STATUS_EVENTS.get(report.status)


def notify_shadow_cycle_once(
    *,
    report: V4ShadowControllerReport,
    previous_status: V4ShadowDecisionStatus | None,
    notifier: H11V4DisabledDualRouteNotifier,
) -> H11V4NotificationResult | None:
    """Decide and, if notify-worthy, perform exactly one notification attempt.

    Returns ``None`` for a routine (non-notify-worthy or deduped) cycle
    without touching ``notifier`` at all. ``notifier`` must be the reviewed
    fake-only-enforcing wrapper class -- its own constructor already refuses
    any transport whose ``fake_only`` is not literally ``True``, so this
    function inherits that guarantee rather than re-implementing it.
    """

    event = decide_shadow_notification_event(report=report, previous_status=previous_status)
    if event is None:
        return None
    if type(notifier) is not H11V4DisabledDualRouteNotifier:
        raise V4UnattendedShadowNotificationError(
            "SHADOW_NOTIFICATION_NOTIFIER_CONTRACT_INVALID"
        )
    return notifier.notify_once(event)
