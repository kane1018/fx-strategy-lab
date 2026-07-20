"""Resident monitor-only entrypoint for H-11 v4 G013."""

from __future__ import annotations

import argparse
from pathlib import Path

from h11_v4_reviewed_digest import compute_reviewed_files_digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    implementation_digest = compute_reviewed_files_digest(repository=repository)
    if implementation_digest != args.expected_reviewed_files_digest:
        raise SystemExit("MONITOR_REVIEWED_FILES_DIGEST_MISMATCH")
    from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation

    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=implementation_digest,
    )
    if generation.digest != args.expected_generation_digest:
        raise SystemExit("MONITOR_GENERATION_DIGEST_MISMATCH")
    from app.h11_auto.v4_gmo_monitor_supervisor import V4GmoMonitorSupervisor

    if (
        compute_reviewed_files_digest(repository=repository)
        != args.expected_reviewed_files_digest
    ):
        raise SystemExit("MONITOR_REVIEWED_FILES_DIGEST_CHANGED_DURING_IMPORT")
    V4GmoMonitorSupervisor(
        repository=repository,
        generation=generation,
    ).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
