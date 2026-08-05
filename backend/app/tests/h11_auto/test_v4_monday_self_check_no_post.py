"""Offline no-POST tests for the Monday readiness self-check."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.services.h11_v4_g076_runtime import (
    G076_GENERATION_LABEL,
    compute_g076_reviewed_files_digest,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest
from scripts import h11_auto_v4_monday_self_check as self_check


def test_local_check_command_set_contains_no_external_trading_entrypoint() -> None:
    commands = [
        *self_check.FOCUSED_TESTS,
        *self_check.RELATED_TESTS,
        *self_check.RUFF_TARGETS,
    ]
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
        '"generation_label":"H11_AUTO_30M_20260728_G022",'
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
            generation_label="H11_AUTO_30M_20260728_G022",
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

    # The canonical template binds to the G076-specific reviewed digest when
    # the canonical generation is G076 (mirrors _load_current_contract in the
    # manual UI); the shared digest nulls a different artifact set.
    canonical_payload = json.loads(
        (
            repository / "docs/templates/h11_v4_gmo_frozen_generation.json"
        ).read_text(encoding="utf-8")
    )
    reviewed_digest = (
        compute_g076_reviewed_files_digest(repository=repository)
        if canonical_payload.get("generation_label") == G076_GENERATION_LABEL
        else compute_reviewed_files_digest(repository=repository)
    )
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )

    assert self_check._GENERATION_LABEL.fullmatch(generation.generation_label)
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
        '"generation_label":"H11_AUTO_30M_20260728_G022",'
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
            generation_label="H11_AUTO_30M_20260728_G022",
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


def test_clear_generation_requires_canonical_review_attestation(
    monkeypatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    reviewed = "sha256:" + "a" * 64
    generation_digest = "sha256:" + "b" * 64
    generation_label = "H11_AUTO_30M_20260728_G099"
    generation = SimpleNamespace(
        generation_label=generation_label,
        maximum_entries_per_day=30,
        same_action_retry_allowed=False,
        same_action_repost_allowed=False,
        actual_post_authorized=False,
        live_ready=False,
        unattended_live_supported=False,
        digest=generation_digest,
    )
    attestation = {
        "schema": "H11_V4_INDEPENDENT_REVIEW_ATTESTATION_V1",
        "reviewed_files_digest": reviewed,
        "generation_digest": generation_digest,
        "generation_label": generation_label,
        "architecture_status": "CLEAR",
        "safety_status": "CLEAR",
        "operations_status": "CLEAR",
    }
    attestation["artifact_digest"] = self_check._canonical_artifact_digest(
        attestation
    )
    evidence = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "reviewed_files_digest": reviewed,
        "generation_digest": generation_digest,
        "generation_manifest_digest": generation_digest,
        "generation_label": generation_label,
        "independent_review_attestation_digest": attestation["artifact_digest"],
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
    evidence_path = repository / self_check.EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    attestation_path = repository / self_check.REVIEW_ATTESTATION_PATH
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    monkeypatch.setattr(
        self_check,
        "compute_reviewed_files_digest",
        lambda **_kwargs: reviewed,
    )
    monkeypatch.setattr(
        self_check,
        "load_v4_gmo_frozen_generation",
        lambda **_kwargs: generation,
    )

    assert self_check._verify_generation(repository) == (reviewed, generation)

    attestation["architecture_status"] = "VETO"
    attestation["artifact_digest"] = self_check._canonical_artifact_digest(
        attestation
    )
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    try:
        self_check._verify_generation(repository)
    except self_check.MondaySelfCheckError as error:
        assert str(error) == "SELF_CHECK_REVIEW_ATTESTATION_MISMATCH"
    else:
        raise AssertionError("VETO attestation must be rejected")
