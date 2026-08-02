"""Fake-only tests for the final G072 switch-control contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g072_switch_control import (
    G072_PERSISTENT_HALT_FILE,
    G072_SWITCH_CAPABILITY_FILE,
    G072EntryEvaluation,
    G072Error,
    G072ReconciliationState,
    G072ResidentSupervisor,
    G072SanitizedSnapshot,
    run_g072_initial_atomic_activation_once,
    run_g072_reconciliation_cycle_once,
    safe_g072_api_status,
    verify_g072_switch_capability,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
GENERATION_DIGEST = "sha256:" + "1" * 64
REVIEWED_FILES_DIGEST = "sha256:" + "2" * 64


class FakeReader:
    def __init__(self, snapshot: G072SanitizedSnapshot, *, failure: Exception | None = None):
        self.snapshot = snapshot
        self.failure = failure

    def read_once(self) -> G072SanitizedSnapshot:
        if self.failure is not None:
            raise self.failure
        return self.snapshot

    def safe_attempt_counts(self) -> tuple[int, int, int]:
        return (3, 3, 1)


class FakeArm:
    def __init__(self, result: bool = True):
        self.calls = 0
        self.result = result

    def arm_once(self, *, generation_digest: str, reviewed_files_digest: str) -> bool:
        self.calls += 1
        assert generation_digest == GENERATION_DIGEST
        assert reviewed_files_digest == REVIEWED_FILES_DIGEST
        return self.result


class FakeWaiter:
    def __init__(self, result: bool = True):
        self.calls = 0
        self.result = result

    def wait_once(
        self,
        *,
        expected_effective_state: str,
        generation_digest: str,
        reviewed_files_digest: str,
        not_before_utc: datetime,
        timeout_seconds: float,
    ) -> bool:
        self.calls += 1
        assert expected_effective_state in {"ON_WAITING", "ON_EXIT_ONLY"}
        assert generation_digest == GENERATION_DIGEST
        assert reviewed_files_digest == REVIEWED_FILES_DIGEST
        assert not_before_utc == NOW
        assert timeout_seconds > 0
        return self.result


class FakeEntryEvaluator:
    def __init__(self, evaluation: G072EntryEvaluation):
        self.evaluation = evaluation

    def evaluate(self, *, now_utc: datetime, evidence):
        assert now_utc == NOW
        assert evidence.state is G072ReconciliationState.FRESH_FLAT
        return self.evaluation


def _snapshot(
    *,
    position_count: int = 0,
    active_order_count: int = 0,
    ownership_exact: bool = False,
    quantity_matches: bool = False,
    protection_confirmed: bool = False,
) -> G072SanitizedSnapshot:
    return G072SanitizedSnapshot(
        latest_execution_count=0,
        open_position_count=position_count,
        active_order_count=active_order_count,
        ownership_exact=ownership_exact,
        quantity_matches=quantity_matches,
        protection_confirmed=protection_confirmed,
    )


def _initial_activation(state_root: Path, snapshot: G072SanitizedSnapshot):
    arm = FakeArm()
    waiter = FakeWaiter()
    result = run_g072_initial_atomic_activation_once(
        state_root=state_root,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        precondition_verifier=lambda: None,
        snapshot_reader=FakeReader(snapshot),
        arm_mutator=arm,
        projection_waiter=waiter,
        now_utc=NOW,
    )
    return result, arm, waiter


def test_initial_activation_enables_switch_only_rearm_and_runtime_projection(tmp_path: Path):
    before = safe_g072_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )
    assert before["runtime_activation_available"] is False

    result, arm, waiter = _initial_activation(tmp_path, _snapshot())
    assert result.status == "PASSED"
    assert result.reconciliation_state is G072ReconciliationState.FRESH_FLAT
    assert arm.calls == 1
    assert waiter.calls == 1
    assert verify_g072_switch_capability(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )

    supervisor = G072ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )
    on_status = supervisor.tick(now_utc=NOW, arm_on=True)
    assert on_status["effective_state"] == "ON_WAITING"
    assert on_status["entry_gate_open"] is False
    assert on_status["entry_state"] == "WAITING_FOR_SIGNAL"

    off_status = supervisor.tick(now_utc=NOW, arm_on=False)
    assert off_status["effective_state"] == "OFF"
    assert off_status["entry_gate_open"] is False

    after = safe_g072_api_status(
        state_root=tmp_path,
        arm_on=True,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )
    assert after["runtime_activation_available"] is True
    assert after["switch_only_rearm_available"] is True


def test_reconciliation_is_one_shot_per_cycle_and_fresh_flat_is_safe(tmp_path: Path):
    evidence = run_g072_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        cycle_index=1,
        reader=FakeReader(_snapshot()),
        now_utc=NOW,
    )
    assert evidence.state is G072ReconciliationState.FRESH_FLAT
    assert evidence.account_flat is True
    with pytest.raises(G072Error, match="ALREADY_STARTED_NO_RETRY"):
        run_g072_reconciliation_cycle_once(
            state_root=tmp_path,
            generation_digest=GENERATION_DIGEST,
            reviewed_files_digest=REVIEWED_FILES_DIGEST,
            cycle_index=1,
            reader=FakeReader(_snapshot()),
            now_utc=NOW,
        )


def test_protected_position_is_exit_only_and_entry_is_closed(tmp_path: Path):
    result, _, _ = _initial_activation(
        tmp_path,
        _snapshot(
            position_count=1,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        ),
    )
    assert result.reconciliation_state is G072ReconciliationState.FRESH_PROTECTED
    status = G072ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    ).tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == "ON_EXIT_ONLY"
    assert status["entry_gate_open"] is False
    assert status["entry_state"] == "BLOCKED_POSITION_OPEN"


def test_unconfirmed_position_halts_and_never_enables_capability(tmp_path: Path):
    with pytest.raises(G072Error, match="RECONCILIATION_NOT_CLEAR"):
        _initial_activation(tmp_path, _snapshot(position_count=1))
    assert (tmp_path / G072_PERSISTENT_HALT_FILE).is_file()
    assert not (tmp_path / G072_SWITCH_CAPABILITY_FILE).is_file()


def test_partial_failure_is_recorded_without_retry(tmp_path: Path):
    reader = FakeReader(_snapshot(), failure=RuntimeError("synthetic failure"))
    with pytest.raises(G072Error, match="RECONCILIATION_UNKNOWN_NO_RETRY"):
        run_g072_reconciliation_cycle_once(
            state_root=tmp_path,
            generation_digest=GENERATION_DIGEST,
            reviewed_files_digest=REVIEWED_FILES_DIGEST,
            cycle_index=1,
            reader=reader,
            now_utc=NOW,
        )
    outcome = json.loads((tmp_path / "g072-reconciliation-1.outcome.json").read_text())
    assert outcome["status"] == "UNKNOWN"
    assert outcome["broker_get_count"] == 3
    assert outcome["private_api_read_count"] == 3
    assert outcome["credential_read_count"] == 1
    assert outcome["broker_post_count"] == 0


def test_unknown_initial_transaction_is_not_a_release(tmp_path: Path):
    arm = FakeArm()
    with pytest.raises(G072Error, match="RECONCILIATION_NOT_CLEAR"):
        run_g072_initial_atomic_activation_once(
            state_root=tmp_path,
            generation_digest=GENERATION_DIGEST,
            reviewed_files_digest=REVIEWED_FILES_DIGEST,
            precondition_verifier=lambda: None,
            snapshot_reader=FakeReader(_snapshot(position_count=1)),
            arm_mutator=arm,
            projection_waiter=FakeWaiter(),
            now_utc=NOW,
        )
    assert arm.calls == 0
    assert not (tmp_path / G072_SWITCH_CAPABILITY_FILE).exists()


def test_release_payload_has_no_daily_or_per_trade_confirmation(tmp_path: Path):
    _initial_activation(tmp_path, _snapshot())
    capability = json.loads((tmp_path / G072_SWITCH_CAPABILITY_FILE).read_text())
    assert capability["daily_authorization_required"] is False
    assert capability["per_trade_confirmation_required"] is False
    assert capability["actual_post_authorized"] is False
    assert capability["broker_post_authorized"] is False


def test_strategy_bound_entry_evaluation_can_open_gate_without_broker_access(tmp_path: Path):
    _initial_activation(tmp_path, _snapshot())
    evaluation = G072EntryEvaluation(
        evaluation_known=True,
        strategy_artifact_bound=True,
        signal_actionable=True,
        risk_clear=True,
        market_open=True,
        spread_clear=True,
        freshness_clear=True,
        limits_clear=True,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )
    status = G072ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        entry_evaluator=FakeEntryEvaluator(evaluation),
    ).tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == "ON_WAITING"
    assert status["entry_gate_open"] is True
    assert status["entry_state"] == "ENTRY_READY"
    assert status["actual_post_count"] == 0


def test_entry_binding_mismatch_halts_instead_of_opening_gate(tmp_path: Path):
    _initial_activation(tmp_path, _snapshot())
    evaluation = G072EntryEvaluation(
        evaluation_known=True,
        strategy_artifact_bound=True,
        signal_actionable=True,
        risk_clear=True,
        market_open=True,
        spread_clear=True,
        freshness_clear=True,
        limits_clear=True,
        generation_digest="sha256:" + "9" * 64,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
    )
    status = G072ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        entry_evaluator=FakeEntryEvaluator(evaluation),
    ).tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == "HALTED"
    assert status["entry_gate_open"] is False
