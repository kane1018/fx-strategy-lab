from __future__ import annotations

import hashlib
import json
import os
import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.h11_v4_g070_candidate import (
    ArmState,
    ControlPlaneState,
    EffectiveState,
    EntryState,
    G070Action,
    G070ActionScopeStore,
    G070Error,
    G070ProjectionInput,
    G070ReleaseCapability,
    G070ResidentSupervisor,
    ReconciliationState,
    activate_g070_release_once,
    load_g070_reconciliation,
    load_g070_release_capability,
    project_g070_runtime,
    run_g070_reconciliation_slot,
    safe_g070_api_status,
    verify_g070_review_artifacts,
    verify_g070_scheduler_binding,
)
from app.services.h11_v4_g070_scoped_action_candidate import (
    G070ActionOutcome,
    G070FakeActionPort,
    G070FakeLifecycleDriver,
    G070ScopedActionCoordinator,
)
from scripts.h11_auto_v4_g070_operation_60_no_post import run_g070_operation_60_candidate

DIGEST = "sha256:" + "1" * 64
REVIEWED = "sha256:" + "2" * 64
NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("arm", "reconciliation", "position", "confirmed", "effective", "entry"),
    [
        (
            ArmState.OFF,
            ReconciliationState.FRESH_FLAT,
            False,
            False,
            EffectiveState.OFF,
            EntryState.DISARMED,
        ),
        (
            ArmState.ON,
            ReconciliationState.REQUIRED,
            False,
            False,
            EffectiveState.RECOVERING,
            EntryState.RECOVERING_RECONCILIATION,
        ),
        (
            ArmState.ON,
            ReconciliationState.IN_PROGRESS,
            False,
            False,
            EffectiveState.RECOVERING,
            EntryState.RECOVERING_RECONCILIATION,
        ),
        (
            ArmState.ON,
            ReconciliationState.FRESH_FLAT,
            False,
            False,
            EffectiveState.ON_WAITING,
            EntryState.WAITING_FOR_SIGNAL,
        ),
        (
            ArmState.ON,
            ReconciliationState.FRESH_PROTECTED,
            True,
            True,
            EffectiveState.ON_EXIT_ONLY,
            EntryState.POSITION_OPEN,
        ),
        (
            ArmState.OFF,
            ReconciliationState.FRESH_PROTECTED,
            True,
            True,
            EffectiveState.EXIT_ONLY,
            EntryState.POSITION_OPEN,
        ),
    ],
)
def test_state_dimensions_are_independent(
    arm, reconciliation, position, confirmed, effective, entry
):
    result = project_g070_runtime(
        G070ProjectionInput(
            ControlPlaneState.READY,
            reconciliation,
            arm,
            position_open=position,
            ownership_exact=confirmed,
            quantity_matches=confirmed,
            protection_confirmed=confirmed,
            entry_gates_clear=True,
        )
    )
    assert result.effective_state is effective
    assert result.entry_state is entry
    assert result.entry_gate_open is (effective is EffectiveState.ON_WAITING)


@pytest.mark.parametrize("field", ["ownership_exact", "quantity_matches", "protection_confirmed"])
def test_unconfirmed_position_halts(field):
    values = dict(ownership_exact=True, quantity_matches=True, protection_confirmed=True)
    values[field] = False
    result = project_g070_runtime(
        G070ProjectionInput(
            ControlPlaneState.READY,
            ReconciliationState.FRESH_PROTECTED,
            ArmState.ON,
            position_open=True,
            **values,
        )
    )
    assert result.effective_state is EffectiveState.HALTED
    assert result.entry_gate_open is False


class FakeCredentials:
    calls = 0
    marker: Path | None = None

    def load_sealed(self):
        self.calls += 1
        assert self.marker is not None and self.marker.exists()
        return object()


class FakeClient:
    def __init__(self, positions=(), orders=(), executions=()):
        self.positions, self.orders, self.executions = positions, orders, executions
        self.calls: list[str] = []

    def latest_executions(self, _credential):
        self.calls.append("latestExecutions")
        return self.executions

    def open_positions(self, _credential):
        self.calls.append("openPositions")
        return self.positions

    def active_orders(self, _credential):
        self.calls.append("activeOrders")
        return self.orders


