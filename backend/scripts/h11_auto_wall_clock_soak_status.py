"""Inspect one H11 auto wall-clock soak checkpoint without mutation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.h11_auto.wall_clock_soak import (
    H11AutoWallClockSoakError,
    inspect_wall_clock_checkpoint,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto wall-clock soak safe checkpoint status"
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--maximum-heartbeat-age-seconds", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        status = inspect_wall_clock_checkpoint(
            args.checkpoint,
            maximum_heartbeat_age_seconds=args.maximum_heartbeat_age_seconds,
        )
    except H11AutoWallClockSoakError as error:
        print(f"SOAK_STATUS_BLOCKED: {error}")
        return 2
    print(json.dumps(status.to_safe_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if status.heartbeat_fresh and status.implementation_matches_current_code else 1


if __name__ == "__main__":
    raise SystemExit(main())
