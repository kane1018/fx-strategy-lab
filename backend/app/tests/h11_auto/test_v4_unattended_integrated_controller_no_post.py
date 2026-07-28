from __future__ import annotations

import inspect
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.h11_auto.runtime_safety import PhaseBRiskPolicy
from app.services import h11_v4_unattended_integrated_controller_no_post as subject
from app.services.h11_v4_unattended_commissioning_no_post import (
    V4CommissioningArtifact,
    V4CommissioningDecision,
    V4CommissioningStatus,
    V4PredecessorCanaryCompletionArtifact,
    V4ShadowEvidenceArtifact,
    build_commissioning_artifact,
    build_predecessor_canary_completion_artifact,
    build_shadow_evidence_artifact,
)


def _commissioning_evidence() -> tuple[
    V4CommissioningArtifact,
    V4ShadowEvidenceArtifact,
    V4PredecessorCanaryCompletionArtifact,
]:
    reviewed = "sha256:" + "a" * 64
    generation = "sha256:" + "b" * 64
    shadow = build_shadow_evidence_artifact(
        reviewed_files_digest=reviewed,
        generation_digest=generation,
        completed_slot_digests=tuple(f"sha256:{index:064x}" for index in range(1, 21)),
        abnormal_status_count=0,
        broker_write=False,
        actual_post_count=0,
    )
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
    artifact = build_commissioning_artifact(
        generation_label="H11_AUTO_30M_20260728_G019",
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest=predecessor.prior_canary_generation_digest,
        prior_canary_reconciliation_artifact_digest=(
            predecessor.reconciliation_passed_marker_digest
        ),
        prior_canary_handoff_digest=predecessor.artifact_digest,
        commissioning_entry_disabled=True,
        reviewed_files_digest=reviewed,
        generation_digest=generation,
        shadow_evidence_digest=shadow.artifact_digest,
        shadow_reviewed_files_digest=reviewed,
        shadow_generation_digest=generation,
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
    return artifact, shadow, predecessor


def _snapshot(**overrides: object) -> subject.V4IntegratedControllerSnapshot:
    reviewed = "sha256:" + "a" * 64
    generation = "sha256:" + "b" * 64
    artifact, shadow, predecessor = _commissioning_evidence()
    risk_policy = PhaseBRiskPolicy(
        policy_label="H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
        maximum_entries_per_day=30,
    )
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "reviewed_files_digest": reviewed,
        "generation_digest": generation,
        "cycle_binding_digest": "sha256:" + "c" * 64,
        "expected_cycle_binding_digest": "sha256:" + "c" * 64,
        "protection_cycle_binding_digest": "sha256:" + "c" * 64,
        "scheduled_exit_cycle_binding_digest": "sha256:" + "c" * 64,
        "risk_policy": risk_policy,
        "expected_risk_policy_digest": risk_policy.digest,
        "arm_reviewed_files_digest": reviewed,
        "arm_generation_digest": generation,
        "arm_armed": True,
        "commissioning_artifact": artifact,
        "commissioning_shadow": shadow,
        "predecessor_completion": predecessor,
        "process_lock_clear": True,
        "persistent_halt_clear": True,
        "dead_man_clear": True,
        "heartbeat_chain_clear": True,
        "notification_ready": True,
        "market_open": True,
        "formal_signal_actionable": True,
        "quote_fresh": True,
        "spread_within_limit": True,
        "account_snapshot_known": True,
        "account_flat": True,
        "active_orders_zero": True,
        "exact_protection_confirmed": False,
        "protection_observed_current": False,
        "position_ownership_confirmed": False,
        "scheduled_exit_due": False,
        "transport_action_pending": False,
        "result_unknown": False,
        "daily_entry_count": 0,
        "daily_loss_jpy": 0,
        "monthly_loss_jpy": 0,
        "consecutive_losses": 0,
        "observed_at_utc": (now - timedelta(seconds=30)).isoformat(),
        "valid_until_utc": (now + timedelta(seconds=30)).isoformat(),
    }
    values.update(overrides)
    evidence_keys = {
        field
        for field in subject.V4IntegratedControllerEvidence.__dataclass_fields__
        if field not in {"schema", "artifact_digest"}
    }
    evidence_values = {key: values[key] for key in evidence_keys}
    evidence = subject.build_integrated_controller_evidence(**evidence_values)
    snapshot_keys = {
        "reviewed_files_digest",
        "generation_digest",
        "cycle_binding_digest",
        "expected_cycle_binding_digest",
        "risk_policy",
        "expected_risk_policy_digest",
        "commissioning_artifact",
        "commissioning_shadow",
        "predecessor_completion",
    }
    snapshot_values = {key: values[key] for key in snapshot_keys}
    return subject.V4IntegratedControllerSnapshot(
        **snapshot_values,
        evidence=evidence,
    )


