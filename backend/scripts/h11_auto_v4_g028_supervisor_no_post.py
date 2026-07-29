"""Foreground G028 supervisor entrypoint; local state only."""

from __future__ import annotations

import argparse
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from h11_v4_reviewed_digest import compute_reviewed_files_digest

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-files-digest", required=True)
    parser.add_argument("--generation-digest", required=True)
    parser.add_argument("--interval-seconds", type=int, default=15)
    parser.add_argument("--max-ticks", type=int, default=0)
    args = parser.parse_args()
    current_reviewed = compute_reviewed_files_digest(repository=REPOSITORY)
    if current_reviewed != args.reviewed_files_digest:
        print("status=G028_SUPERVISOR_REVIEW_BINDING_INVALID broker_post_count=0")
        return 2
    from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
    from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
    from app.services.h11_v4_g028_unattended_runtime_no_post import (
        V4G028ArmProjectionNoPost,
        V4G028ResidentSupervisorNoPost,
    )
    from app.services.h11_v4_unattended_live_arm_state import (
        V4UnattendedLiveArmStore,
    )
    from app.services.h11_v4_unattended_live_paths import (
        v4_unattended_live_arm_state_path,
    )

    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY,
        implementation_digest=current_reviewed,
    )
    if generation.digest != args.generation_digest:
        print("status=G028_SUPERVISOR_GENERATION_BINDING_INVALID broker_post_count=0")
        return 2
    state_directory = v4_gmo_runtime_state_root(
        repository=REPOSITORY,
        generation_digest=generation.digest,
    )
    arm_path = v4_unattended_live_arm_state_path(
        generation_digest=generation.digest
    )

    def arm() -> V4G028ArmProjectionNoPost:
        check = V4UnattendedLiveArmStore(arm_path).check(
            expected_generation_digest=args.generation_digest,
            expected_reviewed_files_digest=args.reviewed_files_digest,
        )
        desired_state = "BLOCKED"
        if check.armed:
            desired_state = "ARMED"
        elif (
            check.desired_state.value == "DISARMED"
            and set(check.blocked_reasons) == {"OPERATOR_DISARMED"}
        ):
            desired_state = "DISARMED"
        return V4G028ArmProjectionNoPost(
            reviewed_files_digest=args.reviewed_files_digest,
            generation_digest=args.generation_digest,
            desired_state=desired_state,
        )

    supervisor = V4G028ResidentSupervisorNoPost(
        state_directory=state_directory,
        reviewed_files_digest=args.reviewed_files_digest,
        generation_digest=args.generation_digest,
    )
    try:
        initial_arm = arm()
    except Exception:
        initial_arm = V4G028ArmProjectionNoPost(
            reviewed_files_digest=args.reviewed_files_digest,
            generation_digest=args.generation_digest,
            desired_state="BLOCKED",
        )
        started = supervisor.start(
            now_utc=datetime.now(UTC),
            arm=initial_arm,
        )
        if started.process_lock_held:
            supervisor.fail_closed(
                now_utc=datetime.now(UTC),
                reason="G028_SUPERVISOR_INITIAL_ARM_LOAD_FAILED",
            )
        print("status=G028_SUPERVISOR_INITIAL_ARM_LOAD_FAILED broker_post_count=0")
        return 2
    started = supervisor.start(now_utc=datetime.now(UTC), arm=initial_arm)
    if not started.process_lock_held:
        print("status=G028_SUPERVISOR_PROCESS_LOCK_HELD broker_post_count=0")
        return 2
    stopping = False

    def request_stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    ticks = 0
    owns_lock = True
    try:
        while not stopping and (args.max_ticks == 0 or ticks < args.max_ticks):
            time.sleep(args.interval_seconds)
            if stopping:
                break
            supervisor.tick(now_utc=datetime.now(UTC), arm=arm())
            ticks += 1
    except Exception:
        supervisor.fail_closed(
            now_utc=datetime.now(UTC),
            reason="G028_SUPERVISOR_ENTRYPOINT_EXCEPTION",
        )
        owns_lock = False
        raise
    finally:
        if owns_lock and supervisor.process_lock.held:
            supervisor.stop(now_utc=datetime.now(UTC), reason="PROCESS_EXIT")
    print("status=G028_SUPERVISOR_STOPPED_NO_POST broker_post_count=0")
    return 0


def run_resident_loop_no_post(
    *,
    supervisor: Any,
    arm_loader: Callable[[], Any],
    sleep: Callable[[float], None],
    now: Callable[[], datetime],
    should_stop: Callable[[], bool],
    interval_seconds: float,
    max_ticks: int,
) -> int:
    """Testable loop core; rechecks stop after sleep before every tick."""

    ticks = 0
    try:
        while not should_stop() and (max_ticks == 0 or ticks < max_ticks):
            sleep(interval_seconds)
            if should_stop():
                break
            supervisor.tick(now_utc=now(), arm=arm_loader())
            ticks += 1
        return ticks
    except Exception:
        supervisor.fail_closed(
            now_utc=now(), reason="G028_SUPERVISOR_ENTRYPOINT_EXCEPTION"
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
