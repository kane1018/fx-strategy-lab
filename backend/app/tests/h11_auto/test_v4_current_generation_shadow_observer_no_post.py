import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services import h11_v4_current_generation_shadow_observer_no_post as subject
from app.services.h11_v4_current_generation_shadow_observer_no_post import (
    V4CurrentGenerationCompletedSlot,
    V4CurrentGenerationShadowError,
    V4CurrentGenerationShadowStatus,
    V4CurrentGenerationShadowStore,
    build_current_generation_commissioning_artifact,
    load_current_review_evidence,
    load_sealed_current_shadow_artifacts,
    write_canonical_shadow_artifacts,
)
from app.services.h11_v4_unattended_commissioning_no_post import (
    build_predecessor_canary_completion_artifact,
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _slot(minute: int) -> V4CurrentGenerationCompletedSlot:
    return V4CurrentGenerationCompletedSlot(
        datetime(2026, 7, 28, 1, minute, tzinfo=UTC), _digest(str(minute))
    )


def _store(tmp_path: Path) -> V4CurrentGenerationShadowStore:
    return V4CurrentGenerationShadowStore(
        path=tmp_path / "shadow-ledger.json",
        reviewed_files_digest=_digest("reviewed"),
        generation_digest=_digest("generation"),
    )


def _review_evidence(tmp_path: Path, shadow) -> str:
    generation_label = "H11_AUTO_30M_20260728_G023"
    attestation = {
        "schema": "H11_V4_INDEPENDENT_REVIEW_ATTESTATION_V1",
        "reviewed_files_digest": shadow.reviewed_files_digest,
        "generation_digest": shadow.generation_digest,
        "generation_label": generation_label,
        "architecture_status": "CLEAR",
        "safety_status": "CLEAR",
        "operations_status": "CLEAR",
    }
    attestation["artifact_digest"] = _digest(
        json.dumps(attestation, sort_keys=True, separators=(",", ":"))
    )
    payload = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "reviewed_files_digest": shadow.reviewed_files_digest,
        "generation_digest": shadow.generation_digest,
        "generation_manifest_digest": shadow.generation_digest,
        "generation_label": generation_label,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
        "diff_check_passed": True,
        "danger_scan_passed": True,
        "independent_review_attestation_digest": attestation["artifact_digest"],
    }
    path = tmp_path / "docs/templates/h11_v4_actual_preparation_evidence.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    (path.parent / "h11_v4_independent_review_attestation.json").write_text(
        json.dumps(attestation), encoding="utf-8"
    )
    return _digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def test_current_generation_shadow_rejects_tampered_review_attestation(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    shadow = store.load_evidence()
    _review_evidence(tmp_path, shadow)
    attestation_path = (
        tmp_path / "docs/templates/h11_v4_independent_review_attestation.json"
    )
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    attestation["artifact_digest"] = "sha256:" + "0" * 64
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

    try:
        load_current_review_evidence(
            repository=tmp_path,
            reviewed_files_digest=shadow.reviewed_files_digest,
            generation_digest=shadow.generation_digest,
            generation_label="H11_AUTO_30M_20260728_G023",
        )
    except V4CurrentGenerationShadowError as error:
        assert str(error) == "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
    else:
        raise AssertionError("tampered review attestation was accepted")


def test_current_generation_shadow_records_opaque_slots_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.observe_once(fetch_completed_slot=lambda: _slot(1))

    assert result.status is V4CurrentGenerationShadowStatus.RECORDED
    assert result.broker_write is False
    assert result.broker_post_count == 0
    assert result.credential_read is False
    assert result.private_api_read is False
    assert bool(result) is False
    serialized = (tmp_path / "shadow-ledger.json").read_text()
    assert "price" not in serialized
    assert "direction" not in serialized


def test_current_generation_shadow_rejects_duplicate_and_caps_at_twenty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.observe_once(fetch_completed_slot=lambda: _slot(1))
    duplicate = store.observe_once(fetch_completed_slot=lambda: _slot(1))
    assert first.status is V4CurrentGenerationShadowStatus.RECORDED
    assert duplicate.status is V4CurrentGenerationShadowStatus.ALREADY_OBSERVED
    for minute in range(2, 21):
        result = store.observe_once(
            fetch_completed_slot=lambda minute=minute: _slot(minute)
        )
        assert result.status is V4CurrentGenerationShadowStatus.RECORDED
    capped = store.observe_once(fetch_completed_slot=lambda: _slot(21))
    assert capped.status is V4CurrentGenerationShadowStatus.CAP_REACHED


def test_current_generation_shadow_failure_is_persisted_without_slot(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.observe_once(fetch_completed_slot=lambda: (_ for _ in ()).throw(RuntimeError()))

    assert (
        result.status
        is V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED
    )
    evidence = store.load_evidence()
    assert evidence.completed_slot_digests == ()
    assert evidence.abnormal_status_count == 1
    second = store.observe_once(
        fetch_completed_slot=lambda: (_ for _ in ()).throw(
            AssertionError("fetch must not run after persistent halt")
        )
    )
    assert (
        second.status
        is V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED
    )
    assert second.public_get_count == 0


def test_abnormal_ledger_write_failure_still_blocks_next_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    original_write = store._write
    monkeypatch.setattr(
        store,
        "_write",
        lambda *_: (_ for _ in ()).throw(
            V4CurrentGenerationShadowError("CURRENT_SHADOW_LEDGER_WRITE_FAILED")
        ),
    )
    first = store.observe_once(
        fetch_completed_slot=lambda: (_ for _ in ()).throw(RuntimeError())
    )
    assert (
        first.status
        is V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED
    )
    assert (tmp_path / "shadow-terminal-halt.json").is_file()

    monkeypatch.setattr(store, "_write", original_write)
    second = store.observe_once(
        fetch_completed_slot=lambda: (_ for _ in ()).throw(
            AssertionError("fetch must not run after terminal marker")
        )
    )
    assert (
        second.status
        is V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED
    )
    assert second.public_get_count == 0


def test_current_generation_shadow_seal_is_one_use_and_loadable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for minute in range(20):
        store.observe_once(fetch_completed_slot=lambda minute=minute: _slot(minute))
    shadow = store.load_evidence()
    predecessor = build_predecessor_canary_completion_artifact(
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest=(
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        coordinator_ledger_digest="sha256:" + "2" * 64,
        coordinator_cycle_count=1,
        market_entry_attempt_count=1,
        exact_size_oco_protection_attempt_count=1,
        entry_fill_recorded=True,
        protection_plan_recorded=True,
        protection_confirmed=True,
        reconciliation_runtime_generation_digest="sha256:" + "3" * 64,
        reconciliation_started_marker_digest="sha256:" + "4" * 64,
        reconciliation_passed_marker_digest="sha256:" + "5" * 64,
        reconciliation_origin_generation_digest=(
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        reconciliation_status="G013_POST_CANARY_FLAT_CONFIRMED",
        commissioning_eligible=False,
        reconciliation_result_known=True,
        subject_entry_observed=True,
        account_flat=True,
        active_orders_zero=True,
        broker_read_count=3,
        broker_write_attempt_count=0,
        raw_response_retained=False,
        identifier_exposed=False,
    )
    artifact = build_current_generation_commissioning_artifact(
        generation_label="H11_AUTO_30M_20260728_G023",
        reviewed_files_digest=shadow.reviewed_files_digest,
        generation_digest=shadow.generation_digest,
        shadow=shadow,
        predecessor=predecessor,
        architecture_review_clear=True,
        safety_review_clear=True,
        operations_review_clear=True,
        review_evidence_digest=_review_evidence(tmp_path, shadow),
    )
    directory = tmp_path / "sealed"
    write_canonical_shadow_artifacts(
        repository=tmp_path,
        directory=directory,
        shadow=shadow,
        commissioning=artifact,
        predecessor=predecessor,
    )
    assert load_sealed_current_shadow_artifacts(directory=directory) == (shadow, artifact)
    try:
        write_canonical_shadow_artifacts(
            repository=tmp_path,
            directory=directory,
            shadow=shadow,
            commissioning=artifact,
            predecessor=predecessor,
        )
    except Exception as error:
        assert "ALREADY_SEALED" in str(error)
    else:
        raise AssertionError("re-sealing was accepted")


@pytest.mark.parametrize("failure_mode", ("symlink", "write"))
def test_post_started_seal_failure_is_immediately_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    test_current_generation_shadow_seal_is_one_use_and_loadable(tmp_path)
    shadow, artifact = load_sealed_current_shadow_artifacts(
        directory=tmp_path / "sealed"
    )
    directory = tmp_path / f"failed-{failure_mode}"
    directory.mkdir()
    monkeypatch.setattr(subject, "load_current_review_evidence", lambda **_: {})

    class _Status:
        value = "SHADOW_COMMISSIONED_NO_POST"

    class _Decision:
        status = _Status()

    monkeypatch.setattr(subject, "evaluate_commissioning", lambda *_: _Decision())
    if failure_mode == "symlink":
        (directory / "shadow-evidence.json").symlink_to(tmp_path / "missing")
    else:
        monkeypatch.setattr(
            subject,
            "_atomic_json",
            lambda *_: (_ for _ in ()).throw(
                V4CurrentGenerationShadowError(
                    "CURRENT_SHADOW_ARTIFACT_WRITE_FAILED"
                )
            ),
        )

    with pytest.raises(
        V4CurrentGenerationShadowError,
        match=(
            "CURRENT_SHADOW_COMMISSION_PERSISTENT_HALT_"
            "CORRECTIVE_GENERATION_REQUIRED"
        ),
    ):
        write_canonical_shadow_artifacts(
            repository=tmp_path,
            directory=directory,
            shadow=shadow,
            commissioning=artifact,
            predecessor=object(),
        )
    assert (directory / "commissioning-seal.started.json").is_file()
    assert not (directory / "commissioning-seal.passed.json").exists()

    with pytest.raises(
        V4CurrentGenerationShadowError,
        match="CURRENT_SHADOW_COMMISSION_ALREADY_SEALED",
    ):
        write_canonical_shadow_artifacts(
            repository=tmp_path,
            directory=directory,
            shadow=shadow,
            commissioning=artifact,
            predecessor=object(),
        )


def test_current_generation_shadow_does_not_seal_ineligible_evidence(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    shadow = store.load_evidence()
    predecessor = build_predecessor_canary_completion_artifact(
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest=(
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        coordinator_ledger_digest="sha256:" + "2" * 64,
        coordinator_cycle_count=1,
        market_entry_attempt_count=1,
        exact_size_oco_protection_attempt_count=1,
        entry_fill_recorded=True,
        protection_plan_recorded=True,
        protection_confirmed=True,
        reconciliation_runtime_generation_digest="sha256:" + "3" * 64,
        reconciliation_started_marker_digest="sha256:" + "4" * 64,
        reconciliation_passed_marker_digest="sha256:" + "5" * 64,
        reconciliation_origin_generation_digest=(
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        reconciliation_status="G013_POST_CANARY_FLAT_CONFIRMED",
        commissioning_eligible=False,
        reconciliation_result_known=True,
        subject_entry_observed=True,
        account_flat=True,
        active_orders_zero=True,
        broker_read_count=3,
        broker_write_attempt_count=0,
        raw_response_retained=False,
        identifier_exposed=False,
    )
    artifact = build_current_generation_commissioning_artifact(
        generation_label="H11_AUTO_30M_20260728_G023",
        reviewed_files_digest=shadow.reviewed_files_digest,
        generation_digest=shadow.generation_digest,
        shadow=shadow,
        predecessor=predecessor,
        architecture_review_clear=True,
        safety_review_clear=True,
        operations_review_clear=True,
        review_evidence_digest=_review_evidence(tmp_path, shadow),
    )
    directory = tmp_path / "unsealed"
    try:
        write_canonical_shadow_artifacts(
            repository=tmp_path,
            directory=directory,
            shadow=shadow,
            commissioning=artifact,
            predecessor=predecessor,
        )
    except Exception as error:
        assert "NOT_ELIGIBLE" in str(error)
    else:
        raise AssertionError("ineligible evidence was sealed")
    assert not directory.exists() or not any(directory.iterdir())
