#!/usr/bin/env python3
"""Bundles the 9 automatable daily H-11 v4 external-preparation steps.

Runs three named stages, one `--stage` at a time -- never all the way
through in one invocation, because two steps (20_email_confirmation,
40_exclusivity_confirmation) require the operator to look at something
real first (the just-sent confirmation email; the broker account/app) and
then type an exact confirmation phrase. No script can substitute for that.

- ``--stage 1``: 00_presence, 05_keychain_access, 10_pushover, 15_smtp.
  Stop after this and run 20_email_confirmation yourself once you have
  read the email.
- ``--stage 2``: 25_network_time, 30_host_kill.
  Stop after this and run 40_exclusivity_confirmation yourself once you
  have confirmed the account is not otherwise in use.
- ``--stage 3``: 45_public_get, 50_private_get, 60_monitor_launchagent.
  All 11 steps are then complete for today.

Each step is still its own separate, already-reviewed script, invoked
exactly as if you had typed it yourself (``python -m scripts.<name>``, in
a fresh subprocess) -- this bundler adds no new preparation logic, no new
safety checks, and never touches the ledger itself.

Each of the 11 steps stays retryable for the rest of the trading day until
it actually passes -- a failed or mismatched attempt does not lock you out.
Once a step has passed today, it is final and cannot be re-attempted until
the next trading day. This bundler still stops immediately at the first
non-zero exit code in a stage rather than attempting the remaining steps
in that stage: re-run the same ``--stage`` command after fixing the cause
shown in that step's own output.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
BACKEND = REPOSITORY / "backend"

_STAGE_1 = (
    ("00_presence", ("scripts.h11_auto_v4_actual_preparation_presence",)),
    ("05_keychain_access", ("scripts.h11_auto_v4_keychain_access_rehearsal",)),
    ("10_pushover", ("scripts.h11_auto_v4_pushover_rehearsal",)),
    ("15_smtp", ("scripts.h11_auto_v4_smtp_rehearsal",)),
)
_STAGE_2 = (
    ("25_network_time", ("scripts.h11_auto_v4_network_time_preflight",)),
    ("30_host_kill", ("scripts.h11_auto_v4_actual_host_kill_rehearsal",)),
)
_STAGE_3 = (
    ("45_public_get", ("scripts.h11_auto_v4_public_get_preflight",)),
    ("50_private_get", ("scripts.h11_auto_v4_private_get_preflight",)),
    (
        "60_monitor_launchagent",
        (
            "scripts.h11_auto_v4_install_monitor_launchagent",
            "--repository",
            str(REPOSITORY),
        ),
    ),
)

_STAGES: dict[int, tuple[tuple[str, tuple[str, ...]], ...]] = {
    1: _STAGE_1,
    2: _STAGE_2,
    3: _STAGE_3,
}

_NEXT_MANUAL_STEP = {
    1: (
        "Next (manual, requires reading the email you just received):\n"
        '  .venv/bin/python -m scripts.h11_auto_v4_email_delivery_confirm "<confirmation phrase>"\n'
        "Then run this bundler again with --stage 2."
    ),
    2: (
        "Next (manual, requires confirming the account is not otherwise in use):\n"
        '  .venv/bin/python -m scripts.h11_auto_v4_exclusivity_confirm "<confirmation phrase>"\n'
        "Then run this bundler again with --stage 3."
    ),
    3: "All 11 daily preparation steps are now complete for today.",
}


def _run_stage(stage: tuple[tuple[str, tuple[str, ...]], ...]) -> int:
    for label, module_args in stage:
        print(f"=== {label} ===")
        sys.stdout.flush()
        result = subprocess.run(
            [sys.executable, "-m", *module_args],
            cwd=BACKEND,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"STOPPED at {label}: exit code {result.returncode}. "
                "See its own output above for the safe failure label. If "
                "it says ALREADY_ATTEMPTED, this step already passed today "
                "-- move on to the next manual/automated step, do not "
                "re-run this bundler stage. Otherwise, fix the cause and "
                "re-run this bundler with the same --stage; this step is "
                "still retryable today."
            )
            return result.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args(argv)

    exit_code = _run_stage(_STAGES[args.stage])
    if exit_code != 0:
        return exit_code

    print()
    print(_NEXT_MANUAL_STEP[args.stage])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
