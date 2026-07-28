#!/usr/bin/env python3
"""Isolated G027 host-readiness probe with no credentials or external action."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore
from app.h11_auto.v4_actual_preparation_guard import require_clean_main
from app.h11_auto.v4_gmo_generation import (
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainPolicy,
    V4HeartbeatChainStore,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_operational_readiness_path,
)
from app.services.h11_v4_unattended_operational_readiness_no_post import (
    V4OperationalReadinessStoreNoPost,
    observe_operational_readiness_no_post,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

_EXPECTED_GENERATION_LABEL = "H11_AUTO_30M_20260729_G027"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        repository = args.repository.resolve()
        require_clean_main(repository=repository)
        reviewed = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed,
        )
        if generation.generation_label != _EXPECTED_GENERATION_LABEL:
            raise RuntimeError("G027_OPERATIONAL_READINESS_GENERATION_INVALID")
        runtime_root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        )
        evidence = observe_operational_readiness_no_post(
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
            process_lock=H11AutoProcessLock(runtime_root / "process.lock"),
            dead_man_store=DeadManStore(
                runtime_root / "dead-man.json",
                policy=v4_gmo_dead_man_policy(),
            ),
            heartbeat_chain_store=V4HeartbeatChainStore(
                runtime_root / "unattended-heartbeat-chain.json",
                policy=V4HeartbeatChainPolicy(
                    policy_label="H11_V4_UNATTENDED_SCHEDULER_CHAIN_V1",
                    maximum_gap_seconds=60,
                    minimum_continuous_seconds=300,
                ),
            ),
            now_utc=datetime.now(UTC),
        )
        V4OperationalReadinessStoreNoPost(
            v4_unattended_operational_readiness_path(
                generation_digest=generation.digest
            )
        ).save(evidence)
        print(
            json.dumps(
                {
                    "status": "G027_OPERATIONAL_READINESS_OBSERVED_NO_POST",
                    "process_lock_clear": evidence.process_lock_clear,
                    "dead_man_clear": evidence.dead_man_clear,
                    "heartbeat_chain_clear": evidence.heartbeat_chain_clear,
                    "notification_ready": False,
                    "credential_read": False,
                    "private_api_read": False,
                    "notification_send_count": 0,
                    "broker_write": False,
                    "broker_post_count": 0,
                    "live_action_authorized": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(
            json.dumps(
                {
                    "status": "G027_OPERATIONAL_READINESS_REFUSED_SAFE",
                    "credential_read": False,
                    "private_api_read": False,
                    "notification_send_count": 0,
                    "broker_write": False,
                    "broker_post_count": 0,
                    "live_action_authorized": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
