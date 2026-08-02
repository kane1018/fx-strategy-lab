"""G070 opaque-scope action orchestration for fake-only candidate review.

This module deliberately has no production broker adapter.  A future release
binding may supply a separately reviewed port, but this candidate can only be
exercised with an explicitly injected test double.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from app.services.h11_v4_g070_candidate import (
    G070Action,
    G070ActionScopeStore,
    G070Error,
    G070OpaqueActionScope,
    G070ReleaseCapability,
    engage_g070_halt,
)


class G070ActionOutcome(str, Enum):
    ACCEPTED_KNOWN = "ACCEPTED_KNOWN"
    PARTIAL_PENDING_KNOWN = "PARTIAL_PENDING_KNOWN"
    PROTECTED_KNOWN = "PROTECTED_KNOWN"
    FLAT_KNOWN = "FLAT_KNOWN"
    UNKNOWN = "UNKNOWN"


class G070ScopedActionPort(Protocol):
    """Narrow action boundary; it intentionally exposes no allow boolean."""

    def attempt_once(self, scope: G070OpaqueActionScope) -> G070ActionOutcome: ...


@dataclass(frozen=True)
class G070ActionRequest:
    cycle_ref: str
    action: G070Action
    symbol: str
    side: str
    quantity: int
    coordinator_digest: str


@dataclass(frozen=True)
class G070LifecycleResult:
    entry_attempt_count: int
    partial_cancel_attempt_count: int
    protection_attempt_count: int
    exit_cancel_attempt_count: int
    close_attempt_count: int
    protected: bool
    flat_reconciled: bool

    def __bool__(self) -> bool:
        return False


class G070ScopedActionCoordinator:
    """Consume one exact opaque scope before each injected action attempt."""

    def __init__(
        self,
        *,
        state_root: Path,
        release: G070ReleaseCapability,
        port: G070ScopedActionPort,
    ) -> None:
        self.state_root = state_root
        self.release = release
        self.port = port
        self.scope_store = G070ActionScopeStore(state_root / "g070-action-scopes")

    def attempt_once(self, *, request: G070ActionRequest, now_utc: datetime) -> G070ActionOutcome:
        scope = self.scope_store.issue(
            release=self.release,
            cycle_ref=request.cycle_ref,
            action=request.action,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            coordinator_digest=request.coordinator_digest,
            now_utc=now_utc,
        )
        self.scope_store.consume_exact(
            scope,
            generation_digest=self.release.generation_digest,
            reviewed_files_digest=self.release.reviewed_files_digest,
            cycle_ref=request.cycle_ref,
            action=request.action,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            coordinator_digest=request.coordinator_digest,
            now_utc=now_utc,
        )
        attempt_path = (
            self.state_root
            / "g070-action-attempts"
            / f"{scope.scope_digest.removeprefix('sha256:')}.json"
        )
        attempt_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(attempt_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G070Error("ACTION_ATTEMPT_ALREADY_RECORDED_NO_RETRY") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "action": request.action.value,
                    "scope_digest": scope.scope_digest,
                    "status": "ATTEMPT_RESERVED",
                },
                stream,
                sort_keys=True,
            )
        try:
            outcome = self.port.attempt_once(scope)
        except BaseException as error:
            engage_g070_halt(state_root=self.state_root, reason="ACTION_TRANSPORT_RESULT_UNKNOWN")
            raise G070Error("ACTION_TRANSPORT_RESULT_UNKNOWN_NO_RETRY") from error
        if not isinstance(outcome, G070ActionOutcome) or outcome is G070ActionOutcome.UNKNOWN:
            engage_g070_halt(state_root=self.state_root, reason="ACTION_TRANSPORT_RESULT_UNKNOWN")
            raise G070Error("ACTION_TRANSPORT_RESULT_UNKNOWN_NO_RETRY")
        result_path = attempt_path.with_name(attempt_path.stem + ".result.json")
        result_path.write_text(
            json.dumps(
                {
                    "action": request.action.value,
                    "scope_digest": scope.scope_digest,
                    "status": outcome.value,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return outcome


class G070FakeLifecycleDriver:
    """Exact action ordering used only with an injected fake action port."""

    def __init__(
        self,
        *,
        coordinator: G070ScopedActionCoordinator,
        cycle_ref: str,
        side: str,
        quantity: int,
        coordinator_digest: str,
    ) -> None:
        self.coordinator = coordinator
        self.cycle_ref = cycle_ref
        self.side = side
        self.quantity = quantity
        self.coordinator_digest = coordinator_digest
        self.counts: dict[G070Action, int] = {action: 0 for action in G070Action}
        self.protected = False
        self.flat_reconciled = False

    def _request(self, action: G070Action) -> G070ActionRequest:
        return G070ActionRequest(
            cycle_ref=self.cycle_ref,
            action=action,
            symbol="USD_JPY",
            side=self.side,
            quantity=self.quantity,
            coordinator_digest=self.coordinator_digest,
        )

    def _attempt(self, action: G070Action, *, now_utc: datetime) -> G070ActionOutcome:
        if self.counts[action] != 0:
            raise G070Error("LIFECYCLE_ACTION_ALREADY_ATTEMPTED_NO_RETRY")
        self.counts[action] += 1
        return self.coordinator.attempt_once(request=self._request(action), now_utc=now_utc)

    def enter_and_protect_once(self, *, now_utc: datetime) -> G070LifecycleResult:
        market = self._attempt(G070Action.MARKET_ENTRY, now_utc=now_utc)
        if market is G070ActionOutcome.PARTIAL_PENDING_KNOWN:
            cancelled = self._attempt(G070Action.PARTIAL_PENDING_CANCEL, now_utc=now_utc)
            if cancelled is not G070ActionOutcome.ACCEPTED_KNOWN:
                self._halt("PARTIAL_CANCEL_NOT_ACCEPTED")
        elif market is not G070ActionOutcome.ACCEPTED_KNOWN:
            self._halt("MARKET_ENTRY_NOT_ACCEPTED")
        protection = self._attempt(G070Action.EXACT_OCO_PROTECTION, now_utc=now_utc)
        if protection is not G070ActionOutcome.PROTECTED_KNOWN:
            self._halt("EXACT_PROTECTION_NOT_CONFIRMED")
        self.protected = True
        return self.result()

    def time_exit_once(self, *, now_utc: datetime) -> G070LifecycleResult:
        if not self.protected:
            self._halt("TIME_EXIT_REQUIRES_PROTECTED_POSITION")
        cancel = self._attempt(G070Action.TIME_EXIT_OCO_CANCEL, now_utc=now_utc)
        if cancel is not G070ActionOutcome.ACCEPTED_KNOWN:
            self._halt("TIME_EXIT_CANCEL_NOT_ACCEPTED")
        close = self._attempt(G070Action.POSITION_SPECIFIC_CLOSE, now_utc=now_utc)
        if close is not G070ActionOutcome.FLAT_KNOWN:
            self._halt("POSITION_CLOSE_NOT_FLAT")
        self.protected = False
        self.flat_reconciled = True
        return self.result()

    def reconcile_natural_flat_once(self) -> G070LifecycleResult:
        if not self.protected:
            self._halt("NATURAL_FLAT_REQUIRES_PROTECTED_POSITION")
        self.protected = False
        self.flat_reconciled = True
        return self.result()

    def result(self) -> G070LifecycleResult:
        return G070LifecycleResult(
            entry_attempt_count=self.counts[G070Action.MARKET_ENTRY],
            partial_cancel_attempt_count=self.counts[G070Action.PARTIAL_PENDING_CANCEL],
            protection_attempt_count=self.counts[G070Action.EXACT_OCO_PROTECTION],
            exit_cancel_attempt_count=self.counts[G070Action.TIME_EXIT_OCO_CANCEL],
            close_attempt_count=self.counts[G070Action.POSITION_SPECIFIC_CLOSE],
            protected=self.protected,
            flat_reconciled=self.flat_reconciled,
        )

    def _halt(self, reason: str) -> None:
        engage_g070_halt(state_root=self.coordinator.state_root, reason=reason)
        raise G070Error(reason)


class G070FakeActionPort:
    """Scripted fake transport for candidate verification only."""

    def __init__(self, outcomes: Mapping[G070Action, G070ActionOutcome]) -> None:
        self.outcomes = dict(outcomes)
        self.calls: list[G070Action] = []

    def attempt_once(self, scope: G070OpaqueActionScope) -> G070ActionOutcome:
        self.calls.append(scope.action)
        return self.outcomes.get(scope.action, G070ActionOutcome.UNKNOWN)
