#!/usr/bin/env python3
"""Seal local current-generation shadow evidence; no network or broker access."""

from __future__ import annotations

# ruff: noqa: E402 -- direct script execution needs the local backend bootstrap.
import json
import sys
from pathlib import Path

_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_ROOT_PATH))

from app.h11_auto.v4_actual_preparation_guard import require_clean_main
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_current_generation_shadow_observer_no_post import (
    V4CurrentGenerationShadowError,
    V4CurrentGenerationShadowStore,
    build_current_generation_commissioning_artifact,
    load_current_review_evidence,
    write_canonical_shadow_artifacts,
)
from app.services.h11_v4_unattended_commissioning_no_post import (
    bind_g018_predecessor_canary_completion,
    evaluate_commissioning,
)
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
        evidence = load_current_review_evidence(
            repository=repository,
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
            generation_label=generation.generation_label,
        )
        shadow = V4CurrentGenerationShadowStore(
            path=root / "shadow-ledger.json",
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
        ).load_evidence()
        predecessor = bind_g018_predecessor_canary_completion(repository=repository)
        commissioning = build_current_generation_commissioning_artifact(
            generation_label=generation.generation_label,
            reviewed_files_digest=reviewed,
            generation_digest=generation.digest,
            shadow=shadow,
            predecessor=predecessor,
            architecture_review_clear=evidence["architecture_review_clear"],
            safety_review_clear=evidence["safety_review_clear"],
            operations_review_clear=evidence["operations_review_clear"],
            review_evidence_digest=evidence["review_evidence_digest"],
        )
        decision = evaluate_commissioning(commissioning, shadow, predecessor)
        if decision.status.value != "SHADOW_COMMISSIONED_NO_POST":
            print(
                json.dumps(
                    _safe_result("CURRENT_GENERATION_SHADOW_COMMISSION_NOT_ELIGIBLE"),
                    sort_keys=True,
                )
            )
            return 2
        write_canonical_shadow_artifacts(
            repository=repository,
            directory=root,
            shadow=shadow,
            commissioning=commissioning,
            predecessor=predecessor,
        )
        print(json.dumps(_safe_result(decision.status.value), sort_keys=True))
        return 0 if decision.status.value == "SHADOW_COMMISSIONED_NO_POST" else 2
    except V4CurrentGenerationShadowError as error:
        status = str(error)
        if status in {
            "CURRENT_SHADOW_COMMISSION_ALREADY_SEALED",
            "CURRENT_SHADOW_SEAL_MARKER_UNAVAILABLE",
            "CURRENT_SHADOW_ARTIFACT_UNAVAILABLE",
            "CURRENT_SHADOW_ARTIFACT_WRITE_FAILED",
        }:
            status = (
                "CURRENT_GENERATION_SHADOW_COMMISSION_PERSISTENT_HALT_"
                "CORRECTIVE_GENERATION_REQUIRED"
            )
        print(json.dumps(_safe_result(status), sort_keys=True))
        return 2
    except Exception:
        print(
            json.dumps(
                _safe_result("CURRENT_GENERATION_SHADOW_COMMISSION_REFUSED_SAFE"),
                sort_keys=True,
            )
        )
        return 2


def _safe_result(status: str) -> dict[str, object]:
    return {
        "status": status,
        "persistent_arm_change_allowed": False,
        "broker_post_authorized": False,
        "broker_write": False,
        "actual_post_count": 0,
    }


if __name__ == "__main__":
    raise SystemExit(main())
