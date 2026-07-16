"""Verify six fixed H-11 v4 Keychain values internally without exposing them."""

from __future__ import annotations

import json
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    check_v4_keychain_access_internal_only,
    load_external_preparation_gate,
    require_clean_main,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        require_clean_main(repository=REPOSITORY)
        gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=gate)
        operation_permit = ledger.begin(V4PreparationOperation.KEYCHAIN_ACCESS)
        report = check_v4_keychain_access_internal_only(
            operation_permit=operation_permit,
        )
        if not report.all_accessible:
            raise V4ActualPreparationGuardError(
                "PREPARATION_KEYCHAIN_ACCESS_NOT_CLEAR"
            )
        ledger.complete(
            V4PreparationOperation.KEYCHAIN_ACCESS,
            operation_permit=operation_permit,
        )
    except V4ActualPreparationGuardError as error:
        print(f"V4_KEYCHAIN_ACCESS_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
