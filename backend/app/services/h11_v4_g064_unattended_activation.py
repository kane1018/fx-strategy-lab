"""G064 activation and resident-runtime safety contract."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

G064_GENERATION_LABEL = "H11_AUTO_30M_20260801_G064"
G064_HEARTBEAT_SCHEMA = "H11_V4_G064_RESIDENT_SUPERVISOR_HEARTBEAT_V1"
G064_RUNTIME_EVIDENCE_FILE = "g064-runtime-commissioning-evidence.json"
G064_SERVICE_STATE_SCHEMA = "H11_V4_G064_SCHEDULER_SERVICE_STATE_V1"
G064_EXIT_ONLY_FILE = "g064-exit-only-dispatch.json"
G064_G063_BASELINE_DIGEST = (
    "sha256:cd3472868472e68dcac0eb313e9aab93f9075140906bc03b0ef4f8fb824499ca"
)
G064_PERSISTENT_HALT_FILE = "g064-runtime-halt.json"
G064_PERSISTENT_HALT_SCHEMA = "H11_V4_G064_PERSISTENT_HALT_V1"
G064_PROCESS_LOCK_OWNER_FILE = "process.lock.owner.json"
G064_SCHEDULER_LABEL = "com.fxstrategylab.h11v4.unattended.scheduler"
_DEFAULT_REPOSITORY = Path(__file__).resolve().parents[3]


class V4G064ActivationError(RuntimeError):
    """Fixed safe G064 activation failure."""


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


def _load_g063_baseline() -> V4GmoFrozenGeneration:
    path = _DEFAULT_REPOSITORY / "docs/templates/h11_v4_g063_frozen_generation.json"
    if path.is_symlink() or not path.is_file():
        raise V4G064ActivationError("G064_G063_BASELINE_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["blocked_hours_jst"] = tuple(payload["blocked_hours_jst"])
        payload["weekend_days_jst"] = tuple(payload["weekend_days_jst"])
        baseline = V4GmoFrozenGeneration(**payload)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_G063_BASELINE_INVALID") from error
    if (
        baseline.generation_label != "H11_AUTO_30M_20260731_G063"
        or baseline.digest != G064_G063_BASELINE_DIGEST
        or baseline.live_ready is not False
        or baseline.unattended_live_supported is not False
        or baseline.actual_post_authorized is not False
    ):
        raise V4G064ActivationError("G064_G063_BASELINE_NOT_FROZEN")
    return baseline


def _review_report_digest(entry: dict[str, Any]) -> str:
    stable = {key: value for key, value in entry.items() if key != "report_digest"}
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _review_provenance_is_clear(attestation: dict[str, Any]) -> bool:
    commit = attestation.get("reviewed_commit")
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
        or attestation.get("reviewed_branch") != "main"
        or not isinstance(attestation.get("reviewed_at_utc"), str)
    ):
        return False
    provenance = attestation.get("review_provenance")
    roles = {
        "architecture": "independent_architecture",
        "safety": "independent_safety",
        "operations": "independent_operations",
    }
    if not isinstance(provenance, dict) or set(provenance) != set(roles):
        return False
    for name, reviewer_role in roles.items():
        entry = provenance.get(name)
        if not isinstance(entry, dict):
            return False
        if (
            entry.get("reviewer_role") != reviewer_role
            or entry.get("status") != "CLEAR"
            or entry.get("review_scope") != "READ_ONLY_NO_POST"
            or entry.get("reviewed_commit") != commit
            or entry.get("reviewed_branch") != "main"
            or not isinstance(entry.get("reviewed_at_utc"), str)
            or entry.get("broker_read_count") != 0
            or entry.get("broker_post_count") != 0
            or entry.get("private_api_read_count") != 0
            or entry.get("credential_read_count") != 0
            or entry.get("notification_attempt_count") != 0
            or entry.get("launchagent_executed") is not False
            or entry.get("report_digest") != _review_report_digest(entry)
        ):
            return False
    return True


def _verify_commissioning_artifacts(
    *, generation: V4GmoFrozenGeneration, payload: object, attestation: object
) -> None:
    if (
        not isinstance(payload, dict)
        or payload.get("generation_digest") != generation.digest
        or payload.get("reviewed_files_digest") != generation.implementation_digest
        or payload.get("artifact_digest") != _stable_artifact_digest(payload)
        or payload.get("artifact_digest")
        != generation.runtime_commissioning_evidence_digest
        or payload.get("broker_post_count") != 0
        or payload.get("broker_write") is not False
        or payload.get("actual_post_count") != 0
        or payload.get("broker_post_authorized") is not False
        or payload.get("private_api_read_count") != 0
        or payload.get("credential_read_count") != 0
        or payload.get("notification_attempt_count") != 0
        or payload.get("launchagent_executed") is not False
        or any(
            payload.get(field) is not True
            for field in (
                "focused_tests_clear",
                "related_tests_clear",
                "ruff_clear",
                "danger_scan_clear",
                "diff_check_clear",
                "architecture_review_clear",
                "safety_review_clear",
                "operations_review_clear",
            )
        )
        or payload.get("actual_post_authorized") is not False
        or payload.get("status") != "G064_RUNTIME_COMMISSIONED_NO_POST"
        or not isinstance(attestation, dict)
        or attestation.get("generation_digest") != generation.digest
        or attestation.get("reviewed_files_digest") != generation.implementation_digest
        or attestation.get("artifact_digest") != _stable_artifact_digest(attestation)
        or attestation.get("artifact_digest") != generation.successor_halt_release_digest
        or payload.get("independent_review_attestation_digest")
        != attestation.get("artifact_digest")
        or attestation.get("review_method") != "INDEPENDENT_A_S_O_REVIEW"
        or attestation.get("review_scope") != "READ_ONLY_NO_POST"
        or attestation.get("review_evidence")
        != {
            "architecture": "CLEAR",
            "operations": "CLEAR",
            "safety": "CLEAR",
        }
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or not _review_provenance_is_clear(attestation)
    ):
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_BINDING_INVALID")


def verify_g064_generation_contract(*, generation: V4GmoFrozenGeneration) -> None:
    if (
        generation.generation_label != G064_GENERATION_LABEL
        or generation.status != "UNATTENDED_LIVE_COMMISSIONED"
        or generation.live_ready is not True
        or generation.unattended_live_supported is not True
        or generation.actual_post_authorized is not False
        or not isinstance(generation.activation_source_generation_digest, str)
        or generation.successful_canary_evidence_digest is not None
        or not isinstance(generation.runtime_commissioning_evidence_digest, str)
        or not isinstance(generation.successor_halt_release_digest, str)
        or not isinstance(generation.reconciliation_contract_digest, str)
    ):
        raise V4G064ActivationError("G064_GENERATION_NOT_COMMISSIONED")
    baseline = _load_g063_baseline()
    if generation.activation_source_generation_digest != baseline.digest:
        raise V4G064ActivationError("G064_G063_BASELINE_DIGEST_MISMATCH")
    evidence = (
        _DEFAULT_REPOSITORY
        / "docs/templates/h11_v4_g064_runtime_commissioning_evidence.json"
    )
    if evidence.is_symlink() or not evidence.is_file():
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_MISSING")
    try:
        payload = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_INVALID") from error
    attestation_path = (
        _DEFAULT_REPOSITORY
        / "docs/templates/h11_v4_g064_independent_review_attestation.json"
    )
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_ATTESTATION_INVALID") from error
    _verify_commissioning_artifacts(
        generation=generation, payload=payload, attestation=attestation
    )


def verify_g064_generation_activation(
    *, generation: V4GmoFrozenGeneration, state_root: Path | None = None
) -> None:
    verify_g064_generation_contract(generation=generation)
    if state_root is None:
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_MISSING")
    evidence_path = state_root / G064_RUNTIME_EVIDENCE_FILE
    if evidence_path.is_symlink() or not evidence_path.is_file():
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_MISSING")
    if (state_root / G064_PERSISTENT_HALT_FILE).is_file():
        raise V4G064ActivationError("G064_RUNTIME_PERSISTENT_HALT")
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        attestation_path = (
            _DEFAULT_REPOSITORY
            / "docs/templates/h11_v4_g064_independent_review_attestation.json"
        )
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(
            str(payload["runtime_observed_at_utc"])
        ).astimezone(UTC)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_INVALID") from error
    age = (datetime.now(UTC) - observed).total_seconds()
    if age < 0 or age > 60:
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_STALE")
    _verify_commissioning_artifacts(
        generation=generation, payload=payload, attestation=attestation
    )


def write_g064_runtime_evidence_no_post(
    *, state_root: Path, generation: V4GmoFrozenGeneration, observed_at_utc: datetime
) -> None:
    if observed_at_utc.tzinfo is None or state_root.is_symlink():
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_WRITE_INVALID")
    verify_g064_generation_contract(generation=generation)
    source = (
        _DEFAULT_REPOSITORY
        / "docs/templates/h11_v4_g064_runtime_commissioning_evidence.json"
    )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_INVALID") from error
    if not isinstance(payload, dict):
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_INVALID")
    payload["runtime_observed_at_utc"] = observed_at_utc.astimezone(UTC).isoformat()
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G064_RUNTIME_EVIDENCE_FILE
    temporary = state_root / f"{G064_RUNTIME_EVIDENCE_FILE}.tmp"
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise V4G064ActivationError("G064_RUNTIME_EVIDENCE_WRITE_FAILED") from error


def write_g064_scheduler_service_evidence(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    observed_at_utc: datetime,
    service_pid: int | None = None,
) -> None:
    if (
        observed_at_utc.tzinfo is None
        or state_root.is_symlink()
        or (service_pid is not None and type(service_pid) is not int)
    ):
        raise V4G064ActivationError("G064_SERVICE_STATE_WRITE_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "actual_post_count": 0,
        "broker_read": False,
        "broker_post_authorized": False,
        "broker_write": False,
        "credential_read_count": 0,
        "generation_digest": generation_digest,
        "launchagent_executed": False,
        "loaded": True,
        "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
        "notification_attempt_count": 0,
        "private_api_read_count": 0,
        "reviewed_files_digest": reviewed_files_digest,
        "service_pid": os.getpid() if service_pid is None else service_pid,
        "service_role": "G064_RESIDENT_WORKER",
        "schema": G064_SERVICE_STATE_SCHEMA,
    }
    target = state_root / "scheduler-service-state.json"
    temporary = state_root / "scheduler-service-state.json.tmp"
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise V4G064ActivationError("G064_SERVICE_STATE_WRITE_FAILED") from error


def _process_lock_is_held(path: Path, *, expected_pid: int | None = None) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    handle = None
    try:
        handle = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if expected_pid is None:
                return True
            owner_path = path.with_name(G064_PROCESS_LOCK_OWNER_FILE)
            try:
                owner = json.loads(owner_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            return owner.get("pid") == expected_pid
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return False
    finally:
        if handle is not None:
            handle.close()


def verify_g064_scheduler_binding(
    *,
    generation: V4GmoFrozenGeneration,
    plist_path: Path,
    state_root: Path | None = None,
    now_utc: datetime,
    maximum_age_seconds: int = 60,
) -> None:
    verify_g064_generation_activation(generation=generation, state_root=state_root)
    if now_utc.tzinfo is None or plist_path.is_symlink() or not plist_path.is_file():
        raise V4G064ActivationError("G064_SCHEDULER_BINDING_NOT_CLEAR")
    try:
        import plistlib

        payload = plistlib.loads(plist_path.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise V4G064ActivationError("G064_SCHEDULER_BINDING_INVALID") from error
    args = payload.get("ProgramArguments")
    expected_args = [
        str(Path(sys.executable).resolve()),
        str(
            _DEFAULT_REPOSITORY
            / "backend/scripts/h11_auto_v4_unattended_live_scheduled_launcher.py"
        ),
        "--repository",
        str(_DEFAULT_REPOSITORY),
        "--expected-reviewed-files-digest",
        generation.implementation_digest,
        "--expected-generation-digest",
        generation.digest,
    ]
    if (
        payload.get("Label") != G064_SCHEDULER_LABEL
        or payload.get("RunAtLoad") is not True
        or payload.get("KeepAlive") is not True
        or payload.get("ThrottleInterval") != 15
        or payload.get("StartInterval") != 15
        or payload.get("WorkingDirectory") != str(_DEFAULT_REPOSITORY / "backend")
        or not isinstance(args, list)
        or args != expected_args
    ):
        raise V4G064ActivationError("G064_SCHEDULER_BINDING_NOT_CLEAR")
    root = state_root or v4_gmo_runtime_state_root(
        repository=_DEFAULT_REPOSITORY,
        generation_digest=generation.digest,
    )
    heartbeat_path = root / "supervisor-heartbeat.json"
    try:
        heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(str(heartbeat["observed_at_utc"])).astimezone(UTC)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_HEARTBEAT_INVALID") from error
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    if (
        heartbeat.get("schema") != G064_HEARTBEAT_SCHEMA
        or heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("broker_read") is not False
        or heartbeat.get("broker_post_authorized") is not False
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("actual_post_count") != 0
        or heartbeat.get("private_api_read_count") != 0
        or heartbeat.get("credential_read_count") != 0
        or heartbeat.get("notification_attempt_count") != 0
        or heartbeat.get("runtime_risk_ready") is not True
        or heartbeat.get("heartbeat_chain_beat") is not True
        or heartbeat.get("dead_man_alive") is not True
        or heartbeat.get("process_lock_clear") is not True
        or age < 0
        or age > maximum_age_seconds
    ):
        raise V4G064ActivationError("G064_HEARTBEAT_NOT_CLEAR")
    service_path = root / "scheduler-service-state.json"
    try:
        service = json.loads(service_path.read_text(encoding="utf-8"))
        service_observed = datetime.fromisoformat(
            str(service["observed_at_utc"])
        ).astimezone(UTC)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_SERVICE_STATE_INVALID") from error
    try:
        worker_pid = json.loads(
            (root / "worker-heartbeat.json").read_text(encoding="utf-8")
        ).get("pid")
    except (OSError, TypeError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_WORKER_LEASE_INVALID") from error
    service_age = (now_utc.astimezone(UTC) - service_observed).total_seconds()
    if (
        service.get("schema") != G064_SERVICE_STATE_SCHEMA
        or service.get("loaded") is not True
        or service.get("generation_digest") != generation.digest
        or service.get("reviewed_files_digest") != generation.implementation_digest
        or service.get("broker_write") is not False
        or service.get("actual_post_count") != 0
        or service.get("broker_read") is not False
        or service.get("broker_post_authorized") is not False
        or service.get("private_api_read_count") != 0
        or service.get("credential_read_count") != 0
        or service.get("notification_attempt_count") != 0
        or service.get("launchagent_executed") is not False
        or service.get("service_pid") != worker_pid
        or service.get("service_role") != "G064_RESIDENT_WORKER"
        or service_age < 0
        or service_age > maximum_age_seconds
    ):
        raise V4G064ActivationError("G064_SERVICE_STATE_NOT_CLEAR")
    if not g064_worker_lease_alive(
        state_root=root,
        generation_digest=generation.digest,
        reviewed_files_digest=generation.implementation_digest,
        now_utc=now_utc,
        maximum_age_seconds=maximum_age_seconds,
    ):
        raise V4G064ActivationError("G064_WORKER_NOT_BOUND_TO_PROCESS_LOCK")


def write_g064_worker_lease(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime,
) -> None:
    if now_utc.tzinfo is None:
        raise V4G064ActivationError("G064_WORKER_LEASE_CLOCK_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    path = state_root / "worker-heartbeat.json"
    temporary = state_root / "worker-heartbeat.json.tmp"
    payload: dict[str, Any] = {
        "actual_post_count": 0,
        "broker_read": False,
        "broker_post_authorized": False,
        "broker_write": False,
        "credential_read_count": 0,
        "generation_digest": generation_digest,
        "lock_path": str(state_root / "process.lock"),
        "notification_attempt_count": 0,
        "observed_at_utc": now_utc.astimezone(UTC).isoformat(),
        "pid": os.getpid(),
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "reviewed_files_digest": reviewed_files_digest,
        "role": "G064_RESIDENT_WORKER",
        "schema": "H11_V4_G064_WORKER_HEARTBEAT_V1",
    }
    owner_payload = {
        "generation_digest": generation_digest,
        "pid": payload["pid"],
        "reviewed_files_digest": reviewed_files_digest,
        "role": "G064_RESIDENT_WORKER",
        "schema": "H11_V4_G064_PROCESS_LOCK_OWNER_V1",
    }
    owner_path = state_root / G064_PROCESS_LOCK_OWNER_FILE
    owner_temporary = state_root / f"{G064_PROCESS_LOCK_OWNER_FILE}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        with owner_temporary.open("w", encoding="utf-8") as stream:
            json.dump(owner_payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(owner_temporary, owner_path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise V4G064ActivationError("G064_WORKER_LEASE_WRITE_FAILED") from error


def clear_g064_worker_lease(*, state_root: Path, expected_pid: int) -> None:
    path = state_root / "worker-heartbeat.json"
    if path.is_symlink():
        raise V4G064ActivationError("G064_WORKER_LEASE_SYMLINK")
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise V4G064ActivationError("G064_WORKER_LEASE_INVALID") from error
        if payload.get("pid") != expected_pid:
            raise V4G064ActivationError("G064_WORKER_LEASE_OWNER_MISMATCH")
    path.unlink(missing_ok=True)
    (state_root / G064_PROCESS_LOCK_OWNER_FILE).unlink(missing_ok=True)


def g064_worker_lease_alive(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime,
    maximum_age_seconds: int = 60,
) -> bool:
    path = state_root / "worker-heartbeat.json"
    if path.is_symlink() or not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        owner = json.loads(
            (state_root / G064_PROCESS_LOCK_OWNER_FILE).read_text(encoding="utf-8")
        )
        observed = datetime.fromisoformat(str(payload["observed_at_utc"])).astimezone(UTC)
        pid = int(payload["pid"])
        os.kill(pid, 0)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    return (
        payload.get("schema") == "H11_V4_G064_WORKER_HEARTBEAT_V1"
        and payload.get("generation_digest") == generation_digest
        and payload.get("reviewed_files_digest") == reviewed_files_digest
        and payload.get("lock_path") == str(state_root / "process.lock")
        and payload.get("role") == "G064_RESIDENT_WORKER"
        and payload.get("broker_post_count") == 0
        and owner.get("schema") == "H11_V4_G064_PROCESS_LOCK_OWNER_V1"
        and owner.get("generation_digest") == generation_digest
        and owner.get("reviewed_files_digest") == reviewed_files_digest
        and owner.get("pid") == pid
        and owner.get("role") == "G064_RESIDENT_WORKER"
        and payload.get("broker_read") is False
        and payload.get("broker_post_authorized") is False
        and payload.get("broker_write") is False
        and payload.get("actual_post_count") == 0
        and payload.get("private_api_read_count") == 0
        and payload.get("credential_read_count") == 0
        and payload.get("notification_attempt_count") == 0
        and _process_lock_is_held(state_root / "process.lock", expected_pid=pid)
        and 0 <= age <= maximum_age_seconds
    )


def write_g064_persistent_halt_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    """Persist a safe HALTED marker for runtime exceptions or interruption."""

    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G064_PERSISTENT_HALT_FILE
    temporary = state_root / f"{G064_PERSISTENT_HALT_FILE}.tmp"
    payload = {
        "actual_post_count": 0,
        "broker_write": False,
        "generation_digest": generation_digest,
        "reason_label": "G064_RUNTIME_UNEXPECTED_FAILURE",
        "reviewed_files_digest": reviewed_files_digest,
        "schema": G064_PERSISTENT_HALT_SCHEMA,
        "status": "HALTED",
    }
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise V4G064ActivationError("G064_PERSISTENT_HALT_WRITE_FAILED") from error


def write_g064_exit_only_dispatch_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    position_open: bool,
    protection_confirmed: bool,
    ownership_exact: bool,
    quantity_matches: bool,
) -> None:
    """Record ARM-OFF exit-only intent without performing any broker action."""

    if position_open and not all(
        (protection_confirmed, ownership_exact, quantity_matches)
    ):
        raise V4G064ActivationError("G064_EXIT_ONLY_PROOF_NOT_CLEAR")
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G064_EXIT_ONLY_FILE
    temporary = state_root / f"{G064_EXIT_ONLY_FILE}.tmp"
    payload = {
        "broker_post_count": 0,
        "broker_write": False,
        "entry_gate_open": False,
        "generation_digest": generation_digest,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "position_open": position_open,
        "protection_confirmed": protection_confirmed,
        "ownership_exact": ownership_exact,
        "quantity_matches": quantity_matches,
        "reviewed_files_digest": reviewed_files_digest,
        "schema": "H11_V4_G064_EXIT_ONLY_DISPATCH_V1",
        "status": "G064_EXIT_ONLY_ACTIVE_NO_POST"
        if position_open
        else "G064_FLAT_RECONCILIATION_COMPLETE_NO_POST",
    }
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise V4G064ActivationError("G064_EXIT_ONLY_DISPATCH_WRITE_FAILED") from error


def run_g064_exit_only_dispatch_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
) -> None:
    """Consume the local exit-only handoff without broker or account access."""

    marker = state_root / G064_EXIT_ONLY_FILE
    if marker.is_symlink() or not marker.is_file():
        raise V4G064ActivationError("G064_EXIT_ONLY_DISPATCH_MISSING")
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G064ActivationError("G064_EXIT_ONLY_DISPATCH_INVALID") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "H11_V4_G064_EXIT_ONLY_DISPATCH_V1"
        or payload.get("generation_digest") != generation_digest
        or payload.get("reviewed_files_digest") != reviewed_files_digest
        or payload.get("entry_gate_open") is not False
        or payload.get("broker_write") is not False
        or payload.get("broker_post_count") != 0
        or payload.get("position_open") is not True
        or not all(
            payload.get(field) is True
            for field in (
                "protection_confirmed",
                "ownership_exact",
                "quantity_matches",
            )
        )
    ):
        raise V4G064ActivationError("G064_EXIT_ONLY_DISPATCH_NOT_CLEAR")
    target = state_root / "g064-exit-only-dispatch-state.json"
    temporary = state_root / "g064-exit-only-dispatch-state.json.tmp"
    state = {
        "broker_post_count": 0,
        "broker_write": False,
        "entry_gate_open": False,
        "generation_digest": generation_digest,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "protection_monitor_required": True,
        "reconciliation_required": True,
        "reviewed_files_digest": reviewed_files_digest,
        "schema": "H11_V4_G064_EXIT_ONLY_DISPATCH_STATE_V1",
        "status": "G064_EXIT_ONLY_DISPATCH_ACTIVE_NO_POST",
    }
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise V4G064ActivationError("G064_EXIT_ONLY_DISPATCH_STATE_WRITE_FAILED") from error
