"""Run the bounded H-11 automatic Phase A synthetic soak."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.h11_auto.soak import MINIMUM_PHASE_A_SOAK_CYCLES, run_phase_a_fault_soak_no_post


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=MINIMUM_PHASE_A_SOAK_CYCLES)
    args = parser.parse_args()
    report = run_phase_a_fault_soak_no_post(target_cycle_count=args.cycles)
    payload = asdict(report)
    payload["status"] = report.status.value
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if report.status.value == "PASSED_SYNTHETIC_NO_POST" else 1


if __name__ == "__main__":
    raise SystemExit(main())
