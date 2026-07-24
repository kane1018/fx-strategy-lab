"""H-11 v4 unattended live entry notification (fake-only in this repo's own
tests; no real transport construction; unwired).

Discharges design doc §14's Option A: ``notification_ready`` stays a cheap,
per-cycle, no-I/O channel-health signal
(``unattended_live_notification_channel_ready``); the actual real send
happens separately, exactly once, via ``H11V4EnabledDualRouteNotifier`` --
the real-transport sibling of the existing, never-to-be-modified
``H11V4DisabledDualRouteNotifier`` (``h11_v4_notification_binding_no_post
.py``), reusing its identical try-primary-then-secondary,
``CRITICAL_EVENTS``-aware decision logic.

Neither construct in this module ever constructs a transport, reads a
credential, or performs network I/O itself. ``H11V4EnabledDualRouteNotifier``
requires real (``fake_only is False``) transports with no default -- exactly
like ``credential_pair``/``client`` everywhere else in this track -- and
only ever calls ``.send_once()`` on whatever transport object the caller
supplied. Implementing a transport that actually calls Pushover/SMTP with
real credentials remains out of scope for this assistant, for the same
reason the GMO broker transport is (design doc §14.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.h11_v4_notification_binding_no_post import (
    CRITICAL_EVENTS,
    H11V4EmailTransport,
    H11V4NotificationError,
    H11V4NotificationEvent,
    H11V4NotificationResult,
    H11V4PushoverTransport,
    build_h11_v4_pushover_request,
)


class V4UnattendedLiveNotificationError(H11V4NotificationError):
    """Fixed safe unattended-live notification failure, safe labels only."""


def unattended_live_notification_channel_ready(
    *,
    primary: H11V4PushoverTransport,
    secondary: H11V4EmailTransport,
) -> bool:
    """Cheap, per-cycle, no-I/O channel-health signal (design doc §14.5).

    Type-invalid inputs raise (a programming error must abort, not silently
    report "not ready"). A structurally valid but fake transport pair is a
    legitimate "not ready" outcome -- returns ``False``, never raises --
    since a launcher that hasn't wired real transports yet is exactly the
    condition this must block on. Never sends anything; the real send is
    ``H11V4EnabledDualRouteNotifier.notify_once``, called separately and
    exactly once when every other condition has already cleared.

    Known limitation (design doc §14.3/§14.5's accepted Option A tradeoff):
    this is a structural check only -- type plus ``fake_only is False`` --
    not a live reachability or credential-validity probe. A real-shaped
    transport pointed at expired or invalid credentials still reports
    ``True`` here; only the one-time real send at issuance time (not this
    per-cycle check) would actually discover that.
    """

    if not isinstance(primary, H11V4PushoverTransport) or not isinstance(
        secondary, H11V4EmailTransport
    ):
        raise V4UnattendedLiveNotificationError(
            "NOTIFICATION_TRANSPORT_CONTRACT_INVALID"
        )
    return primary.fake_only is False and secondary.fake_only is False


@dataclass
class H11V4EnabledDualRouteNotifier:
    """Real-transport sibling of ``H11V4DisabledDualRouteNotifier``.

    Identical try-primary-then-secondary, ``CRITICAL_EVENTS``-aware halt
    decision -- the only differences are requiring real (``fake_only is
    False``) transports with no default, and a distinct
    ``reason_safe_label``. This class never constructs a transport itself.
    """

    primary: H11V4PushoverTransport
    secondary: H11V4EmailTransport

    def __post_init__(self) -> None:
        if not isinstance(self.primary, H11V4PushoverTransport) or not isinstance(
            self.secondary, H11V4EmailTransport
        ):
            raise V4UnattendedLiveNotificationError(
                "NOTIFICATION_TRANSPORT_CONTRACT_INVALID"
            )
        if self.primary.fake_only is not False or self.secondary.fake_only is not False:
            raise V4UnattendedLiveNotificationError(
                "FAKE_NOTIFICATION_TRANSPORT_FORBIDDEN"
            )

    def notify_once(self, event: H11V4NotificationEvent) -> H11V4NotificationResult:
        request = build_h11_v4_pushover_request(event)
        primary = self.primary.send_once(request)
        secondary = self.secondary.send_once(event)
        primary_ready = primary.accepted and (
            not request.receipt_required
            or (primary.receipt_present and primary.acknowledged)
        )
        secondary_ready = bool(secondary)
        halt = not primary_ready or (event in CRITICAL_EVENTS and not secondary_ready)
        return H11V4NotificationResult(
            event=event,
            primary_ready=primary_ready,
            secondary_ready=secondary_ready,
            halt_required=halt,
            application_send_attempts=2,
            reason_safe_label=(
                "DUAL_ROUTE_READY" if not halt else "NOTIFICATION_ROUTE_NOT_READY"
            ),
        )

    def __bool__(self) -> bool:
        return False
