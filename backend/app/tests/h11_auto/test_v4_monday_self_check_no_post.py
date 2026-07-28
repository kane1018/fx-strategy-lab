"""Offline no-POST tests for the Monday readiness self-check."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest
from scripts import h11_auto_v4_monday_self_check as self_check


def test_local_check_command_set_contains_no_external_trading_entrypoint() -> None:
    commands = [*self_check.FOCUSED_TESTS, *self_check.RUFF_TARGETS]
    joined = " ".join(commands).lower()
    for forbidden in (
        "actual_canary",
        "private_get",
        "keychain",
        "pushover",
        "smtp",
        "broker",
        "transport",
        "order",
    ):
        assert forbidden not in joined


def test_generation_check_rejects_commissioned_flags(monkeypatch, tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    evidence_path = repository / self_check.EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        '{"status":"CORRECTIVE_GENERATION_PENDING_REVIEW_NO_BROKER_POST",'
        '"reviewed_files_digest":"sha256:' + "a" * 64 + '",'
        '"generation_digest":"sha256:' + "b" * 64 + '",'
        '"generation_manifest_digest":"sha256:' + "b" * 64 + '",'
        '"generation_label":"H11_AUTO_30M_20260728_G021",'
        '"actual_post_authorized":false,"broker_post_authorized":false,'
        '"activation_permit_issued":false,'
        '"architecture_review_clear":false,"safety_review_clear":false,'
        '"operations_review_clear":false}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        self_check,
        "compute_reviewed_files_digest",
        lambda **_kwargs: "sha256:" + "a" * 64,
    )
    monkeypatch.setattr(
        self_check,
        "load_v4_gmo_frozen_generation",
        lambda **_kwargs: SimpleNamespace(
            generation_label="H11_AUTO_30M_20260728_G021",
            maximum_entries_per_day=30,
            same_action_retry_allowed=False,
            same_action_repost_allowed=False,
            actual_post_authorized=True,
            live_ready=False,
            unattended_live_supported=False,
        ),
    )

    try:
        self_check._verify_generation(repository)
    except self_check.MondaySelfCheckError as error:
        assert str(error) == "SELF_CHECK_GENERATION_NOT_NO_POST"
    else:
        raise AssertionError("commissioned flags must be rejected")


def test_repository_frozen_generation_matches_current_reviewed_digest() -> None:
    repository = Path(__file__).resolve().parents[4]

    reviewed_digest = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )

    assert generation.generation_label == "H11_AUTO_30M_20260728_G021"
    assert generation.implementation_digest == reviewed_digest


def test_pending_review_generation_cannot_report_self_check_clear(
    monkeypatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    evidence_path = repository / self_check.EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        '{"status":"CORRECTIVE_GENERATION_PENDING_REVIEW_NO_BROKER_POST",'
        '"reviewed_files_digest":"sha256:' + "a" * 64 + '",'
        '"generation_digest":"sha256:' + "b" * 64 + '",'
        '"generation_manifest_digest":"sha256:' + "b" * 64 + '",'
        '"generation_label":"H11_AUTO_30M_20260728_G021",'
        '"actual_post_authorized":false,"broker_post_authorized":false,'
        '"activation_permit_issued":false,'
        '"architecture_review_clear":false,"safety_review_clear":false,'
        '"operations_review_clear":false,'
        '"danger_scan_passed":true,"diff_check_passed":true,'
        '"focused_tests_passed":true,"related_tests_passed":true,'
        '"ruff_passed":true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        self_check,
        "compute_reviewed_files_digest",
        lambda **_kwargs: "sha256:" + "a" * 64,
    )
    monkeypatch.setattr(
        self_check,
        "load_v4_gmo_frozen_generation",
        lambda **_kwargs: SimpleNamespace(
            generation_label="H11_AUTO_30M_20260728_G021",
            maximum_entries_per_day=30,
            same_action_retry_allowed=False,
            same_action_repost_allowed=False,
            actual_post_authorized=False,
            live_ready=False,
            unattended_live_supported=False,
            digest="sha256:" + "b" * 64,
        ),
    )

    try:
        self_check._verify_generation(repository)
    except self_check.MondaySelfCheckError as error:
        assert str(error) == "SELF_CHECK_REVIEW_PENDING"
    else:
        raise AssertionError("pending review must not report self-check clear")
