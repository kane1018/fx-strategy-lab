from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_rejection_safe_category_capture_integration_no_post_controlled import (  # noqa: E501
    OfficialSettlementRejectionSafeCategoryIntegrationInput,
    OfficialSettlementRejectionSafeCategoryIntegrationStatus,
    build_official_settlement_rejection_safe_category_capture_integration_no_post,
    render_official_settlement_rejection_safe_category_capture_integration_markdown,
)
from app.live_verification.live_order_real_official_settlement_safe_rejection_category_no_post_controlled import (  # noqa: E501
    OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE,
    OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED,
    SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    SAFE_HTTP_STATUS_RATE_LIMIT,
    SafeRejectionCategory,
    SafeRejectionConfidence,
    SafeRejectionKind,
    SafeRejectionSource,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSafePostResultCategory,
)

RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
ERROR_MESSAGE_SENTINEL = "ERROR_MESSAGE_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
TRADE_ID_SENTINEL = "TRADE_ID_SHOULD_NOT_SURFACE"
QUANTITY_VALUE_SENTINEL = "QUANTITY_VALUE_SHOULD_NOT_SURFACE"
PRICE_VALUE_SENTINEL = "PRICE_VALUE_SHOULD_NOT_SURFACE"
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"


def _build(**overrides: object):
    return build_official_settlement_rejection_safe_category_capture_integration_no_post(
        OfficialSettlementRejectionSafeCategoryIntegrationInput(**overrides),
    )


def test_rejected_result_uses_safe_category_capture_default_unknown_unavailable() -> None:
    result = _build()

    assert result.status is OfficialSettlementRejectionSafeCategoryIntegrationStatus.READY_NO_POST
    assert result.safe_rejection_category_capture_integrated is True
    assert result.official_settlement_rejected_result_uses_safe_category_capture is True
    assert result.safe_rejection_category == SafeRejectionCategory.UNKNOWN.value
    assert (
        result.safe_rejection_kind
        == SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE.value
    )
    assert result.safe_rejection_source == SafeRejectionSource.SANITIZED_RESULT_ONLY.value
    assert result.safe_rejection_confidence == SafeRejectionConfidence.UNKNOWN.value
    assert result.safe_rejection_reason_available is False
    assert result.safe_rejection_reason_unavailable is True
    assert result.safe_rejection_requires_raw_response is True
    assert result.safe_rejection_requires_operator_ui_safe_label is True
    assert result.raw_response_inspected is False
    assert result.broker_response_exposed is False
    assert result.error_message_rendered is False


@pytest.mark.parametrize(
    ("overrides", "category", "kind", "source", "confidence"),
    [
        (
            {"safe_broker_code_label": SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING},
            SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
            SafeRejectionKind.REQUIRED_PARAMETER_MISSING,
            SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
            SafeRejectionConfidence.HIGH,
        ),
        (
            {"safe_http_status_label": SAFE_HTTP_STATUS_RATE_LIMIT},
            SafeRejectionCategory.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
            SafeRejectionKind.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
            SafeRejectionSource.SAFE_HTTP_STATUS_LABEL,
            SafeRejectionConfidence.MEDIUM,
        ),
        (
            {
                "operator_ui_safe_label": (
                    OPERATOR_UI_SAFE_LABEL_POSITION_NOT_FOUND_OR_ALREADY_CLOSED
                ),
            },
            SafeRejectionCategory.POSITION_STATE_OR_TARGET_NOT_FOUND,
            SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
            SafeRejectionSource.OPERATOR_UI_SAFE_LABEL,
            SafeRejectionConfidence.MEDIUM,
        ),
        (
            {
                "official_docs_comparison_safe_result": (
                    OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE
                ),
            },
            SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE,
            SafeRejectionKind.EXECUTION_TYPE_OR_MARKET_BOUND_MISMATCH,
            SafeRejectionSource.OFFICIAL_DOCS_SPEC_COMPARISON,
            SafeRejectionConfidence.MEDIUM,
        ),
    ],
)
def test_safe_detail_labels_classify_only_safe_category_fields(
    overrides: dict[str, object],
    category: SafeRejectionCategory,
    kind: SafeRejectionKind,
    source: SafeRejectionSource,
    confidence: SafeRejectionConfidence,
) -> None:
    result = _build(**overrides)

    assert result.safe_rejection_category_capture_integrated is True
    assert result.safe_rejection_category == category.value
    assert result.safe_rejection_kind == kind.value
    assert result.safe_rejection_source == source.value
    assert result.safe_rejection_confidence == confidence.value
    assert result.safe_rejection_reason_available is True
    assert result.safe_rejection_reason_unavailable is False
    assert result.safe_rejection_requires_raw_response is False


