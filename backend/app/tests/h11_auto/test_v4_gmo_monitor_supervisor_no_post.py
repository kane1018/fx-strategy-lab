from __future__ import annotations

import inspect
import json
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
from app.h11_auto.v4_gmo_contracts import (
    V4GmoExecutionPolicy,
    v4_gmo_trading_day_jst,
)
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4_GMO_MONITOR_LABEL,
    V4GmoLaunchdDomainNotReady,
    V4GmoLaunchdError,
    install_and_restart_v4_gmo_monitor_launchagent,
    render_v4_gmo_monitor_launchagent,
    require_stable_v4_gmo_aqua_domain,
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


def test_monitor_entrypoint_checks_pinned_digests_before_supervisor() -> None:
    import scripts.h11_auto_v4_monitor_supervisor as module

    source = inspect.getsource(module)
    reviewed_check = source.index("MONITOR_REVIEWED_FILES_DIGEST_MISMATCH")
    generation_check = source.index("MONITOR_GENERATION_DIGEST_MISMATCH")
    supervisor_start = source.index("V4GmoMonitorSupervisor(")
    assert reviewed_check < generation_check < supervisor_start
    assert 'parser.add_argument("--expected-reviewed-files-digest"' in source
    assert 'parser.add_argument("--expected-generation-digest"' in source


def test_observer_store_never_latches_restart_halt_on_inflight_pending(
    tmp_path: Path,
) -> None:
    # The pending->halt restart latch protects the OWNING trading process. An
    # observer (the monitor) constructing a store mid-flight must not convert a
    # normal in-flight pending marker into a permanent halt.
    database = tmp_path / "coordinator.sqlite3"
    store = V4GmoActualCoordinatorStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES('pending_transport_attempt',?)",
            ('{"action":"MARKET_ENTRY","cycle_ref":"' + "c" * 64 + '"}',),
        )
    observer = V4GmoActualCoordinatorStore.open_monitor_observer(database)
    assert observer.unknown_halt_latched() is False
    # The owning process's restart path keeps the latch: a DEFAULT construction
    # over the same pending marker still halts.
    restarted = V4GmoActualCoordinatorStore(database)
    assert restarted.unknown_halt_latched() is True
    del store, restarted


