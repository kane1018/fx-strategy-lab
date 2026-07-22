"""Run the one-use read-only administrator network-time preparation step."""

from __future__ import annotations

import json
from pathlib import Path

from app.h11_auto.v4_actual_host_kill_rehearsal import (
    V4ActualHostKillRehearsalError,
    run_readonly_network_time_preparation,
)
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    load_external_preparation_gate,
    require_clean_main,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        operation = V4PreparationOperation.NETWORK_TIME
        operation_permit = ledger.begin(operation)
        report = run_readonly_network_time_preparation(
            external_gate=gate,
            operation_permit=operation_permit,
        )
        if not report.status.startswith("PASSED_"):
            print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
            return 2
        ledger.complete(operation, operation_permit=operation_permit)
    except (V4ActualPreparationGuardError, V4ActualHostKillRehearsalError) as error:
        print(f"V4_NETWORK_TIME_PREFLIGHT_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
