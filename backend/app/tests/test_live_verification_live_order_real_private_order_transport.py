from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

from app.live_verification.live_order_real_private_order_transport import (
    LiveOrderRealPrivateOrderSanitizedResultInput,
    LiveOrderRealPrivateOrderTransportContract,
    LiveOrderRealPrivateOrderTransportPrerequisites,
    LiveOrderRealPrivateOrderTransportResultCategory,
    LiveOrderRealPrivateOrderTransportStatus,
    build_live_order_real_private_order_transport_contract,
    render_live_order_real_private_order_transport_markdown,
)
from app.live_verification.live_order_real_signing_contract import (
    LiveOrderRealSigningInputContract,
    build_live_order_real_signing_contract,
)


def _build(**overrides):
    return build_live_order_real_private_order_transport_contract(**overrides)


def _result(kind: str = "success", **overrides):
    values = {
        "sanitized_result_kind": kind,
        "raw_request_present": False,
        "raw_response_present": False,
        "headers_present": False,
        "signature_value_present": False,
        "credentials_present": False,
        "real_order_id_present": False,
        "real_execution_id_present": False,
        "real_position_id_present": False,
        "real_client_order_id_present": False,
        "retry_on_unknown": False,
        "retry_on_timeout": False,
        "retry_on_reject": False,
        "retry_count": 0,
        "loop_count": 0,
    }
    values.update(overrides)
    return LiveOrderRealPrivateOrderSanitizedResultInput(**values)


def test_valid_prerequisites_build_ready_transport_contract() -> None:
    result = _build()

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus
        .PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST
    )
    assert result.transport_contract_ready is True
    assert result.signing_contract_ready is True
    assert result.redacted_header_contract_ready is True
    assert result.method == "POST"
    assert result.path == "/v1/order"
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_signing_contract_not_ready_blocks_prerequisites() -> None:
    signing = build_live_order_real_signing_contract(
        input_contract=LiveOrderRealSigningInputContract(method="GET"),
    )
    result = _build(signing_contract_result=signing)

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus
        .BLOCKED_PRIVATE_ORDER_TRANSPORT_PREREQUISITES
    )
    assert "signing_status_not_ready" in result.blocked_reasons


def test_prerequisite_flags_block() -> None:
    for field_name in (
        "signing_contract_ready",
        "redacted_header_contract_ready",
        "order_body_allowlist_passed",
        "stable_serialization_ready",
        "endpoint_contract_ready",
    ):
        prerequisites = replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            **{field_name: False},
        )
        result = _build(prerequisites=prerequisites)

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_PREREQUISITES
        )


def test_attempt_count_or_limit_blocks_retry_loop_contract() -> None:
    for kwargs in [
        {"post_attempt_limit": 2},
        {"post_attempt_count_before": 1},
    ]:
        prerequisites = replace(LiveOrderRealPrivateOrderTransportPrerequisites(), **kwargs)
        result = _build(prerequisites=prerequisites)

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP
        )


def test_retry_loop_or_mutation_flags_block() -> None:
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        prerequisites = replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            **{field_name: True},
        )
        result = _build(prerequisites=prerequisites)

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP
        )


def test_http_post_executed_blocks_http_post() -> None:
    result = _build(
        prerequisites=replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            http_post_executed=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_HTTP_POST
    )


def test_order_endpoint_called_blocks_endpoint() -> None:
    result = _build(
        prerequisites=replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            order_endpoint_called=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus
        .BLOCKED_PRIVATE_ORDER_TRANSPORT_ORDER_ENDPOINT
    )


def test_live_order_once_called_blocks_live_order_once() -> None:
    result = _build(
        prerequisites=replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            live_order_once_called=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus
        .BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE
    )


def test_raw_request_response_or_secret_exposure_blocks() -> None:
    for field_name in (
        "raw_request_displayed",
        "raw_request_saved",
        "raw_response_displayed",
        "raw_response_saved",
        "headers_displayed",
        "headers_saved",
        "signature_displayed",
        "signature_saved",
        "credentials_displayed",
        "credentials_saved",
    ):
        prerequisites = replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            **{field_name: True},
        )
        result = _build(prerequisites=prerequisites)

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE
        )