def _replace_evidence(
    snapshot: subject.V4IntegratedControllerSnapshot,
    **overrides: object,
) -> subject.V4IntegratedControllerSnapshot:
    evidence_values = asdict(snapshot.evidence)
    evidence_values.pop("schema")
    evidence_values.pop("artifact_digest")
    evidence_values.update(overrides)
    evidence = subject.build_integrated_controller_evidence(**evidence_values)
    return replace(snapshot, evidence=evidence)


def test_flat_candidate_rejects_legacy_predecessor_as_commissioning_evidence() -> None:
    decision = subject.evaluate_integrated_controller(_snapshot())
    assert (
        decision.status
        is subject.V4IntegratedControllerStatus.ENTRY_BLOCKED_NO_POST
    )
    assert "COMMISSIONING_EVIDENCE_INVALID" in decision.blocked_reasons
    assert bool(decision) is False
    assert decision.to_safe_dict()["broker_post_authorized"] is False
    assert decision.actual_post_count == 0


def test_daily_entry_limit_reuses_the_reviewed_runtime_ceiling() -> None:
    one_entry_policy = PhaseBRiskPolicy(
        policy_label="ONE_ENTRY_TEST",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
        maximum_entries_per_day=1,
    )
    decision = subject.evaluate_integrated_controller(
        _snapshot(
            daily_entry_count=1,
            risk_policy=one_entry_policy,
            expected_risk_policy_digest=one_entry_policy.digest,
        )
    )
    assert "DAILY_ENTRY_LIMIT_REACHED" in decision.blocked_reasons


@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"arm_armed": False}, "PERSISTENT_ARM_NOT_CLEAR"),
        ({"arm_armed": False}, "PERSISTENT_ARM_NOT_CLEAR"),
        ({"notification_ready": False}, "NOTIFICATION_NOT_READY"),
        ({"daily_entry_count": 30}, "DAILY_ENTRY_LIMIT_REACHED"),
        ({"daily_loss_jpy": 10_000}, "DAILY_REALIZED_LOSS_LIMIT_REACHED"),
        ({"monthly_loss_jpy": 50_000}, "MONTHLY_REALIZED_LOSS_LIMIT_REACHED"),
        ({"consecutive_losses": 5}, "CONSECUTIVE_LOSS_LIMIT_REACHED"),
    ),
)
def test_entry_gate_failures_are_sanitized_no_post(
    overrides: dict[str, object], reason: str
) -> None:
    decision = subject.evaluate_integrated_controller(_snapshot(**overrides))
    assert decision.status is subject.V4IntegratedControllerStatus.ENTRY_BLOCKED_NO_POST
    assert reason in decision.blocked_reasons
    assert decision.broker_write is False


