#!/usr/bin/env python3
"""One-slot G013 Public observer with a local-only actionable sound alert."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from app.services.h11_v4_gmo_signal_preview import (
    G013SignalPreviewError,
    G013SignalPreviewReport,
    run_g013_signal_preview,
)

_ACTIONABLE_SOUND = "/System/Library/Sounds/Glass.aiff"


def _play_actionable_sound() -> None:
    """Attempt the fixed local alert once; its result never affects the preview."""

    try:
        subprocess.run(
            ["/usr/bin/afplay", _ACTIONABLE_SOUND],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _safe_output(report: G013SignalPreviewReport) -> dict[str, object]:
    output = report.to_safe_dict()
    if report.candidate_actionable:
        _play_actionable_sound()
        output["status"] = "G013_PUBLIC_SIGNAL_OBSERVER_ACTIONABLE_ALERT_ATTEMPTED"
        output["local_sound_attempted"] = True
    else:
        output["local_sound_attempted"] = False
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Observe exactly one completed G013 Public M1 slot without authorization."
    )
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
                    "local_sound_attempted": False,
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
                    "status": "G013_PUBLIC_SIGNAL_OBSERVER_FAILED_SAFE",
                    "candidate_actionable": False,
                    "local_sound_attempted": False,
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
    print(json.dumps(_safe_output(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
