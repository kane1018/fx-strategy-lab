"""Run one finite sanitized H-11 v4 GMO Private GET sequence."""

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
from app.services.h11_v4_gmo_readonly_preflight import (
    V4GmoFiniteReadOnlyPreflight,
    V4GmoReadOnlyPreflightError,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        operation_permit = ledger.begin(V4PreparationOperation.PRIVATE_GET)
        report = V4GmoFiniteReadOnlyPreflight(
            external_gate=gate,
            operation_permit=operation_permit,
        ).run_once()
        if not report.limited_usd_jpy_snapshot_clear:
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_LIMITED_SNAPSHOT_NOT_CLEAR")
        ledger.complete(
            V4PreparationOperation.PRIVATE_GET,
            operation_permit=operation_permit,
        )
    except (V4ActualPreparationGuardError, V4GmoReadOnlyPreflightError) as error:
        print(f"V4_PRIVATE_GET_PREFLIGHT_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
