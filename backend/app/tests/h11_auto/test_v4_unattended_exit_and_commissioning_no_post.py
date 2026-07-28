import hashlib
import json
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.h11_v4_unattended_commissioning_no_post import (
    G020_COMMISSIONING_SCHEMA,
    G020_SHADOW_EVIDENCE_SCHEMA,
    V4CommissioningArtifact,
    V4CommissioningStatus,
    V4PredecessorCanaryCompletionArtifact,
    V4PredecessorCanaryCompletionError,
    V4ShadowEvidenceArtifact,
    bind_g018_predecessor_canary_completion,
    build_commissioning_artifact,
    build_predecessor_canary_completion_artifact,
    build_shadow_evidence_artifact,
    evaluate_commissioning,
    load_commissioning_artifact,
    load_predecessor_canary_completion_artifact,
    load_shadow_evidence_artifact,
)
from app.services.h11_v4_unattended_exit_recovery_no_post import (
    V4ExitRecoverySnapshot,
    V4ExitRecoveryStatus,
    evaluate_exit_recovery,
)


def _recovery_snapshot(
    **overrides: bool | datetime | str,
) -> V4ExitRecoverySnapshot:
    values = {
        "reviewed_files_digest_matches": True,
        "generation_digest_matches": True,
        "cycle_binding_digest": "sha256:" + ("c" * 64),
        "expected_cycle_binding_digest": "sha256:" + ("c" * 64),
        "exact_protection_confirmed": True,
        "flat_reconciled": False,
        "transport_action_pending": False,
        "result_unknown": False,
        "persistent_operator_halt": False,
        "process_lock_available": True,
        "scheduled_exit_at_utc": datetime(2026, 7, 28, 1, 30, tzinfo=UTC),
        "previous_observed_at_utc": datetime(
            2026, 7, 28, 1, 28, 30, tzinfo=UTC
        ),
        "observed_at_utc": datetime(2026, 7, 28, 1, 29, tzinfo=UTC),
        "time_exit_marker_claimed": False,
    }
    values.update(overrides)
    return V4ExitRecoverySnapshot(**values)


def _shadow_artifact(
    **overrides: bool | int | str | tuple[str, ...],
) -> V4ShadowEvidenceArtifact:
    values: dict[str, bool | int | str | tuple[str, ...]] = {
        "reviewed_files_digest": "sha256:" + ("a" * 64),
        "generation_digest": "sha256:" + ("b" * 64),
        "completed_slot_digests": tuple(
            f"sha256:{index:064x}" for index in range(1, 21)
        ),
        "abnormal_status_count": 0,
        "broker_write": False,
        "actual_post_count": 0,
    }
    values.update(overrides)
    return build_shadow_evidence_artifact(**values)


def _commissioning_artifact(
    shadow: V4ShadowEvidenceArtifact | None = None,
    **overrides: bool | int | str,
) -> V4CommissioningArtifact:
    shadow = shadow or _shadow_artifact()
    values: dict[str, bool | int | str] = {
        "generation_label": "H11_AUTO_30M_20260728_G019",
        "prior_canary_generation_label": "H11_AUTO_30M_20260727_G018",
        "prior_canary_generation_digest": "sha256:" + ("e" * 64),
        "prior_canary_reconciliation_artifact_digest": "sha256:"
        + ("f" * 64),
        "prior_canary_handoff_digest": "sha256:" + ("1" * 64),
        "commissioning_entry_disabled": True,
        "reviewed_files_digest": "sha256:" + ("a" * 64),
        "generation_digest": "sha256:" + ("b" * 64),
        "shadow_evidence_digest": shadow.artifact_digest,
        "shadow_reviewed_files_digest": shadow.reviewed_files_digest,
        "shadow_generation_digest": shadow.generation_digest,
        "prior_canary_cycle_complete": True,
        "prior_canary_flat_reconciled": True,
        "account_wide_active_orders_zero_evidence": True,
        "shadow_scheduler_cycles_clear": 20,
        "restart_safe_exit_contract_clear": True,
        "notification_contract_clear": True,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
    }
    values.update(overrides)
    return build_commissioning_artifact(**values)


