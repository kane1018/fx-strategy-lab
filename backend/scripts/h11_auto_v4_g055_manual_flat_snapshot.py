#!/usr/bin/env python3
"""Run the G055 generation-bound one-use manual-flat Private GET snapshot."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.services.h11_v4_g026_private_get_keychain import (
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_unattended_account_snapshot_producer_no_post import (
    produce_account_snapshot_once_no_post,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_account_snapshot_state_directory,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    GMO_V4_PRIVATE_BASE_URL,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

_EXPECTED_GENERATION_LABEL = "H11_AUTO_30M_20260730_G055"


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    try:
        _require_clean_main(repository)
        reviewed = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed,
        )
        if generation.generation_label != _EXPECTED_GENERATION_LABEL:
            raise RuntimeError("G055_SNAPSHOT_GENERATION_INVALID")
        result = produce_account_snapshot_once_no_post(
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
            store_directory=v4_unattended_account_snapshot_state_directory(
                generation_digest=generation.digest,
            ),
            credential_pair=V4G026PrivateGetKeychainCredentialPair(),
            client_factory=lambda: httpx.Client(
                base_url=GMO_V4_PRIVATE_BASE_URL,
                timeout=10.0,
            ),
        )
        print(json.dumps(result.to_safe_dict(), sort_keys=True))
        return 0 if result.account_flat and result.active_orders_zero else 2
    except Exception:
        print(json.dumps(_safe_failure(), sort_keys=True))
        return 2


def _safe_failure() -> dict[str, object]:
    return {
        "status": "G055_MANUAL_FLAT_SNAPSHOT_REFUSED_OR_FAILED_NO_RETRY",
        "account_flat": False,
        "active_orders_zero": False,
        "broker_get_count": None,
        "raw_response_retained": False,
        "identifier_exposed": False,
        "broker_write": False,
        "broker_post_count": 0,
    }


def _require_clean_main(repository: Path) -> None:
    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("G055_REPOSITORY_GATE_FAILED")
        return result.stdout.strip()

    if (
        git("branch", "--show-current") != "main"
        or git("status", "--porcelain")
        or git("rev-parse", "HEAD") != git("rev-parse", "origin/main")
    ):
        raise RuntimeError("G055_REPOSITORY_GATE_FAILED")


if __name__ == "__main__":
    raise SystemExit(main())
