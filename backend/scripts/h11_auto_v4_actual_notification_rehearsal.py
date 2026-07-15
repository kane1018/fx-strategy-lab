"""Run one finite actual notification rehearsal; never contacts a broker."""

from __future__ import annotations

import json
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    load_external_preparation_gate,
    require_clean_main,
)
from app.services.h11_v4_notification_actual_preparation import (
    H11V4ActualNotificationError,
    run_actual_notification_rehearsal_once,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        operation_permit = ledger.begin(V4PreparationOperation.NOTIFICATION)
        report = run_actual_notification_rehearsal_once(
            external_gate=gate,
            operation_permit=operation_permit,
        )
        ledger.complete(
            V4PreparationOperation.NOTIFICATION,
            operation_permit=operation_permit,
        )
    except (V4ActualPreparationGuardError, H11V4ActualNotificationError) as error:
        print(f"V4_ACTUAL_NOTIFICATION_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
