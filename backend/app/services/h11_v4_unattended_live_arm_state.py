"""Generation-bound persistent operator arm state with no broker capability."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

V4_UNATTENDED_LIVE_ARM_STATE_SCHEMA = "H11_V4_UNATTENDED_ARM_STATE_V1"


class V4UnattendedLiveArmStateError(RuntimeError):
    """Fail-closed arm-state error containing safe labels only."""


class V4ArmDesiredState(str, Enum):
    ARMED = "ARMED"
    DISARMED = "DISARMED"


@dataclass(frozen=True)
class V4UnattendedLiveArmCheck:
    armed: bool
    desired_state: V4ArmDesiredState
    revision: int
    blocked_reasons: tuple[str, ...]
    generation_digest: str
    reviewed_files_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.armed) is not bool
            or type(self.revision) is not int
            or self.revision < 0
            or type(self.blocked_reasons) is not tuple
            or not isinstance(self.desired_state, V4ArmDesiredState)
        ):
            raise V4UnattendedLiveArmStateError("ARM_STATE_CHECK_INVALID")
        if self.armed and self.desired_state is not V4ArmDesiredState.ARMED:
            raise V4UnattendedLiveArmStateError("ARM_STATE_CHECK_INCONSISTENT")
        if self.armed and self.blocked_reasons:
            raise V4UnattendedLiveArmStateError("ARM_STATE_CHECK_INCONSISTENT")

    def __bool__(self) -> bool:
        return False


class V4UnattendedLiveArmStore:
    """Read and atomically replace one local operator-intent artifact."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_name("control.lock")

    def check(
        self,
        *,
        expected_generation_digest: str,
        expected_reviewed_files_digest: str,
    ) -> V4UnattendedLiveArmCheck:
        _require_digest(expected_generation_digest)
        _require_digest(expected_reviewed_files_digest)
        if self.path.is_symlink():
            return _blocked(
                generation_digest=expected_generation_digest,
                reviewed_files_digest=expected_reviewed_files_digest,
                reason="ARM_STATE_SYMLINK_REFUSED",
            )
        if not self.path.is_file():
            return _blocked(
                generation_digest=expected_generation_digest,
                reviewed_files_digest=expected_reviewed_files_digest,
                reason="ARM_STATE_MISSING",
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _blocked(
                generation_digest=expected_generation_digest,
                reviewed_files_digest=expected_reviewed_files_digest,
                reason="ARM_STATE_MALFORMED",
            )
        if not isinstance(payload, dict):
            return _blocked(
                generation_digest=expected_generation_digest,
                reviewed_files_digest=expected_reviewed_files_digest,
                reason="ARM_STATE_MALFORMED",
            )
        reasons: list[str] = []
        if payload.get("schema") != V4_UNATTENDED_LIVE_ARM_STATE_SCHEMA:
            reasons.append("ARM_STATE_SCHEMA_INVALID")
        if payload.get("generation_digest") != expected_generation_digest:
            reasons.append("ARM_STATE_GENERATION_MISMATCH")
        if payload.get("reviewed_files_digest") != expected_reviewed_files_digest:
            reasons.append("ARM_STATE_REVIEWED_FILES_MISMATCH")
        revision = payload.get("revision")
        if type(revision) is not int or revision < 1:
            reasons.append("ARM_STATE_REVISION_INVALID")
            revision = 0
        changed_at = payload.get("changed_at_utc")
        if not _valid_utc_timestamp(changed_at):
            reasons.append("ARM_STATE_TIMESTAMP_INVALID")
        if payload.get("source") != "LOCAL_MANUAL_UI":
            reasons.append("ARM_STATE_SOURCE_INVALID")
        try:
            desired = V4ArmDesiredState(payload.get("desired_state"))
        except (TypeError, ValueError):
            reasons.append("ARM_STATE_DESIRED_STATE_INVALID")
            desired = V4ArmDesiredState.DISARMED
        if desired is V4ArmDesiredState.DISARMED:
            reasons.append("OPERATOR_DISARMED")
        deduped = tuple(dict.fromkeys(reasons))
        return V4UnattendedLiveArmCheck(
            armed=desired is V4ArmDesiredState.ARMED and not deduped,
            desired_state=desired,
            revision=revision,
            blocked_reasons=deduped,
            generation_digest=expected_generation_digest,
            reviewed_files_digest=expected_reviewed_files_digest,
        )

    def set_desired_state(
        self,
        *,
        desired_state: V4ArmDesiredState,
        expected_revision: int,
        generation_digest: str,
        reviewed_files_digest: str,
        changed_at_utc: datetime,
    ) -> V4UnattendedLiveArmCheck:
        if not isinstance(desired_state, V4ArmDesiredState):
            raise V4UnattendedLiveArmStateError("ARM_STATE_DESIRED_STATE_INVALID")
        if type(expected_revision) is not int or expected_revision < 0:
            raise V4UnattendedLiveArmStateError("ARM_STATE_EXPECTED_REVISION_INVALID")
        _require_digest(generation_digest)
        _require_digest(reviewed_files_digest)
        if changed_at_utc.tzinfo is None:
            raise V4UnattendedLiveArmStateError("ARM_STATE_CLOCK_INVALID")
        parent = self.path.parent
        if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
            raise V4UnattendedLiveArmStateError("ARM_STATE_PARENT_INVALID")
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = _open_lock(self.lock_path)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            current = self.check(
                expected_generation_digest=generation_digest,
                expected_reviewed_files_digest=reviewed_files_digest,
            )
            if current.revision != expected_revision:
                raise V4UnattendedLiveArmStateError("ARM_STATE_REVISION_CONFLICT")
            if self.path.is_symlink():
                raise V4UnattendedLiveArmStateError("ARM_STATE_SYMLINK_REFUSED")
            revision = expected_revision + 1
            payload = {
                "changed_at_utc": changed_at_utc.astimezone(UTC).isoformat(),
                "desired_state": desired_state.value,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "revision": revision,
                "schema": V4_UNATTENDED_LIVE_ARM_STATE_SCHEMA,
                "source": "LOCAL_MANUAL_UI",
            }
            temporary = self.path.with_name(
                f".{self.path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
            )
            try:
                temp_descriptor = os.open(
                    temporary,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(temp_descriptor, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(self.path)
            except OSError as error:
                raise V4UnattendedLiveArmStateError("ARM_STATE_WRITE_FAILED") from error
            finally:
                if temporary.exists() and not temporary.is_symlink():
                    temporary.unlink()
            return self.check(
                expected_generation_digest=generation_digest,
                expected_reviewed_files_digest=reviewed_files_digest,
            )
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _blocked(
    *,
    generation_digest: str,
    reviewed_files_digest: str,
    reason: str,
) -> V4UnattendedLiveArmCheck:
    return V4UnattendedLiveArmCheck(
        armed=False,
        desired_state=V4ArmDesiredState.DISARMED,
        revision=0,
        blocked_reasons=(reason,),
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    )


def _open_lock(path: Path) -> int:
    if path.is_symlink():
        raise V4UnattendedLiveArmStateError("ARM_STATE_LOCK_SYMLINK_REFUSED")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        return os.open(path, flags, 0o600)
    except OSError as error:
        raise V4UnattendedLiveArmStateError("ARM_STATE_LOCK_FAILED") from error


def _require_digest(value: str) -> None:
    if not isinstance(value, str):
        raise V4UnattendedLiveArmStateError("ARM_STATE_DIGEST_INVALID")
    normalized = value.removeprefix("sha256:")
    if (
        not value.startswith("sha256:")
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4UnattendedLiveArmStateError("ARM_STATE_DIGEST_INVALID")


def _valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None
