"""Disposable v4 coordinator child used only by the finite host KILL proof."""

from __future__ import annotations

import argparse
import os
import signal
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.h11_auto.contracts import FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_actual_coordinator import (
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoExecutionPolicy,
)
from app.h11_auto.v4_gmo_generation import (
    build_v4_gmo_frozen_generation,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-path", type=Path, required=True)
    parser.add_argument("--implementation-digest", required=True)
    parser.add_argument("--observed-at-utc", required=True)
    parser.add_argument("--mode", choices=("initial", "restart"), required=True)
    parser.add_argument("--transport-marker", type=Path, required=True)
    args = parser.parse_args()
    observed = datetime.fromisoformat(args.observed_at_utc).astimezone(UTC)
    selected = V4ApprovedOperatorSelections()
    policy = V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    generation = build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_KILL_REHEARSAL_G001",
        implementation_digest=args.implementation_digest,
        policy=policy,
    )
    formal_signal = FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=selected.selected_horizon,
        observed_at_utc=observed,
        valid_until_utc=observed + timedelta(minutes=5),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    store = V4GmoActualCoordinatorStore(args.state_path)
    if args.mode == "initial":
        store.prepare_entry_intent(
            generation=generation,
            signal=formal_signal,
            policy=policy,
            frozen_atr_24=Decimal("0.20"),
            now_utc=observed,
        )
    cycle_ref = store.cycle_ref_for_signal_internal(formal_signal.fingerprint)
    lock = H11AutoProcessLock(args.state_path.with_suffix(".lock"))
    if not lock.acquire():
        return 3
    try:
        if args.mode == "initial":
            store.record_kill_rehearsal_pending_no_transport(cycle_ref=cycle_ref)
            os.kill(os.getpid(), signal.SIGSTOP)
            return 5
        if store.unknown_halt_latched() and not args.transport_marker.exists():
            return 0
    except V4GmoActualCoordinatorError:
        return 4
    finally:
        lock.release()
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
