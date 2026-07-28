from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.h11_auto.runtime_safety import PhaseBRiskState
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import (
    build_v4_gmo_frozen_generation,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.services import h11_v4_unattended_controller_snapshot_no_post as subject
from app.services.h11_v4_unattended_commissioning_no_post import (
    build_commissioning_artifact,
    build_predecessor_canary_completion_artifact,
    build_shadow_evidence_artifact,
)
from app.services.h11_v4_unattended_live_arm_state import (
    V4ArmDesiredState,
    V4UnattendedLiveArmCheck,
)


def _sources() -> subject.V4UnattendedControllerOfflineSources:
    reviewed = "sha256:" + "a" * 64
    selected = V4ApprovedOperatorSelections()
    policy = V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )
    generation = build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260728_G020",
        implementation_digest=reviewed,
        policy=policy,
    )
    risk = v4_gmo_risk_policy()
    shadow = build_shadow_evidence_artifact(
        reviewed_files_digest=reviewed,
        generation_digest=generation.digest,
        completed_slot_digests=tuple(
            f"sha256:{index:064x}" for index in range(1, 21)
        ),
        abnormal_status_count=0,
        broker_write=False,
        actual_post_count=0,
    )
    predecessor = build_predecessor_canary_completion_artifact(
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest=(
            "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
        ),
        coordinator_ledger_digest="sha256:" + "1" * 64,
        coordinator_cycle_count=1,
        market_entry_attempt_count=1,
        exact_size_oco_protection_attempt_count=1,
        entry_fill_recorded=True,
        protection_plan_recorded=True,
        protection_confirmed=True,
        reconciliation_runtime_generation_digest="sha256:" + "2" * 64,
        reconciliation_started_marker_digest="sha256:" + "3" * 64,
        reconciliation_passed_marker_digest="sha256:" + "4" * 64,
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
    commissioning = build_commissioning_artifact(
        generation_label="H11_AUTO_30M_20260728_G020",
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        prior_canary_generation_digest=predecessor.prior_canary_generation_digest,
        prior_canary_reconciliation_artifact_digest=(
            predecessor.reconciliation_passed_marker_digest
        ),
        prior_canary_handoff_digest=predecessor.artifact_digest,
        commissioning_entry_disabled=True,
        reviewed_files_digest=reviewed,
        generation_digest=generation.digest,
        shadow_evidence_digest=shadow.artifact_digest,
        shadow_reviewed_files_digest=reviewed,
        shadow_generation_digest=generation.digest,
        shadow_scheduler_cycles_clear=20,
        prior_canary_cycle_complete=True,
        prior_canary_flat_reconciled=True,
        account_wide_active_orders_zero_evidence=True,
        restart_safe_exit_contract_clear=False,
        notification_contract_clear=False,
        architecture_review_clear=True,
        safety_review_clear=True,
        operations_review_clear=True,
    )
    return subject.V4UnattendedControllerOfflineSources(
        reviewed_files_digest=reviewed,
        generation=generation,
        risk_policy=risk,
        risk_state=PhaseBRiskState(policy_digest=risk.digest),
        arm_check=V4UnattendedLiveArmCheck(
            armed=False,
            desired_state=V4ArmDesiredState.DISARMED,
            revision=0,
            blocked_reasons=("ARM_STATE_MISSING",),
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
        ),
        commissioning_artifact=commissioning,
        commissioning_shadow=shadow,
        predecessor_completion=predecessor,
    )


def test_offline_snapshot_fixes_all_external_facts_to_safe_values() -> None:
    snapshot = subject.assemble_offline_controller_snapshot_no_post(
        sources=_sources(),
        now_utc=datetime.now(UTC),
    )
    assert snapshot.arm_armed is False
    assert snapshot.process_lock_clear is False
    assert snapshot.notification_ready is False
    assert snapshot.market_open is False
    assert snapshot.account_snapshot_known is False
    assert snapshot.transport_action_pending is False
    assert snapshot.result_unknown is False


def test_source_binding_mismatch_is_rejected() -> None:
    sources = _sources()
    with pytest.raises(
        subject.V4UnattendedControllerSnapshotNoPostError,
        match="SOURCE_BINDING_INVALID",
    ):
        subject.assemble_offline_controller_snapshot_no_post(
            sources=subject.V4UnattendedControllerOfflineSources(
                **{
                    **sources.__dict__,
                    "reviewed_files_digest": "sha256:" + "9" * 64,
                }
            ),
            now_utc=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "mutation",
    (
        lambda sources: replace(
            sources,
            commissioning_artifact=replace(
                sources.commissioning_artifact,
                generation_digest="sha256:" + "8" * 64,
            ),
        ),
        lambda sources: replace(
            sources,
            commissioning_shadow=replace(
                sources.commissioning_shadow,
                generation_digest="sha256:" + "8" * 64,
            ),
        ),
        lambda sources: replace(
            sources,
            predecessor_completion=replace(
                sources.predecessor_completion,
                prior_canary_generation_digest="sha256:" + "8" * 64,
            ),
        ),
    ),
)
def test_cross_artifact_binding_mismatch_is_rejected(mutation) -> None:
    with pytest.raises(
        subject.V4UnattendedControllerSnapshotNoPostError,
        match="SOURCE_BINDING_INVALID",
    ):
        subject.assemble_offline_controller_snapshot_no_post(
            sources=mutation(_sources()),
            now_utc=datetime.now(UTC),
        )


def test_snapshot_assembler_has_no_live_dependency() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "Keychain",
        "credential",
        "ActualPushover",
        "ActualEmail",
        "closeOrder",
        "cancelOrders",
        "assert_real_broker_post_allowed",
    ):
        assert forbidden not in source
