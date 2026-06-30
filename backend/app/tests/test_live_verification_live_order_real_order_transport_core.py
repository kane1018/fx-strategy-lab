from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_order_transport_core import (
    LiveOrderRealFakeTransportResult,
    LiveOrderRealNoRetryContract,
    LiveOrderRealSensitiveHeaderContract,
    LiveOrderRealTransportCoreStatus,
    LiveOrderRealTransportMethod,
    LiveOrderRealTransportResultCategory,
    LiveOrderRealValidatedOrderIntent,
    build_live_order_real_order_transport_core,
    build_order_body_from_validated_intent,
    build_private_order_header_contract_without_exposure,
    classify_order_transport_result_safely,
    make_live_order_real_transport_endpoint_contract,
    render_live_order_real_order_transport_core_markdown,
    serialize_order_body_stably,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL


def _intent(**overrides: object) -> LiveOrderRealValidatedOrderIntent:
    values = {
        "symbol": SUPPORTED_SYMBOL,
        "side": "BUY",
        "size": LIVE_ORDER_CANDIDATE_SIZE,
        "executionType": LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        "source_label": "explicit_step6g_operator_buy_intent",
        "codex_inferred_symbol": False,
        "codex_inferred_side": False,
        "codex_inferred_size": False,
        "codex_inferred_execution_type": False,
        "retry_allowed": False,
        "loop_allowed": False,
        "add_order_allowed": False,
        "change_order_allowed": False,
        "cancel_order_allowed": False,
        "close_order_allowed": False,
        "extra_fields": (),
    }
    values.update(overrides)
    return LiveOrderRealValidatedOrderIntent(**values)


def _fake_result(**overrides: object) -> LiveOrderRealFakeTransportResult:
    values = {
        "fake_result_kind": "success",
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
    return LiveOrderRealFakeTransportResult(**values)


def _no_retry(**overrides: object) -> LiveOrderRealNoRetryContract:
    values = {
        "post_attempt_limit": 1,
        "post_attempt_count_before": 0,
        "post_attempt_count_after": 0,
        "retry_allowed": False,
        "loop_allowed": False,
        "retry_on_unknown": False,
        "retry_on_timeout": False,
        "retry_on_reject": False,
        "add_order_allowed": False,
        "change_order_allowed": False,
        "cancel_order_allowed": False,
        "close_order_allowed": False,
    }
    values.update(overrides)
    return LiveOrderRealNoRetryContract(**values)


def _build(**kwargs):
    return build_live_order_real_order_transport_core(
        intent=kwargs.pop("intent", _intent()),
        **kwargs,
    )


def test_valid_usd_jpy_buy_100_market_intent_builds_ready_core() -> None:
    result = _build()

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_READY_NO_API_NO_POST
    assert result.body_allowlist_passed is True
    assert result.stable_serialization_ready is True
    assert result.endpoint_contract.method is LiveOrderRealTransportMethod.POST
    assert result.endpoint_contract.path == "/v1/order"
    assert result.sensitive_header_contract.header_values_redacted is True
    assert result.sensitive_header_contract.credentials_used is False
    assert result.sensitive_header_contract.credentials_displayed is False
    assert result.sensitive_header_contract.signature_value_generated is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "intent",
    [
        _intent(symbol="EUR_JPY"),
        _intent(side="SELL"),
        _intent(size=101),
        _intent(executionType="LIMIT"),
        _intent(codex_inferred_side=True),
    ],
)
def test_wrong_or_inferred_intent_blocks_body(intent) -> None:
    result = _build(intent=intent)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_BODY_INVALID
    assert result.body_allowlist_passed is False
    assert result.http_post_executed is False


@pytest.mark.parametrize(
    "extra_fields",
    [
        ("price",),
        ("closeOrder",),
        ("cancelOrders",),
        ("changeOrder",),
        ("clientOrderId",),
        ("unexpected",),
    ],
)
def test_unauthorized_or_order_mutation_fields_block(extra_fields: tuple[str, ...]) -> None:
    result = _build(intent=_intent(extra_fields=extra_fields))

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_UNAUTHORIZED_FIELD


@pytest.mark.parametrize(
    "intent",
    [
        _intent(add_order_allowed=True),
        _intent(change_order_allowed=True),
        _intent(cancel_order_allowed=True),
        _intent(close_order_allowed=True),
    ],
)
def test_add_change_cancel_close_flags_block_as_unauthorized(intent) -> None:
    result = _build(intent=intent)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_UNAUTHORIZED_FIELD


def test_stable_serialization_is_deterministic_and_excludes_unauthorized_fields() -> None:
    order_body = build_order_body_from_validated_intent(_intent())
    first = serialize_order_body_stably(order_body)
    second = serialize_order_body_stably(order_body)

    assert first == second
    assert first == '{"executionType":"MARKET","side":"BUY","size":100,"symbol":"USD_JPY"}'
    assert "price" not in first
    assert "clientOrderId" not in first


def test_serialized_body_is_not_exposed_in_renderer() -> None:
    result = _build()
    rendered = render_live_order_real_order_transport_core_markdown(result)

    assert '{"executionType":"MARKET"' not in rendered
    assert "serialized body" not in rendered.lower()
    assert "This transport core is pure/fake only." in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "does not use real credentials" in rendered


def test_endpoint_method_contract_is_ready_but_not_called() -> None:
    result = _build()

    assert result.endpoint_contract.method is LiveOrderRealTransportMethod.POST
    assert result.endpoint_contract.path == "/v1/order"
    assert result.endpoint_contract.order_endpoint_called is False
    assert result.endpoint_contract.http_post_executed is False
    assert result.endpoint_contract.live_order_once_called is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False


@pytest.mark.parametrize(
    "endpoint",
    [
        replace(make_live_order_real_transport_endpoint_contract(), http_post_executed=True),
        replace(make_live_order_real_transport_endpoint_contract(), order_endpoint_called=True),
        replace(make_live_order_real_transport_endpoint_contract(), live_order_once_called=True),
        replace(make_live_order_real_transport_endpoint_contract(), imports_http_client=True),
        replace(make_live_order_real_transport_endpoint_contract(), imports_private_api=True),
        replace(make_live_order_real_transport_endpoint_contract(), imports_broker=True),
        replace(make_live_order_real_transport_endpoint_contract(), imports_live_order_once=True),
    ],
)
def test_endpoint_or_import_unsafe_contract_blocks(endpoint) -> None:
    result = _build(endpoint_contract=endpoint)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_UNSUPPORTED


def test_sensitive_header_contract_is_redacted_and_uses_no_credentials() -> None:
    contract = build_private_order_header_contract_without_exposure()
    result = _build(header_contract=contract)

    assert result.sensitive_header_contract.header_contract_ready is True
    assert result.sensitive_header_contract.header_names_allowed == (
        "API-KEY",
        "API-TIMESTAMP",
        "API-SIGN",
    )
    assert result.sensitive_header_contract.header_values_redacted is True
    assert result.sensitive_header_contract.credentials_used is False
    assert result.sensitive_header_contract.credentials_displayed is False
    assert result.sensitive_header_contract.signature_value_generated is False
    assert result.sensitive_header_contract.headers_displayed is False
    assert result.sensitive_header_contract.headers_saved is False


@pytest.mark.parametrize(
    "header_contract",
    [
        replace(
            build_private_order_header_contract_without_exposure(),
            header_contract_ready=False,
        ),
        replace(
            build_private_order_header_contract_without_exposure(),
            header_values_redacted=False,
        ),
        LiveOrderRealSensitiveHeaderContract(
            header_contract_ready=True,
            header_names_allowed=("OTHER",),
            header_values_redacted=True,
            signature_value_generated=False,
            signature_value_displayed=False,
            signature_value_saved=False,
            credentials_used=False,
            credentials_displayed=False,
            headers_displayed=False,
            headers_saved=False,
        ),
    ],
)
def test_header_contract_unsafe_blocks(header_contract) -> None:
    result = _build(header_contract=header_contract)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_HEADER_CONTRACT_UNSAFE


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        ("success", LiveOrderRealTransportResultCategory.TRANSPORT_SUCCESS_SANITIZED),
        (
            "api_rejected",
            LiveOrderRealTransportResultCategory.TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY,
        ),
        ("timeout", LiveOrderRealTransportResultCategory.TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY),
        (
            "transport_error",
            LiveOrderRealTransportResultCategory.TRANSPORT_ERROR_SANITIZED_NO_RETRY,
        ),
        (
            "result_unknown",
            LiveOrderRealTransportResultCategory.TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY,
        ),
    ],
)
def test_fake_result_classification_is_sanitized_and_no_retry(kind: str, category) -> None:
    fake = _fake_result(fake_result_kind=kind)
    classified = classify_order_transport_result_safely(fake)
    result = _build(fake_transport_result=fake)

    assert classified.result_category is category
    assert result.status is (
        LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_RESULT_CLASSIFIED_NO_RETRY
    )
    assert result.transport_result_category == category.value
    assert result.one_shot_no_retry_ready is True
    assert result.http_post_executed is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "fake",
    [
        _fake_result(raw_request_present=True),
        _fake_result(raw_response_present=True),
        _fake_result(headers_present=True),
        _fake_result(signature_value_present=True),
        _fake_result(credentials_present=True),
        _fake_result(real_order_id_present=True),
        _fake_result(real_execution_id_present=True),
        _fake_result(real_position_id_present=True),
        _fake_result(real_client_order_id_present=True),
    ],
)
def test_raw_response_headers_signature_credentials_or_real_ids_block(fake) -> None:
    result = _build(fake_transport_result=fake)

    assert result.status is (
        LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_BLOCKED_RAW_OR_SECRET_EXPOSURE
    )
    assert result.http_post_executed is False


