"""Resident monitor-only entrypoint for H-11 v4 G013."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import reviewed_files_digest
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_monitor_supervisor import V4GmoMonitorSupervisor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    implementation_digest = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=implementation_digest,
    )
    V4GmoMonitorSupervisor(
        repository=repository,
        generation=generation,
    ).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
