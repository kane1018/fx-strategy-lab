from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)
from app.live_verification.live_order_real_operator_result_handoff_lifecycle import (
    LiveOrderRealOperatorResultHandoffLifecycleEvent,
    LiveOrderRealOperatorResultHandoffLifecycleInput,
    LiveOrderRealOperatorResultHandoffLifecycleMode,
    LiveOrderRealOperatorResultHandoffLifecycleState,
    LiveOrderRealOperatorResultHandoffLifecycleStatus,
    build_live_order_real_operator_result_handoff_lifecycle,
    render_live_order_real_operator_result_handoff_lifecycle_markdown,
    transition_live_order_real_operator_result_handoff_lifecycle,
)

Status = LiveOrderRealOperatorResultHandoffLifecycleStatus
Mode = LiveOrderRealOperatorResultHandoffLifecycleMode
State = LiveOrderRealOperatorResultHandoffLifecycleState
Event = LiveOrderRealOperatorResultHandoffLifecycleEvent
Category = LiveOrderRealOperatorExecutionResultCategory
UNSUPPORTED_RAW_LABEL = "RAW_LIFECYCLE_LABEL_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_LABEL = "UNSUPPORTED_REDACTED"


def _input(**overrides: object) -> LiveOrderRealOperatorResultHandoffLifecycleInput:
    base = LiveOrderRealOperatorResultHandoffLifecycleInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_result_handoff_lifecycle(
        input_snapshot=_input(**overrides),
    )


def test_not_provided_lifecycle_ready_without_actual_receipt() -> None:
    result = _build()

    assert result.status is Status.LIFECYCLE_RECEIPT_NOT_PROVIDED_NO_ACTUAL_RECEIPT
    assert result.operator_result_handoff_lifecycle_ready is True
    assert result.lifecycle_mode == Mode.OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY.value
    assert result.from_state == State.LIFECYCLE_POLICY_READY.value
    assert result.to_state == State.LIFECYCLE_RECEIPT_NOT_PROVIDED.value
    assert result.lifecycle_event == Event.DECLARE_RECEIPT_NOT_PROVIDED.value
    assert result.operator_result_category == Category.NOT_PROVIDED.value
    assert result.lifecycle_declared is True
    assert result.lifecycle_transition_policy_declared is True
    assert result.one_time_required is True
    assert result.fresh_required is True
    assert result.current_turn_required is True
    assert result.non_reuse_required is True
    assert result.previous_turn_prohibited is True
    assert result.non_raw_required is True
    assert result.non_detail_required is True
    assert result.non_identifier_required is True
    assert result.safe_category_only is True
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_stale is False
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_timeout is False
    assert result.receipt_expired is False
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
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.blocked_reasons == ()


