"""Run non-destructive current-host and persistent KILL preparation proof."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.v4_actual_host_kill_rehearsal import (
    V4ActualHostKillRehearsalError,
    run_actual_host_kill_rehearsal,
)
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    load_external_preparation_gate,
    require_clean_main,
)

REPOSITORY = Path(__file__).resolve().parents[2]
JST = ZoneInfo("Asia/Tokyo")


def _parse_args(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the one-use H-11 v4 current-host and persistent KILL "
            "preparation proof"
        )
    )
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser.parse_args(arguments)
    if arguments:
        parser.error("this operation accepts no arguments")


def main(argv: Sequence[str] | None = None) -> int:
    _parse_args(argv)
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        operation_permit = ledger.begin(V4PreparationOperation.HOST_KILL)
        report = run_actual_host_kill_rehearsal(
            external_gate=gate,
            operation_permit=operation_permit,
            cycle_day_jst=datetime.now(JST).date().isoformat(),
        )
        if not report.status.startswith("PASSED_"):
            print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
            return 2
        ledger.complete(
            V4PreparationOperation.HOST_KILL,
            operation_permit=operation_permit,
        )
    except (V4ActualPreparationGuardError, V4ActualHostKillRehearsalError) as error:
        print(f"V4_ACTUAL_HOST_KILL_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
