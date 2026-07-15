"""Run a finite fake-only H11 auto paper sequence from sanitized JSONL."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.h11_auto.boundary import FakeNotifier
from app.h11_auto.contracts import FormalHorizon, PhaseAExecutionPolicy
from app.h11_auto.paper_runner import (
    BoundedPaperRunConfig,
    H11AutoPaperRunnerError,
    load_sanitized_formal_signal_jsonl,
    run_bounded_paper_signals_no_post,
)
from app.h11_auto.persistence import H11AutoPersistenceError
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    H11AutoRuntimeSafetyError,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto bounded fake-only paper run (no network, no POST)"
    )
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--strategy-version", required=True)
    parser.add_argument("--signal-config-hash", required=True)
    parser.add_argument("--horizon", choices=("10m", "30m"), required=True)
    parser.add_argument("--generation-label", required=True)
    parser.add_argument("--maximum-records", type=int, default=100)
    parser.add_argument("--maximum-wall-seconds", type=float, default=300.0)
    parser.add_argument("--synthetic-auto-flat", action="store_true")
    parser.add_argument("--risk-policy-label", required=True)
    parser.add_argument("--per-trade-loss-bound-jpy", type=int, required=True)
    parser.add_argument("--daily-loss-limit-jpy", type=int, required=True)
    parser.add_argument("--monthly-loss-limit-jpy", type=int, required=True)
    parser.add_argument("--maximum-consecutive-losses", type=int, required=True)
    parser.add_argument("--dead-man-policy-label", required=True)
    parser.add_argument("--dead-man-maximum-age-seconds", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        config = BoundedPaperRunConfig(
            maximum_signal_records=args.maximum_records,
            maximum_wall_seconds=args.maximum_wall_seconds,
            synthetic_auto_flat=args.synthetic_auto_flat,
        )
        signals = load_sanitized_formal_signal_jsonl(
            args.signals,
            strategy_version=args.strategy_version,
            maximum_records=config.maximum_signal_records,
        )
        policy = PhaseAExecutionPolicy(
            strategy_version=args.strategy_version,
            signal_config_hash=args.signal_config_hash,
            selected_horizon=FormalHorizon(args.horizon),
        )
        risk_policy = PhaseBRiskPolicy(
            policy_label=args.risk_policy_label,
            per_trade_loss_bound_jpy=args.per_trade_loss_bound_jpy,
            daily_loss_limit_jpy=args.daily_loss_limit_jpy,
            monthly_loss_limit_jpy=args.monthly_loss_limit_jpy,
            maximum_consecutive_losses=args.maximum_consecutive_losses,
        )
        risk_store = PhaseBRiskStore(
            args.state_dir / "auto_risk.json",
            policy=risk_policy,
        )
        dead_man_store = DeadManStore(
            args.state_dir / "auto_dead_man.json",
            policy=DeadManPolicy(
                policy_label=args.dead_man_policy_label,
                maximum_heartbeat_age_seconds=args.dead_man_maximum_age_seconds,
            ),
        )
        report = run_bounded_paper_signals_no_post(
            signals=signals,
            policy=policy,
            state_path=args.state_dir / "auto_state.sqlite3",
            lock_path=args.state_dir / "auto_phase_b.lock",
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            notifier=FakeNotifier(),
            generation_label=args.generation_label,
            config=config,
        )
    except (
        H11AutoPaperRunnerError,
        H11AutoPersistenceError,
        H11AutoRuntimeSafetyError,
        ValueError,
    ) as error:
        print(f"PAPER_RUN_BLOCKED: {error}")
        return 2

    payload = asdict(report)
    payload["status"] = report.status.value
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report.halt_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
