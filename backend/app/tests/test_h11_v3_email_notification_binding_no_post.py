"""H-11 v3 email notification binding tests (fake transport only, no-POST)."""

from __future__ import annotations

import pytest

from app.services.h11_v3_email_notification_binding_no_post import (
    ALLOWED_EMAIL_NOTIFICATION_CATEGORIES,
    H11V3DisabledEmailNotifier,
    H11V3EmailNotifierError,
    H11V3FakeSmtpTransport,
    H11V3RefusingSmtpTransport,
)

RECIPIENT = "kansuinaoi@gmail.com"


def test_default_transport_refuses():
    notifier = H11V3DisabledEmailNotifier(recipient=RECIPIENT)
    assert isinstance(notifier.transport, H11V3RefusingSmtpTransport)
    with pytest.raises(H11V3EmailNotifierError):
        notifier.notify("H11_V3_HEARTBEAT")


def test_fake_transport_sends_and_records_safe_category():
    transport = H11V3FakeSmtpTransport()
    notifier = H11V3DisabledEmailNotifier(recipient=RECIPIENT, transport=transport)
    result = notifier.notify("H11_V3_KILL_ENGAGED")
    assert result.sent is True
    assert result.category_safe_label == "H11_V3_KILL_ENGAGED"
    assert transport.sent_categories_safe == ["H11_V3_KILL_ENGAGED"]
    assert bool(result) is False


def test_fake_transport_failure_reports_not_sent():
    transport = H11V3FakeSmtpTransport(should_succeed=False)
    notifier = H11V3DisabledEmailNotifier(recipient=RECIPIENT, transport=transport)
    result = notifier.notify("H11_V3_DEAD_MAN_HALTED")
    assert result.sent is False


def test_real_transport_binding_structurally_rejected():
    class FakeRealTransport:
        real_transport = True

        def send_category_only(self, *, recipient: str, category: str) -> bool:
            return True

    with pytest.raises(H11V3EmailNotifierError):
        H11V3DisabledEmailNotifier(recipient=RECIPIENT, transport=FakeRealTransport())


def test_invalid_recipient_rejected():
    with pytest.raises(H11V3EmailNotifierError):
        H11V3DisabledEmailNotifier(recipient="not-an-email")


def test_unknown_category_rejected():
    notifier = H11V3DisabledEmailNotifier(
        recipient=RECIPIENT, transport=H11V3FakeSmtpTransport()
    )
    with pytest.raises(H11V3EmailNotifierError):
        notifier.notify("SOME_RAW_LABEL_NOT_ON_THE_LIST")


def test_all_allowed_categories_deliverable():
    transport = H11V3FakeSmtpTransport()
    notifier = H11V3DisabledEmailNotifier(recipient=RECIPIENT, transport=transport)
    for category in ALLOWED_EMAIL_NOTIFICATION_CATEGORIES:
        assert notifier.notify(category).sent is True
    assert set(transport.sent_categories_safe) == ALLOWED_EMAIL_NOTIFICATION_CATEGORIES
