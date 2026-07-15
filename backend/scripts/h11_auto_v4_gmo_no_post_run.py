"""Finite fake-only operator CLI for the relaxed GMO v4 runtime."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.boundary import FakeNotifier
from app.h11_auto.contracts import FormalHorizon, H11AutoContractError, SignalDecision
from app.h11_auto.paper_runner import (
    H11AutoPaperRunnerError,
    load_sanitized_formal_signal_jsonl,
)
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    H11AutoRuntimeSafetyError,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker, V4GmoBoundaryError
from app.h11_auto.v4_gmo_contracts import (
    V4GmoBrokerSnapshot,
    V4GmoContractError,
    V4GmoExecutionPolicy,
)
from app.h11_auto.v4_gmo_engine import SystemV4GmoClock
from app.h11_auto.v4_gmo_persistence import V4GmoPersistenceError, V4GmoStateStore
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime import (
    V4GmoRuntimeError,
    V4GmoRuntimeStatus,
    resume_v4_gmo_once_no_post,
    run_v4_gmo_once_no_post,
)
from app.h11_auto.v4_gmo_soak import build_v4_gmo_soak_scenarios

_NEW_SCENARIOS = {
    "FULL_FILL_PROTECTED",
    "PARTIAL_REMAINDER_CANCEL_THEN_PROTECT",
    "ENTRY_RECONCILIATION_UNKNOWN_HALT",
    "PROTECTION_MISSING_EMERGENCY_FLAT",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 v4 GMO finite fake-only run (no credential, network, or POST)"
    )
    parser.add_argument("--mode", choices=("signal", "resume"), default="signal")
    parser.add_argument("--signals", type=Path)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--strategy-version", required=True)
    parser.add_argument("--signal-config-hash", required=True)
    parser.add_argument("--horizon", choices=("10m", "30m"), required=True)
    parser.add_argument("--generation-label", required=True)
    parser.add_argument(
        "--scenario",
        choices=tuple(sorted(_NEW_SCENARIOS | {"RESUME_EXACT_PROTECTED"})),
        required=True,
    )
    args = parser.parse_args(argv)
    try:
        if args.state_dir.is_symlink():
            raise V4GmoRuntimeError("v4 state directory must not be a symlink")
        args.state_dir.mkdir(parents=True, exist_ok=True)
        policy = V4GmoExecutionPolicy(
            strategy_version=args.strategy_version,
            signal_config_hash=args.signal_config_hash,
            selected_horizon=FormalHorizon(args.horizon),
            protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        )
        risk_policy = PhaseBRiskPolicy(
            policy_label="H11_V4_GMO_RISK_V1",
            per_trade_loss_bound_jpy=5_000,
            daily_loss_limit_jpy=10_000,
            monthly_loss_limit_jpy=50_000,
            maximum_consecutive_losses=5,
        )
        risk_store = PhaseBRiskStore(
            args.state_dir / "v4_risk.json", policy=risk_policy
        )
        dead_man_store = DeadManStore(
            args.state_dir / "v4_dead_man.json",
            policy=DeadManPolicy(
                policy_label="H11_V4_GMO_DEAD_MAN_V1",
                maximum_heartbeat_age_seconds=60,
            ),
        )
        common = {
            "policy": policy,
            "state_path": args.state_dir / "v4_state.sqlite3",
            "lock_path": args.state_dir / "v4_runtime.lock",
            "risk_store": risk_store,
            "risk_policy": risk_policy,
            "dead_man_store": dead_man_store,
            "notifier": FakeNotifier(),
            "generation_label": args.generation_label,
            "now_utc": datetime.now(UTC),
            "clock": SystemV4GmoClock(),
        }
        if args.mode == "signal":
            if args.signals is None or args.scenario not in _NEW_SCENARIOS:
                raise V4GmoRuntimeError(
                    "signal mode requires one signal file and a new-cycle scenario"
                )
            signals = load_sanitized_formal_signal_jsonl(
                args.signals,
                strategy_version=args.strategy_version,
                maximum_records=1,
            )
            if len(signals) != 1:
                raise V4GmoRuntimeError("signal mode requires exactly one formal signal")
            broker = _new_cycle_broker(
                scenario_name=args.scenario,
                side=signals[0].decision,
            )
            report = run_v4_gmo_once_no_post(
                signal=signals[0],
                broker=broker,
                **common,
            )
        else:
            if args.signals is not None or args.scenario != "RESUME_EXACT_PROTECTED":
                raise V4GmoRuntimeError(
                    "resume mode accepts only RESUME_EXACT_PROTECTED and no signal file"
                )
            active = V4GmoStateStore(
                args.state_dir / "v4_state.sqlite3"
            ).load_single_active_cycle_safe()
            if active is None:
                raise V4GmoRuntimeError("resume mode requires one active v4 cycle")
            report = resume_v4_gmo_once_no_post(
                broker=FakeV4GmoBroker(
                    outcomes={},
                    snapshots=[
                        _exact_protected_snapshot(SignalDecision(active.side))
                    ],
                ),
                **common,
            )
    except (
        H11AutoContractError,
        H11AutoPaperRunnerError,
        H11AutoRuntimeSafetyError,
        V4GmoBoundaryError,
        V4GmoContractError,
        V4GmoPersistenceError,
        V4GmoRuntimeError,
        OSError,
        ValueError,
    ) as error:
        print(f"V4_GMO_RUN_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return (
        0
        if report.status
        in {
            V4GmoRuntimeStatus.NO_ACTION_STAY,
            V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC,
            V4GmoRuntimeStatus.FLAT_RECONCILED_SYNTHETIC,
        }
        else 1
    )


def _new_cycle_broker(
    *, scenario_name: str, side: SignalDecision
) -> FakeV4GmoBroker:
    scenario = next(
        value
        for value in build_v4_gmo_soak_scenarios()
        if value.name == scenario_name
    )
    snapshots = [V4GmoBrokerSnapshot.flat()]
    snapshots.extend(
        replace(snapshot, position_side=side)
        if snapshot.position_count == 1
        else snapshot
        for snapshot in scenario.snapshots
    )
    return FakeV4GmoBroker(
        outcomes={action: list(values) for action, values in scenario.outcomes},
        snapshots=snapshots,
    )


def _exact_protected_snapshot(side: SignalDecision) -> V4GmoBrokerSnapshot:
    scenario = next(
        value
        for value in build_v4_gmo_soak_scenarios()
        if value.name == "FULL_FILL_PROTECTED"
    )
    return replace(scenario.snapshots[-1], position_side=side)


if __name__ == "__main__":
    raise SystemExit(main())