def test_reconciliation_once_per_slot_chain_and_stale(tmp_path: Path):
    credentials = FakeCredentials()
    credentials.marker = (
        tmp_path / "g070-reconciliation-slots" / f"{int(NOW.timestamp()) // 30}.started.json"
    )
    client = FakeClient()
    evidence = run_g070_reconciliation_slot(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        credential_loader=credentials,
        client=client,
        ownership_matcher=lambda *_: (False, False, False),
        now_utc=NOW,
    )
    assert evidence.state is ReconciliationState.FRESH_FLAT
    assert client.calls == ["latestExecutions", "openPositions", "activeOrders"]
    assert credentials.calls == 1
    persisted = (tmp_path / "g070-reconciliation-current.json").read_text()
    assert "credential_value" not in persisted.lower() and "identifier" not in persisted.lower()
    with pytest.raises(G070Error, match="ALREADY_ATTEMPTED"):
        run_g070_reconciliation_slot(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            credential_loader=credentials,
            client=client,
            ownership_matcher=lambda *_: (False, False, False),
            now_utc=NOW,
        )
    stale = load_g070_reconciliation(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        now_utc=NOW + timedelta(seconds=61),
    )
    assert stale is not None and stale.state is ReconciliationState.STALE


def test_protected_requires_exact_match(tmp_path: Path):
    credentials = FakeCredentials()
    credentials.marker = (
        tmp_path / "g070-reconciliation-slots" / f"{int(NOW.timestamp()) // 30}.started.json"
    )
    evidence = run_g070_reconciliation_slot(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        credential_loader=credentials,
        client=FakeClient(positions=({"synthetic": True},), orders=({"synthetic": True},)),
        ownership_matcher=lambda *_: (True, True, True),
        now_utc=NOW,
    )
    assert evidence.state is ReconciliationState.FRESH_PROTECTED


def test_release_activation_is_one_use_and_does_not_arm(tmp_path: Path):
    evidence_file = tmp_path / "seed"
    evidence_file.write_text("x")

    def reconcile():
        credentials = FakeCredentials()
        credentials.marker = (
            tmp_path / "g070-reconciliation-slots" / f"{int(NOW.timestamp()) // 30}.started.json"
        )
        return run_g070_reconciliation_slot(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            credential_loader=credentials,
            client=FakeClient(),
            ownership_matcher=lambda *_: (False, False, False),
            now_utc=NOW,
        )

    release = activate_g070_release_once(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        canonical_g070=True,
        independent_review_clear=True,
        operation_60_passed=True,
        reconciliation_runner=reconcile,
        now_utc=NOW,
    )
    assert release.generation_digest == DIGEST
    assert not (tmp_path / "arm-state.json").exists()
    with pytest.raises(G070Error, match="ALREADY_STARTED"):
        activate_g070_release_once(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            canonical_g070=True,
            independent_review_clear=True,
            operation_60_passed=True,
            reconciliation_runner=reconcile,
            now_utc=NOW,
        )


