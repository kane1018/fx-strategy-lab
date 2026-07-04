from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_rejection_safe_category_capture_integration_no_post_controlled import (  # noqa: E501
    OfficialSettlementRejectionSafeCategoryIntegrationInput,
)
from app.live_verification.live_order_real_official_settlement_rejection_safe_category_reporting_handoff_no_post_controlled import (  # noqa: E501
    OfficialSettlementRejectionSafeCategoryReportingHandoffInput,
    OfficialSettlementRejectionSafeCategoryReportingHandoffStatus,
    build_official_settlement_rejection_safe_category_reporting_handoff_no_post,
    render_official_settlement_rejection_safe_category_chatgpt_handoff_summary,
    render_official_settlement_rejection_safe_category_final_report_markdown,
)
from app.live_verification.live_order_real_official_settlement_safe_rejection_category_no_post_controlled import (  # noqa: E501
    OFFICIAL_DOCS_SPEC_COMPARISON_PARAMETER_MISMATCH_CANDIDATE,
    SAFE_BROKER_CODE_REQUIRED_PARAMETER_MISSING,
    SAFE_HTTP_STATUS_RATE_LIMIT,
    SafeRejectionCategory,
    SafeRejectionConfidence,
    SafeRejectionKind,
    SafeRejectionSource,
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


def _build(**integration_overrides: object):
    return build_official_settlement_rejection_safe_category_reporting_handoff_no_post(
        OfficialSettlementRejectionSafeCategoryReportingHandoffInput(
            integration_input=OfficialSettlementRejectionSafeCategoryIntegrationInput(
                **integration_overrides,
            ),
        ),
    )


def test_rejected_reporting_handoff_includes_safe_fields_in_final_report_and_summary() -> None:
    result = _build()
    final_report = render_official_settlement_rejection_safe_category_final_report_markdown(
        result,
    )
    chatgpt_summary = (
        render_official_settlement_rejection_safe_category_chatgpt_handoff_summary(
            result,
        )
    )

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryReportingHandoffStatus.READY_NO_POST
    )
    assert result.safe_rejection_reporting_handoff_ready is True
    assert result.final_report_includes_safe_rejection_fields is True
    assert result.chatgpt_handoff_includes_safe_rejection_fields is True
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
    for expected in (
        "safe_rejection_category",
        "safe_rejection_kind",
        "safe_rejection_source",
        "safe_rejection_confidence",
        "safe_rejection_reason_available",
        "safe_rejection_reason_unavailable",
        "safe_rejection_requires_raw_response",
        "safe_rejection_requires_operator_ui_safe_label",
        "raw_response_inspected: false",
        "raw/ID/value exposure: false",
    ):
        assert expected in final_report or expected in chatgpt_summary


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
def test_safe_detail_label_reporting_outputs_classified_safe_fields(
    overrides: dict[str, object],
    category: SafeRejectionCategory,
    kind: SafeRejectionKind,
    source: SafeRejectionSource,
    confidence: SafeRejectionConfidence,
) -> None:
    result = _build(**overrides)
    rendered = render_official_settlement_rejection_safe_category_final_report_markdown(
        result,
    )

    assert result.safe_rejection_category == category.value
    assert result.safe_rejection_kind == kind.value
    assert result.safe_rejection_source == source.value
    assert result.safe_rejection_confidence == confidence.value
    assert result.safe_rejection_reason_available is True
    assert result.safe_rejection_reason_unavailable is False
    assert result.safe_rejection_requires_raw_response is False
    assert category.value in rendered
    assert kind.value in rendered
    assert source.value in rendered


def test_reporting_handoff_blocks_raw_value_secret_sentinels_and_never_renders_them() -> None:
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
    final_report = render_official_settlement_rejection_safe_category_final_report_markdown(
        result,
    )
    chatgpt_summary = (
        render_official_settlement_rejection_safe_category_chatgpt_handoff_summary(
            result,
        )
    )

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryReportingHandoffStatus
        .BLOCKED_UNSAFE_INPUT
    )
    assert result.safe_rejection_reporting_handoff_ready is False
    assert result.raw_response_rendered is False
    assert result.broker_response_rendered is False
    assert result.error_message_rendered is False
    assert result.raw_id_value_exposure is False
    assert result.env_read is False
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in final_report
        assert forbidden not in chatgpt_summary


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_settlement_post_this_step",
        "entry_post_this_step",
        "retry_this_step",
        "repost_this_step",
        "second_settlement_post_this_step",
        "generic_close_this_step",
        "ledger_update",
        "receipt_handoff",
        "raw_id_value_exposure",
        "env_read",
    ],
)
def test_reporting_boundary_blocks_execution_or_exposure_attempts(field_name: str) -> None:
    result = build_official_settlement_rejection_safe_category_reporting_handoff_no_post(
        OfficialSettlementRejectionSafeCategoryReportingHandoffInput(
            **{field_name: True},
        ),
    )

    assert (
        result.status
        is OfficialSettlementRejectionSafeCategoryReportingHandoffStatus
        .BLOCKED_EXECUTION_ATTEMPT
    )
    assert result.actual_settlement_post_this_step is False
    assert result.entry_post_this_step is False
    assert result.retry_this_step is False
    assert result.repost_this_step is False
    assert result.second_settlement_post_this_step is False
    assert result.generic_close_this_step is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert result.raw_id_value_exposure is False
    assert result.env_read is False


def test_reporting_handoff_transport_counts_remain_zero() -> None:
    result = _build()

    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.real_http_call_count == 0
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.one_shot_generic_order_path_used_for_settlement is False
    assert result.position_specific_path_executed is False


def test_reporting_handoff_module_has_no_http_env_broker_or_execution_imports() -> None:
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
            "reporting_handoff_no_post_controlled.py"
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