def _predecessor_completion_artifact(
    **overrides: bool | int | str,
) -> V4PredecessorCanaryCompletionArtifact:
    values: dict[str, bool | int | str] = {
        "prior_canary_generation_label": "H11_AUTO_30M_20260727_G018",
        "prior_canary_generation_digest": (
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        "coordinator_ledger_digest": "sha256:" + ("a" * 64),
        "coordinator_cycle_count": 1,
        "market_entry_attempt_count": 1,
        "exact_size_oco_protection_attempt_count": 1,
        "entry_fill_recorded": True,
        "protection_plan_recorded": True,
        "protection_confirmed": True,
        "reconciliation_runtime_generation_digest": "sha256:" + ("b" * 64),
        "reconciliation_started_marker_digest": "sha256:" + ("c" * 64),
        "reconciliation_passed_marker_digest": "sha256:" + ("d" * 64),
        "reconciliation_origin_generation_digest": (
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        "reconciliation_status": "G013_POST_CANARY_FLAT_CONFIRMED",
        "commissioning_eligible": False,
        "reconciliation_result_known": True,
        "subject_entry_observed": True,
        "account_flat": True,
        "active_orders_zero": True,
        "broker_read_count": 3,
        "broker_write_attempt_count": 0,
        "raw_response_retained": False,
        "identifier_exposed": False,
    }
    values.update(overrides)
    return build_predecessor_canary_completion_artifact(**values)


def test_recovery_tick_is_local_only_and_not_truthy() -> None:
    decision = evaluate_exit_recovery(_recovery_snapshot())

    assert decision.status is V4ExitRecoveryStatus.MONITOR_TICK_SAFE_NO_WRITE
    assert decision.monitor_tick_allowed is True
    assert decision.broker_post_authorized is False
    assert decision.broker_write is False
    assert decision.actual_post_count == 0
    assert bool(decision) is False


def test_recovery_marker_requires_separate_exit_scope_but_grants_none() -> None:
    decision = evaluate_exit_recovery(
        _recovery_snapshot(
            previous_observed_at_utc=datetime(
                2026, 7, 28, 1, 29, 30, tzinfo=UTC
            ),
            observed_at_utc=datetime(2026, 7, 28, 1, 30, tzinfo=UTC),
        )
    )

    assert decision.status is V4ExitRecoveryStatus.EXIT_SCOPE_REQUIRED_NO_WRITE
    assert decision.exit_scope_required is True
    assert decision.broker_post_authorized is False


def test_recovery_refuses_unknown_pending_halt_or_claimed_state() -> None:
    for overrides in (
        {"result_unknown": True},
        {"transport_action_pending": True},
        {"persistent_operator_halt": True},
        {"exact_protection_confirmed": False},
        {"time_exit_marker_claimed": True},
        {"expected_cycle_binding_digest": "sha256:" + ("e" * 64)},
        {
            "previous_observed_at_utc": datetime(
                2026, 7, 28, 1, 27, tzinfo=UTC
            )
        },
        {
            "observed_at_utc": datetime(2026, 7, 28, 1, 30)
        },
    ):
        decision = evaluate_exit_recovery(_recovery_snapshot(**overrides))
        assert decision.status is V4ExitRecoveryStatus.REFUSED_FAIL_CLOSED
        assert decision.monitor_tick_allowed is False


def test_commissioning_stays_not_ready_until_reviewed_shadow_producer_exists() -> None:
    shadow = _shadow_artifact()
    decision = evaluate_commissioning(
        _commissioning_artifact(shadow),
        shadow,
    )

    assert decision.status is V4CommissioningStatus.NOT_READY
    assert decision.separate_live_review_required is True
    assert decision.persistent_arm_change_allowed is False
    assert decision.broker_post_authorized is False
    assert decision.actual_post_count == 0
    assert bool(decision) is False


def test_commissioning_requires_all_three_independent_reviews() -> None:
    for field in (
        "architecture_review_clear",
        "safety_review_clear",
        "operations_review_clear",
    ):
        shadow = _shadow_artifact()
        decision = evaluate_commissioning(
            _commissioning_artifact(shadow, **{field: False}),
            shadow,
        )
        assert decision.status is V4CommissioningStatus.NOT_READY


def test_commissioning_rejects_stale_shadow_generation_evidence() -> None:
    shadow = _shadow_artifact(
        generation_digest="sha256:" + ("c" * 64)
    )
    decision = evaluate_commissioning(
        _commissioning_artifact(shadow),
        shadow,
    )

    assert decision.status is V4CommissioningStatus.NOT_READY


def test_commissioning_rejects_tampered_artifact_digest() -> None:
    shadow = _shadow_artifact()
    artifact = _commissioning_artifact(shadow)
    tampered = replace(artifact, shadow_scheduler_cycles_clear=21)

    assert (
        evaluate_commissioning(tampered, shadow).status
        is V4CommissioningStatus.NOT_READY
    )


def test_commissioning_rejects_reused_g018_generation_label() -> None:
    shadow = _shadow_artifact()
    artifact = _commissioning_artifact(
        shadow,
        generation_label="H11_AUTO_30M_20260727_G018"
    )

    assert (
        evaluate_commissioning(artifact, shadow).status
        is V4CommissioningStatus.NOT_READY
    )


def test_commissioning_rejects_wrong_predecessor() -> None:
    shadow = _shadow_artifact()
    artifact = _commissioning_artifact(
        shadow,
        prior_canary_generation_label="H11_AUTO_30M_20260726_G017",
    )

    assert (
        evaluate_commissioning(artifact, shadow).status
        is V4CommissioningStatus.NOT_READY
    )


def test_commissioning_rejects_duplicate_or_placeholder_shadow_slots() -> None:
    duplicated = ("sha256:" + ("0" * 64),) * 20
    shadow = _shadow_artifact(completed_slot_digests=duplicated)
    artifact = _commissioning_artifact(shadow)

    assert (
        evaluate_commissioning(artifact, shadow).status
        is V4CommissioningStatus.NOT_READY
    )


def test_repository_commissioning_template_is_canonical_and_not_ready() -> None:
    repository = Path(__file__).resolve().parents[4]
    artifact = load_commissioning_artifact(
        repository / "docs/templates/h11_v4_g019_commissioning_no_post.json"
    )
    shadow = load_shadow_evidence_artifact(
        repository / "docs/templates/h11_v4_g019_shadow_evidence_no_post.json"
    )

    assert artifact.generation_label == "H11_AUTO_30M_20260728_G019"
    assert artifact.shadow_evidence_digest == shadow.artifact_digest
    assert (
        evaluate_commissioning(artifact, shadow).status
        is V4CommissioningStatus.NOT_READY
    )


def test_repository_g020_templates_are_canonical_and_not_ready() -> None:
    repository = Path(__file__).resolve().parents[4]
    artifact = load_commissioning_artifact(
        repository / "docs/templates/h11_v4_g020_commissioning_no_post.json"
    )
    shadow = load_shadow_evidence_artifact(
        repository / "docs/templates/h11_v4_g020_shadow_evidence_no_post.json"
    )

    assert artifact.generation_label == "H11_AUTO_30M_20260728_G020"
    assert artifact.shadow_evidence_digest == shadow.artifact_digest
    assert evaluate_commissioning(artifact, shadow).status is V4CommissioningStatus.NOT_READY


def test_recovery_uses_reviewed_deadline_not_caller_boolean() -> None:
    before = evaluate_exit_recovery(_recovery_snapshot())
    after = evaluate_exit_recovery(
        _recovery_snapshot(
            previous_observed_at_utc=datetime(
                2026, 7, 28, 1, 29, 30, tzinfo=UTC
            ),
            observed_at_utc=datetime(2026, 7, 28, 1, 29, tzinfo=UTC)
            + timedelta(minutes=1),
        )
    )

    assert before.status is V4ExitRecoveryStatus.MONITOR_TICK_SAFE_NO_WRITE
    assert after.status is V4ExitRecoveryStatus.EXIT_SCOPE_REQUIRED_NO_WRITE


def test_g020_producer_only_reaches_separate_live_review() -> None:
    shadow = build_shadow_evidence_artifact(
        schema=G020_SHADOW_EVIDENCE_SCHEMA,
        reviewed_files_digest="sha256:" + ("a" * 64),
        generation_digest="sha256:" + ("b" * 64),
        completed_slot_digests=tuple(
            f"sha256:{index:064x}" for index in range(1, 21)
        ),
        abnormal_status_count=0,
        broker_write=False,
        actual_post_count=0,
    )
    artifact = build_commissioning_artifact(
        schema=G020_COMMISSIONING_SCHEMA,
        generation_label="H11_AUTO_30M_20260728_G020",
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest="sha256:" + ("e" * 64),
        prior_canary_reconciliation_artifact_digest="sha256:" + ("f" * 64),
        prior_canary_handoff_digest="sha256:" + ("1" * 64),
        commissioning_entry_disabled=True,
        reviewed_files_digest=shadow.reviewed_files_digest,
        generation_digest=shadow.generation_digest,
        shadow_evidence_digest=shadow.artifact_digest,
        shadow_reviewed_files_digest=shadow.reviewed_files_digest,
        shadow_generation_digest=shadow.generation_digest,
        shadow_scheduler_cycles_clear=20,
        prior_canary_cycle_complete=True,
        prior_canary_flat_reconciled=True,
        account_wide_active_orders_zero_evidence=True,
        restart_safe_exit_contract_clear=True,
        notification_contract_clear=True,
        architecture_review_clear=True,
        safety_review_clear=True,
        operations_review_clear=True,
    )

    predecessor = _predecessor_completion_artifact(
        reconciliation_passed_marker_digest=artifact.prior_canary_reconciliation_artifact_digest,
    )
    artifact_fields = asdict(artifact)
    artifact_fields.pop("artifact_digest")
    artifact_fields["prior_canary_generation_digest"] = (
        predecessor.prior_canary_generation_digest
    )
    artifact_fields["prior_canary_reconciliation_artifact_digest"] = (
        predecessor.reconciliation_passed_marker_digest
    )
    artifact_fields["prior_canary_handoff_digest"] = predecessor.artifact_digest
    artifact = build_commissioning_artifact(**artifact_fields)
    decision = evaluate_commissioning(artifact, shadow, predecessor)

    assert decision.status is V4CommissioningStatus.NOT_READY
    assert decision.persistent_arm_change_allowed is False
    assert decision.broker_post_authorized is False


def test_g018_predecessor_completion_binder_uses_a_temporary_sanitized_fixture(
    tmp_path: Path,
) -> None:
    origin_digest = "9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
    reconciliation_digest = "b" * 64
    origin = (
        tmp_path
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / f"generation-{origin_digest}"
    )
    origin.mkdir(parents=True)
    database = origin / "coordinator.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE cycles (
                entry_average_fill_price TEXT,
                protection_plan_digest TEXT,
                protection_confirmed_at_utc TEXT
            )
            """
        )
        connection.execute("CREATE TABLE attempts (action TEXT)")
        connection.execute("INSERT INTO cycles VALUES ('x', 'y', 'z')")
        connection.executemany(
            "INSERT INTO attempts VALUES (?)",
            [("MARKET_ENTRY",), ("EXACT_SIZE_OCO_PROTECTION",)],
        )
        connection.commit()
    finally:
        connection.close()
    reconciliation = origin.parent / f"generation-{reconciliation_digest}"
    reconciliation.mkdir()
    (reconciliation / "post-canary-reconciliation.started.json").write_text(
        json.dumps(
            {
                "schema": "H11_V4_G013_POST_CANARY_RECONCILIATION_V1",
                "origin_generation_digest": "sha256:" + origin_digest,
                "broker_write_attempt_count": 0,
            }
        ),
        encoding="utf-8",
    )
    started = reconciliation / "post-canary-reconciliation.started.json"
    (reconciliation / "post-canary-reconciliation.passed.json").write_text(
        json.dumps(
            {
                "status": "G013_POST_CANARY_FLAT_CONFIRMED",
                "result_known": True,
                "subject_entry_observed": True,
                "account_flat": True,
                "active_orders_zero": True,
                "broker_read_count": 3,
                "broker_write_attempt_count": 0,
                "raw_response_retained": False,
                "identifier_exposed": False,
            }
        ),
        encoding="utf-8",
    )
    binding_payload = {
        "schema": "H11_V4_G018_LEGACY_RECONCILIATION_BINDING_V1",
        "origin_generation_digest": "sha256:" + origin_digest,
        "runtime_generation_digest": "sha256:" + reconciliation_digest,
        "started_marker_digest": "sha256:"
        + hashlib.sha256(started.read_bytes()).hexdigest(),
        "passed_marker_digest": "sha256:"
        + hashlib.sha256(
            (reconciliation / "post-canary-reconciliation.passed.json").read_bytes()
        ).hexdigest(),
        "status": "REVIEWED_HISTORICAL_BINDING_NO_BROKER_POST",
        "broker_write": False,
    }
    binding_payload["artifact_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            binding_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    binding = (
        tmp_path
        / "docs/templates/h11_v4_g018_legacy_reconciliation_binding.json"
    )
    binding.parent.mkdir(parents=True)
    binding.write_text(json.dumps(binding_payload), encoding="utf-8")

    artifact = bind_g018_predecessor_canary_completion(repository=tmp_path)
    artifact_path = tmp_path / "completion.json"
    artifact_path.write_text(json.dumps(asdict(artifact)), encoding="utf-8")

    assert artifact.commissioning_eligible is False
    assert artifact.coordinator_cycle_count == 1
    assert artifact.market_entry_attempt_count == 1
    assert artifact.exact_size_oco_protection_attempt_count == 1
    assert load_predecessor_canary_completion_artifact(artifact_path) == artifact

    passed = reconciliation / "post-canary-reconciliation.passed.json"
    legacy_started_payload = json.loads(started.read_text(encoding="utf-8"))
    legacy_passed_payload = json.loads(passed.read_text(encoding="utf-8"))
    mismatched_optional_bindings = (
        (started, "target_generation_digest", "sha256:" + ("d" * 64)),
        (passed, "schema", "WRONG_SCHEMA"),
        (passed, "origin_generation_digest", "sha256:" + ("d" * 64)),
        (passed, "started_marker_digest", "sha256:" + ("d" * 64)),
        (passed, "target_generation_digest", "sha256:" + ("d" * 64)),
    )
    for marker, key, value in mismatched_optional_bindings:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload[key] = value
        marker.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(
            V4PredecessorCanaryCompletionError,
            match="V4_PREDECESSOR_RECONCILIATION_UNBOUND_OR_AMBIGUOUS",
        ):
            bind_g018_predecessor_canary_completion(repository=tmp_path)
        started.write_text(json.dumps(legacy_started_payload), encoding="utf-8")
        passed.write_text(json.dumps(legacy_passed_payload), encoding="utf-8")

    duplicate = origin.parent / f"generation-{'c' * 64}"
    duplicate.mkdir()
    duplicate_started = duplicate / "post-canary-reconciliation.started.json"
    duplicate_started_payload = json.loads(started.read_text(encoding="utf-8"))
    duplicate_started.write_text(
        json.dumps(duplicate_started_payload), encoding="utf-8"
    )
    duplicate_passed = json.loads(
        (reconciliation / "post-canary-reconciliation.passed.json").read_text(
            encoding="utf-8"
        )
    )
    (duplicate / "post-canary-reconciliation.passed.json").write_text(
        json.dumps(duplicate_passed), encoding="utf-8"
    )

    with pytest.raises(
        V4PredecessorCanaryCompletionError,
        match="V4_PREDECESSOR_RECONCILIATION_UNBOUND_OR_AMBIGUOUS",
    ):
        bind_g018_predecessor_canary_completion(repository=tmp_path)
