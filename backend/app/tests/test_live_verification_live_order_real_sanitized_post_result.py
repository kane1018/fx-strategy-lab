from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_post_guard_controlled import (
    LiveOrderRealPostGuardControlledInput,
    build_live_order_real_post_guard_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SAFE_POST_RESULT_LABEL,
    SAFE_RECONCILIATION_LABEL,
    LiveOrderRealSafePostResultCategory,
    LiveOrderRealSafeReconciliationStatus,
    LiveOrderRealSanitizedPostResultInput,
    LiveOrderRealSanitizedPostResultStatus,
    build_live_order_real_sanitized_post_result,
    render_live_order_real_sanitized_post_result_markdown,
)

Status = LiveOrderRealSanitizedPostResultStatus
Category = LiveOrderRealSafePostResultCategory
ReconciliationStatus = LiveOrderRealSafeReconciliationStatus
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
API_RESPONSE_SENTINEL = "API_RESPONSE_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
CONFIRMATION_SENTINEL = "CONFIRMATION_PHRASE_SHOULD_NOT_SURFACE"
LEDGER_SENTINEL = "LEDGER_STATE_SHOULD_NOT_SURFACE"


def _input(**overrides: object) -> LiveOrderRealSanitizedPostResultInput:
    base = LiveOrderRealSanitizedPostResultInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_sanitized_post_result(
        input_snapshot=_input(**overrides),
    )


def test_default_sanitized_result_ready_no_receipt_or_execution() -> None:
    result = _build()

    assert result.status is Status.SANITIZED_RESULT_READY_NO_RECEIPT
    assert result.sanitized_post_result_ready is True
    assert result.reconciliation_ready is True
    assert result.result_mode == "SANITIZED_POST_RESULT_CONTRACT_ONLY"
    assert result.safe_post_result_label == SAFE_POST_RESULT_LABEL
    assert result.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
    assert result.safe_result_category == Category.RESULT_NOT_RECEIVED.value
    assert (
        result.safe_reconciliation_status
        == ReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
    )
    assert result.blocked_reasons == ()
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.raw_request_stored is False
    assert result.raw_response_stored is False
    assert result.broker_response_exposed is False
    assert result.api_response_exposed is False
    assert result.real_id_exposed is False
    assert result.ledger_update_allowed is False
    assert result.actual_receipt_handoff_allowed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False
    assert result.raw_request_blocked is True
    assert result.raw_response_blocked is True
    assert result.broker_api_response_blocked is True
    assert result.real_id_blocked is True
    assert result.credential_signature_headers_blocked is True
    assert result.fresh_preflight_required is True
    assert result.final_confirmation_required is True
    assert result.ledger_design_required is True
    assert result.attempt_counter_design_required is True


def test_safe_post_guard_result_drives_ready_without_values_or_raw_exposure() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled()
    result = build_live_order_real_sanitized_post_result(
        post_guard_result=post_guard_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.SANITIZED_RESULT_READY_NO_RECEIPT
    assert result.sanitized_post_result_ready is True
    assert result.post_guard_prerequisite_satisfied is True
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        API_RESPONSE_SENTINEL,
        REAL_ID_SENTINEL,
    ):
        assert forbidden not in payload


