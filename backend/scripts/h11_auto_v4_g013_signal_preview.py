#!/usr/bin/env python3
"""Manual one-shot G013 Public signal preview; never authorizes broker actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.h11_v4_gmo_signal_preview import (
    G013SignalPreviewError,
    run_g013_signal_preview,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_g013_signal_preview(repository=args.repository)
    except G013SignalPreviewError as error:
        print(
            json.dumps(
                {
                    "status": str(error),
                    "candidate_actionable": False,
                    "authorization_granted": False,
                    "activation_permit_issued": False,
                    "broker_write": False,
                    "broker_post_count": 0,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "status": "G013_PREVIEW_FAILED_SAFE",
                    "candidate_actionable": False,
                    "authorization_granted": False,
                    "activation_permit_issued": False,
                    "broker_write": False,
                    "broker_post_count": 0,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report.to_safe_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
