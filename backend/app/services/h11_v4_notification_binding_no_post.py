"""H-11 v4 Pushover-primary and email-secondary fake notification boundary.

Only safe event labels cross this interface.  There is no HTTP, SMTP,
credential, environment, Keychain, or activation binding in this module.
Critical Pushover events model one emergency request whose provider receipt
must be acknowledged; the application never retries the send itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class H11V4NotificationError(RuntimeError):
    """Fixed notification failure containing safe labels only."""


class H11V4NotificationEvent(str, Enum):
    ACTIVATION_PREPARATION_TEST = "ACTIVATION_PREPARATION_TEST"
    HEARTBEAT_LOST = "HEARTBEAT_LOST"
    PROCESS_RESTARTED = "PROCESS_RESTARTED"
    BOOT_RECONCILIATION_CLEAR = "BOOT_RECONCILIATION_CLEAR"
    BOOT_RECONCILIATION_BLOCKED = "BOOT_RECONCILIATION_BLOCKED"
    ENTRY_CONFIRMED = "ENTRY_CONFIRMED"
    PROTECTION_CONFIRMED = "PROTECTION_CONFIRMED"
    PROTECTION_MISSING = "PROTECTION_MISSING"
    PROTECTION_SIZE_MISMATCH = "PROTECTION_SIZE_MISMATCH"
    EXIT_CONFIRMED = "EXIT_CONFIRMED"
    RESULT_UNKNOWN = "RESULT_UNKNOWN"
    RISK_STOPPED = "RISK_STOPPED"
    KILL_ENGAGED = "KILL_ENGAGED"
    JOURNAL_INVALID = "JOURNAL_INVALID"
    MANUAL_POSITION_CONFLICT = "MANUAL_POSITION_CONFLICT"
    SHADOW_ACTIONABLE_OBSERVED = "SHADOW_ACTIONABLE_OBSERVED"
    SHADOW_HALT_ENGAGED = "SHADOW_HALT_ENGAGED"
    UNATTENDED_LIVE_ENTRY_ATTEMPTED = "UNATTENDED_LIVE_ENTRY_ATTEMPTED"


CRITICAL_EVENTS = frozenset(
    {
        H11V4NotificationEvent.ACTIVATION_PREPARATION_TEST,
        H11V4NotificationEvent.HEARTBEAT_LOST,
        H11V4NotificationEvent.BOOT_RECONCILIATION_BLOCKED,
        H11V4NotificationEvent.PROTECTION_MISSING,
        H11V4NotificationEvent.PROTECTION_SIZE_MISMATCH,
        H11V4NotificationEvent.RESULT_UNKNOWN,
        H11V4NotificationEvent.RISK_STOPPED,
        H11V4NotificationEvent.KILL_ENGAGED,
        H11V4NotificationEvent.JOURNAL_INVALID,
        H11V4NotificationEvent.MANUAL_POSITION_CONFLICT,
        # Sticky/permanent (no clear-or-reset path); the operator must know.
        H11V4NotificationEvent.SHADOW_HALT_ENGAGED,
    }
)


@dataclass(frozen=True)
class H11V4PushoverRequest:
    event: H11V4NotificationEvent
    emergency_priority: bool
    receipt_required: bool
    retry_seconds: int | None
    expire_seconds: int | None

    def __post_init__(self) -> None:
        critical = self.event in CRITICAL_EVENTS
        expected = (
            self.emergency_priority is critical,
            self.receipt_required is critical,
            self.retry_seconds == (60 if critical else None),
            self.expire_seconds == (3_600 if critical else None),
        )
        if not all(expected):
            raise H11V4NotificationError("PUSHOVER_REQUEST_POLICY_INVALID")

    def __bool__(self) -> bool:
        return False


def build_h11_v4_pushover_request(
    event: H11V4NotificationEvent,
) -> H11V4PushoverRequest:
    if not isinstance(event, H11V4NotificationEvent):
        raise H11V4NotificationError("NOTIFICATION_EVENT_INVALID")
    critical = event in CRITICAL_EVENTS
    return H11V4PushoverRequest(
        event=event,
        emergency_priority=critical,
        receipt_required=critical,
        retry_seconds=60 if critical else None,
        expire_seconds=3_600 if critical else None,
    )


@dataclass(frozen=True)
class H11V4PushoverDelivery:
    accepted: bool
    receipt_present: bool
    acknowledged: bool
    external_send_performed: bool = False

    def __bool__(self) -> bool:
        return False


@runtime_checkable
class H11V4PushoverTransport(Protocol):
    fake_only: bool

    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery: ...


@dataclass
class H11V4FakePushoverTransport:
    accepted: bool = True
    receipt_present: bool = True
    acknowledged: bool = True
    fake_only: bool = field(default=True, init=False)
    calls: list[H11V4NotificationEvent] = field(default_factory=list, init=False)

    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery:
        self.calls.append(request.event)
        receipt = self.receipt_present if request.receipt_required else False
        acknowledged = self.acknowledged if request.receipt_required else self.accepted
        return H11V4PushoverDelivery(
            accepted=self.accepted,
            receipt_present=receipt,
            acknowledged=acknowledged,
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V4RefusingPushoverTransport:
    fake_only: bool = True

    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery:
        del request
        raise H11V4NotificationError("PUSHOVER_TRANSPORT_DISABLED_NO_POST")

    def __bool__(self) -> bool:
        return False


@runtime_checkable
class H11V4EmailTransport(Protocol):
    fake_only: bool

    def send_once(self, event: H11V4NotificationEvent) -> bool: ...


@dataclass
class H11V4FakeEmailTransport:
    accepted: bool = True
    fake_only: bool = field(default=True, init=False)
    calls: list[H11V4NotificationEvent] = field(default_factory=list, init=False)

    def send_once(self, event: H11V4NotificationEvent) -> bool:
        self.calls.append(event)
        return self.accepted

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V4RefusingEmailTransport:
    fake_only: bool = True

    def send_once(self, event: H11V4NotificationEvent) -> bool:
        del event
        raise H11V4NotificationError("EMAIL_TRANSPORT_DISABLED_NO_POST")

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V4NotificationResult:
    event: H11V4NotificationEvent
    primary_ready: bool
    secondary_ready: bool
    halt_required: bool
    application_send_attempts: int
    reason_safe_label: str
    external_send_performed: bool = False
    credential_read: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V4DisabledDualRouteNotifier:
    """Reviewed fake-only binding; both actual routes remain absent."""

    primary: H11V4PushoverTransport = field(default_factory=H11V4RefusingPushoverTransport)
    secondary: H11V4EmailTransport = field(default_factory=H11V4RefusingEmailTransport)

    def __post_init__(self) -> None:
        if not isinstance(self.primary, H11V4PushoverTransport) or not isinstance(
            self.secondary, H11V4EmailTransport
        ):
            raise H11V4NotificationError("NOTIFICATION_TRANSPORT_CONTRACT_INVALID")
        if self.primary.fake_only is not True or self.secondary.fake_only is not True:
            raise H11V4NotificationError("ACTUAL_NOTIFICATION_TRANSPORT_FORBIDDEN")

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
                "FAKE_DUAL_ROUTE_READY" if not halt else "NOTIFICATION_ROUTE_NOT_READY"
            ),
        )

    def __bool__(self) -> bool:
        return False
