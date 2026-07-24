#!/usr/bin/env python3
"""Operator-run CLI: create today's unattended live daily authorization artifact.

This script is the operator's own manual action, run at most once per JST
trading day. It is never invoked by a scheduler, cron, LaunchAgent, resident
process, or any automated caller -- doing so is explicitly prohibited by the
AGENTS.md exception this script is implemented under.

The JST trading day is always "right now" -- there is no flag to author a
past or future day. The generation digest must be typed explicitly; there is
no default or inferred value. An existing file at the canonical path is never
silently overwritten; --force is required.

This script only writes the artifact. It never consumes it (that remains
``app.services.h11_v4_unattended_live_authorization``'s read-and-consume-only
surface) and never touches Private API, Keychain, credentials, or a broker.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.h11_v4_unattended_live_authorization import (
    V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
    check_operator_daily_authorization,
)
from app.services.h11_v4_unattended_live_paths import (
    V4UnattendedLivePathError,
    v4_unattended_live_daily_authorization_path,
)

_JST = ZoneInfo("Asia/Tokyo")
_DEFAULT_REPOSITORY = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create today's unattended live daily authorization artifact. "
            "Run this yourself, once per JST trading day you authorize."
        ),
    )
    parser.add_argument(
        "--generation-digest",
        required=True,
        help="Exact sha256:<64 hex> digest of the generation being authorized.",
    )
    parser.add_argument("--repository", type=Path, default=_DEFAULT_REPOSITORY)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing artifact at today's canonical path.",
    )
    args = parser.parse_args(argv)

    try:
        path = v4_unattended_live_daily_authorization_path(
            repository=args.repository, generation_digest=args.generation_digest
        )
    except V4UnattendedLivePathError as error:
        print(json.dumps({"status": str(error), "created": False}, sort_keys=True))
        return 2

    if path.is_symlink():
        print(
            json.dumps(
                {"status": "AUTHORIZATION_ARTIFACT_PATH_SYMLINK_REFUSED", "created": False},
                sort_keys=True,
            )
        )
        return 2
    if path.exists() and not args.force:
        print(
            json.dumps(
                {
                    "status": "AUTHORIZATION_ARTIFACT_ALREADY_EXISTS_USE_FORCE",
                    "created": False,
                },
                sort_keys=True,
            )
        )
        return 2

    today_jst = datetime.now(UTC).astimezone(_JST).date().isoformat()
    payload = {
        "schema": V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
        "generation_digest": args.generation_digest,
        "trading_day_jst": today_jst,
        "maximum_entries": 1,
        "operator_authorized": True,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        # O_EXCL (not just an is_symlink() check) closes the TOCTOU window
        # where a symlink could be planted at `temporary` between a check and
        # a later open -- mirrors consume_operator_daily_authorization_once's
        # own O_EXCL marker write. A pre-existing temp file (leftover from a
        # crashed prior run, or a planted symlink) fails closed here rather
        # than being silently removed and reopened.
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print(
            json.dumps(
                {
                    "status": "AUTHORIZATION_ARTIFACT_TEMP_FILE_ALREADY_EXISTS",
                    "created": False,
                },
                sort_keys=True,
            )
        )
        return 2
    except OSError as error:
        print(
            json.dumps(
                {"status": f"AUTHORIZATION_ARTIFACT_WRITE_FAILED: {error}", "created": False},
                sort_keys=True,
            )
        )
        return 2
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as error:
        print(
            json.dumps(
                {"status": f"AUTHORIZATION_ARTIFACT_WRITE_FAILED: {error}", "created": False},
                sort_keys=True,
            )
        )
        return 2

    check = check_operator_daily_authorization(
        artifact_path=path,
        expected_generation_digest=args.generation_digest,
        now_utc=datetime.now(UTC),
    )
    print(
        json.dumps(
            {
                "created": True,
                "path": str(path),
                "trading_day_jst": check.trading_day_jst,
                "authorized": check.authorized,
                "blocked_reasons": list(check.blocked_reasons),
                "consumption_available": check.consumption_available,
            },
            sort_keys=True,
        )
    )
    return 0 if check.authorized else 1


if __name__ == "__main__":
    raise SystemExit(main())
