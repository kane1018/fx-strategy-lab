from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_post_guard_controlled import (
    SAFE_POST_GUARD_LABEL,
    LiveOrderRealPostGuardControlledInput,
    LiveOrderRealPostGuardControlledStatus,
    build_live_order_real_post_guard_controlled,
    render_live_order_real_post_guard_controlled_markdown,
)
from app.live_verification.live_order_real_transport_controlled import (
    LiveOrderRealTransportControlledInput,
    build_live_order_real_transport_controlled,
)

Status = LiveOrderRealPostGuardControlledStatus
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
REQUEST_BODY_SENTINEL = "REQUEST_BODY_SHOULD_NOT_SURFACE"
RESPONSE_BODY_SENTINEL = "RESPONSE_BODY_SHOULD_NOT_SURFACE"
ENDPOINT_SENTINEL = "ENDPOINT_ACTUAL_VALUE_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_API_RESPONSE_SHOULD_NOT_SURFACE"
CONFIRMATION_SENTINEL = "CONFIRMATION_PHRASE_SHOULD_NOT_SURFACE"
LEDGER_SENTINEL = "LEDGER_STATE_SHOULD_NOT_SURFACE"


def _input(**overrides: object) -> LiveOrderRealPostGuardControlledInput:
    base = LiveOrderRealPostGuardControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_post_guard_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_post_guard_ready_no_api_post_or_live_order_once() -> None:
    result = _build()

    assert result.status is Status.POST_GUARD_READY_NO_POST
    assert result.post_guard_ready is True
    assert result.post_guard_mode == "POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY"
    assert result.safe_post_guard_label == SAFE_POST_GUARD_LABEL
    assert result.safe_post_guard_status == Status.POST_GUARD_READY_NO_POST.value
    assert result.transport_prerequisite_checked is True
    assert result.transport_prerequisite_satisfied is True
    assert result.transport_controlled_ready is True
    assert result.blocked_reasons == ()
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_client_present is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False
    assert result.one_post_max_enforced is True
    assert result.no_retry_enforced is True
    assert result.timeout_fail_closed_enforced is True
    assert result.max_post_attempts_allowed == 1
    assert result.second_post_attempt_blocked is True
    assert result.multiple_post_attempts_blocked is True
    assert result.retry_after_failure_blocked is True
    assert result.retry_after_timeout_blocked is True
    assert result.retry_after_unknown_blocked is True
    assert result.fresh_preflight_required is True
    assert result.final_confirmation_required is True
    assert result.sanitized_result_required is True
    assert result.step4_approval_phrase_reuse_blocked is True
    assert result.ledger_state_reuse_blocked is True


def test_safe_transport_result_drives_ready_without_value_or_raw_exposure() -> None:
    transport_result = build_live_order_real_transport_controlled()
    result = build_live_order_real_post_guard_controlled(
        transport_result=transport_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.POST_GUARD_READY_NO_POST
    assert result.post_guard_ready is True
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        REAL_ID_SENTINEL,
    ):
        assert forbidden not in payload


def test_missing_transport_prerequisite_fails_closed() -> None:
    transport_result = build_live_order_real_transport_controlled(
        input_snapshot=LiveOrderRealTransportControlledInput(
            transport_declared=False,
        ),
    )
    result = build_live_order_real_post_guard_controlled(
        transport_result=transport_result,
    )

    assert result.status is Status.POST_GUARD_BLOCKED_MISSING_TRANSPORT
    assert result.post_guard_ready is False
    assert result.transport_prerequisite_satisfied is False
    assert "transport_prerequisite_missing" in result.blocked_reasons
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"post_guard_unknown": True}, Status.POST_GUARD_BLOCKED_UNKNOWN),
        ({"post_guard_failed": True}, Status.POST_GUARD_BLOCKED_FAILED),
        (
            {"post_guard_unavailable": True},
            Status.POST_GUARD_BLOCKED_UNAVAILABLE,
        ),
        ({"post_guard_timeout": True}, Status.POST_GUARD_BLOCKED_TIMEOUT),
        ({"post_guard_rejected": True}, Status.POST_GUARD_BLOCKED_REJECTED),
        ({"post_guard_stale": True}, Status.POST_GUARD_BLOCKED_STALE),
        (
            {"post_guard_previous_turn": True},
            Status.POST_GUARD_BLOCKED_PREVIOUS_TURN,
        ),
        ({"post_guard_reused": True}, Status.POST_GUARD_BLOCKED_REUSED),
    ],
)
def test_unknown_failed_unavailable_timeout_rejected_stale_reused_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.post_guard_ready is False
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"raw_request_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_RAW_REQUEST_EXPOSURE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_RAW_RESPONSE_EXPOSURE,
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"request_body_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"response_body_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"endpoint_actual_value_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"account_id_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"order_id_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"preflight_detail_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"unsafe_exposure_attempted": True},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_render": False},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_serialize": False},
            Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_are_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.post_guard_ready is False
    assert result.credential_value_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.raw_request_exposure_attempted is False
    assert result.raw_response_exposure_attempted is False
    assert result.request_body_exposure_attempted is False
    assert result.response_body_exposure_attempted is False
    assert result.endpoint_actual_value_exposure_attempted is False
    assert result.account_id_exposure_attempted is False
    assert result.order_id_exposure_attempted is False
    assert result.real_id_exposure_attempted is False
    assert result.broker_api_response_exposure_attempted is False
    assert result.confirmation_phrase_exposure_attempted is False
    assert result.preflight_detail_exposure_attempted is False
    assert result.ledger_state_exposure_attempted is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    ["api_call_allowed", "api_call_attempted", "http_client_present"],
)
def test_api_or_http_client_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.POST_GUARD_BLOCKED_API_ATTEMPTED
    assert result.post_guard_ready is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_client_present is False


