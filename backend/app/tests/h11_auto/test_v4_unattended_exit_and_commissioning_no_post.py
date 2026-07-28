from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.h11_v4_unattended_commissioning_no_post import (
    V4CommissioningArtifact,
    V4CommissioningStatus,
    V4ShadowEvidenceArtifact,
    build_commissioning_artifact,
    build_shadow_evidence_artifact,
    evaluate_commissioning,
    load_commissioning_artifact,
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
