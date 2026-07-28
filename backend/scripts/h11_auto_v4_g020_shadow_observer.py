#!/usr/bin/env python3
"""Record one G020 Public-only shadow slot; never call a broker endpoint."""

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
from app.services.h11_v4_g020_shadow_observer_no_post import (
    V4G020ShadowEvidenceStore,
    V4G020ShadowObservationStatus,
    fetch_latest_completed_public_m1_slot,
)
from app.shadow.gmo_public import GmoPublicMarketDataClient
from h11_v4_reviewed_digest import compute_reviewed_files_digest

_EXPECTED_GENERATION_LABEL = "H11_AUTO_30M_20260728_G020"
_STATE_RELATIVE = Path("backend/market_data/h11_v4_g020_shadow_observer")


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    try:
        require_clean_main(repository=repository)
        reviewed = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository, implementation_digest=reviewed
        )
        if generation.generation_label != _EXPECTED_GENERATION_LABEL:
            raise ValueError("G020_SHADOW_GENERATION_INVALID")
        state_path = (
            repository
            / _STATE_RELATIVE
            / f"generation-{generation.digest.removeprefix('sha256:')}"
            / "shadow-ledger.json"
        )
        store = V4G020ShadowEvidenceStore(
            path=state_path,
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
        )
        result = store.observe_once(
            fetch_completed_slot=lambda: fetch_latest_completed_public_m1_slot(
                now_utc=datetime.now(UTC), client=GmoPublicMarketDataClient()
            )
        )
        print(json.dumps(result.to_safe_dict(), sort_keys=True))
        return 0 if result.status in {
            V4G020ShadowObservationStatus.RECORDED,
            V4G020ShadowObservationStatus.ALREADY_OBSERVED,
            V4G020ShadowObservationStatus.CAP_REACHED,
        } else 2
    except Exception:
        print(
            json.dumps(
                {
                    "status": "G020_SHADOW_OBSERVER_FAILED_SAFE",
                    "broker_write": False,
                    "broker_post_count": 0,
                    "credential_read": False,
                    "private_api_read": False,
                    "raw_response_retained": False,
                    "authorization_granted": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