def test_monitor_tick_during_inflight_pending_does_not_latch_halt(
    tmp_path: Path,
) -> None:
    # 2026-07-21 false-latch incident: a 15s tick landed inside the ~5s pending
    # window of a fully successful trade and permanently halted the generation.
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
            "INSERT INTO metadata(key,value) VALUES('pending_transport_attempt',?)",
            ('{"action":"MARKET_ENTRY","cycle_ref":"' + "c" * 64 + '"}',),
        )
    supervisor = V4GmoMonitorSupervisor(repository=tmp_path, generation=generation)
    supervisor.acquire_single_process()
    # Tick lands 5 seconds after the entry POST, while the pending marker is a
    # normal in-flight state (protection deadline not yet passed).
    tick = supervisor.run_tick(now_utc=FRIDAY_ENTRY + timedelta(seconds=5))
    supervisor.close()
    assert tick.persistent_halt is False
    assert store.unknown_halt_latched() is False


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
            "UPDATE cycles SET market_attempted_at_utc=?,market_attempted_monotonic=?,"
            "protection_confirmed_at_utc=?",
            (
                FRIDAY_ENTRY.isoformat(),
                100.0,
                (FRIDAY_ENTRY + timedelta(seconds=10)).isoformat(),
            ),
        )
    supervisor = V4GmoMonitorSupervisor(repository=tmp_path, generation=generation)
    supervisor.acquire_single_process()
    dispatch = supervisor.run_tick(
        now_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC)  # Sat 03:45 JST
    )
    assert dispatch.exit_dispatch_required is True
    cycle_day = v4_gmo_trading_day_jst(FRIDAY_ENTRY)
    assert (root / f"exit-sequence-dispatch-required.{cycle_day}.json").is_file()
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
    generation = _generation()
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    payload = plistlib.loads(content)
    joined = " ".join(payload["ProgramArguments"])
    arguments = payload["ProgramArguments"]
    assert payload["Label"] == V4_GMO_MONITOR_LABEL
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is False
    assert "h11_auto_v4_monitor_supervisor" in joined
    assert arguments[arguments.index("--expected-reviewed-files-digest") + 1] == (
        IMPLEMENTATION_DIGEST
    )
    assert arguments[arguments.index("--expected-generation-digest") + 1] == (
        generation.digest
    )
    for forbidden in ("credential", "api-key", "order", "POST", "secret"):
        assert forbidden not in joined
    calls: list[list[str]] = []
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    heartbeat_path = state_root / "supervisor-heartbeat.json"
    print_count = 0

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal print_count
        calls.append(command)
        if command[1] == "print":
            print_count += 1
            return subprocess.CompletedProcess(
                command,
                113 if print_count == 1 else 0,
                "",
                "not found" if print_count == 1 else "",
            )
        if command[1] == "bootstrap":
            _write_safe_monitor_heartbeat(
                heartbeat_path,
                generation_digest=generation.digest,
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = install_and_restart_v4_gmo_monitor_launchagent(
        plist_path=(tmp_path / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"),
        plist_content=content,
        user_id=501,
        runner=runner,
        heartbeat_path=heartbeat_path,
        expected_generation_digest=generation.digest,
    )
    assert result.installed is True
    assert result.restarted is True
    assert result.actual_post_count == 0
    assert result.heartbeat_generation_digest_match is True
    assert [command[1] for command in calls] == ["print", "bootstrap", "print"]
    assert all("kickstart" not in command for command in calls)


def test_launchagent_boots_out_existing_exact_service_once_before_bootstrap(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    generation = _generation()
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    heartbeat_path = (
        v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        )
        / "supervisor-heartbeat.json"
    )
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[1] == "bootstrap":
            _write_safe_monitor_heartbeat(
                heartbeat_path,
                generation_digest=generation.digest,
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = install_and_restart_v4_gmo_monitor_launchagent(
        plist_path=(tmp_path / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"),
        plist_content=content,
        user_id=501,
        runner=runner,
        heartbeat_path=heartbeat_path,
        expected_generation_digest=generation.digest,
    )

    assert result.previous_service_present is True
    assert result.previous_service_booted_out is True
    assert [command[1] for command in calls] == [
        "print",
        "bootout",
        "bootstrap",
        "print",
    ]


def test_launchagent_aqua_domain_preflight_accepts_observed_stable_shape() -> None:
    calls: list[list[str]] = []
    healthy = """
type = login
session = Aqua
auxiliary bootstrapper = com.apple.xpc.otherbsd (complete)
properties = gui | gui login
"""

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, healthy, "")

    require_stable_v4_gmo_aqua_domain(user_id=501, runner=runner)
    assert calls == [["launchctl", "print", "gui/501"]]


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [
        (1, "hidden"),
        (0, ""),
        (
            0,
            "session = Aqua\n"
            "auxiliary bootstrapper = com.apple.xpc.otherbsd (complete)\n"
            "properties = gui | gui login",
        ),
        (
            0,
            "type = login\n"
            "auxiliary bootstrapper = com.apple.xpc.otherbsd (complete)\n"
            "properties = gui | gui login",
        ),
        (0, "type = login\nsession = Aqua\nproperties = gui | gui login"),
        (
            0,
            "type = login\nsession = Aqua\n"
            "auxiliary bootstrapper = com.apple.xpc.otherbsd (complete)",
        ),
    ],
)
def test_launchagent_aqua_domain_preflight_refuses_fixed_safe(
    returncode: int,
    stdout: str,
) -> None:
    with pytest.raises(V4GmoLaunchdDomainNotReady, match="GUI_DOMAIN_NOT_READY"):
        require_stable_v4_gmo_aqua_domain(
            user_id=501,
            runner=lambda command: subprocess.CompletedProcess(
                command,
                returncode,
                stdout,
                "hidden",
            ),
        )


def test_launchagent_aqua_domain_preflight_wraps_timeout() -> None:
    def runner(_command: list[str]) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(["launchctl", "print"], 15.0)

    with pytest.raises(V4GmoLaunchdDomainNotReady, match="GUI_DOMAIN_NOT_READY"):
        require_stable_v4_gmo_aqua_domain(user_id=501, runner=runner)


def _write_safe_monitor_heartbeat(path: Path, *, generation_digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "actual_post_count": 0,
                "broker_read": False,
                "broker_write": False,
                "cycle_present": False,
                "generation_bound": False,
                "generation_digest": generation_digest,
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "status": "WAITING_FOR_CANONICAL_RUNTIME",
            }
        ),
        encoding="utf-8",
    )


def test_launchagent_rejects_unknown_service_state_before_mutation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    generation = _generation()
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "", "hidden")

    with pytest.raises(V4GmoLaunchdError, match="SERVICE_STATE_UNKNOWN"):
        install_and_restart_v4_gmo_monitor_launchagent(
            plist_path=(
                tmp_path / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"
            ),
            plist_content=content,
            user_id=501,
            runner=runner,
            heartbeat_path=tmp_path / "state" / "supervisor-heartbeat.json",
            expected_generation_digest=generation.digest,
        )
    assert [command[1] for command in calls] == ["print"]


