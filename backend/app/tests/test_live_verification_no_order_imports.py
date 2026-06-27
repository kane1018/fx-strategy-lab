from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "live_verification"


def _source_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*.py"))


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in blocked_modules)


def _string_constants(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _field_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            names.update(_target_names(node.target))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_target_names(target))
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Attribute):
        return {target.attr}
    if isinstance(target, ast.Tuple):
        names: set[str] = set()
        for element in target.elts:
            names.update(_target_names(element))
        return names
    return set()


def _call_name(node: ast.Call) -> str | None:
    func: Any = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_live_verification_package_avoids_blocked_imports_and_config_reads() -> None:
    blocked_modules = {
        "app." + "brokers",
        "dot" + "env",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "hmac",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}

    for path in _source_files():
        path_blocked_modules = set(blocked_modules)
        if path.name == "actual_headers_signature.py":
            path_blocked_modules.discard("hmac")
        if path.name == "live_order_once.py":
            path_blocked_modules = path_blocked_modules - {"hmac", "httpx"}
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not _is_blocked_module(alias.name, path_blocked_modules)
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not _is_blocked_module(module, path_blocked_modules)
            if isinstance(node, ast.Name):
                assert node.id not in blocked_names
            if isinstance(node, ast.Attribute):
                assert node.attr not in blocked_attrs


def test_signature_request_design_has_no_crypto_or_http_imports() -> None:
    blocked_modules = {
        "hmac",
        "hashlib",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
    }
    path = PACKAGE_ROOT / "signature_request_design.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_signature_headers_body_plan_has_no_crypto_http_or_secret_imports() -> None:
    blocked_modules = {
        "hmac",
        "hashlib",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "dotenv",
        "app." + "brokers",
    }
    path = PACKAGE_ROOT / "signature_headers_body_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_actual_order_body_has_no_crypto_http_or_secret_imports() -> None:
    blocked_modules = {
        "hmac",
        "hashlib",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "dotenv",
        "app." + "brokers",
    }
    path = PACKAGE_ROOT / "actual_order_body.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_actual_headers_signature_allows_only_crypto_imports() -> None:
    allowed_modules = {"hmac", "hashlib", "json", "dataclasses"}
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "dotenv",
        "app." + "brokers",
    }
    path = PACKAGE_ROOT / "actual_headers_signature.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_modules or not _is_blocked_module(
                    alias.name,
                    blocked_modules,
                )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_mock_signed_transport_has_no_http_or_secret_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "dotenv",
        "app." + "brokers",
    }
    path = PACKAGE_ROOT / "mock_signed_transport.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_order_submission_skeleton_has_no_http_or_secret_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
    }
    path = PACKAGE_ROOT / "order_submission_skeleton.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_one_shot_boundary_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
        "read_text",
        "write_text",
    }
    path = PACKAGE_ROOT / "live_order_one_shot_boundary.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
            assert not module.endswith("live_order_once")
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_one_shot_execution_runbook_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_execution_runbook.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_e2e_dry_run_chain_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_e2e_dry_run_chain.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_readiness_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_readiness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_gate_plan_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_gate_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_pre_approval_fresh_preflight_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_pre_approval_fresh_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_gate_generation_package_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_gate_generation_package.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_pre_implementation_audit_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_pre_implementation_audit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_implementation_readiness_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_implementation_readiness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_disabled_scaffold_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_disabled_scaffold.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_enablement_criteria_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_enablement_criteria.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_enablement_dry_run_plan_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_enablement_dry_run_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_gate_enablement_state_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_gate_enablement_state.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_approval_artifact_validation_has_no_api_order_or_clipboard_dependencies(
) -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_artifact_validation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_live_order_preflight_has_no_http_or_secret_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_verification_package_has_no_execution_function_defs_or_calls() -> None:
    blocked_names = {
        "sub" + "mit",
        "se" + "nd",
        "pl" + "ace",
        "can" + "cel",
        "am" + "end",
        "clo" + "se",
    }
    blocked_http_call_names = {
        "post",
        "put",
        "delete",
        "request",
    }

    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        path_blocked_http_call_names = set(blocked_http_call_names)
        if path.name == "live_order_once.py":
            path_blocked_http_call_names.discard("post")
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert function_names.isdisjoint(blocked_names)
        assert function_names.isdisjoint(path_blocked_http_call_names)
        call_names = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for name in [_call_name(node)]
            if name is not None
        }
        assert call_names.isdisjoint(blocked_names)
        assert call_names.isdisjoint(path_blocked_http_call_names)


