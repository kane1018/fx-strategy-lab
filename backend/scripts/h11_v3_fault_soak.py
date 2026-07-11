"""Run the bounded H-11 v3 synthetic fault soak (no-POST)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.services.h11_v3_fault_soak import run_h11_v3_fault_soak_no_post


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=100)
    args = parser.parse_args()
    report = run_h11_v3_fault_soak_no_post(target_cycle_count=args.cycles)
    print(json.dumps(asdict(report), ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
