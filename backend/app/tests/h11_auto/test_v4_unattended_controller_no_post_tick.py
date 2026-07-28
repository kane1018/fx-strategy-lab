from __future__ import annotations

import ast
import inspect
import runpy
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from app.tests.h11_auto.test_v4_unattended_controller_snapshot_no_post import (
    _sources,
)
from scripts import h11_auto_v4_unattended_controller_no_post_tick as subject


def test_offline_tick_has_no_external_or_live_imports() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "GmoPublicMarketDataClient",
        "V4GmoKeychainCredentialPair",
        "ActualPushover",
        "ActualEmail",
        "actual_transport",
        "bounded_run",
        "prepare_g013_canary_session",
    ):
        assert forbidden not in source


def test_offline_tick_application_imports_are_exactly_allowlisted() -> None:
    tree = ast.parse(inspect.getsource(subject))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module.startswith("app.") or node.module == "h11_v4_reviewed_digest")
    }
    assert imported == {
        "app.h11_auto.runtime_safety",
        "app.h11_auto.v4_actual_preparation_guard",
        "app.h11_auto.v4_gmo_generation",
        "app.h11_auto.v4_gmo_runtime_paths",
        "app.services.h11_v4_current_generation_shadow_observer_no_post",
        "app.services.h11_v4_unattended_commissioning_no_post",
        "app.services.h11_v4_unattended_controller_snapshot_no_post",
        "app.services.h11_v4_unattended_integrated_controller_no_post",
        "app.services.h11_v4_unattended_live_arm_state",
        "app.services.h11_v4_unattended_live_paths",
        "h11_v4_reviewed_digest",
    }


def test_offline_tick_import_has_no_network_or_subprocess_side_effect(
    monkeypatch,
) -> None:
    def refused(*_args, **_kwargs):
        raise AssertionError("external side effect attempted during import")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(subprocess, "run", refused)
    monkeypatch.setattr(subprocess, "Popen", refused)
    runpy.run_path(str(Path(subject.__file__).resolve()), run_name="offline_import_test")


def test_safe_failure_payload_is_literal_no_post() -> None:
    source = inspect.getsource(subject)
    assert '"broker_post_authorized": False' in source
    assert '"broker_write": False' in source
    assert '"actual_post_count": 0' in source
    assert '"private_api_read": False' in source
    assert '"notification_send_count": 0' in source


def test_safe_failure_status_is_phase_specific_and_sanitized() -> None:
    clean = subject._safe_failure("CLEAN_MAIN")
    storage = subject._safe_failure("DURABLE_STATE")
    unknown = subject._safe_failure("not-a-phase")
    assert clean["status"] == (
        "UNATTENDED_CONTROLLER_OFFLINE_CLEAN_MAIN_REFUSED_SAFE"
    )
    assert storage["status"] == (
        "UNATTENDED_CONTROLLER_OFFLINE_DURABLE_STATE_REFUSED_SAFE"
    )
    assert unknown["status"] == (
        "UNATTENDED_CONTROLLER_OFFLINE_UNKNOWN_REFUSED_SAFE"
    )
    for result in (clean, storage, unknown):
        assert result["broker_write"] is False
        assert result["actual_post_count"] == 0


def test_offline_tick_is_repeatable_and_concurrency_safe(tmp_path) -> None:
    database = tmp_path / "controller.sqlite3"
    now = datetime.now(UTC)

    def run_once():
        return subject.run_offline_tick_no_post(
            sources=_sources(),
            now_utc=now,
            database=database,
        ).to_safe_dict()

    first = run_once()
    second = run_once()
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = list(executor.map(lambda _index: run_once(), range(2)))

    assert first["blocked_reasons"] == ["ACCOUNT_SNAPSHOT_UNKNOWN"]
    assert second["blocked_reasons"] == ["PERSISTENT_GENERATION_HALT_LATCHED"]
    assert concurrent == [second, second]
    assert first["broker_write"] is False
    assert first["actual_post_count"] == 0
