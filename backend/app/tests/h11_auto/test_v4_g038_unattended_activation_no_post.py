from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.services import h11_v4_g038_unattended_activation as subject
from app.services.h11_v4_g038_unattended_activation import (
    G038_RELEASE_SCHEMA,
    V4G038ActivationError,
    V4G038SuccessorRelease,
    verify_g038_generation_activation,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_g038_release_path,
)


def _generation(*, reviewed: str, release: V4G038SuccessorRelease) -> V4GmoFrozenGeneration:
    return cast(
        V4GmoFrozenGeneration,
        SimpleNamespace(
            status="UNATTENDED_LIVE_COMMISSIONED",
            digest="sha256:" + "e" * 64,
            live_ready=True,
            unattended_live_supported=True,
            actual_post_authorized=False,
            activation_source_generation_digest=release.source_generation_digest,
            successful_canary_evidence_digest=release.successful_canary_evidence_digest,
            successor_halt_release_digest=release.digest,
            implementation_digest=reviewed,
            generation_label=release.target_generation_label,
        ),
    )


def test_release_is_false_no_post_and_generation_bound(tmp_path: Path) -> None:
    reviewed = "sha256:" + "a" * 64
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest="sha256:" + "b" * 64,
        predecessor_halt_generation_digest="sha256:" + "f" * 64,
        source_reviewed_files_digest="sha256:" + "c" * 64,
        target_reviewed_files_digest=reviewed,
        target_generation_label="H11_AUTO_30M_20260729_G038",
        successful_canary_evidence_digest="sha256:" + "d" * 64,
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    path = v4_unattended_g038_release_path(
        state_root=tmp_path,
        target_reviewed_files_digest=reviewed,
    )
    path.parent.mkdir(parents=True)
    path.write_text(release.canonical_json + "\n", encoding="utf-8")
    assert verify_g038_generation_activation(
        generation=_generation(reviewed=reviewed, release=release),
        state_root=tmp_path,
    ) == release
    assert release.broker_post_count == 0
    assert bool(release) is False


def test_missing_or_wrong_release_refuses(tmp_path: Path) -> None:
    reviewed = "sha256:" + "a" * 64
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest="sha256:" + "b" * 64,
        predecessor_halt_generation_digest="sha256:" + "f" * 64,
        source_reviewed_files_digest="sha256:" + "c" * 64,
        target_reviewed_files_digest=reviewed,
        target_generation_label="H11_AUTO_30M_20260729_G038",
        successful_canary_evidence_digest="sha256:" + "d" * 64,
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    with pytest.raises(V4G038ActivationError):
        verify_g038_generation_activation(
            generation=_generation(reviewed=reviewed, release=release),
            state_root=tmp_path,
        )


def test_record_authenticates_g037_digest_and_is_exactly_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "sha256:" + "b" * 64
    source_reviewed = "sha256:" + "c" * 64
    target_reviewed = "sha256:" + "a" * 64
    evidence = {
        "schema": "H11_V4_G037_SUCCESSFUL_CANARY_EVIDENCE_NO_POST_V1",
        "origin_reviewed_files_digest": "sha256:" + "1" * 64,
        "origin_generation_digest": "sha256:" + "2" * 64,
        "target_reviewed_files_digest": source_reviewed,
        "target_generation_digest": source,
        "cycle_count": 1,
        "flat_cycle_count": 1,
        "protected_cycle_count": 1,
        "unresolved_cycle_count": 0,
        "entry_attempt_count": 1,
        "protection_attempt_count": 1,
        "risk_reducing_attempt_count": 2,
        "permit_marker_count": 1,
        "runtime_binding_marker_count": 1,
        "generation_consumed_marker_count": 1,
        "post_flat_halt_classification": "TERMINAL_FLAT_RECONCILED_HALT_LATCHED",
        "successful_canary_fixed": True,
        "post_flat_halt_blocks_activation": True,
        "broker_write": False,
        "broker_post_count": 0,
        "credential_read": False,
        "private_api_read": False,
        "permit_issued": False,
        "broker_post_authorized": False,
    }
    evidence["evidence_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    evidence_path = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "g037-successful-canary-evidence-no-post.json"
    )
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(subject, "require_clean_main", lambda **_kw: None)
    monkeypatch.setattr(
        subject, "reviewed_files_digest", lambda **_kw: target_reviewed
    )
    kwargs = {
        "repository": tmp_path,
        "state_root": tmp_path,
        "source_generation_digest": source,
        "source_reviewed_files_digest": source_reviewed,
        "target_reviewed_files_digest": target_reviewed,
        "target_generation_label": "H11_AUTO_30M_20260729_G038",
    }
    first = subject.record_g038_successor_release_once(**kwargs)
    second = subject.record_g038_successor_release_once(**kwargs)
    assert first == second
    assert first.predecessor_halt_generation_digest == "sha256:" + "2" * 64


