"""Interactive finite G013 canary; exact confirmations precede all writes."""

from __future__ import annotations

import getpass
import json
import select
import sys
from pathlib import Path

from app.services.h11_v4_gmo_g013_canary import (
    V4GmoG013CanaryError,
    prepare_g013_canary_session,
    run_g013_actual_canary_after_exact_confirmation,
)

REPOSITORY = Path(__file__).resolve().parents[2]
INPUT_TIMEOUT_SECONDS = 300.0


def _hidden_input(prompt: str) -> str:
    print(prompt, flush=True)
    readable, _, _ = select.select([sys.stdin], [], [], INPUT_TIMEOUT_SECONDS)
    if not readable:
        raise V4GmoG013CanaryError("G013_OPERATOR_CONFIRMATION_TIMEOUT")
    return getpass.getpass("")


def _hidden_current_turn_input(challenge: str) -> str:
    readable, _, _ = select.select([sys.stdin], [], [], INPUT_TIMEOUT_SECONDS)
    if not readable:
        raise V4GmoG013CanaryError("G013_OPERATOR_CONFIRMATION_TIMEOUT")
    return getpass.getpass(
        f"current_turn_challenge_exact_required [{challenge}]\n> "
    )


def main() -> int:
    try:
        session = prepare_g013_canary_session(repository=REPOSITORY)
        print(
            json.dumps(
                {
                    "status": "G013_EXACT_ORDER_SHEET_POST_COUNT_ZERO",
                    "order_sheet": session.order_sheet.to_safe_dict(),
                    "broker_post_count": 0,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            flush=True,
        )
        resume = _hidden_input("major_incident_resume_exact_required")
        challenge = session.current_turn_phrase_for_operator()
        current = _hidden_current_turn_input(challenge)
        result = run_g013_actual_canary_after_exact_confirmation(
            session=session,
            major_incident_resume_phrase=resume,
            current_turn_phrase=current,
            on_protected=lambda active: print(
                json.dumps(active.to_safe_dict(), sort_keys=True),
                flush=True,
            ),
        )
    except Exception as error:  # fixed application labels only
        label = str(error)
        if not label.startswith("G013_") and not label.startswith("V4_"):
            label = "G013_CANARY_FAILED_SAFE"
        print(f"G013_CANARY_BLOCKED: {label}", flush=True)
        return 2
    print(json.dumps(result.to_safe_dict(), sort_keys=True, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
