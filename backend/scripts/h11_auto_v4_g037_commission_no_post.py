"""Fix G037 successful-canary evidence from local read-only state, no POST."""

from __future__ import annotations

# ruff: noqa: E402 -- absolute LaunchAgent-style execution needs backend on sys.path.
import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.h11_v4_g037_unattended_commissioning_no_post import (
    V4G037CommissioningNoPostError,
    record_successful_canary_evidence_once_no_post,
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--origin-reviewed-files-digest", required=True)
    parser.add_argument("--origin-generation-digest", required=True)
    parser.add_argument("--target-reviewed-files-digest", required=True)
    parser.add_argument("--target-generation-digest", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _, evidence = record_successful_canary_evidence_once_no_post(
            repository=args.repository,
            origin_reviewed_files_digest=args.origin_reviewed_files_digest,
            origin_generation_digest=args.origin_generation_digest,
            target_reviewed_files_digest=args.target_reviewed_files_digest,
            target_generation_digest=args.target_generation_digest,
            state_root=args.state_root,
        )
    except V4G037CommissioningNoPostError as error:
        print(
            f"status={error} broker_write=false broker_post_count=0 "
            "credential_read=false private_api_read=false"
        )
        return 1
    print(
        "status=G037_SUCCESSFUL_CANARY_EVIDENCE_FIXED_NO_POST "
        f"halt_classification={evidence.post_flat_halt_classification} "
        "post_flat_halt_blocks_activation=true permit_issued=false "
        "broker_post_authorized=false broker_write=false broker_post_count=0 "
        "credential_read=false private_api_read=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
