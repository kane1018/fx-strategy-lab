"""Fake and refusing boundaries for Phase A; no network transport exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class H11AutoBoundaryError(RuntimeError):
    """Fixed safe error raised by a disabled boundary."""


class FakeProtectedEntryOutcome(str, Enum):
    ACCEPTED_AND_PROTECTED = "ACCEPTED_AND_PROTECTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"
    PARTIAL_FILL_SIZE_MISMATCH = "PARTIAL_FILL_SIZE_MISMATCH"


class PhaseAProtectedEntrySender(Protocol):
    fake_only: bool
    network_access_performed: bool
    actual_post_count: int

    def send_once_synthetic(self, *, intent_id: str) -> FakeProtectedEntryOutcome: ...


class FakePositionExitOutcome(str, Enum):
    ACCEPTED_AND_FLAT = "ACCEPTED_AND_FLAT"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"


class PhaseAPositionExitSender(Protocol):
    fake_only: bool
    network_access_performed: bool
    actual_post_count: int

    def send_once_synthetic(self, *, intent_id: str) -> FakePositionExitOutcome: ...


@dataclass
class RefusingProtectedEntrySender:
    fake_only: bool = True
    network_access_performed: bool = False
    actual_post_count: int = 0

    def send_once_synthetic(self, *, intent_id: str) -> FakeProtectedEntryOutcome:
        del intent_id
        raise H11AutoBoundaryError("ACTUAL_TRANSPORT_ABSENT_PHASE_A_NO_POST")

    def __bool__(self) -> bool:
        return False


@dataclass
class FakeProtectedEntrySender:
    outcome: FakeProtectedEntryOutcome
    calls: list[str] = field(default_factory=list)
    fake_only: bool = True
    network_access_performed: bool = False
    actual_post_count: int = 0

    def send_once_synthetic(self, *, intent_id: str) -> FakeProtectedEntryOutcome:
        self.calls.append(intent_id)
        return self.outcome

    def __bool__(self) -> bool:
        return False


@dataclass
class RefusingPositionExitSender:
    fake_only: bool = True
    network_access_performed: bool = False
    actual_post_count: int = 0

    def send_once_synthetic(self, *, intent_id: str) -> FakePositionExitOutcome:
        del intent_id
        raise H11AutoBoundaryError("ACTUAL_EXIT_TRANSPORT_ABSENT_PHASE_A_NO_POST")

    def __bool__(self) -> bool:
        return False


@dataclass
class FakePositionExitSender:
    outcome: FakePositionExitOutcome
    calls: list[str] = field(default_factory=list)
    fake_only: bool = True
    network_access_performed: bool = False
    actual_post_count: int = 0

    def send_once_synthetic(self, *, intent_id: str) -> FakePositionExitOutcome:
        self.calls.append(intent_id)
        return self.outcome

    def __bool__(self) -> bool:
        return False


class NotificationCategory(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    INTENT_RECORDED = "INTENT_RECORDED"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    FLAT_RECONCILED = "FLAT_RECONCILED"
    HALTED = "HALTED"


@dataclass
class FakeNotifier:
    fail: bool = False
    fail_categories: frozenset[NotificationCategory] = field(default_factory=frozenset)
    events: list[NotificationCategory] = field(default_factory=list)
    external_send_performed: bool = False

    def notify(self, category: NotificationCategory) -> bool:
        self.events.append(category)
        return not self.fail and category not in self.fail_categories

    def __bool__(self) -> bool:
        return False