def test_real_id_exposure_blocks() -> None:
    for field_name in ("real_ids_displayed", "real_ids_saved"):
        prerequisites = replace(
            LiveOrderRealPrivateOrderTransportPrerequisites(),
            **{field_name: True},
        )
        result = _build(prerequisites=prerequisites)

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_REAL_ID_EXPOSURE
        )


def test_transport_contract_cannot_import_or_call_real_paths() -> None:
    for kwargs, expected in [
        (
            {"can_execute_http_post": True},
            LiveOrderRealPrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_HTTP_POST,
        ),
        (
            {"can_call_order_endpoint": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_ORDER_ENDPOINT,
        ),
        (
            {"can_call_live_order_once": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE,
        ),
        (
            {"imports_live_order_once": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE,
        ),
        (
            {"imports_http_client": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"imports_private_api": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"imports_broker": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
    ]:
        contract = replace(LiveOrderRealPrivateOrderTransportContract(), **kwargs)
        result = _build(transport_contract=contract)

        assert result.status is expected


def test_sanitized_result_success_is_classified_without_retry() -> None:
    result = _build(sanitized_result_input=_result("success"))

    assert (
        result.status
        is LiveOrderRealPrivateOrderTransportStatus
        .PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY
    )
    assert (
        result.transport_result_category
        == LiveOrderRealPrivateOrderTransportResultCategory
        .PRIVATE_ORDER_TRANSPORT_SUCCESS_SANITIZED_CONTRACT_ONLY
        .value
    )
    assert result.retry_allowed is False
    assert result.loop_allowed is False


def test_rejected_timeout_error_and_unknown_are_classified_without_retry() -> None:
    expected = {
        "api_rejected": (
            LiveOrderRealPrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY
        ),
        "timeout": (
            LiveOrderRealPrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY
        ),
        "transport_error": (
            LiveOrderRealPrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_ERROR_SANITIZED_NO_RETRY
        ),
        "result_unknown": (
            LiveOrderRealPrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY
        ),
    }
    for kind, category in expected.items():
        result = _build(sanitized_result_input=_result(kind))

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY
        )
        assert result.transport_result_category == category.value
        assert result.retry_allowed is False


def test_result_raw_secret_or_real_id_exposure_blocks() -> None:
    for kwargs, expected in [
        (
            {"raw_response_present": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"headers_present": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"signature_value_present": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"credentials_present": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE,
        ),
        (
            {"real_order_id_present": True},
            LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_REAL_ID_EXPOSURE,
        ),
    ]:
        result = _build(sanitized_result_input=_result("success", **kwargs))

        assert result.status is expected


def test_result_retry_loop_blocks() -> None:
    for kwargs in [
        {"retry_on_unknown": True},
        {"retry_on_timeout": True},
        {"retry_on_reject": True},
        {"retry_count": 1},
        {"loop_count": 1},
    ]:
        result = _build(sanitized_result_input=_result("result_unknown", **kwargs))

        assert (
            result.status
            is LiveOrderRealPrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP
        )


def test_renderer_includes_warnings_and_no_sensitive_values() -> None:
    result = _build(sanitized_result_input=_result("timeout"))
    rendered = render_live_order_real_private_order_transport_markdown(result)

    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "actual_raw_response_value" not in rendered
    assert "actual_secret_value" not in rendered
    assert "actual_order_id_value" not in rendered


def test_asdict_does_not_contain_raw_secret_or_real_id_values() -> None:
    result = _build(sanitized_result_input=_result("success"))
    payload = repr(asdict(result))

    assert "actual_raw_response_value" not in payload
    assert "actual_secret_value" not in payload
    assert "actual_order_id_value" not in payload
    assert "actual_execution_id_value" not in payload


def test_new_module_does_not_import_http_private_broker_or_live_order_once() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_private_order_transport.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "speedOrder",
        "live_order_once",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
