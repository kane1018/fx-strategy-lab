"""H-11 v3 email notification injection point (disabled, no-POST).

Mirrors ``h11_v3_actual_transport_binding_no_post``: the SMTP transport
contract and injection point are defined here so the boundary can be
reviewed before activation. This module intentionally ships without a
production SMTP sender implementation. The default transport refuses, and
the only executable path in this build is a locally constructed fake
transport that never opens a network connection.

No ``smtplib``, socket, or credential-value import exists in this module.
The recipient address and category are the only content ever handled here;
no price/PnL/ID/credential value passes through ``notify``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

ALLOWED_EMAIL_NOTIFICATION_CATEGORIES = frozenset(
    {
        "H11_V3_HEARTBEAT",
        "H11_V3_DEAD_MAN_HALTED",
        "H11_V3_KILL_ENGAGED",
        "H11_V3_UNKNOWN_EVENT_HALTED",
        "H11_V3_ENTRY_OBSERVED",
        "H11_V3_SETTLEMENT_OBSERVED",
        "H11_V3_BUDGET_STOP",
        "H11_V3_DISCIPLINE_VIOLATION",
    }
)


class H11V3EmailNotifierError(RuntimeError):
    """Fail-closed error containing safe labels only."""


@runtime_checkable
class H11V3SmtpTransport(Protocol):
    """Future transport interface; a real implementation is deliberately absent."""

    real_transport: bool

    def send_category_only(self, *, recipient: str, category: str) -> bool: ...


@dataclass(frozen=True)
class H11V3RefusingSmtpTransport:
    """Default transport. It cannot be configured to send."""

    real_transport: bool = False

    def send_category_only(self, *, recipient: str, category: str) -> bool:
        raise H11V3EmailNotifierError(
            "H-11 v3 SMTP transport is disabled in the no-POST build"
        )

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3FakeSmtpTransport:
    """Deterministic fake for tests. No socket, no smtplib, no network."""

    should_succeed: bool = True
    real_transport: bool = field(default=False, init=False)
    sent_categories_safe: list[str] = field(default_factory=list, init=False)

    def send_category_only(self, *, recipient: str, category: str) -> bool:
        if "@" not in recipient:
            raise H11V3EmailNotifierError("recipient must look like an email address")
        if category not in ALLOWED_EMAIL_NOTIFICATION_CATEGORIES:
            raise H11V3EmailNotifierError("category is not an allowed safe label")
        if not self.should_succeed:
            return False
        self.sent_categories_safe.append(category)
        return True

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3EmailNotificationResult:
    category_safe_label: str
    sent: bool
    real_transport_used: bool = False
    credential_read: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3DisabledEmailNotifier:
    """Reviewed injection point. Accepts fake-only transports and never sends."""

    recipient: str
    transport: H11V3SmtpTransport = field(default_factory=H11V3RefusingSmtpTransport)
    external_send: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.transport, H11V3SmtpTransport):
            raise H11V3EmailNotifierError("transport does not match SMTP contract")
        if self.transport.real_transport:
            raise H11V3EmailNotifierError(
                "real SMTP transport binding is structurally rejected in this build"
            )
        if not self.recipient or "@" not in self.recipient:
            raise H11V3EmailNotifierError("recipient must be a sanitized email address")

    def notify(self, category: str) -> H11V3EmailNotificationResult:
        if category not in ALLOWED_EMAIL_NOTIFICATION_CATEGORIES:
            raise H11V3EmailNotifierError("category is not an allowed safe label")
        sent = self.transport.send_category_only(
            recipient=self.recipient, category=category
        )
        return H11V3EmailNotificationResult(category_safe_label=category, sent=sent)

    def __bool__(self) -> bool:
        return False
