"""H-11 v4 unattended live supervisor heartbeat-continuity chain (fake-only, unwired).

The existing ``DeadManStore`` (``app.h11_auto.runtime_safety``) proves heartbeat
*recency* — the last beat is fresh. The unattended design (Phase 4 §3.2 item 4)
additionally requires *continuity*: the supervisor must have been continuously
healthy, with no unexplained gap, for a minimum duration immediately before a
permit could be issued. A host that just woke from sleep or just restarted has
a fresh heartbeat but no continuity, and must not be trusted yet.

This store records a chain: the moment continuity started and the latest beat.
A gap larger than the policy's maximum restarts the chain, so continuity is
never claimed across an unexplained silence. This module is not wired into any
runtime; it performs no network, credential, broker, or notification access.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

V4_UNATTENDED_HEARTBEAT_CHAIN_SCHEMA = "H11_V4_UNATTENDED_LIVE_HEARTBEAT_CHAIN_V1"


class V4UnattendedLiveHeartbeatError(RuntimeError):
    """Fail-closed heartbeat-chain error containing safe labels only."""


@dataclass(frozen=True)
class V4HeartbeatChainPolicy:
    policy_label: str
    maximum_gap_seconds: int
    minimum_continuous_seconds: int

    def __post_init__(self) -> None:
        values = (self.maximum_gap_seconds, self.minimum_continuous_seconds)
        if (
            not isinstance(self.policy_label, str)
            or not self.policy_label.strip()
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in values
            )
        ):
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_POLICY_INVALID")
        if self.minimum_continuous_seconds <= self.maximum_gap_seconds:
            # Continuity must mean more than a single surviving gap.
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_POLICY_INCONSISTENT")

    @property
    def digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class V4HeartbeatChainAssessment:
    continuously_healthy: bool
    reason_safe_label: str
    continuous_seconds: float | None
    heartbeat_age_seconds: float | None
    actual_post_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.continuously_healthy) is not bool or (
            self.actual_post_allowed is not False
        ):
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_ASSESSMENT_INVALID")
        if (
            not isinstance(self.reason_safe_label, str)
            or not self.reason_safe_label
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
                for character in self.reason_safe_label
            )
        ):
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_ASSESSMENT_INVALID")

    def __bool__(self) -> bool:
        return False


class V4HeartbeatChainStore:
    """Persist one heartbeat chain; no clear or reset operation exists."""

    def __init__(self, path: Path, *, policy: V4HeartbeatChainPolicy) -> None:
        if not isinstance(path, Path) or type(policy) is not V4HeartbeatChainPolicy:
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_STORE_INPUT_INVALID")
        self.path = path
        self.policy = policy

    def beat(self, *, now_utc: datetime) -> None:
        if now_utc.tzinfo is None:
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_CLOCK_INVALID")
        normalized = now_utc.astimezone(UTC)
        chain_started = normalized
        if self.path.is_symlink():
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_SYMLINK_REFUSED")
        if self.path.exists():
            previous_started, previous_beat = self._load()
            if normalized < previous_beat:
                raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_TIME_BACKWARDS")
            gap = (normalized - previous_beat).total_seconds()
            if gap <= self.policy.maximum_gap_seconds:
                chain_started = previous_started
            # else: an unexplained gap ends the old chain; continuity restarts now.
        payload = {
            "schema": V4_UNATTENDED_HEARTBEAT_CHAIN_SCHEMA,
            "policy_digest": self.policy.digest,
            "chain_started_utc": chain_started.isoformat(),
            "last_heartbeat_utc": normalized.isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        if temporary.is_symlink():
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_SYMLINK_REFUSED")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as error:
            raise V4UnattendedLiveHeartbeatError("HEARTBEAT_CHAIN_SAVE_FAILED") from error

    def assess(self, *, now_utc: datetime) -> V4HeartbeatChainAssessment:
        if now_utc.tzinfo is None:
            return _unhealthy("HEARTBEAT_CHAIN_CLOCK_INVALID")
        if self.path.is_symlink() or not self.path.is_file():
            return _unhealthy("HEARTBEAT_CHAIN_MISSING")
        try:
            chain_started, last_beat = self._load()
        except V4UnattendedLiveHeartbeatError:
            return _unhealthy("HEARTBEAT_CHAIN_STATE_INVALID")
        now = now_utc.astimezone(UTC)
        age = (now - last_beat).total_seconds()
        if age < 0:
            return _unhealthy("HEARTBEAT_CHAIN_FROM_FUTURE", age=age)
        if age > self.policy.maximum_gap_seconds:
            return _unhealthy("HEARTBEAT_CHAIN_STALE", age=age)
        continuous = (now - chain_started).total_seconds()
        if continuous < self.policy.minimum_continuous_seconds:
            return _unhealthy(
                "HEARTBEAT_CHAIN_CONTINUITY_INSUFFICIENT",
                age=age,
                continuous=continuous,
            )
        return V4HeartbeatChainAssessment(
            continuously_healthy=True,
            reason_safe_label="HEARTBEAT_CHAIN_CONTINUOUSLY_HEALTHY",
            continuous_seconds=continuous,
            heartbeat_age_seconds=age,
        )

    def _load(self) -> tuple[datetime, datetime]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                payload.get("schema") != V4_UNATTENDED_HEARTBEAT_CHAIN_SCHEMA
                or payload.get("policy_digest") != self.policy.digest
            ):
                raise ValueError
            chain_started = datetime.fromisoformat(payload["chain_started_utc"])
            last_beat = datetime.fromisoformat(payload["last_heartbeat_utc"])
            if (
                chain_started.tzinfo is None
                or last_beat.tzinfo is None
                or last_beat < chain_started
            ):
                raise ValueError
            return chain_started.astimezone(UTC), last_beat.astimezone(UTC)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise V4UnattendedLiveHeartbeatError(
                "HEARTBEAT_CHAIN_STATE_INVALID"
            ) from None


def _unhealthy(
    reason: str, *, age: float | None = None, continuous: float | None = None
) -> V4HeartbeatChainAssessment:
    return V4HeartbeatChainAssessment(
        continuously_healthy=False,
        reason_safe_label=reason,
        continuous_seconds=continuous,
        heartbeat_age_seconds=age,
    )
