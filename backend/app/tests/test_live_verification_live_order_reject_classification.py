from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from app.live_verification.errors import (
    LiveVerificationLiveOrderRejectClassificationError,
)
from app.live_verification.live_order_reject_classification import (
    LiveOrderRejectCategory,
    LiveOrderRejectClassification,
    LiveOrderRejectClassificationInput,
    classify_live_order_reject,
    make_live_order_reject_classification_id,
)

DUMMY_API_KEY_VALUE = "DUMMY_API_KEY_VALUE"
DUMMY_API_SECRET_VALUE = "DUMMY_API_SECRET_VALUE"
DUMMY_SIGNATURE_VALUE = "DUMMY_SIGNATURE_VALUE"
DUMMY_RAW_RESPONSE_VALUE = "DUMMY_RAW_RESPONSE_VALUE"

EXPECTED_INPUT_FIELDS = {
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
EXPECTED_CLASSIFICATION_FIELDS = {
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


def _input(
    **overrides: object,
) -> LiveOrderRejectClassificationInput:
    values: dict[str, object] = {
        "transport_result": "api_rejected",
        "api_status_success": "false",
        "result_unknown": False,
        "http_status_class": "4xx",
        "has_error_code": False,
        "error_code": "",
        "message_code": "",
        "response_data_present": "false",
        "order_attempt_count": 1,
        "open_positions_count_after": 0,
        "active_orders_count_after": 0,
    }
    values.update(overrides)
    return LiveOrderRejectClassificationInput(**values)  # type: ignore[arg-type]


def _coded(code: str) -> LiveOrderRejectClassificationInput:
    return _input(has_error_code=True, error_code=code)


def test_unknown_api_reject_without_code_is_safe_and_non_retryable() -> None:
    input_data = _input()

    classification = classify_live_order_reject(input_data)

    assert isinstance(classification, LiveOrderRejectClassification)
    assert classification.reject_category == LiveOrderRejectCategory.UNKNOWN_API_REJECTED
    assert classification.confidence == "low"
    assert classification.is_retry_allowed is False
    assert classification.safe_to_retry_today is False
    assert classification.requires_next_day_or_new_ledger is True
    assert classification.requires_user_account_check is True
    assert classification.requires_code_review is True
    assert classification.requires_spec_review is True
    assert "no sanitized code" in classification.reason_summary
    assert "future attempt" in classification.recommended_next_action


@pytest.mark.parametrize(
    ("code", "expected_category"),
    [
        ("AUTH_ORDER_NOT_ALLOWED", LiveOrderRejectCategory.AUTH_OR_PERMISSION),
        ("PERMISSION_ORDER_DISABLED", LiveOrderRejectCategory.AUTH_OR_PERMISSION),
        ("SIGNATURE_INVALID", LiveOrderRejectCategory.INVALID_SIGNATURE),
        ("TIMESTAMP_EXPIRED", LiveOrderRejectCategory.INVALID_TIMESTAMP),
        ("BODY_INVALID_FIELD", LiveOrderRejectCategory.INVALID_REQUEST_BODY),
        ("SIZE_TOO_SMALL", LiveOrderRejectCategory.INVALID_ORDER_SIZE),
        ("CLIENT_ORDER_ID_INVALID", LiveOrderRejectCategory.INVALID_CLIENT_ORDER_ID),
        (
            "DUPLICATE_CLIENT_ORDER_ID_USED",
            LiveOrderRejectCategory.DUPLICATE_OR_REUSED_CLIENT_ORDER_ID,
        ),
        (
            "MARGIN_INSUFFICIENT",
            LiveOrderRejectCategory.INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE,
        ),
        ("MARKET_CLOSED", LiveOrderRejectCategory.MARKET_OR_SERVICE_UNAVAILABLE),
        ("RATE_LIMIT_EXCEEDED", LiveOrderRejectCategory.RATE_LIMIT_OR_USAGE_RESTRICTION),
        ("UNMAPPED_SHORT_CODE", LiveOrderRejectCategory.UNKNOWN_API_REJECTED),
    ],
)
def test_sanitized_codes_map_to_reject_categories(
    code: str,
    expected_category: LiveOrderRejectCategory,
) -> None:
    classification = classify_live_order_reject(_coded(code))

    assert classification.reject_category == expected_category.value
    assert classification.is_retry_allowed is False
    assert classification.safe_to_retry_today is False
    assert classification.requires_next_day_or_new_ledger is True


def test_message_code_can_be_used_when_error_code_is_empty() -> None:
    classification = classify_live_order_reject(
        _input(has_error_code=True, error_code="", message_code="ACCOUNT_RESTRICTED"),
    )

    assert (
        classification.reject_category
        == LiveOrderRejectCategory.INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE.value
    )


def test_classification_id_is_deterministic() -> None:
    input_data = _coded("AUTH_ORDER_NOT_ALLOWED")
    first = classify_live_order_reject(input_data)
    second = classify_live_order_reject(input_data)

    assert first.classification_id == second.classification_id
    assert first.classification_id == make_live_order_reject_classification_id(
        input_data,
        LiveOrderRejectCategory.AUTH_OR_PERMISSION,
    )
    assert first.classification_id.startswith("reject_")


def test_classification_fields_are_sanitized_public_summary_only() -> None:
    input_data = _coded("AUTH_ORDER_NOT_ALLOWED")
    classification = classify_live_order_reject(input_data)

    assert {field.name for field in fields(LiveOrderRejectClassificationInput)} == (
        EXPECTED_INPUT_FIELDS
    )
    assert {field.name for field in fields(LiveOrderRejectClassification)} == (
        EXPECTED_CLASSIFICATION_FIELDS
    )
    forbidden_values = {
        DUMMY_API_KEY_VALUE,
        DUMMY_API_SECRET_VALUE,
        DUMMY_SIGNATURE_VALUE,
        DUMMY_RAW_RESPONSE_VALUE,
    }
    public_views = (
        repr(input_data),
        str(input_data),
        repr(classification),
        str(classification),
        str(asdict(input_data)),
        str(asdict(classification)),
    )
    for value in forbidden_values:
        assert all(value not in view for view in public_views)


@pytest.mark.parametrize(
    "unsafe_field",
    [
        "raw_response",
        "raw_request",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "request_body",
        "response_body",
        "orderId",
        "rootOrderId",
        "clientOrderId",
        "price",
        "timestamp",
    ],
)
def test_input_rejects_raw_or_sensitive_extra_fields(unsafe_field: str) -> None:
    values = {
        "transport_result": "api_rejected",
        "api_status_success": "false",
        "result_unknown": False,
        "http_status_class": "4xx",
        "has_error_code": False,
        "error_code": "",
        "message_code": "",
        "response_data_present": "false",
        "order_attempt_count": 1,
        "open_positions_count_after": 0,
        "active_orders_count_after": 0,
        unsafe_field: DUMMY_RAW_RESPONSE_VALUE,
    }

    with pytest.raises(TypeError):
        LiveOrderRejectClassificationInput(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("transport_result", "placed"),
        ("api_status_success", "yes"),
        ("http_status_class", "200"),
        ("response_data_present", "yes"),
        ("result_unknown", "false"),
        ("has_error_code", "true"),
        ("order_attempt_count", -1),
        ("open_positions_count_after", -1),
        ("active_orders_count_after", -1),
        ("order_attempt_count", True),
        ("open_positions_count_after", False),
    ],
)
def test_input_validation_fails_closed(field_name: str, bad_value: object) -> None:
    with pytest.raises(LiveVerificationLiveOrderRejectClassificationError):
        _input(**{field_name: bad_value})


def test_sanitized_code_presence_must_match_has_error_code_flag() -> None:
    with pytest.raises(LiveVerificationLiveOrderRejectClassificationError):
        _input(has_error_code=True, error_code="", message_code="")

    with pytest.raises(LiveVerificationLiveOrderRejectClassificationError):
        _input(has_error_code=False, error_code="AUTH_ORDER_NOT_ALLOWED")


@pytest.mark.parametrize(
    "field_name",
    [
        "is_retry_allowed",
        "safe_to_retry_today",
        "requires_next_day_or_new_ledger",
    ],
)
def test_output_model_rejects_retry_or_same_day_retry_flags(field_name: str) -> None:
    values = asdict(classify_live_order_reject(_coded("AUTH_ORDER_NOT_ALLOWED")))
    if field_name == "requires_next_day_or_new_ledger":
        values[field_name] = False
    else:
        values[field_name] = True

    with pytest.raises(LiveVerificationLiveOrderRejectClassificationError):
        LiveOrderRejectClassification(**values)


def test_previous_attempt_forces_same_day_retry_blocking_summary() -> None:
    classification = classify_live_order_reject(
        _input(
            has_error_code=True,
            error_code="AUTH_ORDER_NOT_ALLOWED",
            order_attempt_count=1,
        ),
    )

    assert classification.safe_to_retry_today is False
    assert classification.is_retry_allowed is False
    assert "same-day retry is blocked" in classification.reason_summary
