"""G076 fake-only runtime ports.

This candidate deliberately has no credential, HTTP, notification, ARM, or
broker transport imports.  A real release activation remains a separate
reviewed boundary outside this candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.h11_v4_g076_runtime import (
    G076Action,
    G076ActionOutcome,
    G076ActionScope,
    G076Error,
    G076FakeOnlyCallable,
    G076FakeOnlyPort,
    G076ProcessLock,
    G076StrategyObservation,
)


class G076LiveRuntimeError(RuntimeError):
    """Safe-label-only fake runtime failure."""


class G076FakeOnlyTransportRequired(G076LiveRuntimeError):
    """Raised when a caller has not supplied a synthetic dependency."""


@dataclass
class G076PrivateReconciler(G076FakeOnlyPort):
    """Reconciliation port that accepts only an injected fake callable."""

    fake_reconciler: G076FakeOnlyCallable | None = None

    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> Any:
        if not isinstance(self.fake_reconciler, G076FakeOnlyCallable):
            raise G076FakeOnlyTransportRequired(
                "G076_FAKE_ONLY_RECONCILIATION_REQUIRED"
            )
        return self.fake_reconciler(cycle_id=cycle_id, now_utc=now_utc)


@dataclass
class G076LiveActionPort(G076FakeOnlyPort):
    """Action port that accepts only an injected synthetic handler."""

    process_lock: G076ProcessLock | None = None
    fake_observer: G076FakeOnlyCallable | None = None
    fake_action: G076FakeOnlyCallable | None = None

    def observe(self, *, now_utc: datetime) -> G076StrategyObservation:
        if not isinstance(self.fake_observer, G076FakeOnlyCallable):
            raise G076FakeOnlyTransportRequired("G076_FAKE_ONLY_OBSERVER_REQUIRED")
        return self.fake_observer(now_utc=now_utc)

    def attempt_once(self, scope: G076ActionScope) -> G076ActionOutcome:
        if not isinstance(self.fake_action, G076FakeOnlyCallable):
            raise G076FakeOnlyTransportRequired("G076_FAKE_ONLY_ACTION_REQUIRED")
        result = self.fake_action(scope=scope)
        if not isinstance(result, G076ActionOutcome):
            raise G076Error("G076_FAKE_ACTION_OUTCOME_INVALID")
        return result

    def time_exit_reason(self, *, evidence: Any, now_utc: datetime) -> G076Action | None:
        del evidence, now_utc
        return None


__all__ = [
    "G076FakeOnlyTransportRequired",
    "G076LiveActionPort",
    "G076LiveRuntimeError",
    "G076PrivateReconciler",
]
