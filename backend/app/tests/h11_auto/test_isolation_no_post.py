from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import app.h11_auto.boundary as boundary
import app.h11_auto.contracts as contracts
import app.h11_auto.engine as engine
import app.h11_auto.exit_policy as exit_policy
import app.h11_auto.formal_signal_feed as formal_signal_feed
import app.h11_auto.paper as paper
import app.h11_auto.paper_runner as paper_runner
import app.h11_auto.persistence as persistence
import app.h11_auto.recovery as recovery
import app.h11_auto.report as report
import app.h11_auto.risk as risk
import app.h11_auto.runtime_safety as runtime_safety
import app.h11_auto.runtime_status as runtime_status
import app.h11_auto.signal_adapter as signal_adapter
import app.h11_auto.soak as soak
import app.h11_auto.state_machine as state_machine
import app.h11_auto.status as status
import app.h11_auto.wall_clock_soak as wall_clock_soak
from app.h11_auto.persistence import StoredCycle


def test_phase_a_package_has_no_network_private_api_or_secret_surface() -> None:
    source = "\n".join(
        inspect.getsource(module)
        for module in (
            boundary,
            contracts,
            engine,
            exit_policy,
            formal_signal_feed,
            paper,
            paper_runner,
            persistence,
            recovery,
            report,
            risk,
            runtime_safety,
            runtime_status,
            signal_adapter,
            soak,
            state_machine,
            status,
            wall_clock_soak,
        )
    )
    forbidden = (
        "import httpx",
        "import requests",
        "app.private_api",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "forex-api.coin.z.com",
        "closeOrder",
        "cancelOrders",
        "changeOrder",
    )
    for marker in forbidden:
        assert marker not in source


def test_persistent_cycle_has_no_broker_id_raw_or_credential_fields() -> None:
    names = {field.name for field in fields(StoredCycle)}
    forbidden = {
        "order_id",
        "position_id",
        "execution_id",
        "client_order_id",
        "raw_request",
        "raw_response",
        "api_key",
        "api_secret",
        "credential",
        "price",
        "size",
    }
    assert names.isdisjoint(forbidden)


def test_manual_does_not_import_the_isolated_phase_a_paper_engine() -> None:
    """``h11_manual`` must never import the old, isolated no-POST paper engine.

    ``app.h11_auto`` also contains the v4 GMO real-trading system and its
    shared infrastructure (``contracts``/``persistence``/``runtime_safety``/
    ``boundary``/``formal_signal_feed``, all reused by v4 modules) -- the
    unattended arm control panel in ``h11_manual`` legitimately depends on
    that shared infra and on v4-specific modules (``v4_actual_preparation_guard``,
    ``v4_gmo_actual_coordinator``, ``v4_gmo_generation``, ``v4_gmo_runtime_paths``)
    to arm/disarm and display status for the real system. This test protects
    only the phase-A-exclusive research modules below, which have zero v4
    usage and no legitimate reason to be reachable from any manual trading
    interface.
    """
    repo_root = Path(__file__).resolve().parents[2]
    phase_a_only_modules = (
        "engine",
        "exit_policy",
        "paper",
        "paper_runner",
        "recovery",
        "report",
        "risk",
        "runtime_status",
        "signal_adapter",
        "soak",
        "state_machine",
        "status",
        "wall_clock_soak",
    )
    manual_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repo_root / "h11_manual").glob("*.py")
    )
    for module in phase_a_only_modules:
        assert f"app.h11_auto.{module}" not in manual_source

    # The reverse direction is unaffected by v4's evolution: the isolated
    # research engine must never import the manual trading interface.
    auto_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repo_root / "h11_auto").glob("*.py")
    )
    assert "app.h11_manual" not in auto_source


def test_main_readonly_has_no_auto_package_binding() -> None:
    app_root = Path(__file__).resolve().parents[2]
    source = (app_root / "main_readonly.py").read_text(encoding="utf-8")
    assert "h11_auto" not in source
