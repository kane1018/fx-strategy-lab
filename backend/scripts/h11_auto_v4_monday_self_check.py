"""Run offline Monday readiness checks for the current frozen v4 generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest

EVIDENCE_PATH = Path("docs/templates/h11_v4_actual_preparation_evidence.json")
REVIEW_ATTESTATION_PATH = Path(
    "docs/templates/h11_v4_independent_review_attestation.json"
)
FOCUSED_TESTS = (
    "app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "app/tests/h11_auto/test_v4_unattended_live_scheduled_launcher_fake_only.py",
    "app/tests/h11_auto/test_runtime_safety_no_post.py",
    "app/tests/h11_auto/test_v4_monday_self_check_no_post.py",
    "app/tests/h11_auto/test_v4_gmo_g019_exit_policy_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_exit_and_commissioning_no_post.py",
    "app/tests/h11_auto/test_v4_g020_shadow_observer_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_integrated_controller_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_controller_snapshot_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_controller_no_post_tick.py",
    "app/tests/h11_auto/test_v4_unattended_account_snapshot_producer_no_post.py",
    "app/tests/h11_auto/test_h11_manual_auto_import_boundary_no_post.py",
    "app/tests/h11_auto/test_isolation_no_post.py",
)
RELATED_TESTS = (
    "app/tests/h11_auto/test_v4_actual_preparation_fake_first.py",
    "app/tests/h11_auto/test_v4_gmo_launchagent_runner_no_post.py",
)
RUFF_TARGETS = (
    "app/h11_auto/v4_gmo_g019_exit_policy.py",
    "app/services/h11_v4_unattended_exit_recovery_no_post.py",
    "app/services/h11_v4_unattended_commissioning_no_post.py",
    "app/services/h11_v4_g020_shadow_observer_no_post.py",
    "app/services/h11_v4_unattended_integrated_controller_no_post.py",
    "app/services/h11_v4_unattended_controller_snapshot_no_post.py",
    "app/services/h11_v4_unattended_account_snapshot_store_no_post.py",
    "app/services/h11_v4_unattended_account_snapshot_producer_no_post.py",
    "app/services/h11_v4_g026_private_get_keychain.py",
    "scripts/h11_auto_v4_unattended_controller_no_post_tick.py",
    "scripts/h11_auto_v4_g026_private_snapshot_producer.py",
    "scripts/h11_auto_v4_g020_shadow_observer.py",
    "app/tests/h11_auto/test_v4_unattended_live_scheduled_launcher_fake_only.py",
    "app/tests/h11_auto/test_runtime_safety_no_post.py",
    "app/tests/h11_auto/test_v4_monday_self_check_no_post.py",
    "app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "app/tests/h11_auto/test_v4_gmo_g019_exit_policy_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_exit_and_commissioning_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_integrated_controller_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_controller_snapshot_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_controller_no_post_tick.py",
    "app/tests/h11_auto/test_h11_manual_auto_import_boundary_no_post.py",
    "scripts/h11_auto_v4_monday_self_check.py",
    "h11_v4_reviewed_digest.py",
)
DANGER_SCAN_TARGETS = (
    "app/h11_auto/v4_gmo_g019_exit_policy.py",
    "app/services/h11_v4_unattended_exit_recovery_no_post.py",
    "app/services/h11_v4_unattended_commissioning_no_post.py",
    "app/services/h11_v4_g020_shadow_observer_no_post.py",
    "app/services/h11_v4_current_generation_shadow_observer_no_post.py",
    "app/services/h11_v4_unattended_integrated_controller_no_post.py",
    "app/services/h11_v4_unattended_controller_snapshot_no_post.py",
    "scripts/h11_auto_v4_current_generation_shadow_observer.py",
    "scripts/h11_auto_v4_current_generation_shadow_commission.py",
    "scripts/h11_auto_v4_unattended_controller_no_post_tick.py",
)
DANGER_SCAN_TOKENS = (
    "import httpx",
    "import requests",
    "keychain",
    "assert_real_broker_post_allowed",
    "allow=True",
    ".post(",
    "closeOrder",
    "cancelOrders",
)
PRIVATE_GET_DANGER_SCAN_TARGETS = (
    "app/services/h11_v4_unattended_account_snapshot_producer_no_post.py",
    "scripts/h11_auto_v4_g026_private_snapshot_producer.py",
)
PRIVATE_GET_DANGER_SCAN_TOKENS = (
    ".post(",
    '"POST"',
    "closeOrder",
    "cancelOrders",
    "changeOrder",
    "assert_real_broker_post_allowed",
    "ActualPushover",
    "ActualEmail",
    "set_desired_state",
    "install_unattended",
)


class MondaySelfCheckError(RuntimeError):
    """Safe failure for an offline readiness check."""


_GENERATION_LABEL = re.compile(r"^H11_AUTO_30M_[0-9]{8}_G[0-9]{3}$")


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise MondaySelfCheckError(label)


def _git_value(repository: Path, *arguments: str) -> str:
    result = _run(["git", *arguments], cwd=repository)
    _require_success(result, "SELF_CHECK_GIT_QUERY_FAILED")
    return result.stdout.strip()


def _verify_repository_gate(repository: Path) -> None:
    if _git_value(repository, "branch", "--show-current") != "main":
        raise MondaySelfCheckError("SELF_CHECK_BRANCH_NOT_MAIN")
    if _git_value(repository, "status", "--porcelain"):
        raise MondaySelfCheckError("SELF_CHECK_WORKTREE_NOT_CLEAN")
    if _git_value(repository, "rev-parse", "HEAD") != _git_value(
        repository, "rev-parse", "origin/main"
    ):
        raise MondaySelfCheckError("SELF_CHECK_HEAD_ORIGIN_MISMATCH")


def _verify_generation(repository: Path) -> tuple[str, Any]:
    reviewed_digest = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )
    if _GENERATION_LABEL.fullmatch(generation.generation_label) is None:
        raise MondaySelfCheckError("SELF_CHECK_GENERATION_LABEL_MISMATCH")
    if generation.maximum_entries_per_day != 30:
        raise MondaySelfCheckError("SELF_CHECK_ENTRY_CAP_MISMATCH")
    if generation.same_action_retry_allowed or generation.same_action_repost_allowed:
        raise MondaySelfCheckError("SELF_CHECK_RETRY_POLICY_MISMATCH")
    if (
        generation.actual_post_authorized
        or generation.live_ready
        or generation.unattended_live_supported
    ):
        raise MondaySelfCheckError("SELF_CHECK_GENERATION_NOT_NO_POST")

    evidence_path = repository / EVIDENCE_PATH
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MondaySelfCheckError("SELF_CHECK_EVIDENCE_INVALID") from error
    review_fields = (
        "architecture_review_clear",
        "safety_review_clear",
        "operations_review_clear",
    )
    if (
        evidence.get("status")
        == "CORRECTIVE_GENERATION_PENDING_REVIEW_NO_BROKER_POST"
        or any(evidence.get(field) is not True for field in review_fields)
    ):
        raise MondaySelfCheckError("SELF_CHECK_REVIEW_PENDING")
    expected = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "reviewed_files_digest": reviewed_digest,
        "generation_digest": generation.digest,
        "generation_manifest_digest": generation.digest,
        "generation_label": generation.generation_label,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
        "danger_scan_passed": True,
        "diff_check_passed": True,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise MondaySelfCheckError("SELF_CHECK_EVIDENCE_MISMATCH")
    try:
        attestation = json.loads(
            (repository / REVIEW_ATTESTATION_PATH).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise MondaySelfCheckError("SELF_CHECK_REVIEW_ATTESTATION_INVALID") from error
    if (
        not isinstance(attestation, dict)
        or attestation.get("schema")
        != "H11_V4_INDEPENDENT_REVIEW_ATTESTATION_V1"
        or attestation.get("reviewed_files_digest") != reviewed_digest
        or attestation.get("generation_digest") != generation.digest
        or attestation.get("generation_label") != generation.generation_label
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or attestation.get("artifact_digest")
        != _canonical_artifact_digest(attestation)
        or evidence.get("independent_review_attestation_digest")
        != attestation.get("artifact_digest")
    ):
        raise MondaySelfCheckError("SELF_CHECK_REVIEW_ATTESTATION_MISMATCH")
    return reviewed_digest, generation


def _canonical_artifact_digest(payload: dict[str, Any]) -> str:
    canonical = {
        key: value for key, value in payload.items() if key != "artifact_digest"
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _run_local_checks(repository: Path) -> None:
    backend = repository / "backend"
    for relative_path in DANGER_SCAN_TARGETS:
        try:
            source = (backend / relative_path).read_text(encoding="utf-8")
        except OSError as error:
            raise MondaySelfCheckError("SELF_CHECK_DANGER_SCAN_FAILED") from error
        if any(token in source for token in DANGER_SCAN_TOKENS):
            raise MondaySelfCheckError("SELF_CHECK_DANGER_SCAN_FAILED")
    for relative_path in PRIVATE_GET_DANGER_SCAN_TARGETS:
        try:
            source = (backend / relative_path).read_text(encoding="utf-8")
        except OSError as error:
            raise MondaySelfCheckError("SELF_CHECK_DANGER_SCAN_FAILED") from error
        if any(token in source for token in PRIVATE_GET_DANGER_SCAN_TOKENS):
            raise MondaySelfCheckError("SELF_CHECK_DANGER_SCAN_FAILED")
    _require_success(
        _run(["git", "diff", "--check"], cwd=repository),
        "SELF_CHECK_DIFF_CHECK_FAILED",
    )
    _require_success(
        _run([sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS], cwd=backend),
        "SELF_CHECK_FOCUSED_TESTS_FAILED",
    )
    _require_success(
        _run([sys.executable, "-m", "pytest", "-q", *RELATED_TESTS], cwd=backend),
        "SELF_CHECK_RELATED_TESTS_FAILED",
    )
    _require_success(
        _run([sys.executable, "-m", "ruff", "check", *RUFF_TARGETS], cwd=backend),
        "SELF_CHECK_RUFF_FAILED",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    repository = args.repository.resolve()
    try:
        _verify_repository_gate(repository)
        reviewed_digest, generation = _verify_generation(repository)
        _run_local_checks(repository)
    except MondaySelfCheckError as error:
        print(
            f"status={error} broker_post_count=0 "
            "actual_post_authorized=false live_ready=false "
            "unattended_live_supported=false"
        )
        return 2
    print(
        "status=MONDAY_OFFLINE_SELF_CHECK_CLEAR "
        f"generation={generation.generation_label} "
        f"reviewed_files_digest={reviewed_digest} "
        f"generation_digest={generation.digest} "
        "broker_post_count=0 actual_post_authorized=false "
        "live_ready=false unattended_live_supported=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