def test_opaque_action_scope_exact_once_and_no_boolean_allow(tmp_path: Path):
    release = G070ReleaseCapability(
        DIGEST, REVIEWED, "sha256:" + "3" * 64, NOW.isoformat(), "sha256:" + "4" * 64
    )
    store = G070ActionScopeStore(tmp_path)
    scope = store.issue(
        release=release,
        cycle_ref="cycle-synthetic",
        action=G070Action.MARKET_ENTRY,
        symbol="USD_JPY",
        side="SELL",
        quantity=1000,
        coordinator_digest="sha256:" + "5" * 64,
        now_utc=NOW,
    )
    assert bool(scope) is False
    store.consume_exact(
        scope,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        cycle_ref="cycle-synthetic",
        action=G070Action.MARKET_ENTRY,
        symbol="USD_JPY",
        side="SELL",
        quantity=1000,
        coordinator_digest="sha256:" + "5" * 64,
        now_utc=NOW,
    )
    with pytest.raises(G070Error, match="ALREADY_CONSUMED"):
        store.consume_exact(
            scope,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            cycle_ref="cycle-synthetic",
            action=G070Action.MARKET_ENTRY,
            symbol="USD_JPY",
            side="SELL",
            quantity=1000,
            coordinator_digest="sha256:" + "5" * 64,
            now_utc=NOW,
        )


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("generation_digest", "sha256:" + "9" * 64),
        ("cycle_ref", "other-cycle"),
        ("action", G070Action.EXACT_OCO_PROTECTION),
        ("symbol", "OTHER"),
        ("side", "BUY"),
        ("quantity", 999),
        ("coordinator_digest", "sha256:" + "8" * 64),
    ],
)
def test_action_scope_rejects_cross_binding(tmp_path: Path, override: str, value: object) -> None:
    release = G070ReleaseCapability(
        DIGEST,
        REVIEWED,
        "sha256:" + "3" * 64,
        NOW.isoformat(),
        "sha256:" + "4" * 64,
    )
    store = G070ActionScopeStore(tmp_path)
    scope = store.issue(
        release=release,
        cycle_ref="cycle-synthetic",
        action=G070Action.MARKET_ENTRY,
        symbol="USD_JPY",
        side="SELL",
        quantity=1000,
        coordinator_digest="sha256:" + "5" * 64,
        now_utc=NOW,
    )
    values = {
        "generation_digest": DIGEST,
        "reviewed_files_digest": REVIEWED,
        "cycle_ref": "cycle-synthetic",
        "action": G070Action.MARKET_ENTRY,
        "symbol": "USD_JPY",
        "side": "SELL",
        "quantity": 1000,
        "coordinator_digest": "sha256:" + "5" * 64,
        "now_utc": NOW,
    }
    values[override] = value
    with pytest.raises(G070Error, match="EXACT_BINDING_MISMATCH"):
        store.consume_exact(scope, **values)


def test_action_scope_cannot_be_reminted_with_a_new_expiry(tmp_path: Path) -> None:
    release = G070ReleaseCapability(
        DIGEST,
        REVIEWED,
        "sha256:" + "3" * 64,
        NOW.isoformat(),
        "sha256:" + "4" * 64,
    )
    store = G070ActionScopeStore(tmp_path)
    request = {
        "release": release,
        "cycle_ref": "stable-cycle",
        "action": G070Action.MARKET_ENTRY,
        "symbol": "USD_JPY",
        "side": "SELL",
        "quantity": 1000,
        "coordinator_digest": "sha256:" + "5" * 64,
    }
    store.issue(**request, now_utc=NOW)
    with pytest.raises(G070Error, match="ALREADY_RESERVED_NO_RETRY"):
        store.issue(**request, now_utc=NOW + timedelta(seconds=1))