def test_legacy_predecessor_cannot_unlock_position_monitoring_or_exit() -> None:
    protected = _snapshot(
        account_flat=False,
        active_orders_zero=False,
        exact_protection_confirmed=True,
        protection_observed_current=True,
        position_ownership_confirmed=True,
        formal_signal_actionable=False,
    )
    monitoring = subject.evaluate_integrated_controller(protected)
    due = subject.evaluate_integrated_controller(
        _replace_evidence(protected, scheduled_exit_due=True)
    )
    assert (
        monitoring.status
        is subject.V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST
    )
    assert due.status is subject.V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST
    assert "COMMISSIONING_EVIDENCE_INVALID" in monitoring.blocked_reasons
    assert "COMMISSIONING_EVIDENCE_INVALID" in due.blocked_reasons
    assert due.separate_review_required is False
    assert due.broker_post_authorized is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"result_unknown": True}, "RESULT_UNKNOWN"),
        ({"transport_action_pending": True}, "TRANSPORT_ACTION_PENDING"),
        ({"account_snapshot_known": False}, "ACCOUNT_SNAPSHOT_UNKNOWN"),
        ({"account_flat": True, "active_orders_zero": False}, "FLAT_WITH_ACTIVE_ORDERS"),
        (
            {
                "account_flat": False,
                "active_orders_zero": False,
                "exact_protection_confirmed": False,
            },
            "OPEN_POSITION_NOT_EXACTLY_PROTECTED",
        ),
    ),
)
def test_unknown_or_inconsistent_lifecycle_persistently_halts(
    overrides: dict[str, object], reason: str
) -> None:
    decision = subject.evaluate_integrated_controller(_snapshot(**overrides))
    assert decision.status is subject.V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST
    assert decision.persistent_halt is True
    assert reason in decision.blocked_reasons
    assert decision.actual_post_count == 0


def test_nonactionable_flat_cycle_is_idle() -> None:
    decision = subject.evaluate_integrated_controller(
        _snapshot(formal_signal_actionable=False)
    )
    assert decision.status is subject.V4IntegratedControllerStatus.IDLE_NO_POST


def test_nonactionable_flat_cycle_reports_operational_degradation() -> None:
    decision = subject.evaluate_integrated_controller(
        _snapshot(formal_signal_actionable=False, dead_man_clear=False)
    )
    assert (
        decision.status
        is subject.V4IntegratedControllerStatus.OPERATIONAL_DEGRADED_NO_POST
    )
    assert "DEAD_MAN_NOT_CLEAR" in decision.blocked_reasons


def test_review_and_arm_binding_are_checked_before_idle_branch() -> None:
    arm_mismatch = subject.evaluate_integrated_controller(
        _snapshot(
            formal_signal_actionable=False,
            arm_generation_digest="sha256:" + "9" * 64,
        )
    )
    artifact, shadow, predecessor = _commissioning_evidence()
    payload = asdict(artifact)
    payload.pop("artifact_digest")
    payload["architecture_review_clear"] = False
    review_not_clear = subject.evaluate_integrated_controller(
        _snapshot(
            formal_signal_actionable=False,
            commissioning_artifact=build_commissioning_artifact(**payload),
            commissioning_shadow=shadow,
            predecessor_completion=predecessor,
        )
    )
    assert arm_mismatch.persistent_halt is True
    assert "ARM_REVIEW_BOUNDARY_MISMATCH" in arm_mismatch.blocked_reasons
    assert review_not_clear.persistent_halt is True
    assert "ARCHITECTURE_REVIEW_NOT_CLEAR" in review_not_clear.blocked_reasons


def test_open_position_requires_active_current_cycle_bound_protection() -> None:
    decision = subject.evaluate_integrated_controller(
        _snapshot(
            account_flat=False,
            active_orders_zero=True,
            exact_protection_confirmed=True,
            protection_observed_current=True,
            position_ownership_confirmed=True,
        )
    )
    assert decision.persistent_halt is True
    assert "OPEN_POSITION_WITHOUT_ACTIVE_PROTECTION" in decision.blocked_reasons
    stale = subject.evaluate_integrated_controller(
        _snapshot(
            account_flat=False,
            active_orders_zero=False,
            exact_protection_confirmed=True,
            protection_observed_current=True,
            position_ownership_confirmed=True,
            protection_cycle_binding_digest="sha256:" + "d" * 64,
        )
    )
    assert stale.persistent_halt is True
    assert "OPEN_POSITION_CYCLE_BINDING_MISMATCH" in stale.blocked_reasons


def test_boolean_inputs_are_exactly_typed() -> None:
    with pytest.raises(subject.V4IntegratedControllerError, match="BOOLEAN_INVALID"):
        subject.evaluate_integrated_controller(_snapshot(notification_ready=1))


