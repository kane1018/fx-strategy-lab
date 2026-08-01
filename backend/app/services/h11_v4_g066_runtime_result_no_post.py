"""Atomic, generation-bound result recording for G066 operation 60.

This module records only safe operation outcomes.  It never starts a process,
touches launchd, reads credentials, or constructs a broker client.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

G066_GENERATION_LABEL = "H11_AUTO_30M_20260802_G066"
G066_OPERATION_RESULT_SCHEMA = "H11_V4_G066_OPERATION_60_RESULT_V1"
G066_OPERATION_STARTED_FILE = "operation-60-result.started.json"
G066_OPERATION_OUTCOME_FILE = "operation-60-result.outcome.json"


class G066RuntimeResultError(RuntimeError):
    """Safe failure for a one-use operation result ledger."""


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink() or path.exists():
        raise G066RuntimeResultError("G066_OPERATION_60_ALREADY_ATTEMPTED")
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise G066RuntimeResultError("G066_OPERATION_60_RESULT_IN_PROGRESS")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise G066RuntimeResultError("G066_OPERATION_60_RESULT_WRITE_FAILED") from error


def begin_g066_operation_60_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    if (
        state_root.is_symlink()
        or not state_root.is_absolute()
        or not _valid_digest(generation_digest)
        or not _valid_digest(reviewed_files_digest)
    ):
        raise G066RuntimeResultError("G066_OPERATION_60_RESULT_INPUT_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / G066_OPERATION_STARTED_FILE
    payload = {
        "actual_post_count": 0,
        "broker_post_count": 0,
        "broker_write": False,
        "credential_read_count": 0,
        "generation_digest": generation_digest,
        "operation": "60_monitor_launchagent",
        "private_api_read_count": 0,
        "reviewed_files_digest": reviewed_files_digest,
        "schema": G066_OPERATION_RESULT_SCHEMA,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "status": "STARTED",
    }
    _write_once(target, payload)


def record_g066_operation_60_outcome_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, outcome: str
) -> None:
    if outcome not in {"PASSED", "FAILED", "UNKNOWN"}:
        raise G066RuntimeResultError("G066_OPERATION_60_OUTCOME_INVALID")
    started_path = state_root / G066_OPERATION_STARTED_FILE
    if started_path.is_symlink() or not started_path.is_file():
        raise G066RuntimeResultError("G066_OPERATION_60_STARTED_MARKER_MISSING")
    try:
        started = json.loads(started_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G066RuntimeResultError("G066_OPERATION_60_STARTED_MARKER_INVALID") from error
    if (
        not isinstance(started, dict)
        or started.get("schema") != G066_OPERATION_RESULT_SCHEMA
        or started.get("status") != "STARTED"
        or started.get("generation_digest") != generation_digest
        or started.get("reviewed_files_digest") != reviewed_files_digest
    ):
        raise G066RuntimeResultError("G066_OPERATION_60_STARTED_MARKER_MISMATCH")
    target = state_root / G066_OPERATION_OUTCOME_FILE
    payload = {
        "actual_post_count": 0,
        "broker_post_count": 0,
        "broker_write": False,
        "credential_read_count": 0,
        "generation_digest": generation_digest,
        "operation": "60_monitor_launchagent",
        "outcome": outcome,
        "private_api_read_count": 0,
        "reviewed_files_digest": reviewed_files_digest,
        "schema": G066_OPERATION_RESULT_SCHEMA,
        "status": outcome,
        "completed_at_utc": datetime.now(UTC).isoformat(),
    }
    _write_once(target, payload)


def load_g066_operation_60_outcome_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> str:
    path = state_root / G066_OPERATION_OUTCOME_FILE
    if path.is_symlink() or not path.is_file():
        return "UNKNOWN"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "UNKNOWN"
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != G066_OPERATION_RESULT_SCHEMA
        or payload.get("generation_digest") != generation_digest
        or payload.get("reviewed_files_digest") != reviewed_files_digest
        or payload.get("broker_write") is not False
        or payload.get("broker_post_count") != 0
        or payload.get("actual_post_count") != 0
        or payload.get("private_api_read_count") != 0
        or payload.get("credential_read_count") != 0
        or payload.get("outcome") not in {"PASSED", "FAILED", "UNKNOWN"}
    ):
        return "UNKNOWN"
    return str(payload["outcome"])
