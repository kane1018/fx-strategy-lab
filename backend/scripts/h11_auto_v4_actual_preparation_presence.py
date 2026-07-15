"""Presence-only H-11 v4 Keychain check after the clean-main gate."""

from __future__ import annotations

import json
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    check_v4_keychain_presence_only,
    load_external_preparation_gate,
    require_clean_main,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        git_gate = require_clean_main(repository=REPOSITORY)
        external_gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=external_gate)
        operation_permit = ledger.begin(V4PreparationOperation.PRESENCE)
        report = check_v4_keychain_presence_only(
            operation_permit=operation_permit
        )
        if not report.all_present:
            raise V4ActualPreparationGuardError("PREPARATION_KEYCHAIN_ITEMS_MISSING")
        ledger.complete(
            V4PreparationOperation.PRESENCE,
            operation_permit=operation_permit,
        )
    except V4ActualPreparationGuardError as error:
        print(f"V4_ACTUAL_PREPARATION_BLOCKED: {error}")
        return 2
    payload = report.to_safe_dict()
    payload["git_gate_clear"] = git_gate.clear
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
