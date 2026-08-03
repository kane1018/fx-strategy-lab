"""Focused regressions for the G076 no-POST safety boundaries."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.h11_v4_g076_runtime import G076FakeOnlyCallable, safe_g076_api_status
from scripts.h11_auto_v4_g076_operation_60_no_post import (
    run_g076_operation_60_candidate,
)
from scripts.h11_auto_v4_g076_runtime_bootstrap import _refresh_safety_chain


def test_blocking_fake_installer_becomes_unknown_without_waiting_forever(tmp_path):
    release = threading.Event()

    def blocking_installer() -> None:
        release.wait(timeout=1)

    try:
        outcome = run_g076_operation_60_candidate(
            state_root=tmp_path,
            generation_digest="sha256:" + "a" * 64,
            reviewed_files_digest="sha256:" + "b" * 64,
            installer=G076FakeOnlyCallable(blocking_installer),
            readiness_verifier=G076FakeOnlyCallable(lambda: True),
            installer_timeout_seconds=0.01,
        )
    finally:
        release.set()

    assert outcome == "UNKNOWN"
    result_path = next(tmp_path.glob("*result*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "UNKNOWN"


def test_blocking_fake_readiness_becomes_unknown_without_waiting_forever(tmp_path):
    release = threading.Event()

    def blocking_readiness() -> bool:
        release.wait(timeout=1)
        return False

    try:
        outcome = run_g076_operation_60_candidate(
            state_root=tmp_path,
            generation_digest="sha256:" + "a" * 64,
            reviewed_files_digest="sha256:" + "b" * 64,
            installer=G076FakeOnlyCallable(lambda: None),
            readiness_verifier=G076FakeOnlyCallable(blocking_readiness),
            readiness_timeout_seconds=0.01,
        )
    finally:
        release.set()

    assert outcome == "UNKNOWN"
    result_path = next(tmp_path.glob("*result*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "UNKNOWN"


def test_stale_safety_files_are_not_overwritten_before_halt_projection(tmp_path):
    observed = datetime.now(UTC)
    dead_man_path = tmp_path / "dead-man-runtime.json"
    chain_path = tmp_path / "unattended-heartbeat-chain.json"
    dead_man_path.touch()
    chain_path.touch()

    class StaleDeadMan:
        def evaluate_current(self, *, clock):
            return SimpleNamespace(alive=False, halt_required=True)

        def heartbeat(self, *, heartbeat_utc):
            raise AssertionError("stale dead-man must not be overwritten")

    class UnusedChain:
        def assess(self, *, now_utc):
            raise AssertionError("chain must not be refreshed after stale dead-man")

        def beat(self, *, now_utc):
            raise AssertionError("stale chain must not be overwritten")

    assert _refresh_safety_chain(
        dead_man=StaleDeadMan(),
        chain=UnusedChain(),
        dead_man_path=dead_man_path,
        chain_path=chain_path,
        observed=observed,
    ) == (False, False)


def test_generic_scheduler_installer_refuses_g076_mutation():
    installer = Path(
        "backend/scripts/h11_auto_v4_install_unattended_live_scheduler_launchagent.py"
    ).read_text(encoding="utf-8")
    assert "G076_FAKE_ONLY_LAUNCHAGENT_MUTATION_DISABLED" in installer
    shared = Path(
        "backend/app/h11_auto/v4_gmo_unattended_scheduler_launchd.py"
    ).read_text(encoding="utf-8")
    assert "G076_FAKE_ONLY_LAUNCHAGENT_MUTATION_DISABLED" in shared


def test_g076_resident_paths_do_not_reach_live_arm_or_http_clients():
    bootstrap = Path(
        "backend/scripts/h11_auto_v4_g076_runtime_bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "V4UnattendedLiveArmStore" not in bootstrap
    assert "v4_unattended_live_arm_state_path" not in bootstrap
    network = Path(
        "backend/app/services/h11_v4_g076_network_diagnostics.py"
    ).read_text(encoding="utf-8")
    assert "import httpx" not in network
    assert "httpx." not in network


def test_missing_or_mismatched_runtime_status_is_not_ready(tmp_path):
    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=True,
        generation_digest="sha256:" + "a" * 64,
        reviewed_files_digest="sha256:" + "b" * 64,
    )

    assert status["control_plane_state"] == "HALTED"
    assert status["scheduler_ready"] is False
    assert status["effective_state"] == "HALTED"
    assert status["persistent_halt"] is True


def test_cached_ready_status_without_live_resident_evidence_is_halted(tmp_path):
    payload = {
        "generation_label": "H11_AUTO_30M_20260802_G076",
        "generation_digest": "sha256:" + "a" * 64,
        "reviewed_files_digest": "sha256:" + "b" * 64,
        "effective_state": "ON_WAITING",
        "entry_gate_open": False,
        "entry_state": "WAITING_FOR_RECONCILIATION",
        "reconciliation_state": "FRESH_FLAT",
        "heartbeat_at_utc": "2026-08-03T00:00:00+00:00",
        "persistent_halt": False,
        "unknown_halt": False,
        "pending_transport": False,
        "lock_single_owner": True,
        "dead_man_alive": True,
        "heartbeat_chain_beat": True,
    }
    (tmp_path / "g076-runtime-status.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    status = safe_g076_api_status(
        state_root=tmp_path,
        arm_on=True,
        generation_digest=payload["generation_digest"],
        reviewed_files_digest=payload["reviewed_files_digest"],
    )

    assert status["control_plane_state"] == "HALTED"
    assert status["scheduler_ready"] is False
