"""One-slot Public-only G013 formal-aware observer."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from app.services.h11_v4_gmo_formal_aware_preview import run_g013_formal_aware_preview


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=Path)
    args = parser.parse_args()
    result = run_g013_formal_aware_preview(repository=args.repository.resolve())
    if result.formal_candidate_actionable:
        subprocess.run(
            ["/usr/bin/afplay", "/System/Library/Sounds/Glass.aiff"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(json.dumps(result.to_safe_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
