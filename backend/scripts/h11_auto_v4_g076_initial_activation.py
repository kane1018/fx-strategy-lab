"""G076 initial activation candidate.

The executable is intentionally disabled.  The transaction ordering is tested
through ``run_g076_initial_atomic_activation_fake_only`` with synthetic
reconciliation data; real Keychain, Private GET, ARM, and broker paths are a
separate release boundary and are not part of this candidate.
"""

from __future__ import annotations

from app.services.h11_v4_g076_runtime import G076Error


def main() -> int:
    raise G076Error("G076_INITIAL_ACTIVATION_FAKE_ONLY_CANDIDATE")


if __name__ == "__main__":
    raise SystemExit(main())
