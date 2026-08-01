"""Create one G066 local runtime safety chain without external I/O."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.services.h11_v4_g066_runtime_projection_no_post import project_g066_runtime_state
from app.services.h11_v4_g066_unattended_activation import (
    G066_GENERATION_LABEL,
    G066_PERSISTENT_HALT_FILE,
    verify_g066_generation_contract,
    write_g066_runtime_evidence_no_post,
)

G066_HEARTBEAT_SCHEMA = "H11_V4_G066_HEARTBEAT_V1"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    os.replace(temp, path)


def _safe_halt(root: Path, reason: str, generation_digest: str, reviewed_digest: str) -> None:
    _atomic_json(
        root / G066_PERSISTENT_HALT_FILE,
        {
            "schema": "H11_V4_G066_PERSISTENT_HALT_V1",
            "generation_label": G066_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_digest,
            "status": "HALTED",
            "reason_label": reason,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
            "actual_post_count": 0,
        },
    )


def bootstrap(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    runtime_root = (
        repository
        / "backend"
        / "market_data"
        / "h11_v4_gmo_actual_runtime"
        / f"generation-{generation_digest.removeprefix('sha256:')}"
    )
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed_digest,
        )
        if generation.digest != generation_digest:
            raise ValueError("G066_GENERATION_DIGEST_MISMATCH")
        verify_g066_generation_contract(generation=generation, repository=repository)
    except Exception:
        _safe_halt(
            runtime_root,
            "G066_GENERATION_CONTRACT_NOT_CLEAR",
            generation_digest,
            reviewed_digest,
        )
        return 2

    lock_path = runtime_root / "process.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        _safe_halt(runtime_root, "G066_PROCESS_LOCK_CONFLICT", generation_digest, reviewed_digest)
        return 3
    try:
        os.write(fd, G066_GENERATION_LABEL.encode("ascii"))
    finally:
        os.close(fd)

    common = {
        "generation_label": G066_GENERATION_LABEL,
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
    _atomic_json(
        runtime_root / "heartbeat.json",
        {**common, "schema": G066_HEARTBEAT_SCHEMA, "status": "FRESH", "chain_index": 1},
    )
    _atomic_json(
        runtime_root / "dead-man.json",
        {**common, "schema": "H11_V4_G066_DEAD_MAN_V1", "status": "ALIVE"},
    )
    _atomic_json(
        runtime_root / "heartbeat-chain.json",
        {
            **common,
            "schema": "H11_V4_G066_HEARTBEAT_CHAIN_V1",
            "status": "FRESH",
            "length": 1,
        },
    )
    _atomic_json(
        runtime_root / "runtime-projection.json",
        project_g066_runtime_state(arm_state="OFF", position={"unknown": True}),
    )
    write_g066_runtime_evidence_no_post(
        state_root=runtime_root,
        generation=generation,
        observed_at_utc=datetime.now(UTC),
    )
    return 0


def run_resident(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    result = bootstrap(
        repository=repository,
        generation_digest=generation_digest,
        reviewed_digest=reviewed_digest,
    )
    if result != 0:
        return result
    root = (
        repository
        / "backend"
        / "market_data"
        / "h11_v4_gmo_actual_runtime"
        / f"generation-{generation_digest.removeprefix('sha256:')}"
    )
    chain_index = 1
    common = {
        "generation_label": G066_GENERATION_LABEL,
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
    try:
        while True:
            chain_index += 1
            observed = datetime.now(UTC).isoformat()
            _atomic_json(
                root / "heartbeat.json",
                {
                    **common,
                    "schema": G066_HEARTBEAT_SCHEMA,
                    "status": "FRESH",
                    "chain_index": chain_index,
                    "observed_at_utc": observed,
                },
            )
            _atomic_json(
                root / "dead-man.json",
                {
                    **common,
                    "schema": "H11_V4_G066_DEAD_MAN_V1",
                    "status": "ALIVE",
                    "observed_at_utc": observed,
                },
            )
            _atomic_json(
                root / "heartbeat-chain.json",
                {
                    **common,
                    "schema": "H11_V4_G066_HEARTBEAT_CHAIN_V1",
                    "status": "FRESH",
                    "length": chain_index,
                    "observed_at_utc": observed,
                },
            )
            time.sleep(15)
    except KeyboardInterrupt:
        _safe_halt(root, "G066_RUNTIME_STOPPED", generation_digest, reviewed_digest)
        return 0


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
    if args.once:
        return bootstrap(
            repository=args.repository,
            generation_digest=args.generation_digest,
            reviewed_digest=args.reviewed_files_digest,
        )
    return run_resident(
        repository=args.repository,
        generation_digest=args.generation_digest,
        reviewed_digest=args.reviewed_files_digest,
    )


if __name__ == "__main__":
    raise SystemExit(main())