def test_missing_post_guard_prerequisite_fails_closed() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled(
        input_snapshot=LiveOrderRealPostGuardControlledInput(
            post_guard_declared=False,
        ),
    )
    result = build_live_order_real_sanitized_post_result(
        post_guard_result=post_guard_result,
    )

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_MISSING_POST_GUARD
    assert result.sanitized_post_result_ready is False
    assert result.post_guard_prerequisite_satisfied is False
    assert "post_guard_prerequisite_missing" in result.blocked_reasons
    assert result.post_allowed_this_step is False
    assert result.ledger_update_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_category"),
    [
        (
            {"result_unknown": True},
            Status.SANITIZED_RESULT_BLOCKED_UNKNOWN,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_failed": True},
            Status.SANITIZED_RESULT_BLOCKED_FAILED,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_unavailable": True},
            Status.SANITIZED_RESULT_BLOCKED_UNAVAILABLE,
            Category.RESULT_UNAVAILABLE_FAIL_CLOSED,
        ),
        (
            {"result_timeout": True},
            Status.SANITIZED_RESULT_BLOCKED_TIMEOUT,
            Category.RESULT_TIMEOUT_FAIL_CLOSED,
        ),
        (
            {"result_rejected": True},
            Status.SANITIZED_RESULT_BLOCKED_REJECTED,
            Category.RESULT_REJECTED_SANITIZED,
        ),
        (
            {"result_partial": True},
            Status.SANITIZED_RESULT_BLOCKED_PARTIAL,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_ambiguous": True},
            Status.SANITIZED_RESULT_BLOCKED_AMBIGUOUS,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_unmatched": True},
            Status.SANITIZED_RESULT_BLOCKED_UNMATCHED,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_stale": True},
            Status.SANITIZED_RESULT_BLOCKED_STALE,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_previous_turn": True},
            Status.SANITIZED_RESULT_BLOCKED_PREVIOUS_TURN,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
        (
            {"result_reused": True},
            Status.SANITIZED_RESULT_BLOCKED_REUSED,
            Category.RESULT_UNKNOWN_FAIL_CLOSED,
        ),
    ],
)
def test_result_categories_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
    expected_category: Category,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.sanitized_post_result_ready is False
    assert result.reconciliation_ready is False
    assert result.safe_result_category == expected_category.value
    assert result.post_allowed_this_step is False
    assert result.ledger_update_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"raw_request_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE,
        ),
        (
            {"raw_request_stored": True},
            Status.SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE,
        ),
        (
            {"raw_response_stored": True},
            Status.SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE,
        ),
        (
            {"broker_response_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE,
        ),
        (
            {"api_response_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE,
        ),
        (
            {"broker_response_exposed": True},
            Status.SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE,
        ),
        (
            {"api_response_exposed": True},
            Status.SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE,
        ),
        (
            {"endpoint_actual_value_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"account_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"order_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"transaction_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"position_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"trade_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"real_id_exposed": True},
            Status.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"request_body_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"response_body_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"unsafe_exposure_attempted": True},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        ({"safe_to_render": False}, Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE),
        (
            {"safe_to_serialize": False},
            Status.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_are_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.sanitized_post_result_ready is False
    assert result.credential_value_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.raw_request_exposure_attempted is False
    assert result.raw_response_exposure_attempted is False
    assert result.request_body_exposure_attempted is False
    assert result.response_body_exposure_attempted is False
    assert result.broker_response_exposure_attempted is False
    assert result.api_response_exposure_attempted is False
    assert result.endpoint_actual_value_exposure_attempted is False
    assert result.account_id_exposure_attempted is False
    assert result.order_id_exposure_attempted is False
    assert result.transaction_id_exposure_attempted is False
    assert result.position_id_exposure_attempted is False
    assert result.trade_id_exposure_attempted is False
    assert result.real_id_exposure_attempted is False
    assert result.confirmation_phrase_exposure_attempted is False
    assert result.ledger_state_exposure_attempted is False
    assert result.raw_request_stored is False
    assert result.raw_response_stored is False
    assert result.broker_response_exposed is False
    assert result.api_response_exposed is False
    assert result.real_id_exposed is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    ["api_call_allowed", "api_call_attempted", "http_client_present"],
)
def test_api_or_http_client_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_API_ATTEMPTED
    assert result.sanitized_post_result_ready is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_client_present is False


@pytest.mark.parametrize(
    "field_name",
    ["http_post_executed", "post_allowed_this_step", "post_executed"],
)
def test_post_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_POST_ATTEMPTED
    assert result.sanitized_post_result_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False


def test_order_endpoint_blocks_separately() -> None:
    result = _build(order_endpoint_called=True)

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_ORDER_ENDPOINT
    assert result.sanitized_post_result_ready is False
    assert result.order_endpoint_called is False


def test_live_order_once_blocks_separately() -> None:
    result = _build(live_order_once_called=True)

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_LIVE_ORDER_ONCE
    assert result.sanitized_post_result_ready is False
    assert result.live_order_once_called is False


@pytest.mark.parametrize(
    "field_name",
    [
        "ledger_update_allowed",
        "ledger_update_attempted",
        "attempt_counter_persisted",
    ],
)
def test_ledger_update_and_attempt_counter_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_LEDGER_UPDATE
    assert result.sanitized_post_result_ready is False
    assert result.ledger_update_allowed is False
    assert result.ledger_update_attempted is False
    assert result.attempt_counter_persisted is False


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_checker_execution_performed",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "actual_receipt_handoff_allowed",
    ],
)
def test_actual_receipt_or_handoff_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_ACTUAL_RECEIPT
    assert result.sanitized_post_result_ready is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_receipt_handoff_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "fresh_preflight_executed",
        "final_confirmation_received",
        "raw_request_blocked",
        "raw_response_blocked",
        "broker_api_response_blocked",
        "real_id_blocked",
        "credential_signature_headers_blocked",
        "fresh_preflight_required",
        "final_confirmation_required",
        "ledger_design_required",
        "attempt_counter_design_required",
    ],
)
def test_final_gate_blockers_required(field_name: str) -> None:
    value = True if field_name.endswith("_executed") or field_name.endswith("_received") else False
    result = _build(**{field_name: value})

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_PREFLIGHT_OR_CONFIRMATION
    assert result.sanitized_post_result_ready is False
    assert result.raw_request_blocked is (field_name != "raw_request_blocked")
    assert result.raw_response_blocked is (field_name != "raw_response_blocked")
    assert result.broker_api_response_blocked is (
        field_name != "broker_api_response_blocked"
    )
    assert result.real_id_blocked is (field_name != "real_id_blocked")


