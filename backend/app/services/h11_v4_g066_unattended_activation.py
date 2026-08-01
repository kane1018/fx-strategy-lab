"""G066 runtime-only successor contract for the resident scheduler.

G066 changes only operation-result observability and recovery classification.
The entry, risk, quantity, protection, and broker hard-guard contracts remain
those of the reviewed G065 runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration

G066_GENERATION_LABEL = "H11_AUTO_30M_20260802_G066"
G066_RUNTIME_EVIDENCE_FILE = "g066-runtime-commissioning-evidence.json"
G066_PERSISTENT_HALT_FILE = "g066-runtime-halt.json"
G066_HEARTBEAT_SCHEMA = "H11_V4_G066_RESIDENT_SUPERVISOR_HEARTBEAT_V1"
G066_RUNTIME_EVIDENCE_SCHEMA = "H11_V4_G066_RUNTIME_COMMISSIONING_EVIDENCE_V1"
G066_PERSISTENT_HALT_SCHEMA = "H11_V4_G066_PERSISTENT_HALT_V1"
_DEFAULT_REPOSITORY = Path(__file__).resolve().parents[3]


class V4G066ActivationError(RuntimeError):
    """Fixed safe G066 activation failure."""


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
    evidence_path = repository / "docs/templates/h11_v4_g066_runtime_commissioning_evidence.json"
    attestation_path = repository / "docs/templates/h11_v4_g066_independent_review_attestation.json"
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G066ActivationError("G066_RUNTIME_ARTIFACT_INVALID") from error
    if not isinstance(evidence, dict) or not isinstance(attestation, dict):
        raise V4G066ActivationError("G066_RUNTIME_ARTIFACT_INVALID")
    return evidence, attestation


def verify_g066_generation_contract(
    *, generation: V4GmoFrozenGeneration, repository: Path | None = None
) -> None:
    if (
        generation.generation_label != G066_GENERATION_LABEL
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
        raise V4G066ActivationError("G066_GENERATION_NOT_COMMISSIONED")
    root = (repository or _DEFAULT_REPOSITORY).resolve()
    evidence, attestation = _load_artifacts(root)
    if (
        evidence.get("generation_label") != G066_GENERATION_LABEL
        or evidence.get("generation_digest") != generation.digest
        or evidence.get("reviewed_files_digest") != generation.implementation_digest
        or evidence.get("artifact_digest") != _stable_artifact_digest(evidence)
        or evidence.get("artifact_digest") != generation.runtime_commissioning_evidence_digest
        or evidence.get("status") != "G066_RUNTIME_COMMISSIONED_NO_POST"
        or evidence.get("live_ready") is not True
        or evidence.get("unattended_live_supported") is not True
        or evidence.get("actual_post_authorized") is not False
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
        or attestation.get("generation_label") != G066_GENERATION_LABEL
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
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_BINDING_INVALID")


def verify_g066_generation_activation(
    *,
    generation: V4GmoFrozenGeneration,
    state_root: Path | None = None,
    repository: Path | None = None,
    now_utc: datetime | None = None,
    maximum_age_seconds: int = 60,
) -> None:
    verify_g066_generation_contract(generation=generation, repository=repository)
    if state_root is None or state_root.is_symlink():
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_MISSING")
    halt_path = state_root / G066_PERSISTENT_HALT_FILE
    evidence_path = state_root / G066_RUNTIME_EVIDENCE_FILE
    if halt_path.is_file() or halt_path.is_symlink() or not evidence_path.is_file():
        raise V4G066ActivationError("G066_RUNTIME_NOT_CLEAR")
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(str(payload["runtime_observed_at_utc"])).astimezone(UTC)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_INVALID") from error
    age = ((now_utc or datetime.now(UTC)).astimezone(UTC) - observed).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_STALE")


def write_g066_runtime_evidence_no_post(
    *, state_root: Path, generation: V4GmoFrozenGeneration, observed_at_utc: datetime
) -> None:
    if observed_at_utc.tzinfo is None or state_root.is_symlink():
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_WRITE_INVALID")
    verify_g066_generation_contract(generation=generation)
    source = _DEFAULT_REPOSITORY / "docs/templates/h11_v4_g066_runtime_commissioning_evidence.json"
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4G066ActivationError("G066_RUNTIME_ARTIFACT_INVALID") from error
    if not isinstance(payload, dict):
        raise V4G066ActivationError("G066_RUNTIME_ARTIFACT_INVALID")
    payload["runtime_observed_at_utc"] = observed_at_utc.astimezone(UTC).isoformat()
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G066_RUNTIME_EVIDENCE_FILE
    temporary = state_root / f"{G066_RUNTIME_EVIDENCE_FILE}.{os.getpid()}.tmp"
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
        raise V4G066ActivationError("G066_RUNTIME_EVIDENCE_WRITE_FAILED") from error


def write_g066_persistent_halt_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    if (
        state_root.is_symlink()
        or not _valid_digest(generation_digest)
        or not _valid_digest(reviewed_files_digest)
    ):
        raise V4G066ActivationError("G066_PERSISTENT_HALT_WRITE_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G066_PERSISTENT_HALT_FILE
    if target.exists():
        if target.is_symlink():
            raise V4G066ActivationError("G066_PERSISTENT_HALT_WRITE_INVALID")
        return
    temporary = state_root / f"{G066_PERSISTENT_HALT_FILE}.{os.getpid()}.tmp"
    payload = {
        "actual_post_count": 0,
        "broker_post_authorized": False,
        "broker_post_count": 0,
        "broker_read": False,
        "broker_write": False,
        "credential_read_count": 0,
        "generation_digest": generation_digest,
        "notification_attempt_count": 0,
        "private_api_read_count": 0,
        "reason_label": "G066_RUNTIME_UNEXPECTED_FAILURE",
        "reviewed_files_digest": reviewed_files_digest,
        "schema": G066_PERSISTENT_HALT_SCHEMA,
        "status": "HALTED",
    }
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
        raise V4G066ActivationError("G066_PERSISTENT_HALT_WRITE_FAILED") from error