def test_durable_halt_survives_store_restart(tmp_path) -> None:
    database = tmp_path / "integrated.sqlite3"
    first = subject.V4IntegratedControllerStore(database).evaluate_and_record(
        _snapshot(result_unknown=True)
    )
    second = subject.V4IntegratedControllerStore(database).evaluate_and_record(
        _snapshot(result_unknown=False)
    )
    assert first.persistent_halt is True
    assert second.persistent_halt is True
    assert "PERSISTENT_GENERATION_HALT_LATCHED" in second.blocked_reasons


def test_generation_halt_cannot_be_bypassed_with_a_new_cycle(tmp_path) -> None:
    database = tmp_path / "integrated.sqlite3"
    first = subject.V4IntegratedControllerStore(database).evaluate_and_record(
        _snapshot(result_unknown=True)
    )
    second = subject.V4IntegratedControllerStore(database).evaluate_and_record(
        _snapshot(
            cycle_binding_digest="sha256:" + "d" * 64,
            expected_cycle_binding_digest="sha256:" + "d" * 64,
            protection_cycle_binding_digest="sha256:" + "d" * 64,
            scheduled_exit_cycle_binding_digest="sha256:" + "d" * 64,
            result_unknown=False,
        )
    )
    assert first.persistent_halt is True
    assert second.persistent_halt is True
    assert "PERSISTENT_GENERATION_HALT_LATCHED" in second.blocked_reasons