def test_fake_end_to_end_switch_only_lifecycle(tmp_path: Path) -> None:
    assert (
        run_g070_operation_60_candidate(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            installer=lambda: None,
            readiness_verifier=lambda: True,
        )
        == "PASSED"
    )
    credentials = FakeCredentials()
    credentials.marker = (
        tmp_path / "g070-reconciliation-slots" / f"{int(NOW.timestamp()) // 30}.started.json"
    )
    release = activate_g070_release_once(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        canonical_g070=True,
        independent_review_clear=True,
        operation_60_passed=True,
        reconciliation_runner=lambda: run_g070_reconciliation_slot(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            credential_loader=credentials,
            client=FakeClient(),
            ownership_matcher=lambda *_: (False, False, False),
            now_utc=NOW,
        ),
        now_utc=NOW,
    )
    loaded_release = load_g070_release_capability(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
    )
    assert loaded_release == release
    port = G070FakeActionPort(
        {
            G070Action.MARKET_ENTRY: G070ActionOutcome.ACCEPTED_KNOWN,
            G070Action.EXACT_OCO_PROTECTION: G070ActionOutcome.PROTECTED_KNOWN,
            G070Action.TIME_EXIT_OCO_CANCEL: G070ActionOutcome.ACCEPTED_KNOWN,
            G070Action.POSITION_SPECIFIC_CLOSE: G070ActionOutcome.FLAT_KNOWN,
        }
    )
    driver = G070FakeLifecycleDriver(
        coordinator=G070ScopedActionCoordinator(state_root=tmp_path, release=release, port=port),
        cycle_ref="fake-cycle",
        side="SELL",
        quantity=1000,
        coordinator_digest="sha256:" + "5" * 64,
    )
    entry_results = []
    exit_results = []
    supervisor = G070ResidentSupervisor(
        tmp_path,
        DIGEST,
        REVIEWED,
        entry_evaluator=lambda _projection: entry_results.append(
            driver.enter_and_protect_once(now_utc=NOW)
        ),
        exit_manager=lambda _projection: exit_results.append(
            driver.time_exit_once(now_utc=NOW + timedelta(seconds=30))
        ),
    )
    waiting = supervisor.tick(now_utc=NOW, arm_state=ArmState.ON)
    assert waiting.effective_state is EffectiveState.ON_WAITING
    assert entry_results[0].protected is True
    protected_credentials = FakeCredentials()
    protected_credentials.marker = (
        tmp_path
        / "g070-reconciliation-slots"
        / f"{int((NOW + timedelta(seconds=30)).timestamp()) // 30}.started.json"
    )
    run_g070_reconciliation_slot(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        credential_loader=protected_credentials,
        client=FakeClient(positions=({"synthetic": True},), orders=({"synthetic": True},)),
        ownership_matcher=lambda *_: (True, True, True),
        now_utc=NOW + timedelta(seconds=30),
    )
    protected = supervisor.tick(now_utc=NOW + timedelta(seconds=30), arm_state=ArmState.OFF)
    assert protected.effective_state is EffectiveState.EXIT_ONLY
    assert exit_results[0].flat_reconciled is True
    flat_credentials = FakeCredentials()
    flat_credentials.marker = (
        tmp_path
        / "g070-reconciliation-slots"
        / f"{int((NOW + timedelta(seconds=60)).timestamp()) // 30}.started.json"
    )
    run_g070_reconciliation_slot(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        credential_loader=flat_credentials,
        client=FakeClient(),
        ownership_matcher=lambda *_: (False, False, False),
        now_utc=NOW + timedelta(seconds=60),
    )
    flat = supervisor.tick(now_utc=NOW + timedelta(seconds=60), arm_state=ArmState.OFF)
    assert flat.effective_state is EffectiveState.OFF
    assert port.calls == [
        G070Action.MARKET_ENTRY,
        G070Action.EXACT_OCO_PROTECTION,
        G070Action.TIME_EXIT_OCO_CANCEL,
        G070Action.POSITION_SPECIFIC_CLOSE,
    ]


def test_fake_partial_cancel_and_natural_settlement_are_exact_once(tmp_path: Path) -> None:
    release = G070ReleaseCapability(
        DIGEST, REVIEWED, "sha256:" + "3" * 64, NOW.isoformat(), "sha256:" + "4" * 64
    )
    port = G070FakeActionPort(
        {
            G070Action.MARKET_ENTRY: G070ActionOutcome.PARTIAL_PENDING_KNOWN,
            G070Action.PARTIAL_PENDING_CANCEL: G070ActionOutcome.ACCEPTED_KNOWN,
            G070Action.EXACT_OCO_PROTECTION: G070ActionOutcome.PROTECTED_KNOWN,
        }
    )
    driver = G070FakeLifecycleDriver(
        coordinator=G070ScopedActionCoordinator(state_root=tmp_path, release=release, port=port),
        cycle_ref="partial-cycle",
        side="BUY",
        quantity=1000,
        coordinator_digest="sha256:" + "6" * 64,
    )
    entered = driver.enter_and_protect_once(now_utc=NOW)
    assert entered.partial_cancel_attempt_count == 1
    settled = driver.reconcile_natural_flat_once()
    assert settled.flat_reconciled is True
    assert settled.exit_cancel_attempt_count == 0
    assert settled.close_attempt_count == 0
    with pytest.raises(G070Error, match="ALREADY_ATTEMPTED"):
        driver.enter_and_protect_once(now_utc=NOW)


def test_resident_runs_exit_when_off_and_entry_only_when_open(tmp_path: Path):
    exit_calls, entry_calls = [], []
    supervisor = G070ResidentSupervisor(
        tmp_path,
        DIGEST,
        REVIEWED,
        exit_manager=exit_calls.append,
        entry_evaluator=entry_calls.append,
    )
    result = supervisor.tick(now_utc=NOW, arm_state=ArmState.ON)
    assert result.effective_state is EffectiveState.RECOVERING
    assert exit_calls == [] and entry_calls == []


