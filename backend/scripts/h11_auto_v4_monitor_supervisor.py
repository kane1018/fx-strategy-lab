"""Resident monitor-only entrypoint for H-11 v4 G013."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from h11_v4_reviewed_digest import compute_reviewed_files_digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    parser.add_argument("--startup-probe", action="store_true")
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
    supervisor = V4GmoMonitorSupervisor(
        repository=repository,
        generation=generation,
    )
    if args.startup_probe:
        supervisor.acquire_single_process()
        try:
            tick = supervisor.run_tick(now_utc=datetime.now(UTC))
        finally:
            supervisor.close()
        print(
            json.dumps(
                {
                    "status": "V4_MONITOR_STARTUP_PROBE_CLEAR_NO_POST",
                    "runtime_risk_ready": tick.runtime_risk_ready,
                    "dead_man_alive": tick.dead_man_alive,
                    "heartbeat_chain_beat": tick.heartbeat_chain_beat,
                    "broker_write": tick.broker_write,
                    "broker_post_count": tick.actual_post_count,
                    "credential_read": False,
                    "private_api_read": False,
                },
                sort_keys=True,
            )
        )
        return 0
    supervisor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
