#!/usr/bin/env python3
"""Run one generation-bound offline controller tick with zero external I/O."""

from __future__ import annotations

# ruff: noqa: E402 -- direct script execution needs the local backend bootstrap.
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_ROOT_PATH))

from app.h11_auto.runtime_safety import PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import require_clean_main
from app.h11_auto.v4_gmo_generation import (
    load_v4_gmo_frozen_generation,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_unattended_commissioning_no_post import (
    bind_g018_predecessor_canary_completion,
    load_commissioning_artifact,
    load_shadow_evidence_artifact,
)
from app.services.h11_v4_unattended_controller_snapshot_no_post import (
    V4UnattendedControllerOfflineSources,
    V4UnattendedControllerSnapshotNoPostError,
    assemble_offline_controller_snapshot_no_post,
)
from app.services.h11_v4_unattended_integrated_controller_no_post import (
    V4IntegratedControllerStore,
)
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_live_arm_state_path,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

_STATE = Path("backend/market_data/h11_v4_unattended_controller_no_post")


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    phase = "CLEAN_MAIN"
    try:
        require_clean_main(repository=repository)
        phase = "REVIEW_BOUNDARY"
        reviewed = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=reviewed,
        )
        risk_policy = v4_gmo_risk_policy()
        commissioning_path, shadow_path = _current_artifact_paths(
            repository=repository,
            generation_label=generation.generation_label,
        )
        runtime_root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        )
        phase = "LOCAL_EVIDENCE"
        commissioning = load_commissioning_artifact(commissioning_path)
        shadow = load_shadow_evidence_artifact(shadow_path)
        sources = V4UnattendedControllerOfflineSources(
            reviewed_files_digest=reviewed,
            generation=generation,
            risk_policy=risk_policy,
            risk_state=PhaseBRiskStore(
                runtime_root / "risk.json",
                policy=risk_policy,
            ).load(),
            arm_check=V4UnattendedLiveArmStore(
                v4_unattended_live_arm_state_path(
                    generation_digest=generation.digest
                )
            ).check(
                expected_generation_digest=generation.digest,
                expected_reviewed_files_digest=reviewed,
            ),
            commissioning_artifact=commissioning,
            commissioning_shadow=shadow,
            predecessor_completion=bind_g018_predecessor_canary_completion(
                repository=repository
            ),
        )
        state_root = (
            repository
            / _STATE
            / f"generation-{generation.digest.removeprefix('sha256:')}"
        )
        phase = "DURABLE_STATE"
        decision = run_offline_tick_no_post(
            sources=sources,
            now_utc=datetime.now(UTC),
            database=state_root / "controller.sqlite3",
        )
        print(json.dumps(decision.to_safe_dict(), sort_keys=True))
        return 0
    except V4UnattendedControllerSnapshotNoPostError:
        print(json.dumps(_safe_failure("SNAPSHOT_BINDING"), sort_keys=True))
        return 2
    except Exception:
        print(json.dumps(_safe_failure(phase), sort_keys=True))
        return 2


def run_offline_tick_no_post(
    *,
    sources: V4UnattendedControllerOfflineSources,
    now_utc: datetime,
    database: Path,
):
    """Evaluate one local-only snapshot through the durable no-POST store."""

    snapshot = assemble_offline_controller_snapshot_no_post(
        sources=sources,
        now_utc=now_utc,
    )
    return V4IntegratedControllerStore(database).evaluate_and_record(snapshot)


def _current_artifact_paths(
    *,
    repository: Path,
    generation_label: str,
) -> tuple[Path, Path]:
    suffix = generation_label.rsplit("_", maxsplit=1)[-1]
    if (
        len(suffix) != 4
        or not suffix.startswith("G")
        or not suffix[1:].isdigit()
    ):
        raise ValueError("UNATTENDED_CONTROLLER_GENERATION_LABEL_INVALID")
    stem = f"h11_v4_{suffix.lower()}"
    templates = repository / "docs/templates"
    return (
        templates / f"{stem}_commissioning_no_post.json",
        templates / f"{stem}_shadow_evidence_no_post.json",
    )


def _safe_failure(phase: str) -> dict[str, object]:
    allowed = {
        "CLEAN_MAIN",
        "REVIEW_BOUNDARY",
        "LOCAL_EVIDENCE",
        "SNAPSHOT_BINDING",
        "DURABLE_STATE",
    }
    safe_phase = phase if phase in allowed else "UNKNOWN"
    return {
        "status": f"UNATTENDED_CONTROLLER_OFFLINE_{safe_phase}_REFUSED_SAFE",
        "persistent_arm_change_allowed": False,
        "permit_issued": False,
        "broker_post_authorized": False,
        "broker_write": False,
        "actual_post_count": 0,
        "credential_read": False,
        "private_api_read": False,
        "notification_send_count": 0,
    }


if __name__ == "__main__":
    raise SystemExit(main())