@pytest.mark.parametrize(
    "field_name",
    ["http_post_executed", "post_allowed_this_step", "post_executed"],
)
def test_post_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.POST_GUARD_BLOCKED_POST_ATTEMPTED
    assert result.post_guard_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False


@pytest.mark.parametrize(
    ("field_name", "expected_status"),
    [
        ("retry_attempted", Status.POST_GUARD_BLOCKED_RETRY_ATTEMPTED),
        (
            "second_post_attempted",
            Status.POST_GUARD_BLOCKED_SECOND_POST_ATTEMPTED,
        ),
        (
            "multiple_post_attempts_attempted",
            Status.POST_GUARD_BLOCKED_MULTIPLE_POST_ATTEMPTS,
        ),
    ],
)
def test_retry_second_and_multiple_post_attempts_block(
    field_name: str,
    expected_status: Status,
) -> None:
    result = _build(**{field_name: True})

    assert result.status is expected_status
    assert result.post_guard_ready is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.multiple_post_attempts_attempted is False


def test_order_endpoint_blocks_separately() -> None:
    result = _build(order_endpoint_called=True)

    assert result.status is Status.POST_GUARD_BLOCKED_ORDER_ENDPOINT
    assert result.post_guard_ready is False
    assert result.order_endpoint_called is False


def test_live_order_once_blocks_separately() -> None:
    result = _build(live_order_once_called=True)

    assert result.status is Status.POST_GUARD_BLOCKED_LIVE_ORDER_ONCE
    assert result.post_guard_ready is False
    assert result.live_order_once_called is False


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_checker_execution_performed",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "fresh_preflight_executed",
        "final_confirmation_received",
        "one_post_max_enforced",
        "no_retry_enforced",
        "timeout_fail_closed_enforced",
        "second_post_attempt_blocked",
        "multiple_post_attempts_blocked",
        "retry_after_failure_blocked",
        "retry_after_timeout_blocked",
        "retry_after_unknown_blocked",
        "fresh_preflight_required",
        "final_confirmation_required",
        "sanitized_result_required",
        "preflight_must_be_current",
        "confirmation_must_be_new_for_this_step",
        "step4_approval_phrase_reuse_blocked",
        "ledger_state_reuse_blocked",
    ],
)
def test_final_gate_blockers_or_actual_execution_block(field_name: str) -> None:
    false_suffixes = ("_enforced", "_blocked", "_required", "_current", "_step")
    value = False if field_name.endswith(false_suffixes) else True
    result = _build(**{field_name: value})

    assert result.status is Status.POST_GUARD_BLOCKED_PREFLIGHT_OR_CONFIRMATION
    assert result.post_guard_ready is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False


def test_unsupported_mode_or_safe_label_is_redacted() -> None:
    mode_result = _build(post_guard_mode="UNSUPPORTED_RAW_MODE")
    label_result = _build(safe_post_guard_label=RAW_REQUEST_SENTINEL)

    assert mode_result.status is Status.POST_GUARD_BLOCKED_UNKNOWN
    assert mode_result.post_guard_mode == "UNSUPPORTED_REDACTED"
    assert label_result.status is Status.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE
    assert label_result.safe_post_guard_label == "UNSUPPORTED_REDACTED"
    assert RAW_REQUEST_SENTINEL not in repr(asdict(label_result))


def test_renderer_and_asdict_expose_only_safe_summary() -> None:
    result = _build()
    rendered = render_live_order_real_post_guard_controlled_markdown(result)
    payload = repr(asdict(result))

    assert "post_guard_ready: true" in rendered
    assert f"safe_post_guard_label: {SAFE_POST_GUARD_LABEL}" in rendered
    assert "safe_post_guard_status: POST_GUARD_READY_NO_POST" in rendered
    assert "POST guard ready does not allow POST." in rendered
    assert "POST guard ready does not allow order endpoint calls." in rendered
    assert "POST guard ready does not allow live_order_once." in rendered
    assert "api_call_allowed: false" in rendered
    assert "http_post_executed: false" in rendered
    assert "order_endpoint_called: false" in rendered
    assert "live_order_once_called: false" in rendered
    assert "one_post_max_enforced: true" in rendered
    assert "no_retry_enforced: true" in rendered
    assert "timeout_fail_closed_enforced: true" in rendered
    assert "fresh_preflight_required: true" in rendered
    assert "final_confirmation_required: true" in rendered
    assert "sanitized_result_required: true" in rendered

    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        REQUEST_BODY_SENTINEL,
        RESPONSE_BODY_SENTINEL,
        ENDPOINT_SENTINEL,
        REAL_ID_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        CONFIRMATION_SENTINEL,
        LEDGER_SENTINEL,
    ):
        assert forbidden not in rendered
        assert forbidden not in payload


def test_module_imports_no_env_crypto_http_api_post_private_broker_or_live_order_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_post_guard_controlled.py"
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
        "os",
        "hmac",
        "hashlib",
        "base64",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    blocked_calls = {
        "getenv",
        "print",
        "post",
        "request",
        "send",
        "read_text",
        "write_text",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            attr = func.attr if isinstance(func, ast.Attribute) else None
            assert name not in blocked_calls
            assert attr not in blocked_calls
