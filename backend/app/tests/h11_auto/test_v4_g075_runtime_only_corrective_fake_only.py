"""Fake-only tests for the final G075 runtime connection contract."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g075_runtime import (
    G075Action,
    G075ActionOutcome,
    G075EffectiveState,
    G075EntryDispatcher,
    G075EntryState,
    G075Error,
    G075ExitDispatcher,
    G075FrozenStrategyEvaluator,
    G075OneShotActionDispatcher,
    G075ReconciliationState,
    G075ResidentSupervisor,
    G075SanitizedSnapshot,
    G075StrategyObservation,
    build_g075_recovery_scope,
    run_g075_initial_atomic_activation,
    run_g075_reconciliation_cycle_once,
    safe_g075_api_status,
    verify_g075_scheduler_binding,
)
from app.services.h11_v4_gmo_actual_transport import (
    V4GmoActualTransportError,
    V4GmoHttpxPrivateTransport,
    V4GmoSealedSecret,
    V4GmoSignedRequestFactory,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
GEN = "sha256:" + "1" * 64
REVIEWED = "sha256:" + "2" * 64
STRATEGY = "sha256:" + "3" * 64


class FakeReconciler:
    def __init__(self, snapshot: G075SanitizedSnapshot):
        self.snapshot = snapshot
        self.calls = 0

    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G075SanitizedSnapshot:
        self.calls += 1
        return self.snapshot


class FakeSource:
    def __init__(self, *, actionable: bool):
        self.actionable = actionable

    def observe(self, *, now_utc: datetime) -> G075StrategyObservation:
        return G075StrategyObservation(
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


class FakePort:
    def __init__(self, outcomes: dict[G075Action, G075ActionOutcome]):
        self.outcomes = outcomes
        self.calls: list[G075Action] = []

    def attempt_once(self, scope):
        self.calls.append(scope.action)
        return self.outcomes[scope.action]


class FakeCredentialPair:
    def unseal_for_internal_request_only(self):
        return V4GmoSealedSecret("fake-key"), V4GmoSealedSecret("fake-secret")


def snapshot(*, position: int = 0, protected: bool = False) -> G075SanitizedSnapshot:
    return G075SanitizedSnapshot(
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
        "schema": "H11_V4_G075_SWITCH_CONTROL_CAPABILITY_V1",
        "generation_label": "H11_AUTO_30M_20260802_G075",
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
    (root / "g075-switch-control-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest})
    )
    (root / "g075-release-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest})
    )
    outcome = {
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260802_G075",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
    }
    outcome_digest = "sha256:" + hashlib.sha256(
        json.dumps(outcome, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (root / "g075-initial-activation.outcome.json").write_text(
        json.dumps({**outcome, "artifact_digest": outcome_digest})
    )
    (root / "g075-operation-60.result.json").write_text(
        json.dumps(
            {
                "status": "PASSED",
                "generation_label": "H11_AUTO_30M_20260802_G075",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
def test_cycle_is_single_attempt_and_flat(tmp_path: Path):
    runner = FakeReconciler(snapshot())
    evidence = run_g075_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="cycle-1",
        reconciler=runner,
        now_utc=NOW,
    )
    assert evidence.state is G075ReconciliationState.FRESH_FLAT
    assert runner.calls == 1
    with pytest.raises(G075Error, match="ALREADY_STARTED_NO_RETRY"):
        run_g075_reconciliation_cycle_once(
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
    evaluator = G075FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    )
    supervisor = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
        reconciliation_runner=lambda cycle, now: run_g075_reconciliation_cycle_once(
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
    assert status["effective_state"] == G075EffectiveState.ON_WAITING.value
    assert status["entry_gate_open"] is True
    assert status["entry_state"] == G075EntryState.ENTRY_READY.value
    assert status["broker_write"] is False
    assert status["private_api_read_count"] == 0


def test_protected_position_is_exit_only_and_unconfirmed_halts(tmp_path: Path):
    bind_capability(tmp_path)
    protected_runner = FakeReconciler(snapshot(position=1, protected=True))
    supervisor = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
        reconciliation_runner=lambda cycle, now: run_g075_reconciliation_cycle_once(
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
    halted = G075ResidentSupervisor(
        state_root=root2,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
        reconciliation_runner=lambda cycle, now: run_g075_reconciliation_cycle_once(
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
            G075Action.ENTRY: G075ActionOutcome.ACCEPTED,
            G075Action.PROTECTION: G075ActionOutcome.PROTECTED,
            G075Action.CANCEL_PROTECTION: G075ActionOutcome.ACCEPTED,
            G075Action.CLOSE_POSITION: G075ActionOutcome.FLAT,
        }
    )
    actions = G075OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=port,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        release_capability_digest="sha256:" + "c" * 64,
        strategy_artifact_digest=STRATEGY,
    )
    entry = G075EntryDispatcher(actions=actions)
    decision = G075FrozenStrategyEvaluator(
        source=FakeSource(actionable=True),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    ).evaluate(
        now_utc=NOW,
        evidence=run_g075_reconciliation_cycle_once(
            state_root=tmp_path / "recon",
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            cycle_id="cycle-1",
            reconciler=FakeReconciler(snapshot()),
            now_utc=NOW,
        ),
    )
    evidence = run_g075_reconciliation_cycle_once(
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
    assert port.calls == [G075Action.ENTRY, G075Action.PROTECTION]
    exit_dispatcher = G075ExitDispatcher(
        actions=G075OneShotActionDispatcher.bound(
            state_root=tmp_path / "exit",
            port=port,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            release_capability_digest="sha256:" + "c" * 64,
            strategy_artifact_digest=STRATEGY,
        )
    )
    protected = run_g075_reconciliation_cycle_once(
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
        reason=G075Action.TIME_EXIT,
        now_utc=NOW,
    )
    assert port.calls[-2:] == [G075Action.CANCEL_PROTECTION, G075Action.CLOSE_POSITION]


def test_restart_health_and_arm_off_are_fail_closed(tmp_path: Path):
    bind_capability(tmp_path)
    status = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    ).tick(now_utc=NOW, arm_on=False, process_lock_single=False)
    assert status["effective_state"] == "HALTED"
    assert status["entry_gate_open"] is False


def test_initial_activation_is_one_shot_and_enables_switch_only_after_pass(tmp_path: Path):
    import json

    (tmp_path / "g075-operation-60.result.json").write_text(
        json.dumps(
            {
                "status": "PASSED",
                "generation_label": "H11_AUTO_30M_20260802_G075",
                "generation_digest": GEN,
                "reviewed_files_digest": REVIEWED,
            }
        )
    )
    evidence = run_g075_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="initial-flat",
        reconciler=FakeReconciler(snapshot()),
        now_utc=NOW,
    )
    mutations: list[str] = []
    assert (
        run_g075_initial_atomic_activation(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            reconciliation_runner=lambda: evidence,
            arm_mutator=lambda: mutations.append("ON"),
            arm_state_verifier=lambda: mutations == ["ON"],
            now_utc=NOW,
        )
        == "PASSED"
    )
    assert mutations == ["ON"]
    status = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    ).tick(now_utc=NOW, arm_on=True)
    assert status["release_state"] == "ENABLED"
    assert status["effective_state"] == "ON_WAITING"
    assert status["entry_state"] == "WAITING_FOR_SIGNAL"
    with pytest.raises(G075Error, match="ONE_USE_MARKER"):
        run_g075_initial_atomic_activation(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            reconciliation_runner=lambda: evidence,
            arm_mutator=lambda: None,
            arm_state_verifier=lambda: True,
            now_utc=NOW,
        )


def test_recovery_scope_requires_explicit_owned_quantity_and_protection(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g075_reconciliation_cycle_once(
        state_root=tmp_path / "protected",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="recovery-protected",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    scope = build_g075_recovery_scope(
        repository=tmp_path,
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
        state=G075ReconciliationState.UNKNOWN,
        ownership_exact=False,
        quantity_matches=False,
        protection_confirmed=False,
    )
    with pytest.raises(G075Error, match="RECOVERY_EVIDENCE_NOT_CLEAR"):
        build_g075_recovery_scope(
            repository=tmp_path,
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            evidence=unconfirmed,
            side="BUY",
            action_key="sha256:" + "6" * 64,
            now_utc=NOW,
        )


def test_recovered_exit_transport_requires_exact_opaque_scope(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g075_reconciliation_cycle_once(
        state_root=tmp_path / "protected-transport",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="recovery-transport",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    scope = build_g075_recovery_scope(
        repository=tmp_path,
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        evidence=protected,
        side="BUY",
        action_key="sha256:" + "7" * 64,
        now_utc=NOW,
    )
    transport = V4GmoHttpxPrivateTransport(
        recovered_exit_scope=scope,
        signed_request_factory=V4GmoSignedRequestFactory(
            credential_pair=FakeCredentialPair()
        ),
        unknown_post_callback=lambda: None,
        wall_clock_factory=lambda: NOW,
    )
    assert bool(transport) is False
    transport.close()
    with pytest.raises(V4GmoActualTransportError, match="RECOVERY_SCOPE_INVALID"):
        V4GmoHttpxPrivateTransport(
            recovered_exit_scope=replace(scope, scope_digest="sha256:" + "0" * 64),
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=FakeCredentialPair()
            ),
            unknown_post_callback=lambda: None,
            wall_clock_factory=lambda: NOW,
        )


def test_resident_cycle_ids_do_not_collide_across_restarts(tmp_path: Path):
    first = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    )
    second = G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    )
    assert first._next_cycle() != second._next_cycle()


def test_arm_control_availability_is_not_entry_readiness(tmp_path: Path):
    bind_capability(tmp_path)
    status = safe_g075_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    )
    assert status["arm_control_available"] is True
    assert status["arm_ready"] is True
    assert status["entry_gate_open"] is False


def test_release_locked_contract_keeps_control_available_for_safe_refusal(tmp_path: Path):
    status = safe_g075_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    )
    assert status["release_state"] == "LOCKED"
    assert status["runtime_activation_available"] is False
    assert status["arm_control_available"] is True
    assert status["local_arm_on_available"] is True
    assert status["arm_ready"] is True
    assert status["entry_gate_open"] is False


def test_capability_rejects_mismatched_operation_binding(tmp_path: Path):
    import json

    bind_capability(tmp_path)
    operation = json.loads((tmp_path / "g075-operation-60.result.json").read_text())
    operation["generation_digest"] = "sha256:" + "9" * 64
    (tmp_path / "g075-operation-60.result.json").write_text(json.dumps(operation))
    status = safe_g075_api_status(
        state_root=tmp_path,
        arm_on=False,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    )
    assert status["release_state"] == "LOCKED"
    assert status["runtime_activation_available"] is False


def test_recovery_scope_is_action_bound_and_one_use(tmp_path: Path):
    bind_capability(tmp_path)
    protected = run_g075_reconciliation_cycle_once(
        state_root=tmp_path / "protected-one-use",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="recovery-one-use",
        reconciler=FakeReconciler(snapshot(position=1, protected=True)),
        now_utc=NOW,
    )
    kwargs = {
        "repository": tmp_path,
        "state_root": tmp_path,
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "evidence": protected,
        "side": "BUY",
        "action_key": "sha256:" + "8" * 64,
        "now_utc": NOW,
    }
    build_g075_recovery_scope(**kwargs)
    with pytest.raises(G075Error, match="ONE_USE_MARKER"):
        build_g075_recovery_scope(**kwargs)


def test_scheduler_binding_requires_exact_arguments_live_pid_and_chain(tmp_path: Path):
    import json
    import os
    import plistlib
    from types import SimpleNamespace

    repository = Path(__file__).resolve().parents[4]
    bind_capability(tmp_path)
    G075ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        repository=tmp_path,
    ).tick(now_utc=NOW, arm_on=False)
    (tmp_path / "process.lock").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "generation_label": "H11_AUTO_30M_20260802_G075",
            }
        )
    )
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260802_G075",
        digest=GEN,
        implementation_digest=REVIEWED,
    )
    arguments = [
        str((repository / "backend/.venv/bin/python").resolve()),
        str(repository / "backend/scripts/h11_auto_v4_g075_runtime_bootstrap.py"),
        "--repository",
        str(repository),
        "--expected-reviewed-files-digest",
        REVIEWED,
        "--expected-generation-digest",
        GEN,
    ]
    plist = tmp_path / "scheduler.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": arguments}))
    verify_g075_scheduler_binding(
        generation=generation,
        repository=repository,
        plist_path=plist,
        state_root=tmp_path,
        now_utc=NOW,
    )

    swapped = list(arguments)
    swapped[3], swapped[5] = swapped[5], swapped[3]
    plist.write_bytes(plistlib.dumps({"ProgramArguments": swapped}))
    with pytest.raises(G075Error, match="SCHEDULER_BINDING_INVALID"):
        verify_g075_scheduler_binding(
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
                "generation_label": "H11_AUTO_30M_20260802_G075",
            }
        )
    )
    with pytest.raises(G075Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g075_scheduler_binding(
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
                "generation_label": "H11_AUTO_30M_20260802_G075",
            }
        )
    )
    chain_path = tmp_path / "heartbeat-chain.json"
    chain = json.loads(chain_path.read_text())
    chain["chain_hash"] = "sha256:" + "0" * 64
    chain_path.write_text(json.dumps(chain))
    with pytest.raises(G075Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g075_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist,
            state_root=tmp_path,
            now_utc=NOW,
        )


def test_operation_60_renders_the_exact_workspace_interpreter():
    repository = Path(__file__).resolve().parents[4]
    source = (
        repository / "backend/scripts/h11_auto_v4_g075_operation_60_no_post.py"
    ).read_text()
    assert 'python_executable=repository / "backend/.venv/bin/python"' in source
    assert "Path(sys.executable)" not in source
