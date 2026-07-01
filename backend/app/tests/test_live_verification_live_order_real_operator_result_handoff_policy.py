from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)
from app.live_verification.live_order_real_operator_result_handoff_policy import (
    LiveOrderRealOperatorResultHandoffPolicyInput,
    LiveOrderRealOperatorResultHandoffPolicyMode,
    LiveOrderRealOperatorResultHandoffPolicyStatus,
    build_live_order_real_operator_result_handoff_policy,
    render_live_order_real_operator_result_handoff_policy_markdown,
)

Status = LiveOrderRealOperatorResultHandoffPolicyStatus
Mode = LiveOrderRealOperatorResultHandoffPolicyMode
Category = LiveOrderRealOperatorExecutionResultCategory
UNSUPPORTED_RAW_CATEGORY = "RAW_POLICY_CATEGORY_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_CATEGORY = "UNSUPPORTED_REDACTED"


def _input(**overrides: object) -> LiveOrderRealOperatorResultHandoffPolicyInput:
    base = LiveOrderRealOperatorResultHandoffPolicyInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_result_handoff_policy(
        input_snapshot=_input(**overrides),
    )


def test_not_provided_valid_policy_ready_no_receipt() -> None:
    result = _build()

    assert result.status is Status.OPERATOR_RESULT_HANDOFF_POLICY_READY_NO_RECEIPT
    assert result.operator_result_handoff_policy_ready is True
    assert result.policy_mode == Mode.OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY.value
    assert result.policy_declared is True
    assert result.receipt_lifecycle_policy_declared is True
    assert result.freshness_required is True
    assert result.one_time_required is True
    assert result.non_reuse_required is True
    assert result.current_turn_required is True
    assert result.previous_turn_prohibited is True
    assert result.non_raw_required is True
    assert result.non_detail_required is True
    assert result.non_identifier_required is True
    assert result.safe_category_only is True
    assert result.operator_execution_result_category_contract_ready is True
    assert result.operator_executed_execution_boundary_ready is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_result_category == Category.NOT_PROVIDED.value
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_stale is False
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_timeout is False
    assert result.receipt_unknown is False
    assert result.receipt_failed is False
    assert result.receipt_unavailable is False
    assert result.receipt_raw_value_present is False
    assert result.receipt_detail_present is False
    assert result.receipt_id_present is False
    assert result.receipt_token_present is False
    assert result.receipt_nonce_present is False
    assert result.receipt_hash_present is False
    assert result.receipt_fingerprint_present is False
    assert result.receipt_length_present is False
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_execution_performed is False
    assert result.codex_execution_performed is False
    assert result.env_access_requested is False
    assert result.credential_read_performed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.blocked_reasons == ()


def test_ready_confirmed_policy_ready_confirmed_no_post() -> None:
    result = _build(operator_result_category=Category.READY_CONFIRMED.value)

    assert result.status is Status.OPERATOR_RESULT_HANDOFF_POLICY_READY_CONFIRMED_NO_POST
    assert result.operator_result_handoff_policy_ready is True
    assert result.operator_result_category == Category.READY_CONFIRMED.value
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_raw_value_present is False
    assert result.receipt_detail_present is False
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"policy_mode": "UNSUPPORTED_RAW_MODE"},
        {"policy_declared": False},
        {"receipt_lifecycle_policy_declared": False},
        {"freshness_required": False},
        {"one_time_required": False},
        {"non_reuse_required": False},
        {"current_turn_required": False},
        {"previous_turn_prohibited": False},
        {"non_raw_required": False},
        {"non_detail_required": False},
        {"non_identifier_required": False},
        {"safe_category_only": False},
        {"operator_execution_result_category_contract_ready": False},
        {"operator_executed_execution_boundary_ready": False},
        {"operator_result_handoff_safe": False},
        {"ready_confirmed_is_not_post_permission": False},
        {"not_provided_is_not_actual_receipt": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_INPUT
    assert result.operator_result_handoff_policy_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_category_is_safe_label": False},
        {"operator_result_category_is_allowed": False},
    ],
)
def test_unsafe_category_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSAFE_CATEGORY


