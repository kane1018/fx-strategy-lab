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


def test_g040_monitor_carries_risk_and_beats_runtime_safety(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_digest = "sha256:" + ("4" * 64)
    source_digest = "sha256:" + ("3" * 64)
    generation = SimpleNamespace(
        digest=target_digest,
        generation_label="H11_AUTO_30M_20260729_G040",
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
    assert tick.broker_write is False
    assert tick.actual_post_count == 0