def test_live_verification_package_has_no_http_or_private_order_strings() -> None:
    blocked_substrings = {
        "/private/v1/" + "order",
        "/private/v1/" + "speedOrder",
        "/private/v1/" + "cancelOrders",
        "/private/v1/" + "closeOrder",
        "speed" + "Order",
        "close" + "Order",
        "can" + "celOrders",
        "change" + "Order",
        "BROKER_" + "SUBMIT",
        "ORDER_" + "SENT",
        "PRIVATE_" + "ORDER_API",
        "LIVE_" + "ORDER_PLACED",
    }
    blocked_exact_strings = {
        "POST",
        "PUT",
        "DELETE",
        "Authorization",
        "API-" + "KEY",
        "API-" + "SIGN",
        "API-" + "TIMESTAMP",
        "sign" + "ature",
        "status_code",
        "response_body",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "sub" + "mit",
        "se" + "nd",
        "pl" + "ace",
        "can" + "cel",
        "am" + "end",
        "clo" + "se",
    }

    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings = _string_constants(tree)
        path_blocked_exact_strings = set(blocked_exact_strings)
        path_blocked_substrings = set(blocked_substrings)
        if path.name in {
            "actual_headers_signature.py",
            "order_submission_skeleton.py",
        }:
            path_blocked_exact_strings.discard("POST")
            path_blocked_substrings.discard("/private/v1/" + "order")
        if path.name == "live_order_once.py":
            path_blocked_exact_strings = path_blocked_exact_strings - {
                "POST",
                "API-" + "KEY",
                "API-" + "SIGN",
                "API-" + "TIMESTAMP",
            }
            path_blocked_substrings.discard("/private/v1/" + "order")
        if path.name == "actual_headers_signature.py":
            path_blocked_exact_strings = path_blocked_exact_strings - {
                "API-" + "KEY",
                "API-" + "SIGN",
                "API-" + "TIMESTAMP",
            }
        if path.name == "live_order_one_shot_boundary.py":
            path_blocked_exact_strings.discard("sign" + "ature")
            path_blocked_substrings.discard("change" + "Order")
            path_blocked_substrings.discard("close" + "Order")
        assert strings.isdisjoint(path_blocked_exact_strings)
        for marker in path_blocked_substrings:
            assert all(marker not in value for value in strings)


def test_live_verification_package_does_not_define_order_payload_fields() -> None:
    blocked_fields = {
        "price",
        "order_price",
        "orderType",
        "order_type",
        "executionType",
        "timeInForce",
        "settleType",
        "losscutPrice",
        "losscut_price",
        "order_payload",
        "payload",
        "request_body",
        "request_headers",
        "body",
        "endpoint",
        "method",
        "path",
        "url",
        "raw_request",
        "raw_response",
        "response",
        "response_body",
        "response_headers",
        "status_code",
        "headers",
        "header_values",
        "signature",
        "signature_value",
        "api_sign",
        "actual_signature",
        "api_key",
        "api_secret",
        "credential",
        "credentials",
        "hmac_digest",
        "secret",
        "token",
        "authorization",
        "timestamp",
        "sign",
        "http_client",
    }

    for path in _source_files():
        if path.name == "live_order_once.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        field_names = _field_names(tree)
        if path.name == "actual_order_body.py":
            field_names = field_names - {
                "executionType",
                "timeInForce",
                "settleType",
            }
        if path.name == "actual_headers_signature.py":
            field_names = field_names - {
                "api_key",
                "api_secret",
                "timestamp",
                "method",
                "path",
                "body_serialization",
            }
        assert field_names.isdisjoint(blocked_fields)


