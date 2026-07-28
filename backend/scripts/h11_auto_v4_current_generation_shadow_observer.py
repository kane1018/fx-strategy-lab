#!/usr/bin/env python3
"""Record one current-generation Public-only shadow slot; never call a broker."""

from __future__ import annotations

# ruff: noqa: E402 -- direct script execution needs the local backend bootstrap.
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_ROOT_PATH))

from app.h11_auto.v4_actual_preparation_guard import require_clean_main
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_current_generation_shadow_observer_no_post import (
    V4CurrentGenerationShadowStatus,
    V4CurrentGenerationShadowStore,
    fetch_latest_completed_public_m1_slot,
)
from app.shadow.gmo_public import GmoPublicMarketDataClient
from h11_v4_reviewed_digest import compute_reviewed_files_digest


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    try:
        require_clean_main(repository=repository)
        reviewed = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed,
        )
        root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        ) / "shadow-commissioning"
        store = V4CurrentGenerationShadowStore(
            path=root / "shadow-ledger.json",
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
        )
        result = store.observe_once(
            fetch_completed_slot=lambda: fetch_latest_completed_public_m1_slot(
                now_utc=datetime.now(UTC),
                client=GmoPublicMarketDataClient(),
            )
        )
        print(json.dumps(result.to_safe_dict(), sort_keys=True))
        accepted = {
            V4CurrentGenerationShadowStatus.RECORDED,
            V4CurrentGenerationShadowStatus.ALREADY_OBSERVED,
            V4CurrentGenerationShadowStatus.CAP_REACHED,
        }
        return 0 if result.status in accepted else 2
    except Exception:
        print(json.dumps(_safe_failure(), sort_keys=True))
        return 2


def _safe_failure() -> dict[str, object]:
    return {
        "status": "CURRENT_GENERATION_SHADOW_OBSERVER_FAILED_SAFE",
        "broker_write": False,
        "broker_post_count": 0,
        "credential_read": False,
        "private_api_read": False,
        "raw_response_retained": False,
        "authorization_granted": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
