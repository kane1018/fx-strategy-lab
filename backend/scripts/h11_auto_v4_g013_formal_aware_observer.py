"""One-slot current-generation Public-only formal-aware observer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
)
from app.services.h11_v4_gmo_formal_aware_preview import (
    G013FormalAwarePreviewError,
    run_g013_formal_aware_preview,
)
from app.services.h11_v4_gmo_signal_preview import G013SignalPreviewError

ACTIONABLE_EXIT_CODE = 10
WAIT_EXIT_CODE = 3
FAILURE_EXIT_CODE = 2
_WAIT_STATUSES = {
    "G013_PREVIEW_PUBLICATION_PENDING",
    "G013_PREVIEW_SLOT_ALREADY_ATTEMPTED",
}


def _safe_failure(
    status: str,
    *,
    public_get_count: int | None,
    candidate_actionable: bool | None,
    next_action: str,
) -> dict[str, object]:
    return {
        "status": status,
        "candidate_actionable": candidate_actionable,
        "candidate_actionable_known": candidate_actionable is not None,
        "formal_candidate_actionable": False,
        "public_get_count": public_get_count,
        "public_get_count_known": public_get_count is not None,
        "broker_post_count": 0,
        "private_api_read": False,
        "credential_read": False,
        "broker_write": False,
        "permit_issued": False,
        "actual_generation_consumed": False,
        "direction_exposed": False,
        "probability_exposed": False,
        "price_exposed": False,
        "raw_market_data_exposed": False,
        "order_sheet_exposed": False,
        "challenge_exposed": False,
        "notification_attempted": False,
        "local_sound_attempted": False,
        "observer_contract": "ONE_COMPLETED_SLOT_PER_INVOCATION",
        "next_action": next_action,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run_g013_formal_aware_preview(repository=args.repository.resolve())
    except G013FormalAwarePreviewError as error:
        print(
            json.dumps(
                _safe_failure(
                    str(error),
                    public_get_count=error.public_get_count,
                    candidate_actionable=error.candidate_actionable,
                    next_action="STOP_NO_RETRY",
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return FAILURE_EXIT_CODE
    except G013SignalPreviewError as error:
        status = str(error)
        waiting = status in _WAIT_STATUSES
        print(
            json.dumps(
                _safe_failure(
                    status,
                    public_get_count=0 if waiting else None,
                    candidate_actionable=None,
                    next_action="WAIT_NEXT_WAKE" if waiting else "STOP_NO_RETRY",
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return WAIT_EXIT_CODE if waiting else FAILURE_EXIT_CODE
    except V4ActualPreparationGuardError as error:
        status = str(error)
        if not status.startswith("V4_"):
            status = "G013_PREVIEW_CLEAN_MAIN_REQUIRED"
        print(
            json.dumps(
                _safe_failure(
                    status,
                    public_get_count=0,
                    candidate_actionable=None,
                    next_action="STOP_REQUIRES_CLEAN_MAIN",
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return FAILURE_EXIT_CODE
    except Exception:
        print(
            json.dumps(
                _safe_failure(
                    "G013_FORMAL_AWARE_PREVIEW_FAILED_SAFE",
                    public_get_count=None,
                    candidate_actionable=None,
                    next_action="STOP_UNKNOWN",
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return FAILURE_EXIT_CODE
    print(json.dumps(result.to_safe_dict(), sort_keys=True))
    if result.formal_candidate_actionable:
        return ACTIONABLE_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
