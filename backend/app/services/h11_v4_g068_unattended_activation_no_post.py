"""G068 no-POST runtime and release-boundary contract.

This module deliberately stops before any broker capability.  It owns only
local state, generation binding, safe projection, and one-use release markers.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration

G068_GENERATION_LABEL = "H11_AUTO_30M_20260802_G068"
G068_PERSISTENT_HALT_FILE = "g068-runtime-halt.json"
G068_HEARTBEAT_SCHEMA = "H11_V4_G068_RESIDENT_SUPERVISOR_HEARTBEAT_V1"
G068_RELEASE_SCHEMA = "H11_V4_G068_RELEASE_ACTIVATION_NO_POST_V1"
G068_RUNTIME_EVIDENCE_SCHEMA = "H11_V4_G068_RUNTIME_COMMISSIONING_EVIDENCE_V1"
G068_OPERATION_STARTED_FILE = "operation-60-result.started.json"
G068_OPERATION_OUTCOME_FILE = "operation-60-result.outcome.json"
G068_RELEASE_STARTED_FILE = "release-activation.started.json"
G068_RELEASE_OUTCOME_FILE = "release-activation.outcome.json"
_MAX_AGE_SECONDS = 60
_DEFAULT_REPOSITORY = Path(__file__).resolve().parents[3]


class V4G068ActivationError(RuntimeError):
    """Safe G068 failure containing no external data."""


class G068RuntimeState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


@dataclass(frozen=True)
class G068RuntimeProjection:
    arm_state: str
    effective_state: G068RuntimeState
    entry_gate_open: bool
    entry_state: str
    position_open: bool
    ownership_exact: bool
    quantity_matches: bool
    protection_confirmed: bool
    broker_write: bool = False
    actual_post_authorized: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "arm_state": self.arm_state,
            "effective_state": self.effective_state.value,
            "entry_gate_open": self.entry_gate_open,
            "entry_state": self.entry_state,
            "position_open": self.position_open,
            "ownership_exact": self.ownership_exact,
            "quantity_matches": self.quantity_matches,
            "protection_confirmed": self.protection_confirmed,
            "broker_write": False,
            "actual_post_authorized": False,
        }


def _bool(value: object) -> bool:
    return type(value) is bool


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _stable_artifact_digest(payload: dict[str, Any]) -> str:
    excluded = {
        "artifact_digest",
        "generation_digest",
        "generation_manifest_digest",
        "reviewed_files_digest",
        "independent_review_attestation_digest",
        "runtime_observed_at_utc",
    }
    stable = {key: value for key, value in payload.items() if key not in excluded}
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def verify_g068_generation_contract(
    *, generation: V4GmoFrozenGeneration, repository: Path | None = None
) -> None:
    """Require a fully reviewed G068 candidate before any runtime state is written."""

    root = (repository or _DEFAULT_REPOSITORY).resolve()
    try:
        evidence = json.loads(
            (root / "docs/templates/h11_v4_g068_runtime_commissioning_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        attestation = json.loads(
            (root / "docs/templates/h11_v4_g068_independent_review_attestation.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as error:
        raise V4G068ActivationError("G068_RUNTIME_ARTIFACT_INVALID") from error
    review_clear = (
        attestation.get("review_evidence")
        == {"architecture": "CLEAR", "operations": "CLEAR", "safety": "CLEAR"}
        and all(
            attestation.get(f"{name}_status") == "CLEAR"
            for name in ("architecture", "safety", "operations")
        )
        and attestation.get("review_method") == "INDEPENDENT_A_S_O_REVIEW"
        and attestation.get("review_scope") == "READ_ONLY_NO_POST"
        and attestation.get("external_human_signoff_verified") is True
    )
    if (
        generation.generation_label != G068_GENERATION_LABEL
        or generation.actual_post_authorized is not False
        or not _valid_digest(generation.implementation_digest)
        or not isinstance(evidence, dict)
        or evidence.get("schema") != G068_RUNTIME_EVIDENCE_SCHEMA
        or evidence.get("generation_label") != G068_GENERATION_LABEL
        or evidence.get("generation_digest") != generation.digest
        or evidence.get("reviewed_files_digest") != generation.implementation_digest
        or evidence.get("artifact_digest") != _stable_artifact_digest(evidence)
        or evidence.get("artifact_digest") != generation.runtime_commissioning_evidence_digest
        or evidence.get("actual_post_authorized") is not False
        or evidence.get("broker_post_count") != 0
        or evidence.get("private_api_read_count") != 0
        or evidence.get("credential_read_count") != 0
        or not isinstance(attestation, dict)
        or attestation.get("schema") != "H11_V4_G068_INDEPENDENT_REVIEW_ATTESTATION_V1"
        or attestation.get("generation_label") != G068_GENERATION_LABEL
        or attestation.get("generation_digest") != generation.digest
        or attestation.get("reviewed_files_digest") != generation.implementation_digest
        or attestation.get("artifact_digest") != _stable_artifact_digest(attestation)
        or attestation.get("artifact_digest") != generation.successor_halt_release_digest
        or not review_clear
    ):
        raise V4G068ActivationError("G068_RUNTIME_EVIDENCE_BINDING_INVALID")


def _position_value(position: Mapping[str, Any] | None, key: str) -> object:
    if not isinstance(position, Mapping):
        return None
    return position.get(key)


def project_g068_runtime_state(
    *,
    arm_state: str,
    position: Mapping[str, Any] | None,
    runtime_clear: bool = True,
    generation_matches: bool = True,
    heartbeat_alive: bool = True,
    process_lock_clear: bool = True,
    dead_man_alive: bool = True,
    pending_transport: bool = False,
    unknown_halt: bool = False,
) -> G068RuntimeProjection:
    """Project only explicit local evidence; missing position fields are unknown."""

    if arm_state not in {"ON", "OFF"} or not all(
        _bool(value)
        for value in (
            runtime_clear,
            generation_matches,
            heartbeat_alive,
            process_lock_clear,
            dead_man_alive,
            pending_transport,
            unknown_halt,
        )
    ):
        raise V4G068ActivationError("G068_RUNTIME_INPUT_INVALID")

    open_count = _position_value(position, "open_position_count")
    active_count = _position_value(position, "active_order_count")
    position_shape_clear = type(open_count) is int and type(active_count) is int
    position_open = open_count == 1 if position_shape_clear else False
    position_flat = open_count == 0 and active_count == 0 if position_shape_clear else False
    ownership = _position_value(position, "ownership_exact")
    quantity = _position_value(position, "quantity_matches")
    protection = _position_value(position, "protection_confirmed")
    position_flags_known = all(_bool(value) for value in (ownership, quantity, protection))

    unsafe = (
        pending_transport
        or unknown_halt
        or not runtime_clear
        or not generation_matches
        or not heartbeat_alive
        or not process_lock_clear
        or not dead_man_alive
        or not position_shape_clear
        or not (position_flat or position_open)
        or (
            position_open
            and (not position_flags_known or not all((ownership, quantity, protection)))
        )
    )
    if unsafe:
        state = G068RuntimeState.HALTED
        return G068RuntimeProjection(
            arm_state=arm_state,
            effective_state=state,
            entry_gate_open=False,
            entry_state="HALTED",
            position_open=position_open,
            ownership_exact=ownership is True,
            quantity_matches=quantity is True,
            protection_confirmed=protection is True,
        )
    if position_open:
        state = G068RuntimeState.ON_EXIT_ONLY if arm_state == "ON" else G068RuntimeState.EXIT_ONLY
        return G068RuntimeProjection(
            arm_state=arm_state,
            effective_state=state,
            entry_gate_open=False,
            entry_state="EXIT_ONLY",
            position_open=True,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        )
    state = G068RuntimeState.ON_WAITING if arm_state == "ON" else G068RuntimeState.OFF
    return G068RuntimeProjection(
        arm_state=arm_state,
        effective_state=state,
        entry_gate_open=state is G068RuntimeState.ON_WAITING,
        entry_state="ENTRY_GATE_OPEN" if state is G068RuntimeState.ON_WAITING else "DISARMED",
        position_open=False,
        ownership_exact=False,
        quantity_matches=False,
        protection_confirmed=False,
    )


def write_g068_runtime_projection_no_post(
    *, state_root: Path, generation: V4GmoFrozenGeneration, reviewed_files_digest: str
) -> G068RuntimeProjection:
    """Refresh the local ARM/position projection without external I/O."""

    from app.services.h11_v4_g065_position_reconciliation_no_post import (
        load_g065_position_reconciliation_no_post,
    )
    from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore
    from app.services.h11_v4_unattended_live_paths import (
        DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
        v4_unattended_live_arm_state_path,
    )

    arm = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(
            state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
            generation_digest=generation.digest,
        )
    ).check(
        expected_generation_digest=generation.digest,
        expected_reviewed_files_digest=reviewed_files_digest,
    )
    position = load_g065_position_reconciliation_no_post(
        state_root=state_root,
        generation_digest=generation.digest,
        now_utc=datetime.now(UTC),
    )
    position_payload: dict[str, object] | None = None
    if position.evidence_available:
        position_payload = {
            "open_position_count": 1 if position.position_open else 0,
            "active_order_count": 1 if position.position_open else 0,
            "ownership_exact": position.ownership_exact,
            "quantity_matches": position.quantity_matches,
            "protection_confirmed": position.protection_confirmed,
        }
    projection = project_g068_runtime_state(
        arm_state="ON" if arm.armed else "OFF",
        position=position_payload,
    )
    _atomic_json(state_root / "runtime-projection.json", projection.to_safe_dict())
    return projection


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise V4G068ActivationError("G068_STATE_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as error:
        raise V4G068ActivationError("G068_STATE_WRITE_FAILED") from error
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def write_g068_health_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime,
    chain_index: int,
) -> None:
    if now_utc.tzinfo is None or type(chain_index) is not int or chain_index < 1:
        raise V4G068ActivationError("G068_HEALTH_INPUT_INVALID")
    observed = now_utc.astimezone(UTC).isoformat()
    common = {
        "generation_label": G068_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "broker_read": False,
        "broker_write": False,
        "private_api_read": False,
        "credential_read": False,
        "actual_post_count": 0,
        "pending": False,
        "unknown_halt": False,
        "observed_at_utc": observed,
    }
    _atomic_json(
        state_root / "heartbeat.json",
        {**common, "schema": G068_HEARTBEAT_SCHEMA, "status": "FRESH", "chain_index": chain_index},
    )
    _atomic_json(
        state_root / "dead-man.json",
        {**common, "schema": "H11_V4_G068_DEAD_MAN_V1", "status": "ALIVE"},
    )
    _atomic_json(
        state_root / "heartbeat-chain.json",
        {
            **common,
            "schema": "H11_V4_G068_HEARTBEAT_CHAIN_V1",
            "status": "FRESH",
            "chain_index": chain_index,
        },
    )


def write_g068_persistent_halt_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, reason: str
) -> None:
    if not isinstance(reason, str) or not reason or any(char in reason for char in "\r\n"):
        raise V4G068ActivationError("G068_HALT_REASON_INVALID")
    _atomic_json(
        state_root / G068_PERSISTENT_HALT_FILE,
        {
            "schema": "H11_V4_G068_PERSISTENT_HALT_V1",
            "generation_label": G068_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "HALTED",
            "reason_label": reason,
            "broker_write": False,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
        },
    )


class G068OwnerLock:
    """Owner-aware local lock with one safe stale-owner recovery attempt."""

    def __init__(self, path: Path, *, generation_digest: str) -> None:
        self.path = path
        self.generation_digest = generation_digest
        self.owner_token = f"{os.getpid()}:{generation_digest}"
        self.held = False

    def acquire(self) -> None:
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise V4G068ActivationError("G068_LOCK_PATH_INVALID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for stale_attempt in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if stale_attempt:
                    raise V4G068ActivationError("G068_PROCESS_LOCK_CONFLICT") from None
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                    pid = payload.get("pid")
                    owner_generation = payload.get("generation_digest")
                    if type(pid) is not int or owner_generation != self.generation_digest:
                        raise V4G068ActivationError("G068_PROCESS_LOCK_UNKNOWN")
                    os.kill(pid, 0)
                except ProcessLookupError:
                    stale = self.path.with_name(f"{self.path.name}.stale.{pid}")
                    os.replace(self.path, stale)
                    continue
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise V4G068ActivationError("G068_PROCESS_LOCK_UNKNOWN") from error
                raise V4G068ActivationError("G068_PROCESS_LOCK_CONFLICT") from None
            else:
                try:
                    payload = {
                        "schema": "H11_V4_G068_PROCESS_LOCK_V1",
                        "pid": os.getpid(),
                        "generation_digest": self.generation_digest,
                        "owner_token": self.owner_token,
                    }
                    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                        stream.write("\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    self.held = True
                    return
                except OSError as error:
                    raise V4G068ActivationError("G068_PROCESS_LOCK_WRITE_FAILED") from error
        raise V4G068ActivationError("G068_PROCESS_LOCK_CONFLICT")

    def release(self) -> None:
        if not self.held:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("owner_token") != self.owner_token:
                raise V4G068ActivationError("G068_PROCESS_LOCK_OWNER_MISMATCH")
            self.path.unlink()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise V4G068ActivationError("G068_PROCESS_LOCK_RELEASE_FAILED") from error
        finally:
            self.held = False


def begin_g068_one_use_marker(*, state_root: Path, filename: str, payload: dict[str, Any]) -> None:
    if not filename.endswith(".started.json"):
        raise V4G068ActivationError("G068_MARKER_FILENAME_INVALID")
    _atomic_exclusive_json(state_root / filename, payload)


def record_g068_one_use_outcome(
    *, state_root: Path, filename: str, payload: dict[str, Any], outcome: str
) -> None:
    if outcome not in {"PASSED", "FAILED", "UNKNOWN"}:
        raise V4G068ActivationError("G068_OUTCOME_INVALID")
    started = state_root / filename.replace(".outcome.json", ".started.json")
    if not started.is_file() or started.is_symlink():
        raise V4G068ActivationError("G068_STARTED_MARKER_MISSING")
    _atomic_exclusive_json(state_root / filename, {**payload, "status": outcome})


def _atomic_exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise V4G068ActivationError("G068_MARKER_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise V4G068ActivationError("G068_MARKER_ALREADY_EXISTS") from error
    except OSError as error:
        raise V4G068ActivationError("G068_MARKER_WRITE_FAILED") from error


def verify_g068_scheduler_binding(
    *, generation: Any, plist_path: Path, state_root: Path, now_utc: datetime
) -> None:
    verify_g068_generation_contract(generation=generation, repository=_DEFAULT_REPOSITORY)
    if generation.generation_label != G068_GENERATION_LABEL:
        raise V4G068ActivationError("G068_GENERATION_MISMATCH")
    if plist_path.is_symlink() or not plist_path.is_file():
        raise V4G068ActivationError("G068_SCHEDULER_BINDING_MISSING")
    try:
        payload = plistlib.loads(plist_path.read_bytes())
        heartbeat = json.loads((state_root / "heartbeat.json").read_text(encoding="utf-8"))
        dead_man = json.loads((state_root / "dead-man.json").read_text(encoding="utf-8"))
        chain = json.loads((state_root / "heartbeat-chain.json").read_text(encoding="utf-8"))
        lock = json.loads((state_root / "process.lock").read_text(encoding="utf-8"))
        projection = json.loads(
            (state_root / "runtime-projection.json").read_text(encoding="utf-8")
        )
        observed = datetime.fromisoformat(heartbeat["observed_at_utc"]).astimezone(UTC)
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        plistlib.InvalidFileException,
    ) as error:
        raise V4G068ActivationError("G068_RUNTIME_HEALTH_INVALID") from error
    if (
        now_utc.tzinfo is None
        or (now_utc.astimezone(UTC) - observed).total_seconds() > _MAX_AGE_SECONDS
    ):
        raise V4G068ActivationError("G068_HEARTBEAT_STALE")
    args = payload.get("ProgramArguments")
    expected_launcher = str(
        _DEFAULT_REPOSITORY / "backend/scripts/h11_auto_v4_g068_runtime_bootstrap_no_post.py"
    )
    expected_tail = [
        "--repository",
        str(_DEFAULT_REPOSITORY),
        "--expected-reviewed-files-digest",
        generation.implementation_digest,
        "--expected-generation-digest",
        generation.digest,
    ]
    if (
        not isinstance(args, list)
        or len(args) < 2
        or args[1] != expected_launcher
        or args[2:] != expected_tail
        or payload.get("WorkingDirectory") != str(_DEFAULT_REPOSITORY / "backend")
        or payload.get("RunAtLoad") is not True
        or payload.get("KeepAlive") is not False
        or "StartInterval" in payload
        or heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("private_api_read") is not False
        or heartbeat.get("credential_read") is not False
        or heartbeat.get("pending") is not False
        or heartbeat.get("unknown_halt") is not False
        or dead_man.get("status") != "ALIVE"
        or chain.get("status") != "FRESH"
        or lock.get("generation_digest") != generation.digest
        or type(lock.get("pid")) is not int
        or lock.get("pid", 0) < 1
        or not isinstance(lock.get("owner_token"), str)
        or projection.get("actual_post_authorized") is not False
        or projection.get("broker_write") is not False
    ):
        raise V4G068ActivationError("G068_RUNTIME_NOT_CLEAR")
