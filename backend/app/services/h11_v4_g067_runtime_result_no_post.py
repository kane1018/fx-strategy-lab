"""One-use G067 operation 60 result markers with no external I/O."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

G067_OPERATION_60_STARTED_FILE = "operation-60-result.started.json"
G067_OPERATION_60_OUTCOME_FILE = "operation-60-result.outcome.json"
G067_OPERATION_60_SCHEMA = "H11_V4_G067_OPERATION_60_RESULT_V1"


def _validate(root: Path, generation_digest: str, reviewed_files_digest: str) -> None:
    if (
        root.is_symlink()
        or not generation_digest.startswith("sha256:")
        or not reviewed_files_digest.startswith("sha256:")
    ):
        raise ValueError("G067_OPERATION_60_MARKER_INVALID")


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def begin_g067_operation_60_no_post(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    _validate(state_root, generation_digest, reviewed_files_digest)
    _write_exclusive(
        state_root / G067_OPERATION_60_STARTED_FILE,
        {
            "schema": G067_OPERATION_60_SCHEMA,
            "status": "STARTED",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "broker_write": False,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
        },
    )


def record_g067_operation_60_outcome_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    outcome: str,
) -> None:
    _validate(state_root, generation_digest, reviewed_files_digest)
    if outcome not in {"PASSED", "FAILED", "UNKNOWN"}:
        raise ValueError("G067_OPERATION_60_OUTCOME_INVALID")
    _write_exclusive(
        state_root / G067_OPERATION_60_OUTCOME_FILE,
        {
            "schema": G067_OPERATION_60_SCHEMA,
            "status": outcome,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "broker_write": False,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
        },
    )


def load_g067_operation_60_outcome_no_post(*, state_root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(
            (state_root / G067_OPERATION_60_OUTCOME_FILE).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
