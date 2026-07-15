"""Test-only child process that dies after persisting a synthetic attempt."""

from __future__ import annotations

import argparse
import os
import signal
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.persistence import H11AutoProcessLock, H11AutoStateStore

NOW = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)


def build_fixture() -> tuple[FormalSignal, PhaseAExecutionPolicy]:
    formal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:process-crash-test",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    policy = PhaseAExecutionPolicy(
        strategy_version=formal.strategy_version,
        signal_config_hash=formal.signal_config_hash,
        selected_horizon=formal.horizon,
    )
    return formal, policy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    formal, policy = build_fixture()
    store = H11AutoStateStore(args.state_dir / "state.sqlite3")
    with H11AutoProcessLock(args.state_dir / "auto.lock"):
        cycle = store.create_intent(signal=formal, policy=policy, now_utc=NOW)
        store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
        os.kill(os.getpid(), signal.SIGKILL)
    return 99


if __name__ == "__main__":
    raise SystemExit(main())