def test_non_rejected_official_settlement_result_blocks_integration() -> None:
    result = _build(
        official_settlement_result_category=(
            LiveOrderRealSafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
        ),
    )

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryIntegrationStatus.BLOCKED_UNSAFE_INPUT
    )
    assert result.safe_rejection_category_capture_integrated is False
    assert result.official_settlement_rejected_result_uses_safe_category_capture is False
    assert "official_settlement_result_not_rejected_sanitized" in result.blocked_reasons


def test_final_report_render_and_asdict_include_safe_fields_only() -> None:
    result = _build(
        safe_broker_code_label=SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    )
    payload = repr(asdict(result))
    rendered = (
        render_official_settlement_rejection_safe_category_capture_integration_markdown(
            result,
        )
    )

    assert SafeRejectionCategory.PARAMETER_OR_REQUEST_SHAPE.value in payload
    assert SafeRejectionKind.REQUIRED_PARAMETER_MISSING.value in payload
    assert SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL.value in payload
    assert "safe_rejection_category_capture_integrated: true" in rendered
    assert "actual_post_executed: false" in rendered
    assert "settlement_post_count: 0" in rendered
    assert "transport_call_count: 0" in rendered
    assert "real_http_call_count: 0" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_raw_value_and_secret_sentinels_never_surface_when_blocked() -> None:
    result = _build(
        safe_broker_code_label=RAW_RESPONSE_SENTINEL,
        safe_http_status_label=BROKER_RESPONSE_SENTINEL,
        operator_ui_safe_label=ERROR_MESSAGE_SENTINEL,
        official_docs_comparison_safe_result=ACCOUNT_ID_SENTINEL,
        raw_response_supplied=True,
        broker_response_supplied=True,
        error_message_text_supplied=True,
        account_id_supplied=True,
        order_id_supplied=True,
        transaction_id_supplied=True,
        position_id_supplied=True,
        trade_id_supplied=True,
        quantity_value_supplied=True,
        price_value_supplied=True,
        credential_value_supplied=True,
        signature_value_supplied=True,
        headers_value_supplied=True,
        env_read=True,
    )
    payload = repr(asdict(result))
    rendered = (
        render_official_settlement_rejection_safe_category_capture_integration_markdown(
            result,
        )
    )

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryIntegrationStatus.BLOCKED_UNSAFE_INPUT
    )
    assert result.raw_response_rendered is False
    assert result.broker_response_rendered is False
    assert result.error_message_rendered is False
    assert result.account_id_rendered is False
    assert result.order_id_rendered is False
    assert result.position_id_rendered is False
    assert result.trade_id_rendered is False
    assert result.quantity_value_rendered is False
    assert result.price_value_rendered is False
    assert result.credential_value_rendered is False
    assert result.signature_value_rendered is False
    assert result.headers_value_rendered is False
    assert result.raw_id_value_exposure is False
    assert result.env_read is False
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_post_executed",
        "retry",
        "repost",
        "second_post",
        "entry_post_executed",
        "generic_close_executed",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_executed",
    ],
)
def test_execution_attempts_block_and_are_zeroed(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryIntegrationStatus
        .BLOCKED_EXECUTION_ATTEMPT
    )
    assert result.safe_rejection_category_capture_integrated is False
    assert result.actual_post_executed is False
    assert result.retry is False
    assert result.repost is False
    assert result.second_post is False
    assert result.entry_post_executed is False
    assert result.generic_close_executed is False
    assert result.ledger_update_attempted is False
    assert result.receipt_handoff_attempted is False
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.one_shot_generic_order_path_used_for_settlement is False
    assert result.position_specific_path_executed is False


@pytest.mark.parametrize(
    "field_name",
    ["settlement_post_count", "transport_call_count", "real_http_call_count"],
)
def test_post_or_transport_count_blocks_and_is_zeroed(field_name: str) -> None:
    result = _build(**{field_name: 1})

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryIntegrationStatus
        .BLOCKED_EXECUTION_ATTEMPT
    )
    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.real_http_call_count == 0


def test_module_has_no_http_env_broker_or_execution_imports() -> None:
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
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "read_text",
        "write_text",
        "getenv",
        "print",
        "post",
        "request",
        "send",
    }
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / (
            "live_order_real_official_settlement_rejection_safe_category_"
            "capture_integration_no_post_controlled.py"
        )
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
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


_FORBIDDEN_SENTINELS = (
    RAW_RESPONSE_SENTINEL,
    BROKER_RESPONSE_SENTINEL,
    ERROR_MESSAGE_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    POSITION_ID_SENTINEL,
    TRADE_ID_SENTINEL,
    QUANTITY_VALUE_SENTINEL,
    PRICE_VALUE_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(
        module == blocked or module.startswith(f"{blocked}.")
        for blocked in blocked_modules
    )


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
