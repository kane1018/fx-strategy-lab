"""G038 successor-only unattended activation evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import (
    load_external_preparation_gate,
    load_g053_flat_only_carry_forward_evidence,
    require_clean_main,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import (
    V4_GMO_UNATTENDED_ACTIVATED_STATUS,
    V4GmoFrozenGeneration,
    load_v4_gmo_frozen_generation,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g037_unattended_commissioning_no_post import (
    G037_CANARY_EVIDENCE_SCHEMA,
    G037_TERMINAL_FLAT_HALT,
)
from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    validate_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
)
from app.services.h11_v4_unattended_controller_snapshot_no_post import (
    controller_cycle_binding_no_post,
)
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_account_snapshot_state_directory,
    v4_unattended_g037_canary_evidence_path,
    v4_unattended_g038_release_path,
)

G038_RELEASE_SCHEMA = "H11_V4_G038_SUCCESSOR_HALT_RELEASE_NO_POST_V1"
_G052_GENERATION_DIGEST = (
    "sha256:4da28f2e6c49b7fd18fcdf466af9afbf4d875fc6273eaa22d7f2c0352bc8de13"
)
_G052_REVIEWED_FILES_DIGEST = (
    "sha256:a0736d9f06cb912ef262c8321068de9564df8fb1b7f0dd6b0e01ef527ee9d4d3"
)
_G053_GENERATION_LABEL = "H11_AUTO_30M_20260730_G053"
_G053_GENERATION_DIGEST = (
    "sha256:d7e25da3f35da7842b4549913cd1a78749fe64d870b3b9aa4f78e0ce931de665"
)
_G053_REVIEWED_FILES_DIGEST = (
    "sha256:ea83124ef74d681dfcd6ac736fb1980dd55f1d94565f1c4910c0e7d03c49f327"
)
_G054_GENERATION_LABEL = "H11_AUTO_30M_20260730_G054"
_G055_GENERATION_LABEL = "H11_AUTO_30M_20260730_G055"
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


def record_g053_flat_only_successor_release_once(
    *,
    repository: Path,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
) -> V4G038SuccessorRelease:
    """Bind G053 to G052's known-flat result while preserving G052's HALT."""

    require_clean_main(repository=repository)
    target_reviewed = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=target_reviewed,
    )
    if (
        generation.generation_label != _G053_GENERATION_LABEL
        or generation.activation_source_generation_digest
        != _G052_GENERATION_DIGEST
        or generation.successful_canary_evidence_digest is None
    ):
        raise V4G038ActivationError("G053_RELEASE_TARGET_INVALID")
    external_gate = load_external_preparation_gate(repository=repository)
    flat_evidence = load_g053_flat_only_carry_forward_evidence(
        repository=repository,
        external_gate=external_gate,
        generation_digest=generation.digest,
    )
    if (
        flat_evidence.source_generation_digest != _G052_GENERATION_DIGEST
        or flat_evidence.source_reviewed_files_digest
        != _G052_REVIEWED_FILES_DIGEST
        or flat_evidence.account_flat is not True
        or flat_evidence.active_orders_zero is not True
        or flat_evidence.source_halt_remains_latched is not True
        or flat_evidence.broker_post_authorized is not False
        or flat_evidence.activation_permit_issued is not False
        or bool(flat_evidence) is not False
    ):
        raise V4G038ActivationError("G053_FLAT_EVIDENCE_NOT_CLEAR")
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest=_G052_GENERATION_DIGEST,
        predecessor_halt_generation_digest=_G052_GENERATION_DIGEST,
        source_reviewed_files_digest=_G052_REVIEWED_FILES_DIGEST,
        target_reviewed_files_digest=target_reviewed,
        target_generation_label=_G053_GENERATION_LABEL,
        successful_canary_evidence_digest=(
            generation.successful_canary_evidence_digest
        ),
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    if release.digest != generation.successor_halt_release_digest:
        raise V4G038ActivationError("G053_RELEASE_BINDING_MISMATCH")
    path = v4_unattended_g038_release_path(
        state_root=state_root,
        target_reviewed_files_digest=target_reviewed,
    )
    _reject_symlink_ancestry(path, allow_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = release.canonical_json + "\n"
    if path.exists():
        if path.is_symlink() or path.read_text(encoding="utf-8") != payload:
            raise V4G038ActivationError("G053_EXISTING_RELEASE_MISMATCH")
        return release
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise V4G038ActivationError(
            "G053_RELEASE_RACE_OR_UNKNOWN_RESULT"
        ) from error
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


def record_g054_manual_flat_successor_release_once(
    *,
    repository: Path,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    now_utc: datetime | None = None,
) -> V4G038SuccessorRelease:
    return _record_manual_flat_successor_release_once(
        repository=repository,
        state_root=state_root,
        now_utc=now_utc,
        target_generation_label=_G054_GENERATION_LABEL,
    )


def record_g055_manual_flat_successor_release_once(
    *,
    repository: Path,
    state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    now_utc: datetime | None = None,
) -> V4G038SuccessorRelease:
    return _record_manual_flat_successor_release_once(
        repository=repository,
        state_root=state_root,
        now_utc=now_utc,
        target_generation_label=_G055_GENERATION_LABEL,
    )


def _record_manual_flat_successor_release_once(
    *,
    repository: Path,
    state_root: Path,
    now_utc: datetime | None,
    target_generation_label: str,
) -> V4G038SuccessorRelease:
    """Release a corrective generation from a fresh flat snapshot and G053 HALT."""

    require_clean_main(repository=repository)
    target_reviewed = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=target_reviewed,
    )
    if (
        generation.generation_label != target_generation_label
        or generation.activation_source_generation_digest
        != _G053_GENERATION_DIGEST
        or generation.successful_canary_evidence_digest is None
    ):
        raise V4G038ActivationError("G054_RELEASE_TARGET_INVALID")
    snapshot = V4AccountSnapshotStoreNoPost(
        v4_unattended_account_snapshot_state_directory(
            generation_digest=generation.digest,
        )
    ).load_completed(
        expected_reviewed_files_digest=target_reviewed,
        expected_generation_digest=generation.digest,
    )
    evaluated_at = (now_utc or datetime.now(UTC)).astimezone(UTC)
    if snapshot is not None:
        validate_bound_account_snapshot_evidence_no_post(
            snapshot,
            expected_reviewed_files_digest=target_reviewed,
            expected_generation_digest=generation.digest,
            expected_cycle_binding_digest=controller_cycle_binding_no_post(
                generation_digest=generation.digest,
                observed_at_utc=evaluated_at,
            ),
            now_utc=evaluated_at,
        )
    if (
        snapshot is None
        or snapshot.account_flat is not True
        or snapshot.active_orders_zero is not True
        or snapshot.broker_get_count != 3
        or snapshot.broker_write is not False
        or snapshot.broker_post_count != 0
        or snapshot.raw_response_retained is not False
        or snapshot.identifier_exposed is not False
        or bool(snapshot) is not False
    ):
        raise V4G038ActivationError("G054_FLAT_EVIDENCE_NOT_CLEAR")
    source_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=_G053_GENERATION_DIGEST,
    )
    source_lock = H11AutoProcessLock(source_root / "process.lock")
    if not source_lock.acquire():
        raise V4G038ActivationError("G054_G053_FOREGROUND_STILL_RUNNING")
    try:
        _require_g053_halted_protected_cycle(
            repository=repository,
            source_lock=source_lock,
        )
        return _record_g054_release_locked(
            generation=generation,
            target_reviewed=target_reviewed,
            state_root=state_root,
            target_generation_label=target_generation_label,
        )
    finally:
        source_lock.release()


def _record_g054_release_locked(
    *,
    generation: V4GmoFrozenGeneration,
    target_reviewed: str,
    state_root: Path,
    target_generation_label: str,
) -> V4G038SuccessorRelease:
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest=_G053_GENERATION_DIGEST,
        predecessor_halt_generation_digest=_G053_GENERATION_DIGEST,
        source_reviewed_files_digest=_G053_REVIEWED_FILES_DIGEST,
        target_reviewed_files_digest=target_reviewed,
        target_generation_label=target_generation_label,
        successful_canary_evidence_digest=(
            generation.successful_canary_evidence_digest
        ),
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    if release.digest != generation.successor_halt_release_digest:
        raise V4G038ActivationError("G054_RELEASE_BINDING_MISMATCH")
    path = v4_unattended_g038_release_path(
        state_root=state_root,
        target_reviewed_files_digest=target_reviewed,
    )
    _reject_symlink_ancestry(path, allow_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = release.canonical_json + "\n"
    if path.exists():
        if path.is_symlink() or path.read_text(encoding="utf-8") != payload:
            raise V4G038ActivationError("G054_EXISTING_RELEASE_MISMATCH")
        return release
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise V4G038ActivationError(
            "G054_RELEASE_RACE_OR_UNKNOWN_RESULT"
        ) from error
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


def _require_g053_halted_protected_cycle(
    *,
    repository: Path,
    source_lock: H11AutoProcessLock,
) -> None:
    root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=_G053_GENERATION_DIGEST,
    )
    if not source_lock.held or source_lock.path != root / "process.lock":
        raise V4G038ActivationError("G054_G053_SOURCE_LOCK_NOT_HELD")
    database = root / "coordinator.sqlite3"
    if database.is_symlink() or not database.is_file():
        raise V4G038ActivationError("G054_G053_STATE_NOT_CLEAR")
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        halt = connection.execute(
            "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
        ).fetchone()
        pending = connection.execute(
            "SELECT 1 FROM metadata WHERE key='pending_transport_attempt'"
        ).fetchone()
        cycle = connection.execute(
            "SELECT COUNT(*) count,"
            "SUM(CASE WHEN realized_pnl_jpy IS NULL THEN 1 ELSE 0 END) unresolved "
            "FROM cycles"
        ).fetchone()
        attempts = connection.execute(
            "SELECT action,COUNT(*) count FROM attempts GROUP BY action"
        ).fetchall()
        generation_row = connection.execute(
            "SELECT value FROM metadata WHERE key='generation_digest'"
        ).fetchone()
    except sqlite3.Error as error:
        raise V4G038ActivationError("G054_G053_STATE_NOT_CLEAR") from error
    finally:
        if "connection" in locals():
            connection.close()
    actual_attempts = {str(row["action"]): int(row["count"]) for row in attempts}
    try:
        source_risk_state = PhaseBRiskStore(
            root / "risk.json",
            policy=v4_gmo_risk_policy(),
        ).load()
    except Exception as error:
        raise V4G038ActivationError("G054_G053_STATE_NOT_CLEAR") from error
    if (
        generation_row is None
        or generation_row["value"] != _G053_GENERATION_DIGEST
        or halt is None
        or halt["value"] != "true"
        or pending is not None
        or cycle is None
        or int(cycle["count"]) != 1
        or int(cycle["unresolved"] or 0) != 1
        or actual_attempts
        != {"EXACT_SIZE_OCO_PROTECTION": 1, "MARKET_ENTRY": 1}
        or source_risk_state.current_day_jst != "2026-07-30"
        or source_risk_state.entries_today != 3
    ):
        raise V4G038ActivationError("G054_G053_STATE_NOT_CLEAR")


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