def test_launchagent_rejects_prebootstrap_heartbeat(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    generation = _generation()
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    heartbeat_path = tmp_path / "state" / "supervisor-heartbeat.json"
    _write_safe_monitor_heartbeat(
        heartbeat_path,
        generation_digest=generation.digest,
    )
    # Clock must cross the 50s install heartbeat window (default) to reach the
    # deadline and reject the pre-bootstrap heartbeat.
    monotonic_values = iter((0.0, 0.0, 51.0))

    with pytest.raises(V4GmoLaunchdError, match="HEARTBEAT_NOT_CLEAR"):
        install_and_restart_v4_gmo_monitor_launchagent(
            plist_path=(
                tmp_path / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"
            ),
            plist_content=content,
            user_id=501,
            runner=lambda command: subprocess.CompletedProcess(command, 0, "", ""),
            heartbeat_path=heartbeat_path,
            expected_generation_digest=generation.digest,
            monotonic_clock=lambda: next(monotonic_values),
            wait=lambda _seconds: None,
        )


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
    # The position is still open in this scenario; the natural-settlement
    # shortcut must not trigger.
    path.reconciliation_shows_natural_flat.return_value = False
    return path


_DISPATCH_CYCLE_DAY = v4_gmo_trading_day_jst(FRIDAY_ENTRY)


def _write_dispatch_required(root: Path, *, generation_digest: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"exit-sequence-dispatch-required.{_DISPATCH_CYCLE_DAY}.json").write_text(
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
        cycle_day_jst=_DISPATCH_CYCLE_DAY,
    )

    assert result.claimed is True
    assert result.flat_reconciled is True
    assert result.broker_post_attempt_count == 2
    assert path.reconcile_once_fixed.call_count == 3
    assert path.perform_risk_reducing_once.call_count == 2
    assert path.recover_pending_transport_and_carry_once.call_count == 2
    assert cancel_reader.read_once.call_count == 1
    assert close_reader.read_once.call_count == 1
    assert (
        root / f"exit-sequence-dispatch-completed.{_DISPATCH_CYCLE_DAY}.json"
    ).is_file()
    with pytest.raises(V4GmoExitDispatcherError, match="ALREADY_CLAIMED"):
        dispatcher.dispatch_once(
            public_cancel_reader=cancel_reader,
            public_close_reader=close_reader,
            observed_at_utc=datetime(2026, 7, 17, 18, 46, tzinfo=UTC),
            cycle_day_jst=_DISPATCH_CYCLE_DAY,
        )
    assert path.perform_risk_reducing_once.call_count == 2


def test_exit_dispatcher_completes_on_natural_oco_settlement_with_zero_posts(
    tmp_path: Path,
) -> None:
    # SL/TP settled at the broker before the scheduled exit: the first reconcile
    # already shows a clean flat, so the dispatcher records the result and
    # completes WITHOUT posting a cancel or close (a consumed OCO cannot be
    # cancelled; before this shortcut the dispatch fail-closed with a halt and
    # the realized result was never recorded).
    generation_digest = _generation().digest
    root = tmp_path / "state"
    _write_dispatch_required(root, generation_digest=generation_digest)
    path = _exit_dispatch_path(root, generation_digest=generation_digest)
    path.reconciliation_shows_natural_flat.return_value = True
    dispatcher = V4GmoExitDispatcher(coordinated_path=path, state_root=root)

    result = dispatcher.dispatch_once(
        public_cancel_reader=MagicMock(),
        public_close_reader=MagicMock(),
        observed_at_utc=datetime(2026, 7, 17, 18, 45, tzinfo=UTC),
        cycle_day_jst=_DISPATCH_CYCLE_DAY,
    )

    assert result.claimed is True
    assert result.flat_reconciled is True
    assert result.broker_post_attempt_count == 0
    assert result.protection_cancel_accepted is False
    assert result.position_close_accepted is False
    path.perform_risk_reducing_once.assert_not_called()
    path.record_flat_closed_result_once.assert_called_once()
    assert path.reconcile_once_fixed.call_count == 1
    import json as _json

    completed = _json.loads(
        (
            root / f"exit-sequence-dispatch-completed.{_DISPATCH_CYCLE_DAY}.json"
        ).read_text(encoding="utf-8")
    )
    assert completed["status"] == "EXIT_DISPATCH_COMPLETED_NATURAL_SETTLEMENT_FLAT"


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
            cycle_day_jst=_DISPATCH_CYCLE_DAY,
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
            cycle_day_jst=_DISPATCH_CYCLE_DAY,
        )
    path.store.engage_unknown_halt.assert_called_once_with()
    assert (
        root / f"exit-sequence-dispatch-failed.{_DISPATCH_CYCLE_DAY}.json"
    ).is_file()
    with pytest.raises(V4GmoExitDispatcherError, match="ALREADY_CLAIMED"):
        dispatcher.dispatch_once(
            public_cancel_reader=MagicMock(),
            public_close_reader=MagicMock(),
            observed_at_utc=datetime(2026, 7, 17, 18, 46, tzinfo=UTC),
            cycle_day_jst=_DISPATCH_CYCLE_DAY,
        )
    assert path.perform_risk_reducing_once.call_count == 1


def test_foreground_driver_consumes_monitor_marker_with_same_runtime_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir()
    (root / f"exit-sequence-dispatch-required.{_DISPATCH_CYCLE_DAY}.json").write_text(
        "{}\n"
    )
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
