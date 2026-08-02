"""Fake-only tests for the final G073 runtime connection contract."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g073_runtime import (
    G073Action,
    G073ActionOutcome,
    G073EffectiveState,
    G073EntryDispatcher,
    G073EntryState,
    G073Error,
    G073ExitDispatcher,
    G073FrozenStrategyEvaluator,
    G073OneShotActionDispatcher,
    G073ReconciliationState,
    G073ResidentSupervisor,
    G073SanitizedSnapshot,
    G073StrategyObservation,
    run_g073_reconciliation_cycle_once,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
GEN = "sha256:" + "1" * 64
REVIEWED = "sha256:" + "2" * 64
STRATEGY = "sha256:" + "3" * 64


class FakeReconciler:
    def __init__(self, snapshot: G073SanitizedSnapshot):
        self.snapshot = snapshot
        self.calls = 0

    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G073SanitizedSnapshot:
        self.calls += 1
        return self.snapshot


class FakeSource:
    def __init__(self, *, actionable: bool):
        self.actionable = actionable

    def observe(self, *, now_utc: datetime) -> G073StrategyObservation:
        return G073StrategyObservation(
            strategy_artifact_digest=STRATEGY,
            strategy_version="SHORT_V1",
            symbol="USD_JPY",
            quantity=1_000,
            horizon="30m",
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            signal_actionable=self.actionable,
            risk_clear=True,
            market_open=True,
            spread_clear=True,
            quote_fresh=True,
            signal_fresh=True,
            limits_clear=True,
            position_flat=True,
            active_orders_zero=True,
        )


class FakePort:
    def __init__(self, outcomes: dict[G073Action, G073ActionOutcome]):
        self.outcomes = outcomes
        self.calls: list[G073Action] = []

    def attempt_once(self, scope):
        self.calls.append(scope.action)
        return self.outcomes[scope.action]


def snapshot(*, position: int = 0, protected: bool = False) -> G073SanitizedSnapshot:
    return G073SanitizedSnapshot(
        latest_execution_count=0,
        open_position_count=position,
        active_order_count=0,
        ownership_exact=protected,
        quantity_matches=protected,
        protection_confirmed=protected,
    )


def bind_capability(root: Path) -> None:
    base = {
        "schema": "H11_V4_G073_SWITCH_CONTROL_CAPABILITY_V1",
        "generation_label": "H11_AUTO_30M_20260802_G073",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "reconciliation_artifact_digest": "sha256:" + "4" * 64,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "status": "ENABLED",
    }
    import hashlib
    import json

    encoded = json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    (root / "g073-switch-control-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest})
    )
    outcome = {
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260802_G073",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
    }
    (root / "g073-initial-activation.outcome.json").write_text(json.dumps(outcome))


def test_cycle_is_single_attempt_and_flat(tmp_path: Path):
    runner = FakeReconciler(snapshot())
    evidence = run_g073_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="cycle-1",
        reconciler=runner,
        now_utc=NOW,
    )
    assert evidence.state is G073ReconciliationState.FRESH_FLAT
    assert runner.calls == 1
    with pytest.raises(G073Error, match="ALREADY_STARTED_NO_RETRY"):
        run_g073_reconciliation_cycle_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id="cycle-1",
            reconciler=runner,
            now_utc=NOW,
        )


def test_supervisor_connects_reconciliation_and_strategy_without_transport(tmp_path: Path):
    bind_capability(tmp_path)
    runner = FakeReconciler(snapshot())
    evaluator = G073FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    )
    supervisor = G073ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=lambda cycle, now: run_g073_reconciliation_cycle_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id=cycle,
            reconciler=runner,
            now_utc=now,
        ),
        strategy_evaluator=evaluator,
    )
    status = supervisor.tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == G073EffectiveState.ON_WAITING.value
    assert status["entry_gate_open"] is True
    assert status["entry_state"] == G073EntryState.ENTRY_READY.value
    assert status["broker_write"] is False
    assert status["private_api_read_count"] == 0


def test_protected_position_is_exit_only_and_unconfirmed_halts(tmp_path: Path):
    bind_capability(tmp_path)
    protected_runner = FakeReconciler(snapshot(position=1, protected=True))
    supervisor = G073ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=lambda cycle, now: run_g073_reconciliation_cycle_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id=cycle,
            reconciler=protected_runner,
            now_utc=now,
        ),
    )
    assert supervisor.tick(now_utc=NOW, arm_on=True)["effective_state"] == "ON_EXIT_ONLY"
    root2 = tmp_path / "unknown"
    unknown = FakeReconciler(snapshot(position=1, protected=False))
    halted = G073ResidentSupervisor(
        state_root=root2,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=lambda cycle, now: run_g073_reconciliation_cycle_once(
            state_root=root2,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id=cycle,
            reconciler=unknown,
            now_utc=now,
        ),
    ).tick(now_utc=NOW, arm_on=True)
    assert halted["effective_state"] == "HALTED"
    assert halted["entry_gate_open"] is False


def test_action_dispatchers_are_one_shot_fake_only(tmp_path: Path):
    port = FakePort(
        {
            G073Action.ENTRY: G073ActionOutcome.ACCEPTED,
            G073Action.PROTECTION: G073ActionOutcome.PROTECTED,
            G073Action.CANCEL_PROTECTION: G073ActionOutcome.ACCEPTED,
            G073Action.CLOSE_POSITION: G073ActionOutcome.FLAT,
        }
    )
    actions = G073OneShotActionDispatcher.bound(
        state_root=tmp_path, port=port, generation_digest=GEN, reviewed_files_digest=REVIEWED
    )
    entry = G073EntryDispatcher(actions=actions)
    decision = G073FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    ).evaluate(
        now_utc=NOW,
        evidence=run_g073_reconciliation_cycle_once(
            state_root=tmp_path / "recon",
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id="cycle-1",
            reconciler=FakeReconciler(snapshot()),
            now_utc=NOW,
        ),
    )
    evidence = run_g073_reconciliation_cycle_once(
        state_root=tmp_path / "recon2",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="cycle-2",
        reconciler=FakeReconciler(snapshot()),
        now_utc=NOW,
    )
    entry.enter_and_protect_once(
        decision=decision, evidence=evidence, cycle_id="action-1", side="BUY", now_utc=NOW
    )
    assert port.calls == [G073Action.ENTRY, G073Action.PROTECTION]
    exit_dispatcher = G073ExitDispatcher(
        actions=G073OneShotActionDispatcher.bound(
            state_root=tmp_path / "exit",
            port=port,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
        )
    )
    protected = run_g073_reconciliation_cycle_once(
        state_root=tmp_path / "recon3",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="cycle-3",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    exit_dispatcher.exit_once(
        evidence=protected,
        cycle_id="action-2",
        side="BUY",
        reason=G073Action.TIME_EXIT,
        now_utc=NOW,
    )
    assert port.calls[-2:] == [G073Action.CANCEL_PROTECTION, G073Action.CLOSE_POSITION]


def test_restart_health_and_arm_off_are_fail_closed(tmp_path: Path):
    bind_capability(tmp_path)
    status = G073ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=NOW, arm_on=False, process_lock_single=False)
    assert status["effective_state"] == "HALTED"
    assert status["entry_gate_open"] is False
