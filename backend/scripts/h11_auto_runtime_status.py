"""Print one safe Phase B risk/dead-man status snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    H11AutoRuntimeSafetyError,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.h11_auto.runtime_status import project_runtime_safety_status


def _day(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("day must use YYYY-MM-DD") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto Phase B risk/dead-man status (safe aggregate only)"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--cycle-day-jst", type=_day, required=True)
    parser.add_argument("--risk-policy-label", required=True)
    parser.add_argument("--per-trade-loss-bound-jpy", type=int, required=True)
    parser.add_argument("--daily-loss-limit-jpy", type=int, required=True)
    parser.add_argument("--monthly-loss-limit-jpy", type=int, required=True)
    parser.add_argument("--maximum-consecutive-losses", type=int, required=True)
    parser.add_argument("--dead-man-policy-label", required=True)
    parser.add_argument("--dead-man-maximum-age-seconds", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        risk_policy = PhaseBRiskPolicy(
            policy_label=args.risk_policy_label,
            per_trade_loss_bound_jpy=args.per_trade_loss_bound_jpy,
            daily_loss_limit_jpy=args.daily_loss_limit_jpy,
            monthly_loss_limit_jpy=args.monthly_loss_limit_jpy,
            maximum_consecutive_losses=args.maximum_consecutive_losses,
        )
        projection = project_runtime_safety_status(
            risk_store=PhaseBRiskStore(
                args.state_dir / "auto_risk.json",
                policy=risk_policy,
            ),
            risk_policy=risk_policy,
            dead_man_store=DeadManStore(
                args.state_dir / "auto_dead_man.json",
                policy=DeadManPolicy(
                    args.dead_man_policy_label,
                    args.dead_man_maximum_age_seconds,
                ),
            ),
            cycle_day_jst=args.cycle_day_jst,
            now_utc=datetime.now(UTC),
        )
    except H11AutoRuntimeSafetyError as error:
        print(f"RUNTIME_STATUS_BLOCKED: {error}")
        return 2
    print(
        json.dumps(
            projection.to_safe_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0 if not projection.halt_required else 1


if __name__ == "__main__":
    raise SystemExit(main())