def test_policy_ready_event_is_ready_no_receipt() -> None:
    result = _build(lifecycle_event=Event.DECLARE_POLICY_READY.value)

    assert result.status is Status.LIFECYCLE_READY_NO_RECEIPT
    assert result.to_state == State.LIFECYCLE_POLICY_READY.value
    assert result.operator_result_handoff_lifecycle_ready is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_category": Category.READY_CONFIRMED.value},
        {"lifecycle_event": Event.DECLARE_SAFE_CATEGORY_READY_CONFIRMED.value},
    ],
)
def test_ready_confirmed_lifecycle_does_not_allow_post(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.LIFECYCLE_READY_CONFIRMED_NO_POST
    assert result.to_state == State.LIFECYCLE_READY_CONFIRMED_NO_POST.value
    assert result.operator_result_handoff_lifecycle_ready is True
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False
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
        {"lifecycle_mode": "UNSUPPORTED_RAW_MODE"},
        {"lifecycle_declared": False},
        {"lifecycle_transition_policy_declared": False},
        {"one_time_required": False},
        {"fresh_required": False},
        {"current_turn_required": False},
        {"non_reuse_required": False},
        {"previous_turn_prohibited": False},
        {"stale_prohibited": False},
        {"timeout_prohibited": False},
        {"expired_prohibited": False},
        {"non_raw_required": False},
        {"non_detail_required": False},
        {"non_identifier_required": False},
        {"safe_category_only": False},
        {"operator_result_handoff_policy_ready": False},
        {"operator_execution_result_category_contract_ready": False},
        {"operator_executed_execution_boundary_ready": False},
        {"operator_result_handoff_safe": False},
        {"ready_confirmed_is_not_post_permission": False},
        {"not_provided_is_not_actual_receipt": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.LIFECYCLE_NOT_READY
    assert result.operator_result_handoff_lifecycle_ready is False
    assert result.to_state == State.LIFECYCLE_BLOCKED.value


def test_unsupported_raw_labels_block_without_echoing_raw_values() -> None:
    result = _build(
        from_state=UNSUPPORTED_RAW_LABEL,
        lifecycle_event=UNSUPPORTED_RAW_LABEL,
        operator_result_category=UNSUPPORTED_RAW_LABEL,
    )
    rendered = render_live_order_real_operator_result_handoff_lifecycle_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.LIFECYCLE_BLOCKED_UNSUPPORTED
    assert result.unsupported_state_present is True
    assert result.unsupported_event_present is True
    assert result.unsupported_category_present is True
    assert result.from_state == UNSUPPORTED_SAFE_LABEL
    assert result.lifecycle_event == UNSUPPORTED_SAFE_LABEL
    assert result.operator_result_category == UNSUPPORTED_SAFE_LABEL
    assert UNSUPPORTED_RAW_LABEL not in rendered
    assert UNSUPPORTED_RAW_LABEL not in payload


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"receipt_stale": True}, Status.LIFECYCLE_BLOCKED_STALE),
        ({"lifecycle_event": Event.DECLARE_STALE.value}, Status.LIFECYCLE_BLOCKED_STALE),
        (
            {"operator_result_category": Category.BLOCKED_STALE.value},
            Status.LIFECYCLE_BLOCKED_STALE,
        ),
        ({"receipt_reused": True}, Status.LIFECYCLE_BLOCKED_REUSED),
        ({"lifecycle_event": Event.DECLARE_REUSED.value}, Status.LIFECYCLE_BLOCKED_REUSED),
        (
            {"operator_result_category": Category.BLOCKED_REUSED.value},
            Status.LIFECYCLE_BLOCKED_REUSED,
        ),
        ({"receipt_previous_turn": True}, Status.LIFECYCLE_BLOCKED_PREVIOUS_TURN),
        ({"receipt_current_turn": False}, Status.LIFECYCLE_BLOCKED_PREVIOUS_TURN),
        ({"receipt_fresh": False}, Status.LIFECYCLE_BLOCKED_PREVIOUS_TURN),
        (
            {"lifecycle_event": Event.DECLARE_PREVIOUS_TURN.value},
            Status.LIFECYCLE_BLOCKED_PREVIOUS_TURN,
        ),
        (
            {"operator_result_category": Category.BLOCKED_PREVIOUS_TURN.value},
            Status.LIFECYCLE_BLOCKED_PREVIOUS_TURN,
        ),
        ({"receipt_timeout": True}, Status.LIFECYCLE_BLOCKED_TIMEOUT),
        ({"lifecycle_event": Event.DECLARE_TIMEOUT.value}, Status.LIFECYCLE_BLOCKED_TIMEOUT),
        (
            {"operator_result_category": Category.BLOCKED_TIMEOUT.value},
            Status.LIFECYCLE_BLOCKED_TIMEOUT,
        ),
        ({"receipt_expired": True}, Status.LIFECYCLE_BLOCKED_EXPIRED),
    ],
)
def test_stale_reused_previous_timeout_expired_block(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_lifecycle_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"receipt_unknown": True}, Status.LIFECYCLE_BLOCKED_UNKNOWN),
        ({"lifecycle_event": Event.DECLARE_UNKNOWN.value}, Status.LIFECYCLE_BLOCKED_UNKNOWN),
        (
            {"operator_result_category": Category.BLOCKED_UNKNOWN.value},
            Status.LIFECYCLE_BLOCKED_UNKNOWN,
        ),
        ({"receipt_failed": True}, Status.LIFECYCLE_BLOCKED_FAILED),
        ({"lifecycle_event": Event.DECLARE_FAILED.value}, Status.LIFECYCLE_BLOCKED_FAILED),
        (
            {"operator_result_category": Category.BLOCKED_FAILED.value},
            Status.LIFECYCLE_BLOCKED_FAILED,
        ),
        ({"receipt_unavailable": True}, Status.LIFECYCLE_BLOCKED_UNAVAILABLE),
        (
            {"lifecycle_event": Event.DECLARE_UNAVAILABLE.value},
            Status.LIFECYCLE_BLOCKED_UNAVAILABLE,
        ),
        (
            {"operator_result_category": Category.BLOCKED_UNAVAILABLE.value},
            Status.LIFECYCLE_BLOCKED_UNAVAILABLE,
        ),
    ],
)
def test_unknown_failed_unavailable_block(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_lifecycle_ready is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"receipt_raw_value_present": True}, Status.LIFECYCLE_BLOCKED_RAW_RECEIPT),
        ({"operator_result_raw_value_present": True}, Status.LIFECYCLE_BLOCKED_RAW_RECEIPT),
        (
            {"lifecycle_event": Event.DECLARE_RAW_PRESENT.value},
            Status.LIFECYCLE_BLOCKED_RAW_RECEIPT,
        ),
        ({"receipt_detail_present": True}, Status.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE),
        ({"operator_result_detail_present": True}, Status.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE),
        ({"checker_result_detail_present": True}, Status.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE),
        ({"sentinel_value_present": True}, Status.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE),
        (
            {"lifecycle_event": Event.DECLARE_DETAIL_PRESENT.value},
            Status.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE,
        ),
        ({"receipt_id_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        ({"receipt_token_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        ({"receipt_nonce_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        ({"receipt_hash_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        ({"receipt_fingerprint_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        ({"receipt_length_present": True}, Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE),
        (
            {"lifecycle_event": Event.DECLARE_IDENTIFIER_PRESENT.value},
            Status.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE,
        ),
    ],
)
def test_raw_detail_identifier_block(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_lifecycle_ready is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"env_variable_names_present": True}, Status.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL),
        ({"credential_values_present": True}, Status.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL),
        ({"credential_metadata_present": True}, Status.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL),
        ({"env_access_requested": True}, Status.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL),
        ({"credential_read_performed": True}, Status.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL),
        ({"actual_checker_execution_performed": True}, Status.LIFECYCLE_BLOCKED_ACTUAL_EXECUTION),
        ({"actual_execution_performed": True}, Status.LIFECYCLE_BLOCKED_ACTUAL_EXECUTION),
        ({"codex_execution_performed": True}, Status.LIFECYCLE_BLOCKED_ACTUAL_EXECUTION),
        ({"actual_receipt_handoff_executed": True}, Status.LIFECYCLE_BLOCKED_ACTUAL_RECEIPT),
        ({"actual_result_receipt_received": True}, Status.LIFECYCLE_BLOCKED_ACTUAL_RECEIPT),
        (
            {"lifecycle_event": Event.DECLARE_ACTUAL_RECEIPT_ATTEMPTED.value},
            Status.LIFECYCLE_BLOCKED_ACTUAL_RECEIPT,
        ),
        ({"live_order_once_called": True}, Status.LIFECYCLE_BLOCKED_LIVE_ORDER_ONCE),
        ({"can_generate_real_signature": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"can_generate_real_headers": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"can_execute_http_post": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"http_post_executed": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"order_endpoint_called": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"post_allowed_this_step": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        ({"post_executed": True}, Status.LIFECYCLE_BLOCKED_API_OR_POST),
        (
            {"lifecycle_event": Event.DECLARE_API_OR_POST_ATTEMPTED.value},
            Status.LIFECYCLE_BLOCKED_API_OR_POST,
        ),
        ({"final_confirmation_received": True}, Status.LIFECYCLE_BLOCKED_FINAL_CONFIRMATION),
        ({"fresh_preflight_executed": True}, Status.LIFECYCLE_BLOCKED_FRESH_PREFLIGHT),
    ],
)
def test_env_actual_api_post_final_preflight_block(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_lifecycle_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_transition_function_matches_builder() -> None:
    lifecycle_input = _input(operator_result_category=Category.READY_CONFIRMED.value)

    assert transition_live_order_real_operator_result_handoff_lifecycle(
        input_snapshot=lifecycle_input,
    ) == build_live_order_real_operator_result_handoff_lifecycle(
        input_snapshot=lifecycle_input,
    )


def test_renderer_documents_lifecycle_boundaries_without_unsafe_details() -> None:
    result = _build(operator_result_category=Category.READY_CONFIRMED.value)
    rendered = render_live_order_real_operator_result_handoff_lifecycle_markdown(result)

    assert "This operator result handoff lifecycle contract is skeleton-only." in rendered
    assert "This lifecycle does not perform actual receipt handoff." in rendered
    assert "This lifecycle does not receive actual result receipts." in rendered
    assert "This lifecycle does not execute the checker." in rendered
    assert "This lifecycle does not access env or .env." in rendered
    assert "This lifecycle does not read credentials." in rendered
    assert "READY_CONFIRMED is not POST permission." in rendered
    assert "NOT_PROVIDED is not an actual result receipt." in rendered
    assert "This lifecycle does not execute API calls." in rendered
    assert "This lifecycle does not execute HTTP POST." in rendered
    assert "- post_allowed_this_step: false" in rendered
    assert "- post_executed: false" in rendered

    unsafe_snippets = (
        UNSUPPORTED_RAW_LABEL,
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
    assert payload["final_confirmation_received"] is False
    assert payload["fresh_preflight_executed"] is False

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
        / "live_order_real_operator_result_handoff_lifecycle.py"
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
