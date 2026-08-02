#!/usr/bin/env python3
"""G069 resident local-health bootstrap; no broker or credential access."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g069_unattended_activation_no_post import (  # noqa: E402
    G069OwnerLock,
    V4G069ActivationError,
    verify_g069_generation_contract,
    write_g069_health_no_post,
    write_g069_persistent_halt_no_post,
    write_g069_runtime_projection_no_post,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def _load_verified_generation(*, repository: Path, generation_digest: str, reviewed_digest: str):
    computed = compute_reviewed_files_digest(repository=repository)
    if computed != reviewed_digest:
        raise V4G069ActivationError("G069_REVIEWED_FILES_DIGEST_MISMATCH")
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=computed
    )
    if generation.digest != generation_digest:
        raise V4G069ActivationError("G069_GENERATION_DIGEST_MISMATCH")
    verify_g069_generation_contract(generation=generation, repository=repository)
    return generation


def run_once(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    try:
        generation = _load_verified_generation(
            repository=repository,
            generation_digest=generation_digest,
            reviewed_digest=reviewed_digest,
        )
    except V4G069ActivationError:
        return 2
    root = v4_gmo_runtime_state_root(repository=repository, generation_digest=generation_digest)
    root.mkdir(parents=True, exist_ok=True)
    lock = G069OwnerLock(root / "process.lock", generation_digest=generation_digest)
    try:
        lock.acquire()
        write_g069_health_no_post(
            state_root=root,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_digest,
            now_utc=datetime.now(UTC),
            chain_index=1,
        )
        write_g069_runtime_projection_no_post(
            state_root=root,
            generation=generation,
            reviewed_files_digest=reviewed_digest,
        )
        return 0
    except V4G069ActivationError as error:
        try:
            write_g069_persistent_halt_no_post(
                state_root=root,
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_digest,
                reason=str(error),
            )
        except V4G069ActivationError:
            pass
        return 2
    finally:
        lock.release()


def run_resident(*, repository: Path, generation_digest: str, reviewed_digest: str) -> int:
    try:
        generation = _load_verified_generation(
            repository=repository,
            generation_digest=generation_digest,
            reviewed_digest=reviewed_digest,
        )
    except V4G069ActivationError:
        return 2
    root = v4_gmo_runtime_state_root(repository=repository, generation_digest=generation_digest)
    root.mkdir(parents=True, exist_ok=True)
    lock = G069OwnerLock(root / "process.lock", generation_digest=generation_digest)
    try:
        lock.acquire()
        index = 0
        while True:
            index += 1
            write_g069_health_no_post(
                state_root=root,
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_digest,
                now_utc=datetime.now(UTC),
                chain_index=index,
            )
            write_g069_runtime_projection_no_post(
                state_root=root,
                generation=generation,
                reviewed_files_digest=reviewed_digest,
            )
            time.sleep(15)
    except (KeyboardInterrupt, V4G069ActivationError) as error:
        try:
            write_g069_persistent_halt_no_post(
                state_root=root,
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_digest,
                reason=(
                    "G069_RUNTIME_STOPPED"
                    if isinstance(error, KeyboardInterrupt)
                    else str(error)
                ),
            )
        except V4G069ActivationError:
            pass
        return 2
    finally:
        lock.release()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.once:
        return run_once(
            repository=args.repository.resolve(),
            generation_digest=args.expected_generation_digest,
            reviewed_digest=args.expected_reviewed_files_digest,
        )
    return run_resident(
        repository=args.repository.resolve(),
        generation_digest=args.expected_generation_digest,
        reviewed_digest=args.expected_reviewed_files_digest,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
