#!/usr/bin/env python3
"""Bundles the 11 daily H-11 v4 external-preparation steps.

Runs three named stages, one `--stage` at a time -- never all the way
through in one invocation, because two manual steps (20_email_confirmation,
40_exclusivity_confirmation) require the operator to look at something real
first (the just-sent confirmation email; the broker account/app) and then type
an exact confirmation phrase. No script can substitute for that.

- ``--stage 1``: 00_presence, 05_keychain_access, 10_pushover, 15_smtp.
  Stop after this and run 20_email_confirmation yourself once you have
  read the email.
- ``--stage 2``: 25_network_time, 30_host_kill.
  This stage must be launched exactly once by Codex from a confirmed
  GUI-capable escalated execution context. A normal sandbox invocation is
  forbidden and terminal once operation 25 writes its started marker.
  Stop after this and run 40_exclusivity_confirmation yourself once you
  have confirmed the account is not otherwise in use.
- ``--stage 3``: 45_public_get, 50_private_get, 60_monitor_launchagent.
  All 11 steps are then complete for today.

Each step is still its own separate, already-reviewed script, invoked
exactly as if you had typed it yourself (``python -m scripts.<name>``, in
a fresh subprocess) -- this bundler adds no new preparation logic, no new
safety checks, and never touches the ledger itself.

Each step may be retried on the same trading day until it reaches ``PASSED``.
Once ``PASSED`` is durable, that step is final for the day. A retry only
replaces the failed attempt marker and does not prove that a prior external
action did not fire after a crash; the generation lock excludes concurrent
attempts, while crash-after-action remains a disclosed residual risk. This
bundler stops immediately at the first non-zero exit code and never attempts
later steps; rerun the same stage after fixing the cause, without changing the
bundler's stop-on-failure behavior.
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
                "See its own output above for the safe failure label. "
                "Do not infer success from ALREADY_ATTEMPTED or any other "
                "non-zero result. Preserve all markers, stop this generation, "
                "fix the cause, and create a reviewed corrective generation "
                "that restarts external preparation at operation 00."
            )
            return result.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args(argv)

    if args.stage == 2:
        print(
            "REQUIRED: stage 2 must run exactly once from a confirmed "
            "GUI-capable escalated Codex execution context."
        )
    exit_code = _run_stage(_STAGES[args.stage])
    if exit_code != 0:
        return exit_code

    print()
    print(_NEXT_MANUAL_STEP[args.stage])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
