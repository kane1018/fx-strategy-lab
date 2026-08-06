"""Operator-only one-shot HALT discharge script.

Rename-archives a single persistent halt with recorded operator resolution.
This is an OPERATOR action: the runtime never calls this module, and the two
existing unresolved halts (G074/G075) are NOT discharged by this repository's
tests or automation — only by an explicit operator run with a fresh
``--confirm-sha256`` matching the halt file actually on disk.

Usage example (operator only, after reading the file content):

    PYTHONPATH=backend backend/.venv/bin/python \\
        backend/scripts/h11_auto_v4_halt_discharge.py \\
        --repository . \\
        --generation-digest sha256:f0e74bf0... \\
        --halt-file-name g075-persistent-halt.json \\
        --operator "<name>" \\
        --reason "<why the halt is discharged>" \\
        --broker-state-confirmation "<how flat/zero-order was confirmed>" \\
        --confirm-sha256 sha256:<value printed by the script>

The script prints the target halt content and its sha256 BEFORE asking for
``--confirm-sha256``; the discharge aborts unless the values match.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_halt_discharge import (  # noqa: E402
    V4HaltDischargeError,
    discharge_halt,
    halt_content_sha256,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--generation-digest", required=True)
    parser.add_argument("--halt-file-name", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--broker-state-confirmation", required=True)
    parser.add_argument("--confirm-sha256", required=True)
    return parser.parse_args()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = args.repository.resolve()
    halt_path = (
        v4_gmo_runtime_state_root(
            repository=repository, generation_digest=args.generation_digest
        )
        / args.halt_file_name
    )
    if halt_path.is_symlink() or not halt_path.is_file():
        print(
            "status=V4_HALT_DISCHARGE_TARGET_MISSING "
            f"halt={args.halt_file_name} broker_post_count=0 actual_post_count=0"
        )
        return 2
    try:
        payload = json.loads(halt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"status=V4_HALT_DISCHARGE_TARGET_INVALID error={error!r}")
        return 2
    actual = halt_content_sha256(payload)
    print(f"target={halt_path}")
    print("content=" + json.dumps(payload, sort_keys=True))
    print(f"sha256={actual}")
    if args.confirm_sha256 != actual:
        print(
            "status=V4_HALT_DISCHARGE_SHA256_MISMATCH broker_post_count=0 "
            "actual_post_count=0"
        )
        return 2
    try:
        archive_path = discharge_halt(
            repository=repository,
            generation_digest=args.generation_digest,
            halt_file_name=args.halt_file_name,
            resolution={
                "operator": args.operator,
                "reason": args.reason,
                "broker_state_confirmation": args.broker_state_confirmation,
                "halt_content_sha256": actual,
            },
            now_utc=datetime.now(UTC),
        )
    except V4HaltDischargeError as error:
        print(f"status={error} broker_post_count=0 actual_post_count=0")
        return 2
    print(f"status=V4_HALT_DISCHARGED archive={archive_path} "
          "broker_post_count=0 actual_post_count=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
