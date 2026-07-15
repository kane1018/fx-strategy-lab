"""Fake-only operator HALT reload utility for the relaxed GMO v4 profile."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker
from app.h11_auto.v4_gmo_contracts import (
    V4GmoBrokerSnapshot,
    V4GmoEntryStatus,
    V4GmoProtectionStatus,
)
from app.h11_auto.v4_gmo_persistence import V4GmoPersistenceError
from app.h11_auto.v4_gmo_runtime import (
    V4GmoOperatorReloadStatus,
    V4GmoRuntimeError,
    operator_reload_v4_gmo_no_post,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clear a synthetic v4 HALT after a fake flat check (no broker access)"
    )
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument(
        "--synthetic-snapshot", choices=("FLAT", "NONFLAT"), required=True
    )
    args = parser.parse_args(argv)
    snapshot = (
        V4GmoBrokerSnapshot.flat()
        if args.synthetic_snapshot == "FLAT"
        else _nonflat_snapshot()
    )
    try:
        report = operator_reload_v4_gmo_no_post(
            state_path=args.state,
            lock_path=args.lock,
            broker=FakeV4GmoBroker(outcomes={}, snapshots=[snapshot]),
            confirmation=args.confirmation,
            now_utc=_now_utc(),
        )
    except (V4GmoPersistenceError, V4GmoRuntimeError, OSError, ValueError) as error:
        print(f"V4_GMO_RELOAD_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return (
        0
        if report.status
        in {
            V4GmoOperatorReloadStatus.CLEARED_NO_POST,
            V4GmoOperatorReloadStatus.NO_HALT_LATCHED,
        }
        else 1
    )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _nonflat_snapshot() -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=10_000,
        pending_entry_size=0,
        protection_size=0,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=V4GmoProtectionStatus.NONE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
