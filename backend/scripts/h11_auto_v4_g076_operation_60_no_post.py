"""G076 operation 60 candidate contract with injected fake dependencies only."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from app.services.h11_v4_g076_runtime import (
    G076_OPERATION_60_RESULT_FILE,
    G076_OPERATION_60_STARTED_FILE,
    G076Error,
    G076FakeOnlyCallable,
    _canonical_hash,
    engage_g076_halt,
)


def run_g076_operation_60_candidate(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    installer: Callable[[], None],
    readiness_verifier: Callable[[], bool],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    installer_timeout_seconds: float = 60,
    readiness_timeout_seconds: float = 60,
) -> str:
    """Exercise finite timeout ordering without selecting a real installer."""

    if not isinstance(installer, G076FakeOnlyCallable) or not isinstance(
        readiness_verifier, G076FakeOnlyCallable
    ):
        raise G076Error("G076_FAKE_ONLY_OPERATION_PORT_REQUIRED")
    started = state_root / G076_OPERATION_60_STARTED_FILE
    _exclusive_start(started, generation_digest, reviewed_files_digest)
    outcome = "UNKNOWN"
    try:
        _run_with_timeout(installer, installer_timeout_seconds)
        readiness_started = monotonic()
        while monotonic() - readiness_started <= readiness_timeout_seconds:
            remaining = readiness_timeout_seconds - (monotonic() - readiness_started)
            if remaining <= 0:
                break
            if _run_with_timeout(readiness_verifier, remaining):
                outcome = "PASSED"
                break
            sleep(0.25)
    except Exception:
        outcome = "UNKNOWN"
    result_base = {
        "schema": "H11_V4_G076_OPERATION_60_RESULT_V1",
        "status": outcome,
        "generation_label": "H11_AUTO_30M_20260802_G076",
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
        "broker_write": False,
        "actual_post_authorized": False,
    }
    result = {**result_base, "artifact_digest": _canonical_hash(result_base)}
    result_path = state_root / G076_OPERATION_60_RESULT_FILE
    try:
        _exclusive_json(
            result_path,
            result,
            exists_reason="G076_OPERATION_60_RESULT_EXISTS_NO_RETRY",
        )
    except G076Error:
        raise
    except OSError as error:
        engage_g076_halt(state_root=state_root, reason="G076_OPERATION_60_RESULT_WRITE_UNKNOWN")
        raise G076Error("G076_OPERATION_60_RESULT_WRITE_UNKNOWN") from error
    if outcome == "UNKNOWN":
        engage_g076_halt(state_root=state_root, reason="G076_OPERATION_60_UNKNOWN")
    return outcome


def _run_with_timeout(call: Callable[[], object], timeout_seconds: float) -> object:
    state: dict[str, object] = {}
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            state["result"] = call()
        except BaseException as error:  # pragma: no cover - exercised through the caller
            errors.append(error)

    worker = threading.Thread(target=runner, name="g076-fake-installer", daemon=True)
    worker.start()
    worker.join(max(0.0, timeout_seconds))
    if worker.is_alive():
        raise G076Error("G076_OPERATION_60_CALL_TIMEOUT")
    if errors:
        raise errors[0]
    return state.get("result")


def _exclusive_json(path: Path, payload: dict[str, object], *, exists_reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G076Error(exists_reason) from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_parent(path)


def _exclusive_start(path: Path, generation_digest: str, reviewed_files_digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G076Error("G076_OPERATION_60_ALREADY_STARTED_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "status": "STARTED",
            },
            stream,
            sort_keys=True,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_parent(path)


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    """Refuse real operation execution; tests call the injected function."""

    raise G076Error("G076_OPERATION_60_FAKE_ONLY_CANDIDATE")


if __name__ == "__main__":
    raise SystemExit(main())