def test_legacy_cycle_halt_backfills_generation_halt(tmp_path) -> None:
    database = tmp_path / "integrated.sqlite3"
    store = subject.V4IntegratedControllerStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO integrated_controller_state VALUES (?, ?, ?, ?, ?)
            """,
            (
                "sha256:" + "b" * 64,
                "sha256:" + "c" * 64,
                "sha256:" + "a" * 64,
                subject.V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST.value,
                "2026-07-28T00:00:00+00:00",
            ),
        )
    new_cycle = store.evaluate_and_record(
        _snapshot(
            cycle_binding_digest="sha256:" + "e" * 64,
            expected_cycle_binding_digest="sha256:" + "e" * 64,
            protection_cycle_binding_digest="sha256:" + "e" * 64,
            scheduled_exit_cycle_binding_digest="sha256:" + "e" * 64,
        )
    )
    later_cycle = store.evaluate_and_record(
        _snapshot(
            cycle_binding_digest="sha256:" + "f" * 64,
            expected_cycle_binding_digest="sha256:" + "f" * 64,
            protection_cycle_binding_digest="sha256:" + "f" * 64,
            scheduled_exit_cycle_binding_digest="sha256:" + "f" * 64,
        )
    )
    assert "PERSISTENT_LEGACY_GENERATION_HALT_LATCHED" in new_cycle.blocked_reasons
    assert "PERSISTENT_GENERATION_HALT_LATCHED" in later_cycle.blocked_reasons


def test_risk_policy_digest_mismatch_blocks_entry() -> None:
    decision = subject.evaluate_integrated_controller(
        _snapshot(expected_risk_policy_digest="9" * 64)
    )
    assert "RISK_POLICY_BINDING_MISMATCH" in decision.blocked_reasons
    assert decision.persistent_halt is True


def test_risk_policy_digest_mismatch_halts_before_non_entry_branch() -> None:
    decision = subject.evaluate_integrated_controller(
        _snapshot(
            expected_risk_policy_digest="9" * 64,
            formal_signal_actionable=False,
        )
    )
    assert (
        decision.status
        is subject.V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST
    )
    assert decision.blocked_reasons == ("RISK_POLICY_BINDING_MISMATCH",)


def test_replayed_or_oversized_evidence_window_is_rejected() -> None:
    stale = datetime.now(UTC) - timedelta(hours=1)
    with pytest.raises(subject.V4IntegratedControllerError, match="NOT_FRESH"):
        subject.evaluate_integrated_controller(
            _snapshot(
                observed_at_utc=stale.isoformat(),
                valid_until_utc=(stale + timedelta(seconds=60)).isoformat(),
            )
        )
    now = datetime.now(UTC)
    with pytest.raises(subject.V4IntegratedControllerError, match="NOT_FRESH"):
        subject.evaluate_integrated_controller(
            _snapshot(
                observed_at_utc=now.isoformat(),
                valid_until_utc=(now + timedelta(seconds=121)).isoformat(),
            )
        )


def test_noncanonical_commissioning_evidence_blocks_open_position() -> None:
    artifact, shadow, predecessor = _commissioning_evidence()
    invalid_artifact = replace(artifact, artifact_digest="sha256:" + "9" * 64)
    decision = subject.evaluate_integrated_controller(
        _snapshot(
            commissioning_artifact=invalid_artifact,
            commissioning_shadow=shadow,
            predecessor_completion=predecessor,
            account_flat=False,
            active_orders_zero=False,
            exact_protection_confirmed=True,
            protection_observed_current=True,
            position_ownership_confirmed=True,
        )
    )
    assert decision.persistent_halt is True
    assert "COMMISSIONING_HISTORICAL_EVIDENCE_INVALID" in decision.blocked_reasons


def test_missing_or_misbound_predecessor_blocks_open_position() -> None:
    artifact, shadow, predecessor = _commissioning_evidence()
    missing = subject.evaluate_integrated_controller(
        _snapshot(
            predecessor_completion=None,
            account_flat=False,
            active_orders_zero=False,
            exact_protection_confirmed=True,
            protection_observed_current=True,
            position_ownership_confirmed=True,
        )
    )
    payload = asdict(artifact)
    payload.pop("artifact_digest")
    payload["prior_canary_handoff_digest"] = "sha256:" + "9" * 64
    misbound_artifact = build_commissioning_artifact(**payload)
    misbound = subject.evaluate_integrated_controller(
        _snapshot(
            commissioning_artifact=misbound_artifact,
            commissioning_shadow=shadow,
            predecessor_completion=predecessor,
            account_flat=False,
            active_orders_zero=False,
            exact_protection_confirmed=True,
            protection_observed_current=True,
            position_ownership_confirmed=True,
        )
    )
    assert "COMMISSIONING_HISTORICAL_EVIDENCE_INVALID" in missing.blocked_reasons
    assert "COMMISSIONING_HISTORICAL_EVIDENCE_INVALID" in misbound.blocked_reasons


def test_unavailable_durable_store_never_claims_persisted_halt(tmp_path) -> None:
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("x", encoding="utf-8")
    decision = subject.V4IntegratedControllerStore(
        parent_file / "state.sqlite3"
    ).evaluate_and_record(_snapshot())
    assert (
        decision.status
        is subject.V4IntegratedControllerStatus.STORAGE_UNAVAILABLE_NO_POST
    )
    assert decision.persistent_halt is False


def test_invalid_digest_is_rejected() -> None:
    with pytest.raises(subject.V4IntegratedControllerError, match="DIGEST_INVALID"):
        subject.evaluate_integrated_controller(_snapshot(generation_digest="invalid"))


def test_integrated_controller_has_no_live_dependency_or_allow_bridge() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "Keychain",
        "credential",
        "closeOrder",
        "cancelOrders",
        "real_broker_post_hard_guard",
        "assert_real_broker_post_allowed",
    ):
        assert forbidden not in source


def test_commissioning_decision_refuses_direct_live_claims() -> None:
    with pytest.raises(ValueError, match="LIVE_CLAIM_REFUSED"):
        V4CommissioningDecision(
            status=V4CommissioningStatus.NOT_READY,
            separate_live_review_required=True,
            persistent_arm_change_allowed=True,
            broker_post_authorized=True,
            broker_write=True,
            actual_post_count=1,
        )


def test_integrated_decision_refuses_direct_live_claims() -> None:
    with pytest.raises(subject.V4IntegratedControllerError, match="LIVE_CLAIM_REFUSED"):
        subject.V4IntegratedControllerDecision(
            status=subject.V4IntegratedControllerStatus.IDLE_NO_POST,
            blocked_reasons=(),
            separate_review_required=False,
            persistent_halt=False,
            broker_post_authorized=True,
            broker_write=True,
            actual_post_count=1,
        )
