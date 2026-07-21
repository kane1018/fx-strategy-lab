"""Interactive finite G013 canary; exact confirmations precede all writes."""

from __future__ import annotations

import getpass
import json
import signal
from pathlib import Path

from app.services.h11_v4_gmo_g013_canary import (
    V4GmoG013CanaryError,
    prepare_g013_canary_session,
    run_g013_actual_canary_after_exact_confirmation,
)

REPOSITORY = Path(__file__).resolve().parents[2]
INPUT_TIMEOUT_SECONDS = 300.0


def _read_hidden_with_timeout(prompt: str) -> str:
    """Read one hidden line, with getpass owning the terminal before any typing.

    getpass takes the terminal with ``TCSAFLUSH``, which DISCARDS whatever is already
    buffered.  Waiting for input first (the previous ``select`` on stdin) therefore threw
    away exactly the phrase the operator had just typed or pasted, so every confirmation
    silently mismatched.  Calling getpass up front means echo is already off and the
    prompt is already shown when the operator types, so the input is read verbatim.

    The same ``INPUT_TIMEOUT_SECONDS`` bound is kept, enforced with a real-time timer that
    is armed only while waiting for operator input and always disarmed afterwards, so it
    can never fire during a broker write.
    """

    def _expire(signum: int, frame: object) -> None:
        del signum, frame
        raise V4GmoG013CanaryError("G013_OPERATOR_CONFIRMATION_TIMEOUT")

    # Install the handler BEFORE unblocking: an inherited mask that blocks SIGALRM
    # would otherwise leave the itimer pending forever (silently defeating the
    # timeout), and unblocking first could deliver an already-pending SIGALRM under
    # the default disposition — killing the process instead of raising the labelled
    # timeout. Handler first, then unblock, then arm.
    previous = signal.signal(signal.SIGALRM, _expire)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGALRM})
    signal.setitimer(signal.ITIMER_REAL, INPUT_TIMEOUT_SECONDS)
    try:
        return getpass.getpass(prompt)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _hidden_input(prompt: str) -> str:
    # The label rides in the getpass prompt (written to the controlling tty), so the
    # operator still sees it when stdout is redirected, and it appears exactly when
    # echo-off input begins.
    return _read_hidden_with_timeout(f"{prompt}\n")


def _hidden_current_turn_input(challenge: str) -> str:
    return _read_hidden_with_timeout(
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
