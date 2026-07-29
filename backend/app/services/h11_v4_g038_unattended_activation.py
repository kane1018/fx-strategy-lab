"""G038 successor-only unattended activation evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    require_clean_main,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import (
    V4_GMO_UNATTENDED_ACTIVATED_STATUS,
    V4GmoFrozenGeneration,
)
from app.services.h11_v4_g037_unattended_commissioning_no_post import (
    G037_CANARY_EVIDENCE_SCHEMA,
    G037_TERMINAL_FLAT_HALT,
)
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_g037_canary_evidence_path,
    v4_unattended_g038_release_path,
)

G038_RELEASE_SCHEMA = "H11_V4_G038_SUCCESSOR_HALT_RELEASE_NO_POST_V1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class V4G038ActivationError(RuntimeError):
    """Fixed safe G038 activation evidence error."""


@dataclass(frozen=True)
class V4G038SuccessorRelease:
    schema: str
    source_generation_digest: str
    predecessor_halt_generation_digest: str
    source_reviewed_files_digest: str
    target_reviewed_files_digest: str
    target_generation_label: str
    successful_canary_evidence_digest: str
    source_halt_remains_latched: bool
    successor_activation_released: bool
    permit_issued: bool = False
    broker_post_authorized: bool = False
    broker_write: bool = False
    broker_post_count: int = 0

    def __post_init__(self) -> None:
        digests = (
            self.source_generation_digest,
            self.predecessor_halt_generation_digest,
            self.source_reviewed_files_digest,
            self.target_reviewed_files_digest,
            self.successful_canary_evidence_digest,
        )
        if (
            self.schema != G038_RELEASE_SCHEMA
            or not all(isinstance(value, str) and _SHA256.fullmatch(value) for value in digests)
            or not self.target_generation_label.startswith("H11_AUTO_30M_")
            or self.source_halt_remains_latched is not True
            or self.successor_activation_released is not True
            or self.permit_issued is not False
            or self.broker_post_authorized is not False
            or self.broker_write is not False
            or self.broker_post_count != 0
        ):
            raise V4G038ActivationError("G038_RELEASE_INVALID")

    @property
    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json.encode()).hexdigest()

    def __bool__(self) -> bool:
        return False


def record_g038_successor_release_once(
    *,
    repository: Path,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    source_generation_digest: str,
    source_reviewed_files_digest: str,
    target_reviewed_files_digest: str,
    target_generation_label: str,
) -> V4G038SuccessorRelease:
    require_clean_main(repository=repository)
    if reviewed_files_digest(repository=repository) != target_reviewed_files_digest:
        raise V4G038ActivationError("G038_TARGET_REVIEWED_FILES_MISMATCH")
    evidence_path = v4_unattended_g037_canary_evidence_path(
        state_root=state_root,
        generation_digest=source_generation_digest,
    )
    evidence = _load_object(evidence_path)
    declared_evidence_digest = evidence.pop("evidence_digest", None)
    evidence_digest = "sha256:" + hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        evidence.get("schema") != G037_CANARY_EVIDENCE_SCHEMA
        or declared_evidence_digest != evidence_digest
        or evidence.get("target_generation_digest") != source_generation_digest
        or evidence.get("target_reviewed_files_digest") != source_reviewed_files_digest
        or evidence.get("successful_canary_fixed") is not True
        or evidence.get("post_flat_halt_classification") != G037_TERMINAL_FLAT_HALT
        or evidence.get("post_flat_halt_blocks_activation") is not True
        or evidence.get("flat_cycle_count") != 1
        or evidence.get("protected_cycle_count") != 1
        or evidence.get("unresolved_cycle_count") != 0
        or evidence.get("entry_attempt_count") != 1
        or evidence.get("protection_attempt_count") != 1
        or evidence.get("broker_write") is not False
        or evidence.get("broker_post_count") != 0
    ):
        raise V4G038ActivationError("G037_CANARY_EVIDENCE_NOT_CLEAR")
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest=source_generation_digest,
        predecessor_halt_generation_digest=str(
            evidence["origin_generation_digest"]
        ),
        source_reviewed_files_digest=source_reviewed_files_digest,
        target_reviewed_files_digest=target_reviewed_files_digest,
        target_generation_label=target_generation_label,
        successful_canary_evidence_digest=evidence_digest,
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    path = v4_unattended_g038_release_path(
        state_root=state_root,
        target_reviewed_files_digest=target_reviewed_files_digest,
    )
    _reject_symlink_ancestry(path, allow_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = release.canonical_json + "\n"
    if path.exists():
        if path.is_symlink() or path.read_text(encoding="utf-8") != payload:
            raise V4G038ActivationError("G038_EXISTING_RELEASE_MISMATCH")
        return release
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise V4G038ActivationError("G038_RELEASE_RACE_OR_UNKNOWN_RESULT") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    return release


def verify_g038_generation_activation(
    *,
    generation: V4GmoFrozenGeneration,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
) -> V4G038SuccessorRelease:
    if (
        generation.status != V4_GMO_UNATTENDED_ACTIVATED_STATUS
        or generation.live_ready is not True
        or generation.unattended_live_supported is not True
        or generation.actual_post_authorized is not False
        or generation.activation_source_generation_digest is None
        or generation.successful_canary_evidence_digest is None
        or generation.successor_halt_release_digest is None
    ):
        raise V4G038ActivationError("G038_GENERATION_NOT_ACTIVATED")
    path = v4_unattended_g038_release_path(
        state_root=state_root,
        target_reviewed_files_digest=generation.implementation_digest,
    )
    payload = _load_object(path)
    try:
        release = V4G038SuccessorRelease(**payload)
    except TypeError as error:
        raise V4G038ActivationError("G038_RELEASE_INVALID") from error
    if (
        release.digest != generation.successor_halt_release_digest
        or release.source_generation_digest != generation.activation_source_generation_digest
        or release.target_reviewed_files_digest != generation.implementation_digest
        or release.target_generation_label != generation.generation_label
        or release.successful_canary_evidence_digest
        != generation.successful_canary_evidence_digest
    ):
        raise V4G038ActivationError("G038_RELEASE_BINDING_MISMATCH")
    return release


def record_g038_scheduler_heartbeat(
    *,
    generation: V4GmoFrozenGeneration,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    now_utc: datetime | None = None,
) -> None:
    verify_g038_generation_activation(generation=generation, state_root=state_root)
    moment = now_utc or datetime.now(UTC)
    path = _scheduler_heartbeat_path(
        state_root=state_root,
        generation_digest=generation.digest,
    )
    _reject_symlink_ancestry(path, allow_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema": "H11_V4_G038_SCHEDULER_HEARTBEAT_V1",
                "generation_digest": generation.digest,
                "reviewed_files_digest": generation.implementation_digest,
                "observed_at_utc": moment.isoformat(),
                "broker_post_count": 0,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def verify_g038_scheduler_binding(
    *,
    generation: V4GmoFrozenGeneration,
    plist_path: Path,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    now_utc: datetime,
    maximum_age_seconds: int = 660,
) -> None:
    import plistlib

    verify_g038_generation_activation(generation=generation, state_root=state_root)
    if now_utc.tzinfo is None or plist_path.is_symlink() or not plist_path.is_file():
        raise V4G038ActivationError("G038_SCHEDULER_BINDING_NOT_CLEAR")
    try:
        plist = plistlib.loads(plist_path.read_bytes())
        arguments = plist["ProgramArguments"]
        expected_pairs = (
            ("--expected-reviewed-files-digest", generation.implementation_digest),
            ("--expected-generation-digest", generation.digest),
        )
        for name, value in expected_pairs:
            index = arguments.index(name)
            if arguments[index + 1] != value:
                raise ValueError
        heartbeat = _load_object(
            _scheduler_heartbeat_path(
                state_root=state_root,
                generation_digest=generation.digest,
            )
        )
        observed = datetime.fromisoformat(str(heartbeat["observed_at_utc"]))
        age = (now_utc.astimezone(UTC) - observed.astimezone(UTC)).total_seconds()
    except (KeyError, ValueError, TypeError, OSError, IndexError) as error:
        raise V4G038ActivationError("G038_SCHEDULER_BINDING_NOT_CLEAR") from error
    if (
        heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("broker_post_count") != 0
        or age < 0
        or age > maximum_age_seconds
    ):
        raise V4G038ActivationError("G038_SCHEDULER_BINDING_NOT_CLEAR")


def _scheduler_heartbeat_path(*, state_root: Path, generation_digest: str) -> Path:
    normalized = generation_digest.removeprefix("sha256:")
    if not _SHA256.fullmatch(generation_digest):
        raise V4G038ActivationError("G038_GENERATION_DIGEST_INVALID")
    return (
        state_root.resolve()
        / "h11_v4_unattended_live"
        / f"generation-{normalized}"
        / "scheduler-heartbeat.json"
    )


def _load_object(path: Path) -> dict[str, object]:
    _reject_symlink_ancestry(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G038ActivationError("G038_EVIDENCE_INVALID") from error
    if not isinstance(value, dict):
        raise V4G038ActivationError("G038_EVIDENCE_INVALID")
    return value


def _reject_symlink_ancestry(path: Path, *, allow_missing: bool = False) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise V4G038ActivationError("G038_EVIDENCE_SYMLINK_REFUSED")
        if current.parent == current:
            break
        current = current.parent
    if not allow_missing and not path.is_file():
        raise V4G038ActivationError("G038_EVIDENCE_MISSING")
