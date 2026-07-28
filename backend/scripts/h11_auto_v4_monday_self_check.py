"""Run offline Monday readiness checks for the current frozen v4 generation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest

EVIDENCE_PATH = Path("docs/templates/h11_v4_actual_preparation_evidence.json")
FOCUSED_TESTS = (
    "app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "app/tests/h11_auto/test_v4_unattended_live_scheduled_launcher_fake_only.py",
    "app/tests/h11_auto/test_runtime_safety_no_post.py",
    "app/tests/h11_auto/test_v4_monday_self_check_no_post.py",
    "app/tests/h11_auto/test_v4_gmo_g019_exit_policy_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_exit_and_commissioning_no_post.py",
    "app/tests/h11_auto/test_v4_g020_shadow_observer_no_post.py",
    "app/tests/h11_auto/test_h11_manual_auto_import_boundary_no_post.py",
    "app/tests/h11_auto/test_isolation_no_post.py",
)
RUFF_TARGETS = (
    "app/h11_auto/v4_gmo_g019_exit_policy.py",
    "app/services/h11_v4_unattended_exit_recovery_no_post.py",
    "app/services/h11_v4_unattended_commissioning_no_post.py",
    "app/services/h11_v4_g020_shadow_observer_no_post.py",
    "scripts/h11_auto_v4_g020_shadow_observer.py",
    "app/tests/h11_auto/test_v4_unattended_live_scheduled_launcher_fake_only.py",
    "app/tests/h11_auto/test_runtime_safety_no_post.py",
    "app/tests/h11_auto/test_v4_monday_self_check_no_post.py",
    "app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "app/tests/h11_auto/test_v4_gmo_g019_exit_policy_no_post.py",
    "app/tests/h11_auto/test_v4_unattended_exit_and_commissioning_no_post.py",
    "app/tests/h11_auto/test_h11_manual_auto_import_boundary_no_post.py",
    "scripts/h11_auto_v4_monday_self_check.py",
    "h11_v4_reviewed_digest.py",
)
DANGER_SCAN_TARGETS = (
    "app/h11_auto/v4_gmo_g019_exit_policy.py",
    "app/services/h11_v4_unattended_exit_recovery_no_post.py",
    "app/services/h11_v4_unattended_commissioning_no_post.py",
    "app/services/h11_v4_g020_shadow_observer_no_post.py",
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


class MondaySelfCheckError(RuntimeError):
    """Safe failure for an offline readiness check."""


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
    if generation.generation_label != "H11_AUTO_30M_20260728_G021":
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
    expected = {
        "status": "CORRECTIVE_GENERATION_PENDING_REVIEW_NO_BROKER_POST",
        "reviewed_files_digest": reviewed_digest,
        "generation_digest": generation.digest,
        "generation_manifest_digest": generation.digest,
        "generation_label": generation.generation_label,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "architecture_review_clear": False,
        "safety_review_clear": False,
        "operations_review_clear": False,
        "danger_scan_passed": True,
        "diff_check_passed": True,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise MondaySelfCheckError("SELF_CHECK_EVIDENCE_MISMATCH")
    raise MondaySelfCheckError("SELF_CHECK_REVIEW_PENDING")


def _run_local_checks(repository: Path) -> None:
    backend = repository / "backend"
    for relative_path in DANGER_SCAN_TARGETS:
        try:
            source = (backend / relative_path).read_text(encoding="utf-8")
        except OSError as error:
            raise MondaySelfCheckError("SELF_CHECK_DANGER_SCAN_FAILED") from error
        if any(token in source for token in DANGER_SCAN_TOKENS):
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