@pytest.mark.parametrize(
    "header_contract",
    [
        replace(
            build_private_order_header_contract_without_exposure(),
            signature_value_generated=True,
        ),
        replace(
            build_private_order_header_contract_without_exposure(),
            signature_value_displayed=True,
        ),
        replace(build_private_order_header_contract_without_exposure(), signature_value_saved=True),
        replace(build_private_order_header_contract_without_exposure(), credentials_used=True),
        replace(build_private_order_header_contract_without_exposure(), credentials_displayed=True),
        replace(build_private_order_header_contract_without_exposure(), headers_displayed=True),
        replace(build_private_order_header_contract_without_exposure(), headers_saved=True),
    ],
)
def test_header_value_or_credential_exposure_blocks(header_contract) -> None:
    result = _build(header_contract=header_contract)

    assert result.status is (
        LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_BLOCKED_RAW_OR_SECRET_EXPOSURE
    )


@pytest.mark.parametrize(
    "fake",
    [
        _fake_result(retry_on_unknown=True),
        _fake_result(retry_on_timeout=True),
        _fake_result(retry_on_reject=True),
        _fake_result(retry_count=1),
        _fake_result(loop_count=1),
    ],
)
def test_retry_or_loop_in_fake_result_blocks(fake) -> None:
    result = _build(fake_transport_result=fake)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_BLOCKED_RETRY_OR_LOOP


