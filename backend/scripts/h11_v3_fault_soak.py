"""Run the bounded H-11 v3 synthetic fault soak (no-POST)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.services.h11_v3_fault_soak import run_h11_v3_fault_soak_no_post
from app.services.h11_v3_wall_clock_soak import (
    read_h11_v3_wall_clock_soak_status,
    run_h11_v3_wall_clock_soak_no_post,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--wall-clock-hours", type=float)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--soak-interval-seconds", type=int, default=900)
    parser.add_argument(
        "--status-path",
        type=Path,
        default=Path("market_data/h11_v3_wall_clock_soak_status.json"),
    )
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    if args.status_only:
        report = read_h11_v3_wall_clock_soak_status(args.status_path)
        print(json.dumps(asdict(report), ensure_ascii=True, sort_keys=True, indent=2))
        return

    if args.wall_clock_hours is not None:
        duration_seconds = round(args.wall_clock_hours * 60 * 60)
        print(
            json.dumps(
                {
                    "actual_post_count": 0,
                    "duration_seconds": duration_seconds,
                    "mode": "BOUNDED_WALL_CLOCK_FAKE_SOAK_NO_POST",
                    "resident_process": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            flush=True,
        )
        report = run_h11_v3_wall_clock_soak_no_post(
            duration_seconds=duration_seconds,
            poll_seconds=args.poll_seconds,
            soak_interval_seconds=args.soak_interval_seconds,
            status_path=args.status_path,
            target_cycle_count=args.cycles,
        )
        print(json.dumps(asdict(report), ensure_ascii=True, sort_keys=True, indent=2))
        return

    report = run_h11_v3_fault_soak_no_post(target_cycle_count=args.cycles)
    print(json.dumps(asdict(report), ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
