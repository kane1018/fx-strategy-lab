"""Record the one-use G038 successor-only HALT release."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.h11_v4_g038_unattended_activation import (  # noqa: E402
    V4G038ActivationError,
    record_g038_successor_release_once,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-generation-digest", required=True)
    parser.add_argument("--source-reviewed-files-digest", required=True)
    parser.add_argument("--target-reviewed-files-digest", required=True)
    parser.add_argument("--target-generation-label", required=True)
    args = parser.parse_args()
    try:
        release = record_g038_successor_release_once(
            repository=Path(__file__).resolve().parents[2],
            source_generation_digest=args.source_generation_digest,
            source_reviewed_files_digest=args.source_reviewed_files_digest,
            target_reviewed_files_digest=args.target_reviewed_files_digest,
            target_generation_label=args.target_generation_label,
        )
    except V4G038ActivationError as error:
        print(
            f"status={error} broker_write=false broker_post_count=0 "
            "permit_issued=false"
        )
        return 2
    print(
        "status=G038_SUCCESSOR_HALT_RELEASED_NO_POST "
        f"release_digest={release.digest} source_halt_remains_latched=true "
        "broker_write=false broker_post_count=0 permit_issued=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
