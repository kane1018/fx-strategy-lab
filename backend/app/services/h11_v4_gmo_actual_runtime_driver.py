"""Finite foreground lifecycle driver for an activated H-11 v4 canary.

The monitor-only LaunchAgent owns no broker capability.  After a separately
authorized canary starts, this driver stays in the same permit-bound process,
holds the canonical process lock, refreshes the dead-man heartbeat, and is the
only production consumer of the supervisor's generation-bound exit marker.
It is never installed as a LaunchAgent and has no restart/rebind shortcut.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.h11_v4_gmo_coordinated_actual_path import (
    V4GmoCoordinatedActualPath,
)
from app.services.h11_v4_gmo_exit_dispatcher import (
    V4GmoExitDispatcher,
    V4GmoExitDispatchResult,
)
from app.services.h11_v4_gmo_public_market_status import (
    V4GmoPublicMarketStatusReader,
)


class V4GmoActualRuntimeDriverError(RuntimeError):
    """Fixed safe foreground lifecycle failure."""


@dataclass(frozen=True)
class V4GmoActualRuntimeDriverResult:
    flat_reconciled: bool
    exit_dispatch_claimed: bool
    broker_post_attempt_count: int

    def __bool__(self) -> bool:
        return False


ReaderFactory = Callable[[], V4GmoPublicMarketStatusReader]


class V4GmoActualRuntimeDriver:
    """Own one activated runtime continuously from protection to flat."""

    def __init__(
        self,
        *,
        coordinated_path: V4GmoCoordinatedActualPath,
        dispatcher: V4GmoExitDispatcher,
    ) -> None:
        if (
            dispatcher.path is not coordinated_path
            or not coordinated_path.process_lock.held
        ):
            raise V4GmoActualRuntimeDriverError("V4_RUNTIME_DRIVER_BINDING_INVALID")
        self.path = coordinated_path
        self.dispatcher = dispatcher
        self.state_root = coordinated_path.store.path.parent.resolve()

    def run_until_flat(
        self,
        *,
        public_reader_factory: ReaderFactory | None = None,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        wait: Callable[[float], None] = time.sleep,
        poll_interval_seconds: float = 5.0,
    ) -> V4GmoActualRuntimeDriverResult:
        if poll_interval_seconds != 5.0 or not self.path.process_lock.held:
            raise V4GmoActualRuntimeDriverError("V4_RUNTIME_DRIVER_CONFIG_INVALID")
        reader_factory = public_reader_factory or (
            lambda: V4GmoPublicMarketStatusReader(
                generation_digest=self.path.generation.digest
            )
        )
        required = self.state_root / "exit-sequence-dispatch-required.json"
        try:
            initial = self.path.store.monitor_snapshot_safe()
            if (
                initial.entry_attempted_at_utc is None
                or initial.flat_reconciled
                or not initial.protection_confirmed
                or initial.pending_transport
            ):
                raise V4GmoActualRuntimeDriverError("V4_RUNTIME_DRIVER_NOT_PROTECTED")
            while True:
                now = wall_clock()
                if now.tzinfo is None:
                    raise V4GmoActualRuntimeDriverError(
                        "V4_RUNTIME_DRIVER_CLOCK_INVALID"
                    )
                self.path.dead_man_store.heartbeat(heartbeat_utc=now.astimezone(UTC))
                snapshot = self.path.store.monitor_snapshot_safe()
                if snapshot.flat_reconciled:
                    return V4GmoActualRuntimeDriverResult(
                        flat_reconciled=True,
                        exit_dispatch_claimed=False,
                        broker_post_attempt_count=0,
                    )
                if required.is_file() and not required.is_symlink():
                    result: V4GmoExitDispatchResult = self.dispatcher.dispatch_once(
                        public_cancel_reader=reader_factory(),
                        public_close_reader=reader_factory(),
                        observed_at_utc=now,
                    )
                    return V4GmoActualRuntimeDriverResult(
                        flat_reconciled=result.flat_reconciled,
                        exit_dispatch_claimed=result.claimed,
                        broker_post_attempt_count=result.broker_post_attempt_count,
                    )
                wait(poll_interval_seconds)
        except BaseException as error:
            self.path.store.engage_unknown_halt()
            if isinstance(error, V4GmoActualRuntimeDriverError):
                raise
            raise V4GmoActualRuntimeDriverError(
                "V4_RUNTIME_DRIVER_FAILED_PERSISTENT_HALT"
            ) from error

    def __repr__(self) -> str:
        return "V4GmoActualRuntimeDriver(<foreground-generation-bound>)"

    def __bool__(self) -> bool:
        return False
