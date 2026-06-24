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
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert function_names.isdisjoint(blocked_names)
        assert function_names.isdisjoint(blocked_http_call_names)
        call_names = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for name in [_call_name(node)]
            if name is not None
        }
        assert call_names.isdisjoint(blocked_names)
        assert call_names.isdisjoint(blocked_http_call_names)


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
        if path.name == "actual_headers_signature.py":
            path_blocked_exact_strings = path_blocked_exact_strings - {
                "API-" + "KEY",
                "API-" + "SIGN",
                "API-" + "TIMESTAMP",
            }
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
