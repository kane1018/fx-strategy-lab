from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.h11_auto import v4_actual_preparation_guard as guard_module
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
from app.services import h11_v4_gmo_g013_canary as canary_module


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


def test_runtime_only_source_evidence_uses_recorded_source_day() -> None:
    source = inspect.getsource(
        guard_module.load_g040_runtime_only_carry_forward_evidence
    )
    assert "_G040_SOURCE_TRADING_DAY_JST}.started.json" in source
    assert "_G040_SOURCE_TRADING_DAY_JST}.passed.json" in source
    assert "target_ledger._trading_day_jst}.started.json" not in source
    assert "target_ledger._trading_day_jst}.passed.json" not in source


def test_canary_uses_generation_aware_preparation_evidence() -> None:
    prepare_source = inspect.getsource(canary_module.prepare_g013_canary_session)
    refresh_source = inspect.getsource(
        canary_module._refresh_session_evidence_before_permit
    )
    for source in (prepare_source, refresh_source):
        assert "load_generation_completed_preparation_evidence" in source
        assert "generation_label=generation.generation_label" in source
        assert "now_utc=current" in source
        assert "load_completed_preparation_evidence" not in source
    assert "current = datetime.now(UTC)" in refresh_source


def test_runtime_only_completed_evidence_is_target_bound_and_one_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generation_digest = "sha256:" + ("4" * 64)
    reviewed_digest = "sha256:" + ("5" * 64)
    state_root = tmp_path / f"generation-{reviewed_digest[7:]}-{generation_digest[7:]}"
    state_root.mkdir()
    external_gate = guard_module.V4ExternalPreparationGate(
        token=guard_module._GATE_TOKEN,
        reviewed_files_digest=reviewed_digest,
        state_root=state_root,
    )
    monkeypatch.setattr(
        guard_module,
        "require_g040_runtime_only_monitor_completion",
        lambda **_kwargs: SimpleNamespace(),
    )

    evidence = guard_module.load_generation_completed_preparation_evidence(
        repository=tmp_path,
        external_gate=external_gate,
        generation_digest=generation_digest,
        generation_label="H11_AUTO_30M_20260730_G050",
        now_utc=datetime(2026, 7, 30, 0, 0, tzinfo=UTC),
    )

    evidence.consume_for_generation(generation_digest)
    assert (
        state_root / "generation_consumed.2026-07-30.json"
    ).is_file()
    with pytest.raises(
        V4ActualPreparationGuardError,
        match="PREPARATION_COMPLETED_EVIDENCE_INVALID",
    ):
        evidence.consume_for_generation(generation_digest)


@pytest.mark.parametrize(
    "generation_label",
    (
        "H11_AUTO_30M_20260729_G040",
        "H11_AUTO_30M_20260729_G041",
        "H11_AUTO_30M_20260730_G047",
        "H11_AUTO_30M_20260730_G048",
        "H11_AUTO_30M_20260730_G049",
        "H11_AUTO_30M_20260730_G050",
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
