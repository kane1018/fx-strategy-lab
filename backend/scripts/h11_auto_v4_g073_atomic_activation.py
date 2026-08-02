"""G073 initial activation boundary; fake-only until separately authorized."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.services.h11_v4_g073_runtime import G073Error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G073 activation boundary is not executable in this phase"
    )
    parser.add_argument("--repository", type=Path, required=True)
    parser.parse_args()
    raise G073Error("G073_INITIAL_ATOMIC_ACTIVATION_REQUIRES_SEPARATE_AUTHORIZATION")


if __name__ == "__main__":
    raise SystemExit(main())
