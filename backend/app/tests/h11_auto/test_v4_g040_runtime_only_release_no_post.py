from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.h11_auto import v4_gmo_monitor_supervisor as supervisor_module
from app.h11_auto.runtime_safety import PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4RuntimeOnlyPreparationCarryForwardEvidence,
)
from app.h11_auto.v4_gmo_actual_coordinator import (
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
)


def test_runtime_only_carry_forward_cannot_be_publicly_minted() -> None:
    with pytest.raises(
        V4ActualPreparationGuardError,
        match="G040_RUNTIME_CARRY_FORWARD_INVALID",
    ):
        V4RuntimeOnlyPreparationCarryForwardEvidence(
            token=object(),
            source_reviewed_files_digest="sha256:" + ("1" * 64),
            source_generation_digest="sha256:" + ("2" * 64),
            target_reviewed_files_digest="sha256:" + ("3" * 64),
            target_generation_digest="sha256:" + ("4" * 64),
            trading_day_jst="2026-07-29",
            completed_operations=("00_presence",),
        )


@pytest.mark.parametrize(
    "generation_label",
    (
        "H11_AUTO_30M_20260729_G040",
        "H11_AUTO_30M_20260729_G041",
        "H11_AUTO_30M_20260730_G046",
    ),
)
def test_runtime_only_monitor_carries_risk_and_coordinator_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    generation_label: str,
) -> None:
    target_digest = "sha256:" + ("4" * 64)
    source_digest = "sha256:" + ("3" * 64)
    generation = SimpleNamespace(
        digest=target_digest,
        generation_label=generation_label,
        canonical_json="{}",
        implementation_digest="sha256:" + ("5" * 64),
        operator_selection_digest="sha256:" + ("6" * 64),
        policy_config_hash="sha256:" + ("7" * 64),
        risk_policy_digest="8" * 64,
        dead_man_policy_digest="9" * 64,
    )

    def runtime_root(*, generation_digest: str, **_kwargs: object) -> Path:
        return tmp_path / generation_digest.removeprefix("sha256:")

    monkeypatch.setattr(
        supervisor_module,
        "v4_gmo_runtime_state_root",
        runtime_root,
    )
    monkeypatch.setattr(
        supervisor_module,
        "verify_g038_generation_activation",
        lambda **_kwargs: SimpleNamespace(
            predecessor_halt_generation_digest=source_digest
        ),
    )
    policy = supervisor_module.v4_gmo_risk_policy()
    source_store = PhaseBRiskStore(
        runtime_root(generation_digest=source_digest) / "risk.json",
        policy=policy,
    )
    source_state = source_store.load()
    source_state.current_day_jst = "2026-07-29"
    source_state.current_month_jst = "2026-07"
    source_state.entries_today = 1
    source_store.save(source_state)

    supervisor = supervisor_module.V4GmoMonitorSupervisor(
        repository=tmp_path,
        generation=generation,
    )
    supervisor.acquire_single_process()
    try:
        tick = supervisor.run_tick(
            now_utc=datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
        )
        second_tick = supervisor.run_tick(
            now_utc=datetime(2026, 7, 29, 0, 0, 15, tzinfo=UTC)
        )
    finally:
        supervisor.close()

    target_root = runtime_root(generation_digest=target_digest)
    target_state = PhaseBRiskStore(
        target_root / "risk.json",
        policy=policy,
    ).load()
    assert target_state.entries_today == 1
    assert tick.runtime_risk_ready is True
    assert tick.dead_man_alive is True
    assert tick.heartbeat_chain_beat is True
    assert (target_root / "dead-man.json").is_file()
    assert (target_root / "unattended-heartbeat-chain.json").is_file()
    coordinator_path = target_root / "coordinator.sqlite3"
    coordinator = V4GmoActualCoordinatorStore.open_monitor_observer(
        coordinator_path
    )
    assert (
        coordinator.market_attempt_count_for_day(
            trading_day_jst="2026-07-29"
        )
        == 1
    )
    assert tick.generation_bound is True
    assert second_tick.generation_bound is True
    assert tick.broker_write is False
    assert tick.actual_post_count == 0
    with coordinator._connect() as connection:
        connection.execute(
            "INSERT INTO cycles("
            "cycle_ref,signal_fingerprint,trading_day_jst,side,requested_size,"
            "frozen_atr_24,frozen_atr_digest,probability_up,"
            "planned_loss_bound_jpy,signal_valid_until_utc,created_at_utc"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                "synthetic-cycle",
                "synthetic-signal",
                "2026-07-29",
                "BUY",
                1_000,
                "0.1",
                "sha256:" + ("a" * 64),
                "0.6",
                100,
                "2026-07-29T01:00:00+00:00",
                "2026-07-29T00:00:00+00:00",
            ),
        )
    coordinator.initialize_inherited_market_attempt_baseline_once(
        source_generation_digest=source_digest,
        target_generation_digest=target_digest,
        trading_day_jst="2026-07-29",
        attempt_count=1,
    )
    with pytest.raises(
        V4GmoActualCoordinatorError,
        match="inherited attempt baseline mismatch",
    ):
        coordinator.initialize_inherited_market_attempt_baseline_once(
            source_generation_digest=source_digest,
            target_generation_digest=target_digest,
            trading_day_jst="2026-07-29",
            attempt_count=2,
        )
    target_state.entries_today = 2
    PhaseBRiskStore(
        target_root / "risk.json",
        policy=policy,
    ).save(target_state)
    supervisor.acquire_single_process()
    try:
        post_cycle_tick = supervisor.run_tick(
            now_utc=datetime(2026, 7, 29, 0, 0, 30, tzinfo=UTC)
        )
    finally:
        supervisor.close()
    assert post_cycle_tick.generation_bound is True
    assert post_cycle_tick.persistent_halt is False
    assert (
        coordinator.market_attempt_count_for_day(
            trading_day_jst="2026-07-29"
        )
        == 1
    )


def test_monitor_observer_refuses_to_create_missing_coordinator(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordinator.sqlite3"
    with pytest.raises(
        V4GmoActualCoordinatorError,
        match="observer requires an existing ledger",
    ):
        V4GmoActualCoordinatorStore.open_monitor_observer(path)
    assert not path.exists()
