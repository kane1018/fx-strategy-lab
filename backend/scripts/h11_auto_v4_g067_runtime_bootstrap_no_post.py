"""Resident G067 no-POST runtime bootstrap."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.services.h11_v4_g066_runtime_projection_no_post import (  # noqa: E402
    project_g066_runtime_state,  # noqa: E402
)
from app.services.h11_v4_g067_unattended_activation import (  # noqa: E402
    G067_GENERATION_LABEL,
    G067_HEARTBEAT_SCHEMA,
    G067_PERSISTENT_HALT_FILE,
    V4G067ActivationError,
    verify_g067_generation_contract,
    write_g067_persistent_halt_no_post,
    write_g067_runtime_evidence_no_post,
)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    os.replace(temporary, path)


def _runtime_root(repository: Path, generation_digest: str) -> Path:
    return (
        repository
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / f"generation-{generation_digest.removeprefix('sha256:')}"
    )


def _common(generation_digest: str, reviewed_digest: str) -> dict[str, Any]:
    return {
        "generation_label": G067_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_digest,
        "broker_read": False,
        "broker_write": False,
        "private_api_read": False,
        "credential_read": False,
        "actual_post_count": 0,
        "pending": False,
        "unknown_halt": False,
    }


def _safe_halt(root: Path, generation_digest: str, reviewed_digest: str, reason: str) -> None:
    try:
        write_g067_persistent_halt_no_post(
            state_root=root,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_digest,
        )
    except V4G067ActivationError:
        _atomic_json(
            root / G067_PERSISTENT_HALT_FILE,
            {
                **_common(generation_digest, reviewed_digest),
                "schema": "H11_V4_G067_PERSISTENT_HALT_V1",
                "status": "HALTED",
                "reason_label": reason,
            },
        )


def bootstrap(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    root = _runtime_root(repository, generation_digest)
    root.mkdir(parents=True, exist_ok=True)
    try:
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed_digest,
        )
        if generation.digest != generation_digest:
            raise V4G067ActivationError("G067_GENERATION_DIGEST_MISMATCH")
        verify_g067_generation_contract(generation=generation, repository=repository)
    except Exception:
        _safe_halt(root, generation_digest, reviewed_digest, "G067_GENERATION_CONTRACT_NOT_CLEAR")
        return 2

    lock_path = root / "process.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        _safe_halt(root, generation_digest, reviewed_digest, "G067_PROCESS_LOCK_CONFLICT")
        return 3
    try:
        os.write(descriptor, G067_GENERATION_LABEL.encode("ascii"))
    finally:
        os.close(descriptor)

    common = _common(generation_digest, reviewed_digest)
    now = datetime.now(UTC).isoformat()
    _atomic_json(
        root / "heartbeat.json",
        {
            **common,
            "schema": G067_HEARTBEAT_SCHEMA,
            "status": "FRESH",
            "chain_index": 1,
            "observed_at_utc": now,
        },
    )
    _atomic_json(
        root / "dead-man.json",
        {**common, "schema": "H11_V4_G067_DEAD_MAN_V1", "status": "ALIVE", "observed_at_utc": now},
    )
    _atomic_json(
        root / "heartbeat-chain.json",
        {
            **common,
            "schema": "H11_V4_G067_HEARTBEAT_CHAIN_V1",
            "status": "FRESH",
            "length": 1,
            "observed_at_utc": now,
        },
    )
    _atomic_json(
        root / "runtime-projection.json",
        project_g066_runtime_state(arm_state="OFF", position={"unknown": True}),
    )
    write_g067_runtime_evidence_no_post(
        state_root=root,
        generation=generation,
        observed_at_utc=datetime.now(UTC),
        repository=repository,
    )
    return 0


def run_resident(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    result = bootstrap(
        repository=repository, generation_digest=generation_digest, reviewed_digest=reviewed_digest
    )
    if result != 0:
        return result
    root = _runtime_root(repository, generation_digest)
    chain_index = 1
    common = _common(generation_digest, reviewed_digest)
    try:
        while True:
            chain_index += 1
            observed = datetime.now(UTC).isoformat()
            _atomic_json(
                root / "heartbeat.json",
                {
                    **common,
                    "schema": G067_HEARTBEAT_SCHEMA,
                    "status": "FRESH",
                    "chain_index": chain_index,
                    "observed_at_utc": observed,
                },
            )
            _atomic_json(
                root / "dead-man.json",
                {
                    **common,
                    "schema": "H11_V4_G067_DEAD_MAN_V1",
                    "status": "ALIVE",
                    "observed_at_utc": observed,
                },
            )
            _atomic_json(
                root / "heartbeat-chain.json",
                {
                    **common,
                    "schema": "H11_V4_G067_HEARTBEAT_CHAIN_V1",
                    "status": "FRESH",
                    "length": chain_index,
                    "observed_at_utc": observed,
                },
            )
            write_g067_runtime_evidence_no_post(
                state_root=root,
                generation=load_v4_gmo_frozen_generation(
                    repository=repository, implementation_digest=reviewed_digest
                ),
                observed_at_utc=datetime.now(UTC),
                repository=repository,
            )
            time.sleep(15)
    except KeyboardInterrupt:
        _safe_halt(root, generation_digest, reviewed_digest, "G067_RUNTIME_STOPPED")
        return 0
    except Exception:
        _safe_halt(root, generation_digest, reviewed_digest, "G067_RUNTIME_UNEXPECTED_FAILURE")
        return 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument(
        "--generation-digest",
        "--expected-generation-digest",
        dest="generation_digest",
        required=True,
    )
    parser.add_argument(
        "--reviewed-files-digest",
        "--expected-reviewed-files-digest",
        dest="reviewed_files_digest",
        required=True,
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    repository = args.repository.resolve()
    if args.once:
        return bootstrap(
            repository=repository,
            generation_digest=args.generation_digest,
            reviewed_digest=args.reviewed_files_digest,
        )
    return run_resident(
        repository=repository,
        generation_digest=args.generation_digest,
        reviewed_digest=args.reviewed_files_digest,
    )


if __name__ == "__main__":
    raise SystemExit(main())
