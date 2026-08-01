"""G067 runtime-only activation contract.

This module validates the reviewed no-POST runtime artifacts and never grants
broker authorization.  Live entry remains a separate operator boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration

G067_GENERATION_LABEL = "H11_AUTO_30M_20260802_G067"
G067_RUNTIME_EVIDENCE_FILE = "g067-runtime-commissioning-evidence.json"
G067_PERSISTENT_HALT_FILE = "g067-runtime-halt.json"
G067_HEARTBEAT_SCHEMA = "H11_V4_G067_RESIDENT_SUPERVISOR_HEARTBEAT_V1"
G067_RUNTIME_EVIDENCE_SCHEMA = "H11_V4_G067_RUNTIME_COMMISSIONING_EVIDENCE_V1"
G067_PERSISTENT_HALT_SCHEMA = "H11_V4_G067_PERSISTENT_HALT_V1"
_DEFAULT_REPOSITORY = Path(__file__).resolve().parents[3]


class V4G067ActivationError(RuntimeError):
    """Fixed safe G067 activation failure."""


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


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _review_provenance_is_clear(attestation: dict[str, Any]) -> bool:
    commit = attestation.get("reviewed_commit")
    provenance = attestation.get("review_provenance")
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
        or attestation.get("reviewed_branch") != "main"
        or not isinstance(attestation.get("reviewed_at_utc"), str)
        or not isinstance(provenance, dict)
        or set(provenance) != {"architecture", "safety", "operations"}
    ):
        return False
    roles = {
        "architecture": "independent_architecture",
        "safety": "independent_safety",
        "operations": "independent_operations",
    }
    for name, role in roles.items():
        entry = provenance.get(name)
        if (
            not isinstance(entry, dict)
            or entry.get("reviewer_role") != role
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
        ):
            return False
    return True


def _load_artifacts(repository: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        evidence = json.loads(
            (
                repository / "docs/templates/h11_v4_g067_runtime_commissioning_evidence.json"
            ).read_text(encoding="utf-8")
        )
        attestation = json.loads(
            (
                repository / "docs/templates/h11_v4_g067_independent_review_attestation.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise V4G067ActivationError("G067_RUNTIME_ARTIFACT_INVALID") from error
    if not isinstance(evidence, dict) or not isinstance(attestation, dict):
        raise V4G067ActivationError("G067_RUNTIME_ARTIFACT_INVALID")
    return evidence, attestation


def verify_g067_generation_contract(
    *, generation: V4GmoFrozenGeneration, repository: Path | None = None
) -> None:
    if (
        generation.generation_label != G067_GENERATION_LABEL
        or generation.status != "UNATTENDED_LIVE_COMMISSIONED"
        or generation.live_ready is not True
        or generation.unattended_live_supported is not True
        or generation.actual_post_authorized is not False
        or not _valid_digest(generation.activation_source_generation_digest)
        or generation.successful_canary_evidence_digest is not None
        or not _valid_digest(generation.runtime_commissioning_evidence_digest)
        or not _valid_digest(generation.successor_halt_release_digest)
        or not _valid_digest(generation.reconciliation_contract_digest)
    ):
        raise V4G067ActivationError("G067_GENERATION_NOT_COMMISSIONED")
    root = (repository or _DEFAULT_REPOSITORY).resolve()
    evidence, attestation = _load_artifacts(root)
    if (
        evidence.get("schema") != G067_RUNTIME_EVIDENCE_SCHEMA
        or evidence.get("generation_label") != G067_GENERATION_LABEL
        or evidence.get("generation_digest") != generation.digest
        or evidence.get("reviewed_files_digest") != generation.implementation_digest
        or evidence.get("artifact_digest") != _stable_artifact_digest(evidence)
        or evidence.get("artifact_digest") != generation.runtime_commissioning_evidence_digest
        or evidence.get("status") != "G067_RUNTIME_COMMISSIONED_NO_POST"
        or evidence.get("live_ready") is not True
        or evidence.get("unattended_live_supported") is not True
        or evidence.get("actual_post_authorized") is not False
        or evidence.get("broker_post_authorized") is not False
        or evidence.get("broker_post_count") != 0
        or evidence.get("broker_write") is not False
        or evidence.get("actual_post_count") != 0
        or evidence.get("private_api_read_count") != 0
        or evidence.get("credential_read_count") != 0
        or evidence.get("notification_attempt_count") != 0
        or evidence.get("launchagent_executed") is not False
        or evidence.get("predecessor_evidence_limited") is not True
        or any(
            evidence.get(field) is not True
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
        or attestation.get("schema") != "H11_V4_G067_INDEPENDENT_REVIEW_ATTESTATION_V1"
        or attestation.get("generation_label") != G067_GENERATION_LABEL
        or attestation.get("generation_digest") != generation.digest
        or attestation.get("reviewed_files_digest") != generation.implementation_digest
        or attestation.get("artifact_digest") != _stable_artifact_digest(attestation)
        or attestation.get("artifact_digest") != generation.successor_halt_release_digest
        or attestation.get("review_method") != "INDEPENDENT_A_S_O_REVIEW"
        or attestation.get("review_scope") != "READ_ONLY_NO_POST"
        or attestation.get("review_evidence")
        != {"architecture": "CLEAR", "operations": "CLEAR", "safety": "CLEAR"}
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or not _review_provenance_is_clear(attestation)
    ):
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_BINDING_INVALID")


def verify_g067_generation_activation(
    *,
    generation: V4GmoFrozenGeneration,
    state_root: Path | None = None,
    repository: Path | None = None,
    now_utc: datetime | None = None,
    maximum_age_seconds: int = 60,
) -> None:
    verify_g067_generation_contract(generation=generation, repository=repository)
    if state_root is None or state_root.is_symlink():
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_MISSING")
    halt_path = state_root / G067_PERSISTENT_HALT_FILE
    evidence_path = state_root / G067_RUNTIME_EVIDENCE_FILE
    if halt_path.is_file() or halt_path.is_symlink() or not evidence_path.is_file():
        raise V4G067ActivationError("G067_RUNTIME_NOT_CLEAR")
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        if (
            payload.get("generation_label") != G067_GENERATION_LABEL
            or payload.get("generation_digest") != generation.digest
            or payload.get("reviewed_files_digest") != generation.implementation_digest
            or payload.get("broker_write") is not False
            or payload.get("broker_post_count") != 0
            or payload.get("private_api_read_count") != 0
            or payload.get("credential_read_count") != 0
            or payload.get("pending") is True
            or payload.get("unknown_halt") is True
        ):
            raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_UNSAFE")
        observed = datetime.fromisoformat(str(payload["runtime_observed_at_utc"])).astimezone(UTC)
    except V4G067ActivationError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_INVALID") from error
    age = ((now_utc or datetime.now(UTC)).astimezone(UTC) - observed).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_STALE")


def verify_g067_scheduler_binding(
    *,
    generation: V4GmoFrozenGeneration,
    plist_path: Path,
    state_root: Path | None = None,
    now_utc: datetime,
    maximum_age_seconds: int = 60,
) -> None:
    """Verify the resident G067 files and plist without invoking launchctl."""

    verify_g067_generation_activation(
        generation=generation,
        state_root=state_root,
        repository=_DEFAULT_REPOSITORY,
        now_utc=now_utc,
        maximum_age_seconds=maximum_age_seconds,
    )
    if now_utc.tzinfo is None or plist_path.is_symlink() or not plist_path.is_file():
        raise V4G067ActivationError("G067_SCHEDULER_BINDING_NOT_CLEAR")
    try:
        import plistlib

        payload = plistlib.loads(plist_path.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise V4G067ActivationError("G067_SCHEDULER_BINDING_INVALID") from error
    args = payload.get("ProgramArguments")
    expected_launcher = str(
        _DEFAULT_REPOSITORY / "backend/scripts/h11_auto_v4_g067_runtime_bootstrap_no_post.py"
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
        or payload.get("RunAtLoad") is not True
        or payload.get("KeepAlive") is not False
        or "StartInterval" in payload
        or payload.get("WorkingDirectory") != str(_DEFAULT_REPOSITORY / "backend")
    ):
        raise V4G067ActivationError("G067_SCHEDULER_BINDING_NOT_CLEAR")
    root = state_root or (
        _DEFAULT_REPOSITORY
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / f"generation-{generation.digest.removeprefix('sha256:')}"
    )
    try:
        heartbeat = json.loads((root / "heartbeat.json").read_text(encoding="utf-8"))
        dead_man = json.loads((root / "dead-man.json").read_text(encoding="utf-8"))
        chain = json.loads((root / "heartbeat-chain.json").read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(str(heartbeat["observed_at_utc"])).astimezone(UTC)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G067ActivationError("G067_HEARTBEAT_INVALID") from error
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    common_safe = all(
        payload.get(field) in (False, 0)
        for payload in (heartbeat, dead_man, chain)
        for field in (
            "broker_read",
            "broker_write",
            "private_api_read",
            "credential_read",
            "actual_post_count",
        )
    )
    if (
        heartbeat.get("schema") != G067_HEARTBEAT_SCHEMA
        or heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("status") != "FRESH"
        or heartbeat.get("pending") is not False
        or heartbeat.get("unknown_halt") is not False
        or dead_man.get("status") != "ALIVE"
        or chain.get("status") != "FRESH"
        or not (root / "process.lock").is_file()
        or (root / "process.lock").is_symlink()
        or not common_safe
        or age < 0
        or age > maximum_age_seconds
    ):
        raise V4G067ActivationError("G067_HEARTBEAT_NOT_CLEAR")


def write_g067_runtime_evidence_no_post(
    *,
    state_root: Path,
    generation: V4GmoFrozenGeneration,
    observed_at_utc: datetime,
    repository: Path | None = None,
) -> None:
    if observed_at_utc.tzinfo is None or state_root.is_symlink():
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_WRITE_INVALID")
    root = (repository or _DEFAULT_REPOSITORY).resolve()
    verify_g067_generation_contract(generation=generation, repository=root)
    try:
        payload = json.loads(
            (root / "docs/templates/h11_v4_g067_runtime_commissioning_evidence.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as error:
        raise V4G067ActivationError("G067_RUNTIME_ARTIFACT_INVALID") from error
    if not isinstance(payload, dict):
        raise V4G067ActivationError("G067_RUNTIME_ARTIFACT_INVALID")
    payload["runtime_observed_at_utc"] = observed_at_utc.astimezone(UTC).isoformat()
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G067_RUNTIME_EVIDENCE_FILE
    temporary = state_root / f".{G067_RUNTIME_EVIDENCE_FILE}.{os.getpid()}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise V4G067ActivationError("G067_RUNTIME_EVIDENCE_WRITE_FAILED") from error


def write_g067_persistent_halt_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    if (
        state_root.is_symlink()
        or not _valid_digest(generation_digest)
        or not _valid_digest(reviewed_files_digest)
    ):
        raise V4G067ActivationError("G067_PERSISTENT_HALT_WRITE_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G067_PERSISTENT_HALT_FILE
    if target.exists():
        if target.is_symlink():
            raise V4G067ActivationError("G067_PERSISTENT_HALT_WRITE_INVALID")
        return
    payload = {
        "schema": G067_PERSISTENT_HALT_SCHEMA,
        "generation_label": G067_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "status": "HALTED",
        "reason_label": "G067_RUNTIME_UNEXPECTED_FAILURE",
        "broker_read": False,
        "broker_write": False,
        "broker_post_authorized": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "notification_attempt_count": 0,
        "actual_post_count": 0,
    }
    temporary = state_root / f".{G067_PERSISTENT_HALT_FILE}.{os.getpid()}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise V4G067ActivationError("G067_PERSISTENT_HALT_WRITE_FAILED") from error
