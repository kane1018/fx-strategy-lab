"""Generation-bound operational readiness evidence with no external action."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainStore,
)

_SCHEMA = "H11_V4_UNATTENDED_OPERATIONAL_READINESS_NO_POST_V1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class V4OperationalReadinessNoPostError(ValueError):
    """Fixed safe failure for invalid readiness observation or evidence."""


@dataclass(frozen=True)
class V4OperationalReadinessEvidenceNoPost:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    observed_at_utc: str
    valid_until_utc: str
    process_lock_clear: bool
    dead_man_clear: bool
    heartbeat_chain_clear: bool
    notification_ready: bool
    credential_read: bool
    private_api_read: bool
    notification_send_count: int
    broker_write: bool
    broker_post_count: int
    live_action_authorized: bool
    artifact_digest: str

    def __bool__(self) -> bool:
        return False


def observe_operational_readiness_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    process_lock: H11AutoProcessLock,
    dead_man_store: DeadManStore,
    heartbeat_chain_store: V4HeartbeatChainStore,
    now_utc: datetime,
) -> V4OperationalReadinessEvidenceNoPost:
    """Observe existing runtime gates without beating, sending, or authorizing."""

    if (
        type(process_lock) is not H11AutoProcessLock
        or type(dead_man_store) is not DeadManStore
        or type(heartbeat_chain_store) is not V4HeartbeatChainStore
        or now_utc.tzinfo is None
    ):
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_INPUT_INVALID"
        )
    was_held = process_lock.held
    try:
        process_lock.acquire()
        dead_man_store.evaluate(now_utc=now_utc)
        heartbeat_chain_store.assess(now_utc=now_utc)
        return build_operational_readiness_evidence_no_post(
            reviewed_files_digest=reviewed_files_digest,
            generation_digest=generation_digest,
            observed_at_utc=now_utc,
            # A detached probe cannot truthfully preserve these gates after it
            # releases the lock and returns. They remain blockers until an
            # action-owning runtime validates them atomically in a separately
            # reviewed generation.
            process_lock_clear=False,
            dead_man_clear=False,
            heartbeat_chain_clear=False,
            # Structural transport conformance is not delivery readiness.
            # This no-send probe cannot read credentials or contact providers,
            # so notification readiness must remain false.
            notification_ready=False,
        )
    except Exception as error:
        if isinstance(error, V4OperationalReadinessNoPostError):
            raise
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_OBSERVATION_FAILED"
        ) from error
    finally:
        if process_lock.held and not was_held:
            process_lock.release()


def build_operational_readiness_evidence_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    observed_at_utc: datetime,
    process_lock_clear: bool,
    dead_man_clear: bool,
    heartbeat_chain_clear: bool,
    notification_ready: bool,
) -> V4OperationalReadinessEvidenceNoPost:
    if (
        not _SHA256.fullmatch(reviewed_files_digest)
        or not _SHA256.fullmatch(generation_digest)
        or observed_at_utc.tzinfo is None
        or any(
            type(value) is not bool
            for value in (
                process_lock_clear,
                dead_man_clear,
                heartbeat_chain_clear,
                notification_ready,
            )
        )
        or notification_ready is not False
        or process_lock_clear is not False
        or dead_man_clear is not False
        or heartbeat_chain_clear is not False
    ):
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_EVIDENCE_INPUT_INVALID"
        )
    observed = observed_at_utc.astimezone(UTC)
    payload: dict[str, object] = {
        "schema": _SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "observed_at_utc": observed.isoformat(),
        "valid_until_utc": (observed + timedelta(seconds=60)).isoformat(),
        "process_lock_clear": process_lock_clear,
        "dead_man_clear": dead_man_clear,
        "heartbeat_chain_clear": heartbeat_chain_clear,
        "notification_ready": notification_ready,
        "credential_read": False,
        "private_api_read": False,
        "notification_send_count": 0,
        "broker_write": False,
        "broker_post_count": 0,
        "live_action_authorized": False,
    }
    return V4OperationalReadinessEvidenceNoPost(
        **payload,
        artifact_digest=_canonical_digest(payload),
    )


def validate_operational_readiness_evidence_no_post(
    evidence: V4OperationalReadinessEvidenceNoPost,
    *,
    expected_reviewed_files_digest: str,
    expected_generation_digest: str,
    now_utc: datetime,
) -> None:
    if type(evidence) is not V4OperationalReadinessEvidenceNoPost:
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_EVIDENCE_TYPE_INVALID"
        )
    payload = asdict(evidence)
    artifact_digest = payload.pop("artifact_digest")
    if (
        evidence.schema != _SCHEMA
        or artifact_digest != _canonical_digest(payload)
        or evidence.reviewed_files_digest != expected_reviewed_files_digest
        or evidence.generation_digest != expected_generation_digest
        or not _SHA256.fullmatch(evidence.reviewed_files_digest)
        or not _SHA256.fullmatch(evidence.generation_digest)
        or not _SHA256.fullmatch(evidence.artifact_digest)
        or any(
            type(value) is not bool
            for value in (
                evidence.process_lock_clear,
                evidence.dead_man_clear,
                evidence.heartbeat_chain_clear,
                evidence.notification_ready,
            )
        )
        or evidence.credential_read is not False
        or evidence.private_api_read is not False
        or evidence.notification_send_count != 0
        or evidence.broker_write is not False
        or evidence.broker_post_count != 0
        or evidence.live_action_authorized is not False
        or evidence.notification_ready is not False
        or evidence.process_lock_clear is not False
        or evidence.dead_man_clear is not False
        or evidence.heartbeat_chain_clear is not False
    ):
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_EVIDENCE_INVALID"
        )
    if now_utc.tzinfo is None:
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_CLOCK_INVALID"
        )
    try:
        observed = datetime.fromisoformat(evidence.observed_at_utc)
        valid_until = datetime.fromisoformat(evidence.valid_until_utc)
    except ValueError:
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_TIME_INVALID"
        ) from None
    now = now_utc.astimezone(UTC)
    if (
        observed.tzinfo is None
        or valid_until.tzinfo is None
        or observed.utcoffset() != UTC.utcoffset(observed)
        or valid_until.utcoffset() != UTC.utcoffset(valid_until)
        or now < observed
        or now > valid_until
        or valid_until <= observed
        or (valid_until - observed).total_seconds() != 60
    ):
        raise V4OperationalReadinessNoPostError(
            "OPERATIONAL_READINESS_EVIDENCE_NOT_FRESH"
        )


class V4OperationalReadinessStoreNoPost:
    """Atomic replace store for short-lived, non-authorizing observations."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, evidence: V4OperationalReadinessEvidenceNoPost) -> None:
        validate_operational_readiness_evidence_no_post(
            evidence,
            expected_reviewed_files_digest=evidence.reviewed_files_digest,
            expected_generation_digest=evidence.generation_digest,
            now_utc=datetime.now(UTC),
        )
        if self.path.is_symlink():
            raise V4OperationalReadinessNoPostError(
                "OPERATIONAL_READINESS_PATH_INVALID"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        if temporary.is_symlink():
            raise V4OperationalReadinessNoPostError(
                "OPERATIONAL_READINESS_PATH_INVALID"
            )
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(evidence), sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as error:
            raise V4OperationalReadinessNoPostError(
                "OPERATIONAL_READINESS_SAVE_FAILED"
            ) from error

    def load(
        self,
        *,
        expected_reviewed_files_digest: str,
        expected_generation_digest: str,
        now_utc: datetime,
    ) -> V4OperationalReadinessEvidenceNoPost | None:
        if not self.path.exists():
            return None
        if self.path.is_symlink() or not self.path.is_file():
            raise V4OperationalReadinessNoPostError(
                "OPERATIONAL_READINESS_PATH_INVALID"
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            evidence = V4OperationalReadinessEvidenceNoPost(**payload)
        except (OSError, TypeError, json.JSONDecodeError):
            raise V4OperationalReadinessNoPostError(
                "OPERATIONAL_READINESS_LOAD_FAILED"
            ) from None
        validate_operational_readiness_evidence_no_post(
            evidence,
            expected_reviewed_files_digest=expected_reviewed_files_digest,
            expected_generation_digest=expected_generation_digest,
            now_utc=now_utc,
        )
        return evidence


def _canonical_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
