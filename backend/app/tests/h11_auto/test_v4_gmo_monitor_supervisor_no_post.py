from __future__ import annotations

import inspect
import plistlib
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4_GMO_MONITOR_LABEL,
    install_and_restart_v4_gmo_monitor_launchagent,
    render_v4_gmo_monitor_launchagent,
)
from app.h11_auto.v4_gmo_monitor_supervisor import V4GmoMonitorSupervisor
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_adapter import V4GmoPrivateOutcome
from app.services.h11_v4_gmo_actual_runtime_driver import V4GmoActualRuntimeDriver
from app.services.h11_v4_gmo_exit_dispatcher import (
    V4GmoExitDispatcher,
    V4GmoExitDispatcherError,
    V4GmoExitDispatchResult,
)

IMPLEMENTATION_DIGEST = "sha256:" + "c" * 64
FRIDAY_ENTRY = datetime(2026, 7, 17, 1, 0, tzinfo=UTC)  # 10:00 JST


def _policy() -> V4GmoExecutionPolicy:
    selected = V4ApprovedOperatorSelections()
    return V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _generation():
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260717_G012_TEST",
        implementation_digest=IMPLEMENTATION_DIGEST,
        policy=_policy(),
    )


def _signal() -> FormalSignal:
    policy = _policy()
    return FormalSignal(
        strategy_version=policy.strategy_version,
        signal_config_hash=policy.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=FRIDAY_ENTRY - timedelta(minutes=1),
        valid_until_utc=FRIDAY_ENTRY + timedelta(minutes=1),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )


def test_monitor_source_has_no_broker_or_credential_dependency() -> None:
    import app.h11_auto.v4_gmo_monitor_supervisor as module

    source = inspect.getsource(module)
    forbidden = (
        "httpx",
        "Keychain",
        "credential",
        "actual_transport",
        "cancelOrders",
        "closeOrder",
        '"/private/',
        "allow=True",
    )
    for marker in forbidden:
        assert marker not in source


def test_monitor_marks_0345_dispatch_and_latches_0400_flat_miss(
    tmp_path: Path,
) -> None:
    generation = _generation()
    root = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest=generation.digest,
    )
    store = V4GmoActualCoordinatorStore(root / "coordinator.sqlite3")
    signal = _signal()
    store.prepare_entry_intent(
        generation=generation,
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=FRIDAY_ENTRY - timedelta(seconds=1),
    )
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE cycles SET market_attempted_at_utc=?,market_attempted_monotonic=?",
            (FRIDAY_ENTRY.isoformat(), 100.0),
        )
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES('protection_confirmed_at_utc',?)",
            ((FRIDAY_ENTRY + timedelta(seconds=10)).isoformat(),),
        )
    supervisor = V4GmoMonitorSupervisor(repository=tmp_path, generation=generation)
    supervisor.acquire_single_process()
    dispatch = supervisor.run_tick(
        now_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC)  # Sat 03:45 JST
    )
    assert dispatch.exit_dispatch_required is True
    assert (root / "exit-sequence-dispatch-required.json").is_file()
    missed = supervisor.run_tick(
        now_utc=datetime(2026, 7, 17, 19, 0, tzinfo=UTC)  # Sat 04:00 JST
    )
    assert missed.flat_target_missed is True
    assert missed.persistent_halt is True
    assert missed.actual_post_count == 0
    assert store.unknown_halt_latched() is True
    supervisor.close()


