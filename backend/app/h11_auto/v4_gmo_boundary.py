"""Fake/refusing boundary for the relaxed GMO v4 profile.

There is deliberately no HTTP client, signing code, credential loader, or real
transport injection point in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoActionPlan,
    V4GmoBrokerSnapshot,
    V4GmoSyntheticOutcome,
)


class V4GmoBoundaryError(RuntimeError):
    """Fixed safe refusal emitted by the no-POST boundary."""


class V4GmoSyntheticBroker(Protocol):
    fake_only: bool
    actual_post_count: int
    broker_write_performed: bool
    credential_read_performed: bool
    network_access_performed: bool

    def perform_once_synthetic(self, *, plan: V4GmoActionPlan) -> V4GmoSyntheticOutcome: ...

    def reconcile_synthetic(self) -> V4GmoBrokerSnapshot: ...


@dataclass
class RefusingV4GmoBroker:
    fake_only: bool = True
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False

    def perform_once_synthetic(self, *, plan: V4GmoActionPlan) -> V4GmoSyntheticOutcome:
        del plan
        raise V4GmoBoundaryError("V4_GMO_ACTUAL_TRANSPORT_ABSENT_NO_POST")

    def reconcile_synthetic(self) -> V4GmoBrokerSnapshot:
        raise V4GmoBoundaryError("V4_GMO_ACTUAL_READ_BOUNDARY_ABSENT_NO_POST")

    def __bool__(self) -> bool:
        return False


@dataclass
class FakeV4GmoBroker:
    outcomes: dict[V4GmoAction, list[V4GmoSyntheticOutcome]]
    snapshots: list[V4GmoBrokerSnapshot]
    calls: list[V4GmoActionPlan] = field(default_factory=list)
    reconciliation_count: int = 0
    fake_only: bool = True
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False

    def perform_once_synthetic(self, *, plan: V4GmoActionPlan) -> V4GmoSyntheticOutcome:
        if (
            plan.actual_post_allowed
            or plan.credential_read_allowed
            or plan.network_access_allowed
        ):
            raise V4GmoBoundaryError("V4_GMO_NON_FAKE_PLAN_REFUSED")
        queued = self.outcomes.get(plan.action)
        if not queued:
            raise V4GmoBoundaryError("V4_GMO_UNPLANNED_SYNTHETIC_ACTION_REFUSED")
        self.calls.append(plan)
        return queued.pop(0)

    def reconcile_synthetic(self) -> V4GmoBrokerSnapshot:
        if not self.snapshots:
            raise V4GmoBoundaryError("V4_GMO_SYNTHETIC_RECONCILIATION_MISSING")
        self.reconciliation_count += 1
        return self.snapshots.pop(0)

    def __bool__(self) -> bool:
        return False