def test_resident_never_opens_entry_without_release_and_adapter(tmp_path: Path) -> None:
    credentials = FakeCredentials()
    credentials.marker = (
        tmp_path / "g070-reconciliation-slots" / f"{int(NOW.timestamp()) // 30}.started.json"
    )
    run_g070_reconciliation_slot(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        credential_loader=credentials,
        client=FakeClient(),
        ownership_matcher=lambda *_: (False, False, False),
        now_utc=NOW,
    )
    supervisor = G070ResidentSupervisor(tmp_path, DIGEST, REVIEWED)
    result = supervisor.tick(now_utc=NOW, arm_state=ArmState.ON)
    assert result.effective_state is EffectiveState.ON_WAITING
    assert result.entry_gate_open is False
    assert result.entry_state is EntryState.ENTRY_GATES_BLOCKED


def test_operation60_uses_fresh_readiness_window_and_required_is_success(tmp_path: Path):
    clock = iter([0.0, 59.0, 59.0, 60.0, 61.0])
    checks = iter([False, True])
    outcome = run_g070_operation_60_candidate(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        installer=lambda: None,
        readiness_verifier=lambda: next(checks),
        monotonic=lambda: next(clock),
        sleep=lambda _seconds: None,
    )
    assert outcome == "PASSED"
    payload = json.loads((tmp_path / "g070-operation-60.result.json").read_text())
    assert payload["reconciliation_state"] == "REQUIRED"
    assert payload["private_api_read_count"] == 0
    with pytest.raises(G070Error, match="ALREADY_STARTED"):
        run_g070_operation_60_candidate(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            installer=lambda: None,
            readiness_verifier=lambda: True,
        )


def test_scheduler_binding_requires_all_runtime_artifacts_exactly_bound(
    tmp_path: Path,
) -> None:
    generation = SimpleNamespace(
        generation_label="H11_AUTO_30M_20260802_G070",
        digest=DIGEST,
        implementation_digest=REVIEWED,
    )
    plist_path = tmp_path / "scheduler.plist"
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    "/synthetic/python",
                    "/synthetic/h11_auto_v4_g070_runtime_bootstrap_no_post.py",
                    "--repository",
                    str(tmp_path.resolve()),
                    "--expected-reviewed-files-digest",
                    REVIEWED,
                    "--expected-generation-digest",
                    DIGEST,
                ]
            }
        )
    )
    heartbeat = {
        "generation_digest": DIGEST,
        "reviewed_files_digest": REVIEWED,
        "heartbeat_at_utc": NOW.isoformat(),
        "broker_write": False,
        "actual_post_count": 0,
    }
    (tmp_path / "heartbeat.json").write_text(json.dumps(heartbeat))
    (tmp_path / "dead-man.json").write_text(json.dumps({**heartbeat, "alive": True}))
    chain_base = {
        **heartbeat,
        "chain_index": 1,
        "previous_chain_hash": "sha256:" + "0" * 64,
    }
    chain_hash = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(chain_base, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    (tmp_path / "heartbeat-chain.json").write_text(
        json.dumps({**chain_base, "chain_hash": chain_hash})
    )
    (tmp_path / "process.lock").write_text(json.dumps({"pid": os.getpid()}))
    (tmp_path / "g070-runtime-status.json").write_text(
        json.dumps(
            {
                **heartbeat,
                "control_plane_state": "READY",
                "reconciliation_state": "REQUIRED",
            }
        )
    )
    verify_g070_scheduler_binding(
        generation=generation,
        repository=tmp_path,
        plist_path=plist_path,
        state_root=tmp_path,
        now_utc=NOW,
    )
    (tmp_path / "dead-man.json").write_text(
        json.dumps({**heartbeat, "alive": True, "generation_digest": "bad"})
    )
    with pytest.raises(G070Error, match="RUNTIME_READINESS_NOT_CLEAR"):
        verify_g070_scheduler_binding(
            generation=generation,
            repository=tmp_path,
            plist_path=plist_path,
            state_root=tmp_path,
            now_utc=NOW,
        )
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    "/synthetic/python",
                    "/synthetic/h11_auto_v4_g070_runtime_bootstrap_no_post.py",
                    "--repository",
                    "/different/repository",
                    "--expected-reviewed-files-digest",
                    REVIEWED,
                    "--expected-generation-digest",
                    DIGEST,
                ]
            }
        )
    )
    with pytest.raises(G070Error, match="SCHEDULER_BINDING_MISMATCH"):
        verify_g070_scheduler_binding(
            generation=generation,
            repository=tmp_path,
            plist_path=plist_path,
            state_root=tmp_path,
            now_utc=NOW,
        )


