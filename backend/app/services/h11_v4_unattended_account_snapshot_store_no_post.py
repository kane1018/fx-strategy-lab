"""Durable one-use store for inert account-snapshot evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    V4AccountSnapshotOperationMarkerNoPost,
    V4BoundAccountSnapshotEvidenceNoPost,
    V4BoundAccountSnapshotEvidenceNoPostError,
)

_STARTED_SCHEMA = "H11_V4_ACCOUNT_SNAPSHOT_PRODUCER_STARTED_V1"
_PASSED_SCHEMA = "H11_V4_ACCOUNT_SNAPSHOT_PRODUCER_PASSED_V1"
_FAILED_SCHEMA = "H11_V4_ACCOUNT_SNAPSHOT_PRODUCER_FAILED_V1"
_STARTED = "ACCOUNT_SNAPSHOT_PRODUCER_STARTED_NO_RETRY"
_PASSED = "ACCOUNT_SNAPSHOT_PRODUCER_COMPLETED_NO_POST"
_FAILED = "ACCOUNT_SNAPSHOT_PRODUCER_FAILED_NO_RETRY"
_FILENAMES = {
    "started": "producer.started.json",
    "passed": "producer.passed.json",
    "failed": "producer.failed.json",
    "evidence": "account-snapshot-evidence.json",
}


class V4AccountSnapshotStoreNoPostError(RuntimeError):
    """Fixed safe failure for the local one-use producer store."""


class V4AccountSnapshotStoreNoPost:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def begin(
        self,
        *,
        reviewed_files_digest: str,
        generation_digest: str,
        cycle_binding_digest: str,
        started_at_utc: str,
    ) -> str:
        self._require_safe_directory()
        payload = {
            "schema": _STARTED_SCHEMA,
            "status": _STARTED,
            "reviewed_files_digest": reviewed_files_digest,
            "generation_digest": generation_digest,
            "cycle_binding_digest": cycle_binding_digest,
            "started_at_utc": started_at_utc,
        }
        payload["artifact_digest"] = _canonical_digest(payload)
        _write_once(self._path("started"), payload)
        return str(payload["artifact_digest"])

    def complete(
        self,
        *,
        evidence: V4BoundAccountSnapshotEvidenceNoPost,
        started_marker_digest: str,
        completed_at_utc: str,
    ) -> None:
        started = self._load_json(self._path("started"))
        self._validate_started(
            started,
            reviewed_files_digest=evidence.reviewed_files_digest,
            generation_digest=evidence.generation_digest,
            cycle_binding_digest=evidence.cycle_binding_digest,
            expected_digest=started_marker_digest,
        )
        if self._path("failed").exists() or self._path("passed").exists():
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_ALREADY_TERMINAL"
            )
        _write_atomic(self._path("evidence"), asdict(evidence))
        payload = {
            "schema": _PASSED_SCHEMA,
            "status": _PASSED,
            "reviewed_files_digest": evidence.reviewed_files_digest,
            "generation_digest": evidence.generation_digest,
            "cycle_binding_digest": evidence.cycle_binding_digest,
            "started_marker_digest": started_marker_digest,
            "evidence_digest": evidence.artifact_digest,
            "completed_at_utc": completed_at_utc,
            "broker_get_count": 3,
            "broker_write": False,
            "broker_post_count": 0,
        }
        payload["artifact_digest"] = _canonical_digest(payload)
        _write_once(self._path("passed"), payload)

    def record_failure(
        self,
        *,
        reviewed_files_digest: str,
        generation_digest: str,
        cycle_binding_digest: str,
        started_marker_digest: str,
        failed_at_utc: str,
        failure_phase: str,
    ) -> None:
        if failure_phase not in {
            "CREDENTIAL",
            "CLIENT",
            "PRIVATE_GET",
            "CYCLE",
            "EVIDENCE",
            "STORE",
        }:
            failure_phase = "UNKNOWN"
        payload = {
            "schema": _FAILED_SCHEMA,
            "status": _FAILED,
            "reviewed_files_digest": reviewed_files_digest,
            "generation_digest": generation_digest,
            "cycle_binding_digest": cycle_binding_digest,
            "started_marker_digest": started_marker_digest,
            "failed_at_utc": failed_at_utc,
            "failure_phase": failure_phase,
            "broker_write": False,
            "broker_post_count": 0,
        }
        payload["artifact_digest"] = _canonical_digest(payload)
        try:
            _write_once(self._path("failed"), payload)
        except V4AccountSnapshotStoreNoPostError:
            pass

    def load_completed(
        self,
        *,
        expected_reviewed_files_digest: str,
        expected_generation_digest: str,
    ) -> V4BoundAccountSnapshotEvidenceNoPost | None:
        if self.directory.is_symlink() or (
            self.directory.exists() and not self.directory.is_dir()
        ):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_PATH_INVALID"
            )
        paths = {name: self._path(name) for name in _FILENAMES}
        if not any(path.exists() for path in paths.values()):
            return None
        if paths["failed"].exists():
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_FAILED_NO_RETRY"
            )
        if not (
            paths["started"].is_file()
            and paths["passed"].is_file()
            and paths["evidence"].is_file()
        ):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_INCOMPLETE_NO_RETRY"
            )
        if any(path.is_symlink() for path in paths.values() if path.exists()):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_PATH_INVALID"
            )
        started = self._load_json(paths["started"])
        passed = self._load_json(paths["passed"])
        evidence = _decode_evidence(self._load_json(paths["evidence"]))
        started_digest = started.get("artifact_digest")
        self._validate_started(
            started,
            reviewed_files_digest=expected_reviewed_files_digest,
            generation_digest=expected_generation_digest,
            cycle_binding_digest=evidence.cycle_binding_digest,
            expected_digest=started_digest,
        )
        expected_passed = {
            "schema": _PASSED_SCHEMA,
            "status": _PASSED,
            "reviewed_files_digest": expected_reviewed_files_digest,
            "generation_digest": expected_generation_digest,
            "cycle_binding_digest": evidence.cycle_binding_digest,
            "started_marker_digest": started_digest,
            "evidence_digest": evidence.artifact_digest,
            "completed_at_utc": passed.get("completed_at_utc"),
            "broker_get_count": 3,
            "broker_write": False,
            "broker_post_count": 0,
        }
        expected_passed["artifact_digest"] = _canonical_digest(expected_passed)
        if passed != expected_passed:
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_PASSED_INVALID"
            )
        if (
            evidence.reviewed_files_digest != expected_reviewed_files_digest
            or evidence.generation_digest != expected_generation_digest
        ):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_BINDING_INVALID"
            )
        return evidence

    def _path(self, name: str) -> Path:
        return self.directory / _FILENAMES[name]

    def _require_safe_directory(self) -> None:
        if self.directory.is_symlink() or (
            self.directory.exists() and not self.directory.is_dir()
        ):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_PATH_INVALID"
            )
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_PATH_INVALID"
            )

    def _load_json(self, path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_INVALID"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_INVALID"
            ) from None
        if not isinstance(payload, dict):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_INVALID"
            )
        return payload

    def _validate_started(
        self,
        payload: dict[str, Any],
        *,
        reviewed_files_digest: str,
        generation_digest: str,
        cycle_binding_digest: str,
        expected_digest: object,
    ) -> None:
        expected = {
            "schema": _STARTED_SCHEMA,
            "status": _STARTED,
            "reviewed_files_digest": reviewed_files_digest,
            "generation_digest": generation_digest,
            "cycle_binding_digest": cycle_binding_digest,
            "started_at_utc": payload.get("started_at_utc"),
        }
        expected["artifact_digest"] = _canonical_digest(expected)
        if (
            payload != expected
            or not isinstance(expected_digest, str)
            or payload["artifact_digest"] != expected_digest
        ):
            raise V4AccountSnapshotStoreNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_STARTED_INVALID"
            )


def _decode_evidence(
    payload: dict[str, Any],
) -> V4BoundAccountSnapshotEvidenceNoPost:
    expected_evidence_keys = {
        "schema",
        "reviewed_files_digest",
        "generation_digest",
        "cycle_binding_digest",
        "operation_marker",
        "observed_at_utc",
        "valid_until_utc",
        "status",
        "broker_read_performed",
        "broker_get_count",
        "open_positions_count",
        "active_orders_count",
        "account_flat",
        "active_orders_zero",
        "raw_response_retained",
        "identifier_exposed",
        "broker_write",
        "broker_post_count",
        "artifact_digest",
    }
    marker_payload = payload.get("operation_marker")
    if set(payload) != expected_evidence_keys or not isinstance(marker_payload, dict):
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_EVIDENCE_INVALID"
        )
    marker_keys = {
        "schema",
        "reviewed_files_digest",
        "generation_digest",
        "cycle_binding_digest",
        "observed_at_utc",
        "valid_until_utc",
        "status",
        "broker_read_performed",
        "broker_get_count",
        "open_positions_count",
        "active_orders_count",
        "broker_write",
        "broker_post_count",
        "artifact_digest",
    }
    if set(marker_payload) != marker_keys:
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_EVIDENCE_INVALID"
        )
    values = dict(payload)
    try:
        values["operation_marker"] = V4AccountSnapshotOperationMarkerNoPost(
            **marker_payload
        )
        return V4BoundAccountSnapshotEvidenceNoPost(**values)
    except (TypeError, V4BoundAccountSnapshotEvidenceNoPostError):
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_EVIDENCE_INVALID"
        ) from None


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_PATH_INVALID"
        )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError:
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_ALREADY_ATTEMPTED"
        ) from None
    except OSError:
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_MARKER_WRITE_FAILED"
        ) from None


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_ALREADY_EXISTS"
        )
    descriptor, temporary = tempfile.mkstemp(
        prefix=".account-snapshot-", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    except OSError:
        raise V4AccountSnapshotStoreNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_WRITE_FAILED"
        ) from None
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "artifact_digest"}
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
