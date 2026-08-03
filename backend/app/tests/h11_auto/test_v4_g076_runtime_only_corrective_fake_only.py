"""Fake-only tests for the final G076 runtime connection contract."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.h11_v4_g076_network_diagnostics import (
    G076_PUBLIC_STATUS_URL,
    G076NetworkFailureClass,
    G076PublicClient,
    run_g076_public_preflight,
)
from app.services.h11_v4_g076_runtime import (
    G076Action,
    G076ActionOutcome,
    G076EffectiveState,
    G076EntryDispatcher,
    G076EntryState,
    G076Error,
    G076ExitDispatcher,
    G076FakeOnlyCallable,
    G076FakeOnlyPort,
    G076FrozenStrategyEvaluator,
    G076OneShotActionDispatcher,
    G076ProcessLock,
    G076ReconciliationState,
    G076ResidentSupervisor,
    G076SanitizedSnapshot,
    G076StrategyObservation,
    build_g076_recovery_scope,
    resume_g076_protected_exit_once,
    run_g076_initial_atomic_activation,
    run_g076_reconciliation_cycle_once,
    safe_g076_api_status,
    verify_g076_scheduler_binding,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
GEN = "sha256:" + "1" * 64
REVIEWED = "sha256:" + "2" * 64
STRATEGY = "sha256:" + "3" * 64


class FakePublicClient(G076PublicClient):
    def __init__(self, response: SimpleNamespace):
        self.response = response
        self.calls: list[str] = []

    def get(self, url: str) -> SimpleNamespace:
        self.calls.append(url)
        return self.response


def test_network_preflight_is_one_credential_free_public_attempt():
    client = FakePublicClient(SimpleNamespace(status_code=200))
    result = run_g076_public_preflight(client=client)
    assert result.status == "PASSED"
    assert result.failure_class is None
    assert result.public_get_count == 1
    assert result.private_api_read_count == 0
    assert result.credential_read_count == 0
    assert result.broker_post_count == 0
    assert client.calls == [G076_PUBLIC_STATUS_URL]


def test_network_preflight_maps_timeout_without_exposing_exception():
    class TimeoutClient(G076PublicClient):
        def get(self, url: str) -> object:
            raise TimeoutError("secret endpoint detail")

    result = run_g076_public_preflight(client=TimeoutClient())
    assert result.status == "FAILED"
    assert result.failure_class is G076NetworkFailureClass.READ_TIMEOUT
    assert result.public_get_count == 1
    assert result.private_api_read_count == 0
    assert result.credential_read_count == 0


class FakeReconciler(G076FakeOnlyPort):
    def __init__(self, snapshot: G076SanitizedSnapshot):
        self.snapshot = snapshot
        self.calls = 0

    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G076SanitizedSnapshot:
        self.calls += 1
        return self.snapshot


class FakeSource(G076FakeOnlyPort):
    def __init__(self, *, actionable: bool):
        self.actionable = actionable

    def observe(self, *, now_utc: datetime) -> G076StrategyObservation:
        return G076StrategyObservation(
            strategy_artifact_digest=STRATEGY,
            strategy_version="SHORT_V1",
            symbol="USD_JPY",
            quantity=1_000,
            side="BUY",
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


class FakePort(G076FakeOnlyPort):
    def __init__(self, outcomes: dict[G076Action, G076ActionOutcome]):
        self.outcomes = outcomes
        self.calls: list[G076Action] = []

    def attempt_once(self, scope):
        self.calls.append(scope.action)
        return self.outcomes[scope.action]


def snapshot(*, position: int = 0, protected: bool = False) -> G076SanitizedSnapshot:
    return G076SanitizedSnapshot(
        latest_execution_count=0,
        open_position_count=position,
        active_order_count=2 if protected else 0,
        position_side="BUY" if position else None,
        ownership_exact=protected,
        quantity_matches=protected,
        protection_confirmed=protected,
    )


def bind_capability(root: Path) -> None:
    base = {
        "schema": "H11_V4_G076_SWITCH_CONTROL_CAPABILITY_V1",
        "generation_label": "H11_AUTO_30M_20260802_G076",
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
    (root / "g076-switch-control-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest})
    )
    (root / "g076-release-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest})
    )
    outcome = {
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260802_G076",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
    }
    outcome_digest = "sha256:" + hashlib.sha256(
        json.dumps(outcome, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (root / "g076-initial-activation.outcome.json").write_text(
        json.dumps({**outcome, "artifact_digest": outcome_digest})
    )
    operation = {
        "schema": "H11_V4_G076_OPERATION_60_RESULT_V1",
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260802_G076",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
        "actual_post_authorized": False,
    }
    operation_digest = "sha256:" + hashlib.sha256(
        json.dumps(operation, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (root / "g076-operation-60.result.json").write_text(
        json.dumps({**operation, "artifact_digest": operation_digest})
    )
def test_cycle_is_single_attempt_and_flat(tmp_path: Path):
    runner = FakeReconciler(snapshot())
    evidence = run_g076_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="cycle-1",
        reconciler=runner,
        now_utc=NOW,
    )
    assert evidence.state is G076ReconciliationState.FRESH_FLAT
    assert runner.calls == 1
    with pytest.raises(G076Error, match="ALREADY_STARTED_NO_RETRY"):
        run_g076_reconciliation_cycle_once(
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
    evaluator = G076FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    )
    supervisor = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=tmp_path,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=runner,
                now_utc=now,
            )
        ),
        strategy_evaluator=evaluator,
    )
    status = supervisor.tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == G076EffectiveState.ON_WAITING.value
    assert status["entry_gate_open"] is True
    assert status["entry_state"] == G076EntryState.ENTRY_READY.value
    assert status["broker_write"] is False
    assert status["private_api_read_count"] == 0


def test_entry_action_invalidates_flat_evidence_for_next_cycle(tmp_path: Path):
    bind_capability(tmp_path)
    runner = FakeReconciler(snapshot())
    evaluator = G076FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    )
    port = FakePort(
        {
            G076Action.ENTRY: G076ActionOutcome.ACCEPTED,
            G076Action.PROTECTION: G076ActionOutcome.PROTECTED,
        }
    )
    actions = G076OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=port,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        release_capability_digest="sha256:" + "c" * 64,
        strategy_artifact_digest=STRATEGY,
    )
    supervisor = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=tmp_path,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=runner,
                now_utc=now,
            )
        ),
        strategy_evaluator=evaluator,
        entry_dispatcher=G076EntryDispatcher(actions=actions),
    )
    supervisor.tick(now_utc=NOW, arm_on=True)
    supervisor.tick(now_utc=NOW, arm_on=True)
    assert runner.calls == 2


def test_protected_position_is_exit_only_and_unconfirmed_halts(tmp_path: Path):
    bind_capability(tmp_path)
    protected_runner = FakeReconciler(snapshot(position=1, protected=True))
    supervisor = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=tmp_path,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=protected_runner,
                now_utc=now,
            )
        ),
    )
    assert supervisor.tick(now_utc=NOW, arm_on=True)["effective_state"] == "ON_EXIT_ONLY"
    root2 = tmp_path / "unknown"
    unknown = FakeReconciler(snapshot(position=1, protected=False))
    halted = G076ResidentSupervisor(
        state_root=root2,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=root2,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=unknown,
                now_utc=now,
            )
        ),
    ).tick(now_utc=NOW, arm_on=True)
    assert halted["effective_state"] == "HALTED"
    assert halted["entry_gate_open"] is False

    multi_root = tmp_path / "multi"
    multi = FakeReconciler(snapshot(position=2, protected=True))
    multi_status = G076ResidentSupervisor(
        state_root=multi_root,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=multi_root,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=multi,
                now_utc=now,
            )
        ),
    ).tick(now_utc=NOW, arm_on=True)
    assert multi_status["effective_state"] == "HALTED"
    assert multi_status["entry_gate_open"] is False


def test_release_locked_protected_position_halts_before_exit_projection(tmp_path: Path):
    runner = FakeReconciler(snapshot(position=1, protected=True))
    status = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G076FakeOnlyCallable(
            lambda cycle, now: run_g076_reconciliation_cycle_once(
                state_root=tmp_path,
                generation_digest=GEN,
                reviewed_files_digest=REVIEWED,
                cycle_id=cycle,
                reconciler=runner,
                now_utc=now,
            )
        ),
    ).tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] == G076EffectiveState.HALTED.value
    assert status["entry_gate_open"] is False
    assert status["entry_state"] == G076EntryState.HALTED.value


def test_stale_process_lock_is_not_deleted_or_reacquired(tmp_path: Path):
    import json

    lock_path = tmp_path / "process.lock"
    lock_path.write_text(
        json.dumps(
            {
                "pid": 99_999_999,
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    lock = G076ProcessLock(
        tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    with pytest.raises(G076Error, match="G076_PROCESS_LOCK_STALE"):
        lock.acquire()
    assert lock_path.exists()
    assert lock.held is False


def test_live_process_lock_conflict_is_rejected_without_replacement(tmp_path: Path):
    import json
    import os

    lock_path = tmp_path / "process.lock"
    lock_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    lock = G076ProcessLock(
        tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    with pytest.raises(G076Error, match="G076_PROCESS_LOCK_CONFLICT"):
        lock.acquire()
    assert lock_path.exists()
    assert lock.held is False


def test_stale_heartbeat_is_not_ready(tmp_path: Path):
    import json
    import os

    bind_capability(tmp_path)
    old = NOW - timedelta(seconds=120)
    G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=old, arm_on=False)
    (tmp_path / "process.lock").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        now_utc=NOW,
    )
    assert status["control_plane_state"] == "HALTED"
    assert status["scheduler_ready"] is False


def test_action_dispatchers_are_one_shot_fake_only(tmp_path: Path):
    port = FakePort(
        {
            G076Action.ENTRY: G076ActionOutcome.ACCEPTED,
            G076Action.PROTECTION: G076ActionOutcome.PROTECTED,
            G076Action.CANCEL_PROTECTION: G076ActionOutcome.ACCEPTED,
            G076Action.CLOSE_POSITION: G076ActionOutcome.FLAT,
        }
    )
    actions = G076OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=port,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        release_capability_digest="sha256:" + "c" * 64,
        strategy_artifact_digest=STRATEGY,
    )
    entry = G076EntryDispatcher(actions=actions)
    decision = G076FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    ).evaluate(
        now_utc=NOW,
        evidence=run_g076_reconciliation_cycle_once(
            state_root=tmp_path / "recon",
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id="cycle-1",
            reconciler=FakeReconciler(snapshot()),
            now_utc=NOW,
        ),
    )
    evidence = run_g076_reconciliation_cycle_once(
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
    assert port.calls == [G076Action.ENTRY, G076Action.PROTECTION]
    exit_dispatcher = G076ExitDispatcher(
        actions=G076OneShotActionDispatcher.bound(
            state_root=tmp_path / "exit",
            port=port,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            release_capability_digest="sha256:" + "c" * 64,
            strategy_artifact_digest=STRATEGY,
        )
    )
    protected = run_g076_reconciliation_cycle_once(
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
        reason=G076Action.TIME_EXIT,
        now_utc=NOW,
    )
    assert port.calls[-2:] == [G076Action.CANCEL_PROTECTION, G076Action.CLOSE_POSITION]


def test_action_dispatcher_rejects_non_fake_port(tmp_path: Path):
    class NonFakePort:
        def attempt_once(self, scope):
            return G076ActionOutcome.ACCEPTED

    with pytest.raises(G076Error, match="G076_FAKE_ONLY_ACTION_PORT_REQUIRED"):
        G076OneShotActionDispatcher.bound(
            state_root=tmp_path,
            port=NonFakePort(),
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            release_capability_digest="sha256:" + "c" * 64,
            strategy_artifact_digest=STRATEGY,
        )


def test_fake_only_markers_reject_external_modules():
    with pytest.raises(TypeError, match="G076_FAKE_ONLY_PORT_MODULE_REQUIRED"):
        type(
            "ExternalPort",
            (G076FakeOnlyPort,),
            {"__module__": "app.services.h11_v4_gmo_actual_transport"},
        )

    def external_callback() -> None:
        return None

    external_callback.__module__ = "app.services.h11_v4_gmo_actual_transport"
    with pytest.raises(G076Error, match="G076_FAKE_ONLY_CALLABLE_MODULE_REQUIRED"):
        G076FakeOnlyCallable(external_callback)


def test_restart_health_and_arm_off_are_fail_closed(tmp_path: Path):
    bind_capability(tmp_path)
    status = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=NOW, arm_on=False, process_lock_single=False)
    assert status["effective_state"] == "HALTED"
    assert status["entry_gate_open"] is False


def test_initial_activation_is_one_shot_and_enables_switch_only_after_pass(tmp_path: Path):
    import hashlib
    import json

    operation = {
        "schema": "H11_V4_G076_OPERATION_60_RESULT_V1",
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260802_G076",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
        "actual_post_authorized": False,
    }
    operation_digest = "sha256:" + hashlib.sha256(
        json.dumps(operation, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (tmp_path / "g076-operation-60.result.json").write_text(
        json.dumps({**operation, "artifact_digest": operation_digest})
    )
    evidence = run_g076_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="initial-flat",
        reconciler=FakeReconciler(snapshot()),
        now_utc=NOW,
    )
    mutations: list[str] = []

    def mutate() -> None:
        assert not (tmp_path / "g076-release-capability.json").exists()
        assert not (tmp_path / "g076-switch-control-capability.json").exists()
        mutations.append("ON")

    assert (
        run_g076_initial_atomic_activation(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            reconciliation_runner=G076FakeOnlyCallable(lambda: evidence),
            resident_readiness_verifier=G076FakeOnlyCallable(lambda: True),
            arm_mutator=G076FakeOnlyCallable(mutate),
            arm_state_verifier=G076FakeOnlyCallable(lambda: mutations == ["ON"]),
            now_utc=NOW,
        )
        == "PASSED"
    )
    assert mutations == ["ON"]
    status = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=NOW, arm_on=True)
    assert status["release_state"] == "ENABLED"
    assert status["effective_state"] == "ON_WAITING"
    assert status["entry_state"] == "WAITING_FOR_SIGNAL"
    with pytest.raises(G076Error, match="ONE_USE_MARKER"):
        run_g076_initial_atomic_activation(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            reconciliation_runner=G076FakeOnlyCallable(lambda: evidence),
            resident_readiness_verifier=G076FakeOnlyCallable(lambda: True),
            arm_mutator=G076FakeOnlyCallable(lambda: None),
            arm_state_verifier=G076FakeOnlyCallable(lambda: True),
            now_utc=NOW,
        )


def test_recovery_scope_requires_explicit_owned_quantity_and_protection(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g076_reconciliation_cycle_once(
        state_root=tmp_path / "protected",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="recovery-protected",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    scope = build_g076_recovery_scope(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        evidence=protected,
        side="BUY",
        action_key="sha256:" + "5" * 64,
        now_utc=NOW,
    )
    assert bool(scope) is False
    assert scope.ownership_exact is True
    assert scope.quantity_matches is True
    assert scope.protection_confirmed is True

    unconfirmed = replace(
        protected,
        state=G076ReconciliationState.UNKNOWN,
        ownership_exact=False,
        quantity_matches=False,
        protection_confirmed=False,
    )
    with pytest.raises(G076Error, match="RECOVERY_EVIDENCE_NOT_CLEAR"):
        build_g076_recovery_scope(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            evidence=unconfirmed,
            side="BUY",
            action_key="sha256:" + "6" * 64,
            now_utc=NOW,
        )


def test_resident_cycle_ids_do_not_collide_across_restarts(tmp_path: Path):
    first = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    second = G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    assert first._next_cycle() != second._next_cycle()


def test_arm_control_availability_is_not_entry_readiness(tmp_path: Path):
    bind_capability(tmp_path)
    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    assert status["arm_control_available"] is False
    assert status["arm_ready"] is False
    assert status["entry_gate_open"] is False


def test_release_locked_contract_keeps_control_available_for_safe_refusal(tmp_path: Path):
    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    assert status["release_state"] == "LOCKED"
    assert status["runtime_activation_available"] is False
    assert status["arm_control_available"] is False
    assert status["local_arm_on_available"] is False
    assert status["arm_ready"] is False
    assert status["entry_gate_open"] is False


def test_capability_rejects_mismatched_operation_binding(tmp_path: Path):
    import json

    bind_capability(tmp_path)
    operation = json.loads((tmp_path / "g076-operation-60.result.json").read_text())
    operation["generation_digest"] = "sha256:" + "9" * 64
    (tmp_path / "g076-operation-60.result.json").write_text(json.dumps(operation))
    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    )
    assert status["release_state"] == "LOCKED"
    assert status["runtime_activation_available"] is False


def test_recovery_scope_is_action_bound_and_one_use(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g076_reconciliation_cycle_once(
        state_root=tmp_path / "protected-one-use",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="recovery-one-use",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    kwargs = {
        "state_root": tmp_path,
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "evidence": protected,
        "side": "BUY",
        "action_key": "sha256:" + "8" * 64,
        "now_utc": NOW,
    }
    build_g076_recovery_scope(**kwargs)
    with pytest.raises(G076Error, match="ONE_USE_MARKER"):
        build_g076_recovery_scope(**kwargs)


def test_restart_resumes_existing_protected_scope_once(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g076_reconciliation_cycle_once(
        state_root=tmp_path / "protected-restart",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="restart-cycle",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    scope = build_g076_recovery_scope(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        evidence=protected,
        side="BUY",
        action_key="sha256:" + "7" * 64,
        now_utc=NOW,
    )

    def fake_exit(loaded_scope):
        assert loaded_scope.scope_digest == scope.scope_digest
        return G076ActionOutcome.FLAT

    assert (
        resume_g076_protected_exit_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            recovery_action=G076FakeOnlyCallable(fake_exit),
            now_utc=NOW,
        )
        is G076ActionOutcome.FLAT
    )
    with pytest.raises(G076Error, match="ALREADY_RESUMED"):
        resume_g076_protected_exit_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            recovery_action=G076FakeOnlyCallable(fake_exit),
            now_utc=NOW,
        )


def test_scheduler_binding_requires_exact_arguments_live_pid_and_chain(tmp_path: Path):
    import json
    import os
    import plistlib
    from types import SimpleNamespace

    repository = Path(__file__).resolve().parents[4]
    bind_capability(tmp_path)
    G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=NOW, arm_on=False)
    (tmp_path / "process.lock").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260802_G076",
        digest=GEN,
        implementation_digest=REVIEWED,
    )
    arguments = [
        str((repository / "backend/.venv/bin/python").resolve()),
        str(repository / "backend/scripts/h11_auto_v4_g076_runtime_bootstrap.py"),
        "--repository",
        str(repository),
        "--expected-reviewed-files-digest",
        REVIEWED,
        "--expected-generation-digest",
        GEN,
    ]
    plist = tmp_path / "scheduler.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": arguments}))
    verify_g076_scheduler_binding(
        generation=generation,
        repository=repository,
        plist_path=plist,
        state_root=tmp_path,
        now_utc=NOW,
    )

    heartbeat = json.loads((tmp_path / "heartbeat.json").read_text())
    heartbeat["broker_read"] = True
    (tmp_path / "heartbeat.json").write_text(json.dumps(heartbeat))
    with pytest.raises(G076Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g076_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=NOW,
        )
    G076ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
    ).tick(now_utc=NOW, arm_on=False)

    swapped = list(arguments)
    swapped[3], swapped[5] = swapped[5], swapped[3]
    plist.write_bytes(plistlib.dumps({"ProgramArguments": swapped}))
    with pytest.raises(G076Error, match="SCHEDULER_BINDING_INVALID"):
        verify_g076_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=NOW,
        )

    plist.write_bytes(plistlib.dumps({"ProgramArguments": arguments}))
    (tmp_path / "process.lock").write_text(
        json.dumps(
            {
                "pid": 999_999_999,
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    with pytest.raises(G076Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g076_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=NOW,
        )

    (tmp_path / "process.lock").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "generation_label": "H11_AUTO_30M_20260802_G076",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    chain_path = tmp_path / "heartbeat-chain.json"
    chain = json.loads(chain_path.read_text())
    chain["chain_hash"] = "sha256:" + "0" * 64
    chain_path.write_text(json.dumps(chain))
    with pytest.raises(G076Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g076_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=NOW,
        )


def test_operation_60_cli_refuses_real_installer_execution():
    repository = Path(__file__).resolve().parents[4]
    source = (
        repository / "backend/scripts/h11_auto_v4_g076_operation_60_no_post.py"
    ).read_text()
    assert "launchctl" not in source
    assert "install_and_restart_v4_gmo_unattended_scheduler_launchagent" not in source
    assert 'G076_OPERATION_60_FAKE_ONLY_CANDIDATE' in source
    assert "Path(sys.executable)" not in source
