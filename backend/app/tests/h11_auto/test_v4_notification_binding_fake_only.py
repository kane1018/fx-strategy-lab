from __future__ import annotations

import inspect

import pytest

from app.services import h11_v4_notification_binding_no_post as notification_module
from app.services.h11_v4_notification_binding_no_post import (
    H11V4DisabledDualRouteNotifier,
    H11V4FakeEmailTransport,
    H11V4FakePushoverTransport,
    H11V4NotificationError,
    H11V4NotificationEvent,
    build_h11_v4_pushover_request,
)


def test_critical_event_uses_one_emergency_request_and_both_fake_routes() -> None:
    primary = H11V4FakePushoverTransport()
    secondary = H11V4FakeEmailTransport()
    notifier = H11V4DisabledDualRouteNotifier(primary=primary, secondary=secondary)
    result = notifier.notify_once(H11V4NotificationEvent.RESULT_UNKNOWN)
    request = build_h11_v4_pushover_request(H11V4NotificationEvent.RESULT_UNKNOWN)

    assert request.emergency_priority is True
    assert request.receipt_required is True
    assert request.retry_seconds == 60
    assert request.expire_seconds == 3_600
    assert result.primary_ready is True
    assert result.secondary_ready is True
    assert result.halt_required is False
    assert result.application_send_attempts == 2
    assert result.external_send_performed is False
    assert result.credential_read is False
    assert result.actual_post_count == 0
    assert primary.calls == [H11V4NotificationEvent.RESULT_UNKNOWN]
    assert secondary.calls == [H11V4NotificationEvent.RESULT_UNKNOWN]


def test_missing_critical_ack_or_secondary_route_requires_halt() -> None:
    notifier = H11V4DisabledDualRouteNotifier(
        primary=H11V4FakePushoverTransport(acknowledged=False),
        secondary=H11V4FakeEmailTransport(accepted=False),
    )
    result = notifier.notify_once(H11V4NotificationEvent.HEARTBEAT_LOST)
    assert result.primary_ready is False
    assert result.secondary_ready is False
    assert result.halt_required is True
    assert result.reason_safe_label == "NOTIFICATION_ROUTE_NOT_READY"


def test_noncritical_event_does_not_claim_emergency_receipt() -> None:
    request = build_h11_v4_pushover_request(H11V4NotificationEvent.ENTRY_CONFIRMED)
    assert request.emergency_priority is False
    assert request.receipt_required is False
    assert request.retry_seconds is None
    assert request.expire_seconds is None


def test_default_transports_refuse_and_module_has_no_real_sender() -> None:
    with pytest.raises(H11V4NotificationError, match="PUSHOVER_TRANSPORT_DISABLED"):
        H11V4DisabledDualRouteNotifier().notify_once(
            H11V4NotificationEvent.ENTRY_CONFIRMED
        )
    source = inspect.getsource(notification_module)
    forbidden = (
        "httpx",
        "requests.",
        "urllib",
        "socket",
        "smtplib",
        "subprocess",
        "read_v4_gmo_keychain_secret(",
        "os.environ",
        "os.getenv",
        "api.pushover.net",
        "ENABLE_LIVE_TRADING",
    )
    for marker in forbidden:
        assert marker not in source