def test_review_artifacts_recompute_self_digests_and_cross_bind(tmp_path: Path) -> None:
    templates = tmp_path / "docs/templates"
    templates.mkdir(parents=True)

    def canonical_hash(payload: dict[str, object]) -> str:
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )

    evidence = {
        "generation_digest": "pending",
        "reviewed_files_digest": REVIEWED,
        "artifact_digest": "pending",
        "focused_tests_clear": True,
        "related_tests_clear": True,
        "ruff_clear": True,
        "diff_check_clear": True,
        "danger_scan_clear": True,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "broker_write": False,
        "broker_get_count": 0,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "notification_attempt_count": 0,
        "arm_mutation_count": 0,
        "launchagent_mutation_count": 0,
    }
    attestation = {
        "generation_digest": "pending",
        "reviewed_files_digest": REVIEWED,
        "artifact_digest": "pending",
        "architecture_status": "CLEAR",
        "safety_status": "CLEAR",
        "operations_status": "CLEAR",
        "blocking_findings": [],
    }
    manifest = {
        "implementation_digest": REVIEWED,
        "actual_post_authorized": False,
        "live_ready": False,
        "unattended_live_supported": False,
        "runtime_commissioning_evidence_digest": "pending",
        "successor_halt_release_digest": "pending",
    }
    generation_digest = canonical_hash(
        {
            key: value
            for key, value in manifest.items()
            if key
            not in {
                "runtime_commissioning_evidence_digest",
                "successor_halt_release_digest",
            }
        }
    )
    evidence["generation_digest"] = generation_digest
    attestation["generation_digest"] = generation_digest
    evidence["artifact_digest"] = canonical_hash(
        {key: value for key, value in evidence.items() if key != "artifact_digest"}
    )
    attestation["artifact_digest"] = canonical_hash(
        {key: value for key, value in attestation.items() if key != "artifact_digest"}
    )
    manifest["runtime_commissioning_evidence_digest"] = evidence["artifact_digest"]
    manifest["successor_halt_release_digest"] = attestation["artifact_digest"]
    for name, payload in (
        ("h11_v4_g070_frozen_generation.json", manifest),
        ("h11_v4_g070_runtime_commissioning_evidence.json", evidence),
        ("h11_v4_g070_independent_review_attestation.json", attestation),
    ):
        (templates / name).write_text(json.dumps(payload))
    verify_g070_review_artifacts(
        repository=tmp_path,
        generation_digest=generation_digest,
        reviewed_files_digest=REVIEWED,
    )
    evidence["broker_post_count"] = 1
    (templates / "h11_v4_g070_runtime_commissioning_evidence.json").write_text(json.dumps(evidence))
    with pytest.raises(G070Error, match="ARTIFACT_BINDING_MISMATCH"):
        verify_g070_review_artifacts(
            repository=tmp_path,
            generation_digest=generation_digest,
            reviewed_files_digest=REVIEWED,
        )


def test_g070_call_graph_has_no_legacy_authorization_or_real_io():
    import ast

    source = Path("app/services/h11_v4_g070_candidate.py").read_text()
    imports = {
        alias.name.lower()
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    forbidden = (
        "daily_authorization",
        "major_incident",
        "current_turn",
        "actual_transport",
        "private_api",
        "keychain",
        "notification",
        "httpx",
        "assert_real_broker_post_allowed",
    )
    assert all(not any(token in imported for imported in imports) for token in forbidden)


def test_missing_resident_status_is_halted_but_arm_intent_remains_separate(
    tmp_path: Path,
) -> None:
    status = safe_g070_api_status(
        state_root=tmp_path,
        arm_on=True,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
    )
    assert status["control_plane_state"] == "HALTED"
    assert status["effective_state"] == "HALTED"
    assert status["entry_gate_open"] is False
