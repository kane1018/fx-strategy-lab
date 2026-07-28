"""Offline no-POST tests for the Monday readiness self-check."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
        '{"status":"REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",'
        '"reviewed_files_digest":"sha256:' + "a" * 64 + '",'
        '"generation_digest":"sha256:' + "b" * 64 + '",'
        '"generation_manifest_digest":"sha256:' + "b" * 64 + '",'
        '"generation_label":"H11_AUTO_30M_20260728_G019",'
        '"actual_post_authorized":false,"broker_post_authorized":false,'
        '"activation_permit_issued":false,'
        '"architecture_review_clear":true,"safety_review_clear":true,'
        '"operations_review_clear":true}',
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
            generation_label="H11_AUTO_30M_20260728_G019",
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
