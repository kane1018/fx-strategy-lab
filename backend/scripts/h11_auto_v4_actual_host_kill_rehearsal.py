"""Run non-destructive current-host and persistent KILL preparation proof."""

from __future__ import annotations

import json
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


def main() -> int:
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
            raise V4ActualHostKillRehearsalError("HOST_REHEARSAL_NOT_CLEAR")
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
