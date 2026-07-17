"""Run one finite sanitized H-11 v4 GMO Public GET sequence."""

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
from app.services.h11_v4_gmo_public_preflight import (
    V4GmoFinitePublicPreflight,
    V4GmoPublicPreflightError,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        permit = ledger.begin(V4PreparationOperation.PUBLIC_GET)
        report = V4GmoFinitePublicPreflight(
            external_gate=gate,
            operation_permit=permit,
        ).run_once()
        if not report.status.startswith("PASSED_"):
            raise V4GmoPublicPreflightError("PUBLIC_GET_NOT_CLEAR")
        ledger.complete(V4PreparationOperation.PUBLIC_GET, operation_permit=permit)
    except (V4ActualPreparationGuardError, V4GmoPublicPreflightError) as error:
        print(f"V4_PUBLIC_GET_PREFLIGHT_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
