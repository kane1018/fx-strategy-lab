#!/usr/bin/env python3
"""Operator-run CLI: authorize today's unattended live entry, digest computed for you.

Friction-reducing wrapper around
``h11_auto_v4_unattended_live_create_daily_authorization``: the operator no
longer has to look up or hand-type the current generation digest (a
transcription slip there previously had no built-in check other than the
downstream mismatch failing closed). This script computes the current
digest itself, prints it plainly, and still requires the operator to type a
fixed confirmation phrase before anything is written -- the actual decision
to authorize today's unattended entry remains the operator's own, same-day,
deliberate act. This script writes nothing itself; it only computes the
digest and, once confirmed, delegates the actual artifact write to the
already-reviewed creation script unchanged.

Like the script it wraps, this must never be invoked by a scheduler, cron,
LaunchAgent, resident process, or any automated caller -- it is an
operator-run CLI only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    require_clean_main,
)
from app.h11_auto.v4_gmo_generation import V4GmoGenerationError, load_v4_gmo_frozen_generation
from app.services.h11_v4_unattended_live_paths import DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT
from h11_v4_reviewed_digest import compute_reviewed_files_digest
from scripts import h11_auto_v4_unattended_live_create_daily_authorization as create_authorization

REPOSITORY = Path(__file__).resolve().parents[2]

AUTHORIZATION_CONFIRMATION = "I AUTHORIZE UNATTENDED LIVE ENTRY FOR TODAY"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Authorize today's unattended live entry. The current generation "
            "digest is computed and shown to you; you never type it. Requires "
            "the fixed confirmation phrase to proceed."
        ),
    )
    parser.add_argument("confirmation")
    parser.add_argument(
        "--state-root", type=Path, default=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        require_clean_main(repository=REPOSITORY)
        digest = compute_reviewed_files_digest(repository=REPOSITORY)
        generation = load_v4_gmo_frozen_generation(
            repository=REPOSITORY, implementation_digest=digest
        )
    except (V4ActualPreparationGuardError, V4GmoGenerationError) as error:
        print(f"V4_UNATTENDED_LIVE_AUTHORIZE_TODAY_BLOCKED: {error}")
        return 2

    print(f"generation_label={generation.generation_label}")
    print(f"generation_digest={generation.digest}")

    if args.confirmation != AUTHORIZATION_CONFIRMATION:
        print(
            "V4_UNATTENDED_LIVE_AUTHORIZE_TODAY_BLOCKED: "
            "AUTHORIZATION_CONFIRMATION_MISMATCH"
        )
        return 2

    create_argv = [
        "--generation-digest",
        generation.digest,
        "--state-root",
        str(args.state_root),
    ]
    if args.force:
        create_argv.append("--force")
    return create_authorization.main(create_argv)


if __name__ == "__main__":
    raise SystemExit(main())