def test_launchagent_is_monitor_only_and_finite_restart_is_testable(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=_generation(),
        python_executable=Path(sys.executable),
    )
    payload = plistlib.loads(content)
    joined = " ".join(payload["ProgramArguments"])
    assert payload["Label"] == V4_GMO_MONITOR_LABEL
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert "h11_auto_v4_monitor_supervisor" in joined
    for forbidden in ("credential", "api-key", "order", "POST", "secret"):
        assert forbidden not in joined
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    result = install_and_restart_v4_gmo_monitor_launchagent(
        plist_path=(tmp_path / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"),
        plist_content=content,
        user_id=501,
        runner=runner,
    )
    assert result.installed is True
    assert result.restarted is True
    assert result.actual_post_count == 0
    assert [command[1] for command in calls] == ["bootstrap", "kickstart"]


def _exit_dispatch_path(root: Path, *, generation_digest: str) -> MagicMock:
    path = MagicMock()
    path.store.path = root / "coordinator.sqlite3"
    path.store.load_single_signal_fingerprint_internal.return_value = "safe-fp"
    path.store.cycle_ref_for_signal_internal.return_value = "c" * 64
    path.store.side_for_signal_internal.return_value = SignalDecision.BUY
    path.store.expected_closed_size_for_signal_internal.return_value = 10_000
    path.process_lock = SimpleNamespace(held=True)
    path.generation = SimpleNamespace(
        digest=generation_digest,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    path.reconcile_once_fixed.side_effect = [object() for _ in range(3)]
    path.recover_pending_transport_and_carry_once.side_effect = [
        (SimpleNamespace(classification="FILLED_UNPROTECTED"), object()),
        (SimpleNamespace(classification="FLAT_OR_REJECTED"), object()),
    ]
    path.perform_risk_reducing_once.side_effect = [
        V4GmoPrivateOutcome.ACCEPTED_SANITIZED,
        V4GmoPrivateOutcome.ACCEPTED_SANITIZED,
    ]
    path.record_flat_closed_result_once.return_value = True
    return path


def _write_dispatch_required(root: Path, *, generation_digest: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "exit-sequence-dispatch-required.json").write_text(
        (
            '{"generation_digest":"'
            + generation_digest
            + '","status":"GENERATION_BOUND_EXIT_DISPATCH_REQUIRED"}\n'
        ),
        encoding="utf-8",
    )


def test_exit_dispatcher_claims_once_and_runs_fixed_cancel_close_sequence(
    tmp_path: Path,
) -> None:
    generation_digest = _generation().digest
    root = tmp_path / "state"
    _write_dispatch_required(root, generation_digest=generation_digest)
    path = _exit_dispatch_path(root, generation_digest=generation_digest)
    cancel_reader = MagicMock()
    close_reader = MagicMock()
    cancel_reader.read_once.return_value = object()
    close_reader.read_once.return_value = object()
    dispatcher = V4GmoExitDispatcher(coordinated_path=path, state_root=root)

    result = dispatcher.dispatch_once(
        public_cancel_reader=cancel_reader,
        public_close_reader=close_reader,
        observed_at_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
    )

    assert result.claimed is True
    assert result.flat_reconciled is True
    assert result.broker_post_attempt_count == 2
    assert path.reconcile_once_fixed.call_count == 3
    assert path.perform_risk_reducing_once.call_count == 2
    assert path.recover_pending_transport_and_carry_once.call_count == 2
    assert cancel_reader.read_once.call_count == 1
    assert close_reader.read_once.call_count == 1
    assert (root / "exit-sequence-dispatch-completed.json").is_file()
    with pytest.raises(V4GmoExitDispatcherError, match="ALREADY_CLAIMED"):
        dispatcher.dispatch_once(
            public_cancel_reader=cancel_reader,
            public_close_reader=close_reader,
            observed_at_utc=datetime(2026, 7, 17, 18, 46, tzinfo=UTC),
        )
    assert path.perform_risk_reducing_once.call_count == 2


def test_exit_dispatcher_generation_mismatch_fails_before_io(tmp_path: Path) -> None:
    generation_digest = _generation().digest
    root = tmp_path / "state"
    _write_dispatch_required(root, generation_digest="sha256:" + "f" * 64)
    path = _exit_dispatch_path(root, generation_digest=generation_digest)
    dispatcher = V4GmoExitDispatcher(coordinated_path=path, state_root=root)

    with pytest.raises(V4GmoExitDispatcherError, match="GENERATION_MISMATCH"):
        dispatcher.dispatch_once(
            public_cancel_reader=MagicMock(),
            public_close_reader=MagicMock(),
            observed_at_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
        )
    path.reconcile_once_fixed.assert_not_called()
    path.perform_risk_reducing_once.assert_not_called()


def test_exit_dispatcher_unknown_latches_halt_and_cannot_retry(tmp_path: Path) -> None:
    generation_digest = _generation().digest
    root = tmp_path / "state"
    _write_dispatch_required(root, generation_digest=generation_digest)
    path = _exit_dispatch_path(root, generation_digest=generation_digest)
    path.perform_risk_reducing_once.side_effect = TimeoutError
    dispatcher = V4GmoExitDispatcher(coordinated_path=path, state_root=root)

    with pytest.raises(V4GmoExitDispatcherError, match="DISPATCH_FAILED"):
        dispatcher.dispatch_once(
            public_cancel_reader=MagicMock(),
            public_close_reader=MagicMock(),
            observed_at_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
        )
    path.store.engage_unknown_halt.assert_called_once_with()
    assert (root / "exit-sequence-dispatch-failed.json").is_file()
    with pytest.raises(V4GmoExitDispatcherError, match="ALREADY_CLAIMED"):
        dispatcher.dispatch_once(
            public_cancel_reader=MagicMock(),
            public_close_reader=MagicMock(),
            observed_at_utc=datetime(2026, 7, 17, 18, 46, tzinfo=UTC),
        )
    assert path.perform_risk_reducing_once.call_count == 1


def test_foreground_driver_consumes_monitor_marker_with_same_runtime_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir()
    (root / "exit-sequence-dispatch-required.json").write_text("{}\n")
    path = MagicMock()
    path.store.path = root / "coordinator.sqlite3"
    path.process_lock = SimpleNamespace(held=True)
    path.generation = SimpleNamespace(digest=_generation().digest)
    protected = SimpleNamespace(
        entry_attempted_at_utc=FRIDAY_ENTRY,
        flat_reconciled=False,
        protection_confirmed=True,
        pending_transport=False,
        unknown_halt_latched=False,
    )
    path.store.monitor_snapshot_safe.side_effect = [protected, protected]
    dispatcher = MagicMock()
    dispatcher.path = path
    dispatcher.dispatch_once.return_value = V4GmoExitDispatchResult(
        claimed=True,
        protection_cancel_accepted=True,
        position_close_accepted=True,
        flat_reconciled=True,
        broker_post_attempt_count=2,
    )
    reader_factory = MagicMock(side_effect=[MagicMock(), MagicMock()])
    driver = V4GmoActualRuntimeDriver(
        coordinated_path=path,
        dispatcher=dispatcher,
    )

    result = driver.run_until_flat(
        public_reader_factory=reader_factory,
        wall_clock=lambda: datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
        wait=lambda _seconds: None,
    )

    assert result.flat_reconciled is True
    assert result.exit_dispatch_claimed is True
    assert result.broker_post_attempt_count == 2
    dispatcher.dispatch_once.assert_called_once()
    path.dead_man_store.heartbeat.assert_called_once()


def test_foreground_driver_observes_local_flat_without_private_polling(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir()
    path = MagicMock()
    path.store.path = root / "coordinator.sqlite3"
    path.process_lock = SimpleNamespace(held=True)
    path.generation = SimpleNamespace(digest=_generation().digest)
    protected = SimpleNamespace(
        entry_attempted_at_utc=FRIDAY_ENTRY,
        flat_reconciled=False,
        protection_confirmed=True,
        pending_transport=False,
        unknown_halt_latched=False,
    )
    locally_recorded_flat = SimpleNamespace(
        entry_attempted_at_utc=FRIDAY_ENTRY,
        flat_reconciled=True,
        protection_confirmed=True,
        pending_transport=False,
        unknown_halt_latched=False,
    )
    path.store.monitor_snapshot_safe.side_effect = [protected, locally_recorded_flat]
    dispatcher = MagicMock()
    dispatcher.path = path
    waits: list[float] = []
    driver = V4GmoActualRuntimeDriver(
        coordinated_path=path,
        dispatcher=dispatcher,
    )

    result = driver.run_until_flat(
        wall_clock=lambda: datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
        wait=waits.append,
    )

    assert result.flat_reconciled is True
    assert result.exit_dispatch_claimed is False
    assert result.broker_post_attempt_count == 0
    assert waits == [5.0]
    path.reconcile_once_fixed.assert_not_called()
    path.record_flat_closed_result_once.assert_not_called()
    dispatcher.dispatch_once.assert_not_called()


def test_exit_dispatch_claim_fsyncs_parent_directory_before_io() -> None:
    import app.services.h11_v4_gmo_exit_dispatcher as module

    source = inspect.getsource(module.V4GmoExitDispatcher._write_terminal_marker)
    assert "os.fsync(handle.fileno())" in source
    assert "os.fsync(directory)" in source
