"""Run a bounded H11 auto fake-only wall-clock soak."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.h11_auto.wall_clock_soak import (
    H11AutoWallClockSoakError,
    WallClockSoakConfig,
    WallClockSoakStatus,
    run_wall_clock_fake_soak_no_post,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto bounded wall-clock fake soak (no network, no POST)"
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--duration-seconds", type=float, default=86_400.0)
    parser.add_argument("--batch-interval-seconds", type=float, default=60.0)
    parser.add_argument("--maximum-gap-seconds", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        config = WallClockSoakConfig(
            duration_seconds=args.duration_seconds,
            batch_interval_seconds=args.batch_interval_seconds,
            maximum_observation_gap_seconds=args.maximum_gap_seconds,
        )
        report = run_wall_clock_fake_soak_no_post(
            config=config,
            checkpoint_path=args.checkpoint,
            lock_path=args.lock or args.checkpoint.with_suffix(".lock"),
        )
    except H11AutoWallClockSoakError as error:
        print(f"SOAK_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report.status is WallClockSoakStatus.PASSED_FAKE_ONLY else 1


if __name__ == "__main__":
    raise SystemExit(main())