@pytest.mark.parametrize(
    "no_retry_contract",
    [
        _no_retry(post_attempt_limit=2),
        _no_retry(post_attempt_count_before=1),
        _no_retry(post_attempt_count_after=2),
        _no_retry(retry_allowed=True),
        _no_retry(loop_allowed=True),
        _no_retry(retry_on_unknown=True),
        _no_retry(retry_on_timeout=True),
        _no_retry(retry_on_reject=True),
        _no_retry(add_order_allowed=True),
        _no_retry(change_order_allowed=True),
        _no_retry(cancel_order_allowed=True),
        _no_retry(close_order_allowed=True),
    ],
)
def test_one_shot_no_retry_contract_blocks_bad_attempt_state(no_retry_contract) -> None:
    result = _build(no_retry_contract=no_retry_contract)

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_BLOCKED_RETRY_OR_LOOP
    assert result.one_shot_no_retry_ready is False


def test_unknown_fake_kind_is_unsupported() -> None:
    result = _build(fake_transport_result=_fake_result(fake_result_kind="other"))

    assert result.status is LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_UNSUPPORTED
    assert result.transport_result_category == (
        LiveOrderRealTransportResultCategory.TRANSPORT_BLOCKED_UNSUPPORTED.value
    )


def test_renderer_does_not_include_forbidden_values() -> None:
    result = _build(fake_transport_result=_fake_result(fake_result_kind="result_unknown"))
    rendered = render_live_order_real_order_transport_core_markdown(result)

    forbidden = (
        "RAW_REQUEST_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "SECRET_SENTINEL",
        "REAL_ORDER_ID_SENTINEL",
        '{"executionType":"MARKET","side":"BUY","size":100,"symbol":"USD_JPY"}',
    )
    for token in forbidden:
        assert token not in rendered
    assert "Future real signing / real transport must be a separate Step." in rendered


def test_serialization_contains_no_raw_secret_real_ids_or_full_body() -> None:
    result = _build(fake_transport_result=_fake_result(fake_result_kind="success"))
    payload = str(asdict(result))

    forbidden = (
        "RAW_REQUEST_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "SECRET_SENTINEL",
        "REAL_ORDER_ID_SENTINEL",
        '{"executionType":"MARKET","side":"BUY","size":100,"symbol":"USD_JPY"}',
    )
    for token in forbidden:
        assert token not in payload
    assert "'http_post_executed': False" in payload
    assert "'order_endpoint_called': False" in payload
    assert "'live_order_once_called': False" in payload
    assert "'post_executed': False" in payload


def test_new_module_does_not_import_http_private_broker_live_order_once_or_env() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_order_transport_core.py"
    )
    tree = ast.parse(module_path.read_text())
    forbidden_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "http.client",
        "socket",
        "subprocess",
        "app.brokers",
        "app.private_api",
        "dotenv",
        "os",
        "app.live_verification.live_order_once",
    }
    forbidden_names = {
        "OrderRequest",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "speedOrder",
        "changeOrder",
        "cancelOrders",
        "closeOrder",
        "ENABLE_LIVE_TRADING",
        "LIVE_ORDER_PLACED",
        "BROKER_SUBMIT",
        "ORDER_SENT",
        "live_order_once",
        "pbcopy",
        "getenv",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules
            assert not any(
                node.module and node.module.startswith(f"{module}.")
                for module in forbidden_modules
            )
            for alias in node.names:
                assert alias.name not in forbidden_names
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden_names