def test_signature_headers_body_plan_has_no_actual_transport_or_credential_fields() -> None:
    allowed_safe_flags = {
        "body_plan_created",
        "headers_plan_created",
        "signature_plan_created",
        "actual_body_created",
        "actual_headers_created",
        "actual_signature_created",
        "headers_saved",
        "signature_saved",
        "raw_request_saved",
        "raw_response_saved",
        "api_key_value_exposed",
        "api_secret_value_exposed",
        "credential_values_exposed",
        "hmac_used",
        "http_post_enabled",
        "real_order_attempted",
    }
    blocked_fields = {
        "actual_body",
        "body",
        "request_body",
        "body_json",
        "actual_headers",
        "headers",
        "header_values",
        "actual_signature",
        "signature",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "url",
        "status_code",
        "response_body",
        "request_headers",
    }
    path = PACKAGE_ROOT / "signature_headers_body_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_safe_flags.issubset(field_names)


def test_actual_order_body_has_no_header_signature_http_or_credential_fields() -> None:
    allowed_safe_flags = {
        "body_created",
        "headers_created",
        "signature_created",
        "raw_request_saved",
        "raw_response_saved",
        "credential_values_logged",
        "http_post_enabled",
        "real_order_attempted",
    }
    allowed_body_fields = {
        "executionType",
        "timeInForce",
        "settleType",
    }
    blocked_fields = {
        "headers",
        "request_headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "credential",
        "credentials",
        "authorization",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "url",
        "status_code",
        "response_body",
        "request_body",
    }
    path = PACKAGE_ROOT / "actual_order_body.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_safe_flags.issubset(field_names)
    assert allowed_body_fields.issubset(field_names)


def test_actual_order_body_has_no_http_payload_conversion_methods() -> None:
    blocked_function_names = {
        "to_json",
        "to_http_payload",
        "to_request_body",
    }
    blocked_fields = {
        "request_body",
        "raw_request",
        "headers",
        "signature",
        "header_values",
        "signature_value",
        "credential",
        "credentials",
    }
    path = PACKAGE_ROOT / "actual_order_body.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    field_names = _field_names(tree)

    assert function_names.isdisjoint(blocked_function_names)
    assert field_names.isdisjoint(blocked_fields)


def test_actual_headers_signature_exposes_only_safe_public_fields() -> None:
    allowed_safe_flags = {
        "headers_created",
        "signature_created",
        "hmac_used",
        "http_post_enabled",
        "raw_headers_saved",
        "raw_signature_saved",
        "raw_request_saved",
        "raw_response_saved",
        "credential_values_logged",
        "api_key_value_exposed",
        "api_secret_value_exposed",
        "signature_value_exposed",
        "bundle_passed",
    }
    allowed_summaries = {
        "header_names_summary",
        "signature_algorithm_summary",
        "body_serialization_summary",
    }
    allowed_inputs = {
        "api_key",
        "api_secret",
        "timestamp",
        "method",
        "path",
        "body_serialization",
    }
    blocked_fields = {
        "headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "secret",
        "token",
        "authorization",
        "raw_headers",
        "raw_signature",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "url",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
    }
    path = PACKAGE_ROOT / "actual_headers_signature.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_safe_flags.issubset(field_names)
    assert allowed_summaries.issubset(field_names)
    assert allowed_inputs.issubset(field_names)


def test_mock_signed_transport_exposes_only_safe_public_fields() -> None:
    allowed_safe_flags = {
        "network_enabled",
        "http_client_enabled",
        "http_post_enabled",
        "real_order_attempted",
        "raw_request_saved",
        "raw_response_saved",
        "credential_values_logged",
        "bundle_passed",
        "transport_passed",
    }
    blocked_fields = {
        "headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "raw_headers",
        "raw_signature",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "url",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
    }
    path = PACKAGE_ROOT / "mock_signed_transport.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_safe_flags.issubset(field_names)


def test_order_submission_skeleton_exposes_only_safe_public_fields() -> None:
    allowed_safe_flags = {
        "endpoint_allowlisted",
        "manual_approval_confirmed",
        "safety_passed",
        "network_enabled",
        "http_client_enabled",
        "http_post_enabled",
        "mock_transport_only",
        "retry_enabled",
        "loop_enabled",
        "result_unknown",
        "real_order_attempted",
        "raw_request_saved",
        "raw_response_saved",
        "raw_headers_saved",
        "raw_signature_saved",
        "credential_values_logged",
        "skeleton_passed",
        "mock_transport_passed",
    }
    allowed_metadata = {
        "endpoint_path",
        "http_method",
    }
    blocked_fields = {
        "headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "raw_headers",
        "raw_signature",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "url",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
    }
    path = PACKAGE_ROOT / "order_submission_skeleton.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_safe_flags.issubset(field_names)
    assert allowed_metadata.issubset(field_names)