def test_unsupported_mode_and_label_are_redacted() -> None:
    result = _build(
        result_mode="UNSUPPORTED_MODE",
        safe_post_result_label="UNSAFE_LABEL",
        safe_reconciliation_label="UNSAFE_RECONCILIATION_LABEL",
    )

    assert result.status is Status.SANITIZED_RESULT_BLOCKED_UNKNOWN
    assert result.result_mode == "UNSUPPORTED_REDACTED"
    assert result.safe_post_result_label == "UNSUPPORTED_REDACTED"
    assert result.safe_reconciliation_label == "UNSUPPORTED_REDACTED"
    assert result.sanitized_post_result_ready is False


def test_renderer_and_asdict_are_safe_summary_only() -> None:
    result = _build()
    payload = repr(asdict(result))
    rendered = render_live_order_real_sanitized_post_result_markdown(result)

    assert "sanitized_post_result_ready: true" in rendered
    assert "safe_result_category: RESULT_NOT_RECEIVED" in rendered
    assert "post_allowed_this_step: false" in rendered
    assert "ledger_update_allowed: false" in rendered
    assert "actual_receipt_handoff_allowed: false" in rendered
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        API_RESPONSE_SENTINEL,
        ACCOUNT_ID_SENTINEL,
        ORDER_ID_SENTINEL,
        TRANSACTION_ID_SENTINEL,
        REAL_ID_SENTINEL,
        CONFIRMATION_SENTINEL,
        LEDGER_SENTINEL,
    ):
        assert forbidden not in payload
        assert forbidden not in rendered


def test_module_has_no_env_crypto_http_api_or_file_io_dependencies() -> None:
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
        "os",
        "hmac",
        "hashlib",
        "base64",
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
        "getenv",
        "print",
        "post",
        "request",
        "send",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_sanitized_post_result.py"
    )
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


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in blocked_modules)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
