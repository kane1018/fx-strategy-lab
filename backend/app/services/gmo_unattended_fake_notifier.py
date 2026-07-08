"""Fake notification adapter for the unattended paper readiness layer.

In-memory collector only: no email/slack/webhook/external send exists in
this module, and every notification is a safe category label. There is no
field that can carry an ID, a size, a price, a PnL, a credential, or any
raw broker data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GmoUnattendedNotificationCategory(str, Enum):
    NOTIFY_PREVIEW_READY = "NOTIFY_PREVIEW_READY"
    NOTIFY_PAPER_ENTRY_ACCEPTED = "NOTIFY_PAPER_ENTRY_ACCEPTED"
    NOTIFY_PAPER_POSITION_OPEN = "NOTIFY_PAPER_POSITION_OPEN"
    NOTIFY_PAPER_SETTLEMENT_ACCEPTED = "NOTIFY_PAPER_SETTLEMENT_ACCEPTED"
    NOTIFY_PAPER_NO_POSITION_CONFIRMED = "NOTIFY_PAPER_NO_POSITION_CONFIRMED"
    NOTIFY_GUARD_HALTED = "NOTIFY_GUARD_HALTED"
    NOTIFY_UNKNOWN_SAFE_STOP = "NOTIFY_UNKNOWN_SAFE_STOP"
    NOTIFY_DUPLICATE_ATTEMPT_BLOCKED = "NOTIFY_DUPLICATE_ATTEMPT_BLOCKED"
    NOTIFY_KILL_SWITCH_HALTED = "NOTIFY_KILL_SWITCH_HALTED"
    NOTIFY_MAX_HOLD_HALTED = "NOTIFY_MAX_HOLD_HALTED"
    NOTIFY_MAX_LOSS_HALTED = "NOTIFY_MAX_LOSS_HALTED"


class GmoUnattendedNotifierResult(str, Enum):
    NOTIFY_RECORDED_SAFE = "NOTIFY_RECORDED_SAFE"
    NOTIFY_FAILED_SAFE = "NOTIFY_FAILED_SAFE"


@dataclass
class FakeUnattendedNotifier:
    """In-memory fake notifier. ``external_send`` is fixed false."""

    external_send: bool = False
    collected_categories: list[GmoUnattendedNotificationCategory] = field(
        default_factory=list
    )

    def notify_safe_category(
        self, category: GmoUnattendedNotificationCategory
    ) -> GmoUnattendedNotifierResult:
        if not isinstance(category, GmoUnattendedNotificationCategory):
            return GmoUnattendedNotifierResult.NOTIFY_FAILED_SAFE
        self.collected_categories.append(category)
        return GmoUnattendedNotifierResult.NOTIFY_RECORDED_SAFE

    def __bool__(self) -> bool:
        return False


@dataclass
class FailingFakeUnattendedNotifier:
    """Fake notifier that always fails, for notification-failure scenarios."""

    external_send: bool = False
    collected_categories: list[GmoUnattendedNotificationCategory] = field(
        default_factory=list
    )

    def notify_safe_category(
        self, category: GmoUnattendedNotificationCategory
    ) -> GmoUnattendedNotifierResult:
        return GmoUnattendedNotifierResult.NOTIFY_FAILED_SAFE

    def __bool__(self) -> bool:
        return False