def test_live_order_preflight_exposes_only_safe_public_fields() -> None:
    allowed_presence_fields = {
        "api_key_present",
        "api_secret_present",
    }
    allowed_preflight_flags = {
        "readonly_assets_check_passed",
        "readonly_open_positions_check_passed",
        "readonly_active_orders_check_passed",
        "previous_result_known",
        "result_unknown",
        "step2_skeleton_passed",
        "mock_submission_passed",
        "tests_passed",
        "ruff_passed",
        "git_clean",
        "market_window_allowed",
        "maintenance_active",
        "important_event_window_active",
        "initial_live_order_only",
        "manual_approval_required",
        "manual_approval_present_for_execution",
        "retry_enabled",
        "loop_enabled",
        "kill_switch_active",
        "safety_violation_detected",
        "http_post_enabled",
        "real_order_attempted",
        "preflight_passed",
        "ready_for_step4_prompt",
        "live_order_allowed_now",
        "requires_separate_user_approval",
    }
    allowed_counts = {
        "open_positions_count",
        "active_orders_count",
        "max_daily_attempts",
        "session_attempt_count",
        "daily_attempt_count",
    }
    blocked_fields = {
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "raw_headers",
        "raw_signature",
        "raw_request",
        "raw_response",
        "request_url",
        "url",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
        "account_balance",
        "account_assets",
        "open_positions",
        "active_orders",
        "position_detail",
        "order_detail",
    }
    path = PACKAGE_ROOT / "live_order_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_presence_fields.issubset(field_names)
    assert allowed_preflight_flags.issubset(field_names)
    assert allowed_counts.issubset(field_names)


def test_live_order_reject_classification_has_no_http_secret_or_order_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_reject_classification.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_reject_classification_exposes_only_sanitized_fields() -> None:
    allowed_input_fields = {
        "transport_result",
        "api_status_success",
        "result_unknown",
        "http_status_class",
        "has_error_code",
        "error_code",
        "message_code",
        "response_data_present",
        "order_attempt_count",
        "open_positions_count_after",
        "active_orders_count_after",
    }
    allowed_classification_fields = {
        "classification_id",
        "reject_category",
        "confidence",
        "is_retry_allowed",
        "requires_user_account_check",
        "requires_code_review",
        "requires_spec_review",
        "requires_next_day_or_new_ledger",
        "safe_to_retry_today",
        "reason_summary",
        "recommended_next_action",
    }
    blocked_fields = {
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "headers",
        "actual_headers",
        "header_values",
        "signature",
        "signature_value",
        "actual_signature",
        "api_sign",
        "hmac_digest",
        "raw_headers",
        "raw_signature",
        "raw_request",
        "raw_response",
        "request_url",
        "url",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
        "account_balance",
        "account_assets",
        "open_positions",
        "active_orders",
        "orderId",
        "rootOrderId",
        "clientOrderId",
        "price",
        "timestamp",
    }
    path = PACKAGE_ROOT / "live_order_reject_classification.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_input_fields.issubset(field_names)
    assert allowed_classification_fields.issubset(field_names)


