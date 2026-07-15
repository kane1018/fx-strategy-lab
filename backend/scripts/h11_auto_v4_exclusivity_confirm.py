"""Record exact operator confirmation of temporary account exclusivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    confirm_account_exclusivity_exact,
    load_external_preparation_gate,
    require_clean_main,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record exact H-11 v4 exclusive-account confirmation"
    )
    parser.add_argument("confirmation")
    args = parser.parse_args(argv)
    try:
        require_clean_main(repository=REPOSITORY)
        external_gate = load_external_preparation_gate(repository=REPOSITORY)
        ledger = V4PreparationAttemptLedger(external_gate=external_gate)
        operation_permit = ledger.begin(
            V4PreparationOperation.EXCLUSIVITY_CONFIRMATION
        )
        report = confirm_account_exclusivity_exact(
            phrase=args.confirmation,
            operation_permit=operation_permit,
        )
        ledger.complete(
            V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
            operation_permit=operation_permit,
        )
    except V4ActualPreparationGuardError as error:
        print(f"V4_EXCLUSIVITY_CONFIRMATION_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
