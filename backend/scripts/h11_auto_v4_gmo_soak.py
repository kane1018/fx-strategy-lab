"""Run the bounded relaxed-GMO-v4 fake fault soak."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.h11_auto.v4_gmo_soak import (
    MINIMUM_V4_GMO_SOAK_CYCLES,
    V4GmoSoakStatus,
    run_v4_gmo_fault_soak_no_post,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 v4 GMO bounded fake-only fault soak (no network, no POST)"
    )
    parser.add_argument("--cycles", type=int, default=MINIMUM_V4_GMO_SOAK_CYCLES)
    args = parser.parse_args(argv)
    report = run_v4_gmo_fault_soak_no_post(target_cycle_count=args.cycles)
    payload = asdict(report)
    payload["status"] = report.status.value
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report.status is V4GmoSoakStatus.PASSED_SYNTHETIC_NO_POST else 1


if __name__ == "__main__":
    raise SystemExit(main())
