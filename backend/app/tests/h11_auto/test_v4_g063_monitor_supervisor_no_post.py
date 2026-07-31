from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_monitor_supervisor import V4GmoMonitorSupervisor
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g063_position_reconciliation_no_post import (
    write_g063_position_reconciliation_no_post,
)

NOW = datetime(2026, 7, 31, 1, 0, tzinfo=UTC)


def _policy() -> V4GmoExecutionPolicy:
    selected = V4ApprovedOperatorSelections()
    return V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )


def _generation():
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260731_G063",
        implementation_digest="sha256:" + "c" * 64,
        policy=_policy(),
    )


def _seed_open_cycle(repository: Path):
    generation = _generation()
    root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    store = V4GmoActualCoordinatorStore(root / "coordinator.sqlite3")
    selected = V4ApprovedOperatorSelections()
    signal = FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=NOW - timedelta(minutes=1),
        valid_until_utc=NOW + timedelta(minutes=1),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    store.prepare_entry_intent(
        generation=generation,
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW - timedelta(seconds=1),
    )
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE cycles SET market_attempted_at_utc=?, "
            "protection_confirmed_at_utc=?",
            (NOW.isoformat(), NOW.isoformat()),
        )
    return generation, root


def test_g063_explicit_position_evidence_projects_on_exit_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.h11_auto.v4_gmo_monitor_supervisor as module

    generation, root = _seed_open_cycle(tmp_path)
    write_g063_position_reconciliation_no_post(
        state_root=root,
        generation_digest=generation.digest,
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
        observed_at_utc=NOW,
    )
    monkeypatch.setattr(
        module.V4GmoMonitorSupervisor,
        "_maintain_g040_runtime_safety",
        lambda *args, **kwargs: None,
    )
    supervisor = V4GmoMonitorSupervisor(repository=tmp_path, generation=generation)
    supervisor.acquire_single_process()
    try:
        tick = supervisor.run_tick(now_utc=NOW)
    finally:
        supervisor.close()

    assert tick.protection_confirmed is True
    assert tick.ownership_exact is True
    assert tick.quantity_matches is True
    assert tick.entry_gate_open is False
    assert tick.persistent_halt is False


def test_g063_missing_position_evidence_projects_halted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.h11_auto.v4_gmo_monitor_supervisor as module

    generation, _root = _seed_open_cycle(tmp_path)
    monkeypatch.setattr(
        module.V4GmoMonitorSupervisor,
        "_maintain_g040_runtime_safety",
        lambda *args, **kwargs: None,
    )
    supervisor = V4GmoMonitorSupervisor(repository=tmp_path, generation=generation)
    supervisor.acquire_single_process()
    try:
        tick = supervisor.run_tick(now_utc=NOW)
    finally:
        supervisor.close()

    assert tick.protection_confirmed is False
    assert tick.ownership_exact is False
    assert tick.quantity_matches is False
    assert tick.persistent_halt is True
    assert tick.entry_gate_open is False