def test_unsupported_raw_category_blocks_without_echoing_raw_value() -> None:
    result = _build(operator_result_category=UNSUPPORTED_RAW_CATEGORY)
    rendered = render_live_order_real_operator_result_handoff_policy_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSUPPORTED
    assert result.operator_result_category == UNSUPPORTED_SAFE_CATEGORY
    assert result.unsupported_category_present is True
    assert UNSUPPORTED_RAW_CATEGORY not in rendered
    assert UNSUPPORTED_RAW_CATEGORY not in payload
    assert UNSUPPORTED_SAFE_CATEGORY in rendered
    assert UNSUPPORTED_SAFE_CATEGORY in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_current_turn": False},
        {"receipt_fresh": False},
        {"receipt_stale": True},
        {"receipt_reused": True},
        {"receipt_previous_turn": True},
        {"receipt_expired": True},
        {"operator_result_category": Category.BLOCKED_STALE.value},
        {"operator_result_category": Category.BLOCKED_REUSED.value},
        {"operator_result_category": Category.BLOCKED_PREVIOUS_TURN.value},
    ],
)
def test_stale_reused_previous_receipts_block(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_STALE_OR_REUSED
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_timeout": True},
        {"receipt_unknown": True},
        {"receipt_failed": True},
        {"receipt_unavailable": True},
        {"operator_result_category": Category.BLOCKED_UNKNOWN.value},
        {"operator_result_category": Category.BLOCKED_FAILED.value},
        {"operator_result_category": Category.BLOCKED_UNAVAILABLE.value},
        {"operator_result_category": Category.BLOCKED_TIMEOUT.value},
    ],
)
def test_unknown_failed_unavailable_timeout_receipts_block(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    blocked_status = (
        Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
        {"operator_result_raw_value_present": True},
        {"operator_result_detail_present": True},
        {"checker_result_detail_present": True},
        {"sentinel_value_present": True},
    ],
)
def test_raw_or_detail_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_RAW_OR_DETAIL


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
    ],
)
def test_identifier_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is (
        Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_IDENTIFIER_EXPOSURE
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_variable_names_present": True},
        {"credential_values_present": True},
        {"credential_metadata_present": True},
        {"env_access_requested": True},
        {"credential_read_performed": True},
    ],
)
def test_env_or_credential_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ENV_OR_CREDENTIAL


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_checker_execution_performed": True},
        {"actual_execution_performed": True},
        {"codex_execution_performed": True},
    ],
)
def test_actual_execution_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_EXECUTION


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_receipt_handoff_executed": True},
        {"actual_result_receipt_received": True},
    ],
)
def test_actual_receipt_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_RECEIPT


@pytest.mark.parametrize(
    "overrides",
    [
        {"can_generate_real_signature": True},
        {"can_generate_real_headers": True},
        {"can_execute_http_post": True},
        {"http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
        {"post_allowed_this_step": True},
        {"post_executed": True},
    ],
)
def test_api_or_post_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_API_OR_POST


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_saved": True},
        {"receipt_displayed": True},
        {"receipt_broadly_propagated": True},
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_DISPLAY_OR_SAVE


def test_renderer_documents_policy_boundaries_without_unsafe_details() -> None:
    result = _build(operator_result_category=Category.READY_CONFIRMED.value)
    rendered = render_live_order_real_operator_result_handoff_policy_markdown(result)

    assert "This operator result handoff policy is skeleton-only." in rendered
    assert "This policy does not perform actual receipt handoff." in rendered
    assert "This policy does not receive actual results." in rendered
    assert "This policy does not execute the checker." in rendered
    assert "This policy does not access env or .env." in rendered
    assert "This policy does not read credentials." in rendered
    assert "READY_CONFIRMED is not POST permission." in rendered
    assert "NOT_PROVIDED is not an actual result receipt." in rendered
    assert "This policy does not execute API calls." in rendered
    assert "This policy does not execute HTTP POST." in rendered
    assert "- post_allowed_this_step: false" in rendered
    assert "- post_executed: false" in rendered

    unsafe_snippets = (
        "RAW_POLICY_CATEGORY_SHOULD_NOT_SURFACE",
        "operator result detail value",
        "checker detail value",
        "receipt token value",
        "receipt nonce value",
        "receipt hash value",
        "receipt fingerprint value",
        "receipt length value",
        "credential metadata value",
        "env actual name",
        "raw request body",
        "raw response body",
    )
    for snippet in unsafe_snippets:
        assert snippet not in rendered


def test_serialization_contains_only_safe_fields_not_raw_values() -> None:
    result = _build()
    payload = asdict(result)
    serialized = repr(payload)

    assert payload["receipt_raw_value_present"] is False
    assert payload["receipt_token_present"] is False
    assert payload["receipt_hash_present"] is False
    assert payload["receipt_fingerprint_present"] is False
    assert payload["receipt_length_present"] is False
    assert payload["operator_result_raw_value_present"] is False
    assert payload["operator_result_detail_present"] is False
    assert payload["checker_result_detail_present"] is False
    assert payload["credential_metadata_present"] is False
    assert payload["env_variable_names_present"] is False
    assert payload["actual_receipt_handoff_executed"] is False
    assert payload["actual_result_receipt_received"] is False
    assert payload["actual_checker_execution_performed"] is False

    unsafe_snippets = (
        "receipt token value",
        "receipt nonce value",
        "receipt hash value",
        "receipt fingerprint value",
        "receipt length value",
        "operator result detail value",
        "checker detail value",
        "credential metadata value",
        "env actual name",
        "raw request body",
        "raw response body",
    )
    for snippet in unsafe_snippets:
        assert snippet not in serialized


def test_module_has_no_api_order_or_env_dependencies() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_operator_result_handoff_policy.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
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
    blocked_call_names = blocked_names | {"read_text", "write_text"}
    blocked_attrs = {"en" + "viron", "get" + "env"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not _is_blocked_module(alias.name, blocked_modules) for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(module == blocked or module.startswith(blocked + ".") for blocked in blocked_modules)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""