def test_g053_release_requires_exact_falsey_flat_carry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FlatEvidence(SimpleNamespace):
        def __bool__(self) -> bool:
            return False

    reviewed = "sha256:" + "a" * 64
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest=subject._G052_GENERATION_DIGEST,
        predecessor_halt_generation_digest=subject._G052_GENERATION_DIGEST,
        source_reviewed_files_digest=subject._G052_REVIEWED_FILES_DIGEST,
        target_reviewed_files_digest=reviewed,
        target_generation_label=subject._G053_GENERATION_LABEL,
        successful_canary_evidence_digest="sha256:" + "d" * 64,
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    generation = SimpleNamespace(
        generation_label=subject._G053_GENERATION_LABEL,
        activation_source_generation_digest=subject._G052_GENERATION_DIGEST,
        successful_canary_evidence_digest=release.successful_canary_evidence_digest,
        successor_halt_release_digest=release.digest,
        digest="sha256:" + "e" * 64,
    )
    flat = FlatEvidence(
        source_generation_digest=subject._G052_GENERATION_DIGEST,
        source_reviewed_files_digest=subject._G052_REVIEWED_FILES_DIGEST,
        account_flat=True,
        active_orders_zero=True,
        source_halt_remains_latched=True,
        broker_post_authorized=False,
        activation_permit_issued=False,
    )
    monkeypatch.setattr(subject, "require_clean_main", lambda **_kw: None)
    monkeypatch.setattr(subject, "reviewed_files_digest", lambda **_kw: reviewed)
    monkeypatch.setattr(
        subject, "load_v4_gmo_frozen_generation", lambda **_kw: generation
    )
    monkeypatch.setattr(
        subject, "load_external_preparation_gate", lambda **_kw: object()
    )
    monkeypatch.setattr(
        subject,
        "load_g053_flat_only_carry_forward_evidence",
        lambda **_kw: flat,
    )
    recorded = subject.record_g053_flat_only_successor_release_once(
        repository=tmp_path,
        state_root=tmp_path,
    )
    assert recorded == release
    assert recorded.broker_post_count == 0
    assert bool(recorded) is False


def test_g055_release_uses_distinct_target_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subject,
        "_record_manual_flat_successor_release_once",
        lambda **kwargs: kwargs["target_generation_label"],
    )
    assert (
        subject.record_g055_manual_flat_successor_release_once(
            repository=tmp_path,
            state_root=tmp_path,
        )
        == subject._G055_GENERATION_LABEL
    )


def test_g056_release_uses_distinct_target_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subject,
        "_record_manual_flat_successor_release_once",
        lambda **kwargs: kwargs["target_generation_label"],
    )
    assert (
        subject.record_g056_manual_flat_successor_release_once(
            repository=tmp_path,
            state_root=tmp_path,
        )
        == subject._G056_GENERATION_LABEL
    )


def test_g056_release_started_marker_is_one_use(
    tmp_path: Path,
) -> None:
    reviewed = "sha256:" + "a" * 64
    generation = cast(
        V4GmoFrozenGeneration,
        SimpleNamespace(
            digest="sha256:" + "b" * 64,
            generation_label=subject._G056_GENERATION_LABEL,
        ),
    )
    subject._claim_g056_release_operation_once(
        state_root=tmp_path,
        target_reviewed=reviewed,
        generation=generation,
    )
    with pytest.raises(
        V4G038ActivationError,
        match="G056_RELEASE_ALREADY_STARTED_NO_RETRY",
    ):
        subject._claim_g056_release_operation_once(
            state_root=tmp_path,
            target_reviewed=reviewed,
            generation=generation,
        )


def test_g054_release_requires_fresh_flat_snapshot_and_g053_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Snapshot(SimpleNamespace):
        def __bool__(self) -> bool:
            return False

    reviewed = "sha256:" + "a" * 64
    release = V4G038SuccessorRelease(
        schema=G038_RELEASE_SCHEMA,
        source_generation_digest=subject._G053_GENERATION_DIGEST,
        predecessor_halt_generation_digest=subject._G053_GENERATION_DIGEST,
        source_reviewed_files_digest=subject._G053_REVIEWED_FILES_DIGEST,
        target_reviewed_files_digest=reviewed,
        target_generation_label=subject._G054_GENERATION_LABEL,
        successful_canary_evidence_digest="sha256:" + "d" * 64,
        source_halt_remains_latched=True,
        successor_activation_released=True,
    )
    generation = SimpleNamespace(
        generation_label=subject._G054_GENERATION_LABEL,
        activation_source_generation_digest=subject._G053_GENERATION_DIGEST,
        successful_canary_evidence_digest=release.successful_canary_evidence_digest,
        successor_halt_release_digest=release.digest,
        digest="sha256:" + "e" * 64,
    )
    snapshot = Snapshot(
        account_flat=True,
        active_orders_zero=True,
        broker_get_count=3,
        broker_write=False,
        broker_post_count=0,
        raw_response_retained=False,
        identifier_exposed=False,
    )
    monkeypatch.setattr(subject, "require_clean_main", lambda **_kw: None)
    monkeypatch.setattr(subject, "reviewed_files_digest", lambda **_kw: reviewed)
    monkeypatch.setattr(
        subject, "load_v4_gmo_frozen_generation", lambda **_kw: generation
    )
    monkeypatch.setattr(
        subject.V4AccountSnapshotStoreNoPost,
        "load_completed",
        lambda self, **_kw: snapshot,
    )
    monkeypatch.setattr(
        subject,
        "validate_bound_account_snapshot_evidence_no_post",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        subject,
        "controller_cycle_binding_no_post",
        lambda **_kw: "sha256:" + "f" * 64,
    )
    monkeypatch.setattr(
        subject, "_require_g053_halted_protected_cycle", lambda **_kw: None
    )
    recorded = subject.record_g054_manual_flat_successor_release_once(
        repository=tmp_path,
        state_root=tmp_path,
    )
    assert recorded == release
    assert recorded.broker_post_count == 0
    assert bool(recorded) is False