def test_live_order_candidate_has_no_http_secret_private_api_or_broker_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_candidate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_candidate_exposes_only_dry_run_review_fields() -> None:
    allowed_fields = {
        "candidate",
        "candidate_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "confidence",
        "rationale",
        "created_at",
        "expires_at",
        "market_snapshot_ref",
        "paper_trade_ref",
        "shadow_run_ref",
        "status",
        "blocked_reason",
        "size",
        "execution_type",
        "requires_human_approval",
        "allowed_for_live",
        "dry_run_only",
        "risk_gate_required",
        "approval_gate_required",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_candidate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_candidate_risk_gate_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_candidate_risk_gate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_candidate_risk_gate_exposes_only_sanitized_review_fields() -> None:
    allowed_fields = {
        "snapshot_id",
        "created_at",
        "account_assets_success",
        "open_positions_count",
        "active_orders_count",
        "symbol_min_open_order_size",
        "symbol_size_step",
        "spread_jpy",
        "ticker_age_seconds",
        "market_window_allowed",
        "maintenance_active",
        "important_event_window_ok",
        "ledger_unused",
        "daily_live_attempt_count",
        "session_live_attempt_count",
        "result_unknown",
        "git_clean",
        "tests_passed",
        "ruff_passed",
        "secret_scan_passed",
        "raw_response_saved",
        "raw_response_displayed",
        "decision_id",
        "candidate_id",
        "status",
        "risk_gate_passed",
        "eligible_for_human_review",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "blocked_reasons",
        "reason_summary",
        "recommended_next_step",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
    }
    path = PACKAGE_ROOT / "live_order_candidate_risk_gate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_candidate_trace_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_candidate_trace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_candidate_trace_exposes_only_sanitized_review_fields() -> None:
    allowed_fields = {
        "trace_record",
        "trace_id",
        "created_at",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "paper_trade_ref",
        "shadow_run_ref",
        "paper_decision_ref",
        "shadow_decision_ref",
        "review_batch_id",
        "candidate_id",
        "risk_decision_id",
        "risk_status",
        "risk_gate_passed",
        "eligible_for_human_review",
        "symbol",
        "side",
        "size",
        "execution_type",
        "candidate_status",
        "trace_status",
        "blocked_reasons",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "recommended_next_step",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_candidate_trace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_candidate_review_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_candidate_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_candidate_review_exposes_only_sanitized_report_fields() -> None:
    allowed_fields = {
        "review_report",
        "review_id",
        "created_at",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "paper_trade_ref",
        "shadow_run_ref",
        "symbol",
        "side",
        "size",
        "execution_type",
        "candidate_status",
        "risk_status",
        "trace_status",
        "review_status",
        "risk_gate_passed",
        "eligible_for_human_review",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_candidate_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_session_policy_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_session_policy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_session_policy_exposes_only_sanitized_policy_fields() -> None:
    allowed_fields = {
        "snapshot_id",
        "created_at",
        "policy_date",
        "initial_micro_live_completed",
        "previous_order_result_confirmed",
        "previous_result_unknown",
        "open_positions_count",
        "active_orders_count",
        "session_count_today",
        "daily_live_size_total",
        "last_session_completed_at",
        "minutes_since_last_session",
        "session_size",
        "max_sessions_per_day",
        "min_minutes_between_sessions",
        "max_daily_size_total",
        "git_clean",
        "tests_passed",
        "ruff_passed",
        "secret_scan_passed",
        "raw_response_saved",
        "raw_response_displayed",
        "market_window_allowed",
        "maintenance_active",
        "important_event_window_ok",
        "decision_id",
        "review_id",
        "candidate_id",
        "status",
        "policy_passed",
        "eligible_for_review_session",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "blocked_reasons",
        "reason_summary",
        "recommended_next_step",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_session_policy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_review_session_bundle_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_review_session_bundle.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_review_session_bundle_exposes_only_sanitized_bundle_fields() -> None:
    allowed_fields = {
        "bundle",
        "bundle_id",
        "created_at",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "review_status",
        "policy_status",
        "bundle_status",
        "risk_gate_passed",
        "eligible_for_human_review",
        "policy_passed",
        "eligible_for_review_session",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "blocked_reasons",
        "session_size",
        "session_count_today",
        "max_sessions_per_day",
        "remaining_sessions_today",
        "daily_live_size_total",
        "max_daily_size_total",
        "remaining_daily_size",
        "min_minutes_between_sessions",
        "minutes_since_last_session",
        "next_session_time_hint",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_review_session_bundle.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_operator_review_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_operator_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_operator_review_exposes_only_sanitized_procedure_fields() -> None:
    allowed_fields = {
        "procedure",
        "operator_review_id",
        "created_at",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "bundle_status",
        "operator_review_status",
        "risk_gate_passed",
        "policy_passed",
        "eligible_for_operator_review",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "dry_run_only",
        "blocked_reasons",
        "remaining_sessions_today",
        "remaining_daily_size",
        "checklist_items",
        "summary",
        "recommended_next_step",
        "item_id",
        "label",
        "detail",
        "required",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
    }
    path = PACKAGE_ROOT / "live_order_operator_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_approval_handoff_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_approval_handoff.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_approval_handoff_exposes_only_sanitized_package_fields() -> None:
    allowed_fields = {
        "package",
        "handoff_id",
        "created_at",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "operator_review_status",
        "handoff_status",
        "eligible_for_operator_review",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "approval_gate_issued",
        "approval_command_generated",
        "final_dynamic_preflight_required",
        "dry_run_only",
        "display_allowed_fields",
        "display_forbidden_fields",
        "final_dynamic_preflight_items",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
        "approval_id",
        "approval_command",
    }
    path = PACKAGE_ROOT / "live_order_approval_handoff.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_approval_gate_design_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_approval_gate_design.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_approval_gate_design_exposes_only_sanitized_design_fields() -> None:
    allowed_fields = {
        "design",
        "design_id",
        "created_at",
        "handoff_id",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "handoff_status",
        "design_status",
        "eligible_for_operator_review",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_template_only",
        "approval_command_copyable",
        "ttl_seconds",
        "exact_match_required",
        "same_session_required",
        "final_dynamic_preflight_required",
        "dry_run_only",
        "command_template",
        "template_text",
        "approval_id_placeholder",
        "side_placeholder",
        "ack_tokens",
        "template_only",
        "copyable",
        "display_allowed_fields",
        "display_forbidden_fields",
        "final_dynamic_preflight_items",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
        "approval_id",
        "approval_command",
    }
    path = PACKAGE_ROOT / "live_order_approval_gate_design.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_approval_gate_preview_has_no_ordering_or_real_approval_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_approval_gate_preview.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_approval_gate_preview_exposes_only_sanitized_preview_fields() -> None:
    allowed_fields = {
        "preview",
        "preview_id",
        "created_at",
        "design_id",
        "handoff_id",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "design_status",
        "preview_status",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_template_only",
        "approval_command_copyable",
        "ttl_seconds",
        "exact_match_required",
        "same_session_required",
        "final_dynamic_preflight_required",
        "dry_run_only",
        "approval_id_placeholder",
        "approval_command_template",
        "ack_tokens",
        "display_allowed_fields",
        "display_forbidden_fields",
        "final_dynamic_preflight_items",
        "validation_rules",
        "rule_id",
        "description",
        "required",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
        "approval_id",
        "approval_command",
        "copyable_command",
        "pbcopy",
    }
    path = PACKAGE_ROOT / "live_order_approval_gate_preview.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_approval_validation_simulator_has_no_ordering_imports() -> None:
    blocked_modules = {
        "hmac",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_approval_validation_simulator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def test_live_order_approval_validation_simulator_exposes_only_sanitized_fields() -> None:
    allowed_fields = {
        "simulation",
        "simulation_id",
        "created_at",
        "preview_id",
        "design_id",
        "handoff_id",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "preview_status",
        "simulation_status",
        "simulated_command_received",
        "simulated_command_exact_match",
        "simulated_command_template_only",
        "simulated_command_copyable",
        "simulated_ttl_seconds",
        "same_session",
        "already_used",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_template_only",
        "approval_command_copyable",
        "ttl_seconds",
        "exact_match_required",
        "same_session_required",
        "final_dynamic_preflight_required",
        "dry_run_only",
        "approval_id_placeholder",
        "side_placeholder",
        "ack_tokens",
        "validation_rule_results",
        "rule_results",
        "rule_id",
        "passed",
        "blocked_reason",
        "detail",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
        "section_id",
        "title",
        "lines",
        "command_text",
        "safe_simulated_ttl_seconds",
        "safe_same_session",
        "safe_already_used",
        "command_reasons",
        "preview_reasons",
        "tokens",
        "expected_tokens",
        "ack_values",
        "id_components",
        "digest",
        "created",
        "reasons",
        "merged",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger",
        "approval_id",
        "approval_command",
        "copyable_command",
        "pbcopy",
    }
    path = PACKAGE_ROOT / "live_order_approval_validation_simulator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert allowed_fields.issubset(field_names)


def test_live_order_final_dynamic_preflight_has_no_ordering_or_api_imports() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
    }
    path = PACKAGE_ROOT / "live_order_final_dynamic_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)


def test_live_order_final_dynamic_preflight_exposes_only_sanitized_fields() -> None:
    required_safe_fields = {
        "snapshot_id",
        "created_at",
        "simulation_id",
        "preview_id",
        "design_id",
        "handoff_id",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "size",
        "execution_type",
        "account_assets_status",
        "open_positions_count",
        "active_orders_count",
        "min_open_order_size",
        "size_step",
        "ticker_available",
        "spread_jpy",
        "ticker_age_seconds",
        "market_window_allowed",
        "maintenance_active",
        "important_event_window_ok",
        "ledger_unused",
        "session_attempt_count_today",
        "daily_live_size_total",
        "previous_result_confirmed",
        "result_unknown",
        "git_clean",
        "tests_passed",
        "ruff_passed",
        "secret_scan_passed",
        "raw_response_saved",
        "raw_response_displayed",
        "outbound_body_allowlist_matched",
        "request_body_equals_signing_body",
        "final_preflight_age_seconds",
        "allowed_for_live",
        "requires_human_approval",
        "approval_gate_required",
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_template_only",
        "approval_command_copyable",
        "final_dynamic_preflight_required",
        "dry_run_only",
        "check_results",
        "blocked_reasons",
        "summary",
        "recommended_next_step",
        "sections",
    }
    blocked_fields = {
        "request_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "url",
        "endpoint",
        "method",
        "http_client",
        "open_price",
        "detailed_pl",
        "ledger_path",
        "approval_id",
        "approval_command",
        "copyable_command",
        "pbcopy",
    }
    path = PACKAGE_ROOT / "live_order_final_dynamic_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    field_names = _field_names(tree)

    assert field_names.isdisjoint(blocked_fields)
    assert required_safe_fields.issubset(field_names)


def test_real_approval_artifact_generation_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_approval_artifact_generation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_api_preflight_plan_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_api_preflight_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_real_api_preflight_execution_has_no_api_order_or_clipboard_dependencies() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = PACKAGE_ROOT / "live_order_real_api_preflight_execution.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def test_live_order_once_allows_only_explicit_one_shot_http_boundary() -> None:
    path = PACKAGE_ROOT / "live_order_once.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "aiohttp",
        "urllib",
        "urllib3",
        "dotenv",
        "app." + "brokers",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    blocked_strings = {
        "speed" + "Order",
        "close" + "Order",
        "can" + "celOrders",
        "change" + "Order",
        "Authorization",
        "BROKER_" + "SUBMIT",
        "ORDER_" + "SENT",
        "PRIVATE_" + "ORDER_API",
        "LIVE_" + "ORDER_PLACED",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs

    strings = _string_constants(tree)
    for marker in blocked_strings:
        assert all(marker not in value for value in strings)


def test_live_order_once_post_call_is_limited_to_real_transport_function() -> None:
    path = PACKAGE_ROOT / "live_order_once.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        call_names = {
            name
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            for name in [_call_name(child)]
            if name is not None
        }
        if node.name == "post_live_order_with_httpx":
            assert "post" in call_names
            assert call_names.isdisjoint({"put", "delete", "request"})
        else:
            assert "post" not in call_names
            assert call_names.isdisjoint({"put", "delete", "request"})


def test_live_order_once_public_fields_do_not_store_sensitive_artifacts() -> None:
    path = PACKAGE_ROOT / "live_order_once.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_public_fields = {
        "headers",
        "header_values",
        "signature",
        "signature_value",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "raw_request",
        "raw_response",
        "request_headers",
        "response_headers",
        "response_body",
        "account_balance",
        "position_detail",
        "order_detail",
    }
    allowed_internal_names = {
        "api_key",
        "api_secret",
        "sensitive_headers",
        "headers",
        "signature_digest",
        "body_serialization",
        "headers_saved",
        "signature_saved",
        "raw_request_saved",
        "raw_response_saved",
    }
    field_names = _field_names(tree) - allowed_internal_names

    assert field_names.isdisjoint(blocked_public_fields)
