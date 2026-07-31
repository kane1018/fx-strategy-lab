from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.h11_auto.v4_gmo_monitor_supervisor as supervisor_module
import scripts.h11_auto_v4_unattended_live_scheduled_launcher as launcher
from app.h11_auto.runtime_safety import DeadManStore
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_monitor_supervisor import V4GmoMonitorSupervisor
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

NOW = datetime(2026, 7, 31, 1, 0, tzinfo=UTC)


def _generation():
    selected = V4ApprovedOperatorSelections()
    policy = V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260731_G063",
        implementation_digest="sha256:" + "c" * 64,
        policy=policy,
    )


def test_g063_no_post_bootstrap_creates_only_safety_evidence(
    tmp_path: Path,
) -> None:
    generation = _generation()
    supervisor = V4GmoMonitorSupervisor(
        repository=tmp_path,
        generation=generation,
        runtime_clock=lambda: NOW,
    )
    supervisor.acquire_single_process()
    try:
        tick = supervisor.run_tick(now_utc=NOW)
    finally:
        supervisor.close()

    root = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest=generation.digest,
    )
    assert tick.runtime_risk_ready is True
    assert tick.dead_man_alive is True
    assert tick.heartbeat_chain_beat is True
    assert tick.broker_write is False
    assert tick.actual_post_count == 0
    assert tick.entry_gate_open is False
    assert (root / "risk.json").is_file()
    assert (root / "dead-man.json").is_file()
    assert (root / "unattended-heartbeat-chain.json").is_file()
    assert (root / "supervisor-heartbeat.json").is_file()
    assert not (root / "coordinator.sqlite3").exists()


def test_g063_no_post_bootstrap_rejects_stale_dead_man(tmp_path: Path) -> None:
    generation = _generation()
    root = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest=generation.digest,
    )
    root.mkdir(parents=True)
    dead_man = DeadManStore(
        root / "dead-man.json",
        policy=__import__(
            "app.h11_auto.v4_gmo_monitor_supervisor",
            fromlist=["v4_gmo_dead_man_policy"],
        ).v4_gmo_dead_man_policy(),
    )
    dead_man.heartbeat(heartbeat_utc=NOW - timedelta(seconds=61))
    supervisor = V4GmoMonitorSupervisor(
        repository=tmp_path,
        generation=generation,
        runtime_clock=lambda: NOW,
    )
    supervisor.acquire_single_process()
    try:
        with pytest.raises(
            RuntimeError,
            match="V4_SUPERVISOR_G063_DEAD_MAN_NOT_ALIVE",
        ):
            supervisor.run_tick(now_utc=NOW)
    finally:
        supervisor.close()


def test_g063_no_post_bootstrap_marker_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generation = SimpleNamespace(
        digest="sha256:" + "d" * 64,
        generation_label="H11_AUTO_30M_20260731_G063",
        live_ready=False,
        unattended_live_supported=False,
        actual_post_authorized=False,
    )
    state_root = tmp_path / "state"
    state_root.mkdir()
    for name in (
        "risk.json",
        "dead-man.json",
        "unattended-heartbeat-chain.json",
        "supervisor-heartbeat.json",
    ):
        (state_root / name).write_text("{}\n", encoding="utf-8")
    (state_root / "g063-no-post-runtime-bootstrap-completed.json").write_text(
        json.dumps(
            {
                "generation_digest": generation.digest,
                "status": "G063_NO_POST_RUNTIME_BOOTSTRAP_COMPLETED",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_: state_root)
    monkeypatch.setattr(
        supervisor_module,
        "v4_gmo_runtime_state_root",
        lambda **_: state_root,
    )
    monkeypatch.setattr(
        launcher,
        "_verify_baked_digests",
        lambda **_: ("sha256:" + "e" * 64, generation),
    )
    monkeypatch.setattr(
        supervisor_module.V4GmoMonitorSupervisor,
        "run_tick",
        lambda *args, **kwargs: pytest.fail("completed bootstrap must not rerun"),
    )

    result = launcher.main(
        [
            "--repository",
            str(tmp_path),
            "--expected-reviewed-files-digest",
            "sha256:" + "e" * 64,
            "--expected-generation-digest",
            generation.digest,
        ]
    )

    assert result == 0
    assert "G063_NO_POST_RUNTIME_BOOTSTRAP_ALREADY_COMPLETED" in capsys.readouterr().out
