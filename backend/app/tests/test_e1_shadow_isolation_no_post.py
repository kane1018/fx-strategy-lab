"""Structural isolation tests for the E1 shadow-only package."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.shadow.e1.contracts import (
    E1CycleResult,
    EnginePhase,
    ShadowGateToken,
    shadow_safety_flags,
)
from app.shadow.e1.engine import (
    E1EngineError,
    ShadowVirtualExecutor,
    build_e1_shadow_engine,
)
from app.shadow.e1.persistence import VirtualVenueStateStore

E1_ROOT = Path(__file__).resolve().parents[1] / "shadow" / "e1"


def _modules():
    return tuple(sorted(E1_ROOT.glob("*.py")))


def _imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_e1_package_imports_no_network_broker_private_live_or_settings_modules() -> None:
    banned = (
        "app.brokers",
        "app.private_api",
        "app.live_verification",
        "app.security",
        "app.services.gmo_live",
        "app.shadow.gmo_public",
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "socket",
        "hmac",
        "dotenv",
        "pydantic_settings",
        "subprocess",
    )
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _imports(tree)
        assert not {
            name
            for name in imports
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in banned)
        }, path.name


def test_e1_threading_surface_is_mutex_only_and_starts_no_worker() -> None:
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "threading":
                assert {alias.name for alias in node.names} <= {"RLock"}, path.name
            if isinstance(node, ast.Call):
                called = node.func.attr if isinstance(node.func, ast.Attribute) else None
                if isinstance(node.func, ast.Name):
                    called = node.func.id
                assert called not in {"Thread", "Timer", "start_new_thread"}, path.name


def test_e1_package_uses_stdlib_or_its_own_package_only() -> None:
    allowed_imports = {
        "__future__",
        "app.shadow.e1.contracts",
        "app.shadow.e1.engine",
        "app.shadow.e1.persistence",
        "app.shadow.e1.qualification",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fcntl",
        "functools",
        "hashlib",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "threading",
        "typing",
    }
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert _imports(tree) <= allowed_imports, path.name


def test_e1_package_has_no_env_dynamic_import_or_sleep_surface() -> None:
    forbidden_calls = {
        "getenv",
        "__import__",
        "import_module",
        "sleep",
        "system",
        "popen",
    }
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"environ", *forbidden_calls}, path.name
            elif isinstance(node, ast.Name):
                assert node.id not in forbidden_calls, path.name


def test_e1_source_contains_no_order_endpoint_or_live_allow_bridge_vocabulary() -> None:
    forbidden = (
        "/private/v1",
        "closeOrder",
        "cancelOrders",
        "changeOrder",
        "live_order_once",
        "allow_real_broker_post",
        "allow_live_http_post",
        "ENABLE_LIVE_TRADING",
        "GMO_FX_ORDER_ENABLED",
    )
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in source, (path.name, needle)


def test_virtual_executor_has_only_entry_and_position_specific_settlement_effects() -> None:
    public_methods = {
        name
        for name, value in inspect.getmembers(ShadowVirtualExecutor, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == {"execute_entry", "execute_settlement"}
    assert not any(
        word in name
        for name in public_methods
        for word in ("generic", "opposite", "flip", "hedge", "cancel", "change", "close")
    )
    entry_signature = inspect.signature(ShadowVirtualExecutor.execute_entry)
    settlement_signature = inspect.signature(ShadowVirtualExecutor.execute_settlement)
    assert entry_signature.parameters["token"].annotation == "ShadowGateToken"
    assert settlement_signature.parameters["token"].annotation == "ShadowGateToken"


def test_virtual_venue_public_surface_is_read_only() -> None:
    public_methods = {
        name
        for name, value in inspect.getmembers(VirtualVenueStateStore, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == set()


def test_token_and_results_cannot_be_mistaken_for_live_permission() -> None:
    assert ShadowGateToken.__module__.startswith("app.shadow.e1")
    result = E1CycleResult(
        status="SAFE_FIXTURE",
        phase=EnginePhase.READY_FLAT,
        reason_codes=(),
        virtual_execution_attempted=False,
        token_issued=False,
    )
    assert result.actual_post_count == 0
    assert result.real_http_performed is False
    assert result.broker_or_private_api_used is False
    assert result.live_permission_granted is False
    assert not result
    assert shadow_safety_flags()["real_post_count"] == 0


def test_e1_output_root_is_ignored_by_git_policy() -> None:
    gitignore = (E1_ROOT.parents[3] / ".gitignore").read_text(encoding="utf-8")
    assert "shadow_exports/" in gitignore


def test_public_factory_rejects_run_id_path_escape_before_writing(tmp_path) -> None:
    output_root = tmp_path / "shadow_exports" / "e1"
    escaped = tmp_path / "escaped"
    with pytest.raises(E1EngineError, match="safe local identifier"):
        build_e1_shadow_engine(output_root=output_root, run_id="../../escaped")
    assert escaped.exists() is False


def test_public_factory_rejects_symlinked_run_root(tmp_path) -> None:
    output_root = tmp_path / "shadow_exports" / "e1"
    output_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (output_root / "safe-run").symlink_to(outside, target_is_directory=True)
    with pytest.raises(E1EngineError, match="run root cannot be a symlink"):
        build_e1_shadow_engine(output_root=output_root, run_id="safe-run")
    assert tuple(outside.iterdir()) == ()


def test_public_factory_rejects_symlinked_output_ancestor(tmp_path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside-ancestor"
    outside.mkdir()
    (work / "shadow_exports").symlink_to(outside, target_is_directory=True)
    output_root = work / "shadow_exports" / "e1"
    with pytest.raises(E1EngineError, match="ancestors cannot be symlinks"):
        build_e1_shadow_engine(output_root=output_root, run_id="safe-run")
    assert (outside / "e1").exists() is False
