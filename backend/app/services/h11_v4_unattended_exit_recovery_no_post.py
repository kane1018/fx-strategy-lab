"""Generation-bound restart decisions without broker access or authorization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
MAXIMUM_OBSERVATION_GAP_SECONDS = 60


class V4ExitRecoveryStatus(str, Enum):
    COMPLETE_FLAT_NO_WRITE = "COMPLETE_FLAT_NO_WRITE"
    MONITOR_TICK_SAFE_NO_WRITE = "MONITOR_TICK_SAFE_NO_WRITE"
    EXIT_SCOPE_REQUIRED_NO_WRITE = "EXIT_SCOPE_REQUIRED_NO_WRITE"
    REFUSED_FAIL_CLOSED = "REFUSED_FAIL_CLOSED"


@dataclass(frozen=True)
class V4ExitRecoverySnapshot:
    reviewed_files_digest_matches: bool
    generation_digest_matches: bool
    cycle_binding_digest: str
    expected_cycle_binding_digest: str
    exact_protection_confirmed: bool
    flat_reconciled: bool
    transport_action_pending: bool
    result_unknown: bool
    persistent_operator_halt: bool
    process_lock_available: bool
    scheduled_exit_at_utc: datetime
    previous_observed_at_utc: datetime
    observed_at_utc: datetime
    time_exit_marker_claimed: bool


@dataclass(frozen=True)
class V4ExitRecoveryDecision:
    status: V4ExitRecoveryStatus
    monitor_tick_allowed: bool
    exit_scope_required: bool
    broker_post_authorized: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        """Prevent this decision object from becoming an allow bridge."""

        return False


def evaluate_exit_recovery(
    snapshot: V4ExitRecoverySnapshot,
) -> V4ExitRecoveryDecision:
    """Classify local durable state; never authorize or perform a broker action."""

    if not snapshot.reviewed_files_digest_matches:
        return _refused()
    if not snapshot.generation_digest_matches:
        return _refused()
    if not _SHA256.fullmatch(snapshot.cycle_binding_digest):
        return _refused()
    if snapshot.cycle_binding_digest != snapshot.expected_cycle_binding_digest:
        return _refused()
    if snapshot.transport_action_pending or snapshot.result_unknown:
        return _refused()
    if snapshot.persistent_operator_halt:
        return _refused()
    if snapshot.flat_reconciled:
        return V4ExitRecoveryDecision(
            status=V4ExitRecoveryStatus.COMPLETE_FLAT_NO_WRITE,
            monitor_tick_allowed=False,
            exit_scope_required=False,
        )
    if not snapshot.exact_protection_confirmed:
        return _refused()
    if not snapshot.process_lock_available:
        return _refused()
    if snapshot.time_exit_marker_claimed:
        return _refused()
    if (
        snapshot.scheduled_exit_at_utc.utcoffset() is None
        or snapshot.previous_observed_at_utc.utcoffset() is None
        or snapshot.observed_at_utc.utcoffset() is None
    ):
        return _refused()
    observation_gap = (
        snapshot.observed_at_utc - snapshot.previous_observed_at_utc
    ).total_seconds()
    if (
        observation_gap < 0
        or observation_gap > MAXIMUM_OBSERVATION_GAP_SECONDS
    ):
        return _refused()
    if snapshot.observed_at_utc >= snapshot.scheduled_exit_at_utc:
        return V4ExitRecoveryDecision(
            status=V4ExitRecoveryStatus.EXIT_SCOPE_REQUIRED_NO_WRITE,
            monitor_tick_allowed=False,
            exit_scope_required=True,
        )
    return V4ExitRecoveryDecision(
        status=V4ExitRecoveryStatus.MONITOR_TICK_SAFE_NO_WRITE,
        monitor_tick_allowed=True,
        exit_scope_required=False,
    )


def _refused() -> V4ExitRecoveryDecision:
    return V4ExitRecoveryDecision(
        status=V4ExitRecoveryStatus.REFUSED_FAIL_CLOSED,
        monitor_tick_allowed=False,
        exit_scope_required=False,
    )
