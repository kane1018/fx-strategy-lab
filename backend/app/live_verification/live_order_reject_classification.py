"""Sanitized classification for one-shot live order API rejects.

The classifier accepts only short, sanitized fields. It does not accept or store
raw API payloads, request artifacts, credential material, or order details.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationLiveOrderRejectClassificationError


class LiveOrderRejectCategory(str, Enum):
    AUTH_OR_PERMISSION = "auth_or_permission"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_REQUEST_BODY = "invalid_request_body"
    INVALID_ORDER_SIZE = "invalid_order_size"
    INVALID_CLIENT_ORDER_ID = "invalid_client_order_id"
    INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE = "insufficient_margin_or_account_state"
    MARKET_OR_SERVICE_UNAVAILABLE = "market_or_service_unavailable"
    RATE_LIMIT_OR_USAGE_RESTRICTION = "rate_limit_or_usage_restriction"
    DUPLICATE_OR_REUSED_CLIENT_ORDER_ID = "duplicate_or_reused_client_order_id"
    UNKNOWN_API_REJECTED = "unknown_api_rejected"


@dataclass(frozen=True)
class LiveOrderRejectClassificationInput:
    transport_result: str
    api_status_success: str
    result_unknown: bool
    http_status_class: str
    has_error_code: bool
    error_code: str
    message_code: str
    response_data_present: str
    order_attempt_count: int
    open_positions_count_after: int
    active_orders_count_after: int

    def __post_init__(self) -> None:
        if self.transport_result not in {
            "api_rejected",
            "success",
            "transport_error",
            "result_unknown",
        }:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "transport_result is invalid"
            )
        if self.api_status_success not in {"true", "false", "unknown"}:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "api_status_success is invalid"
            )
        if self.http_status_class not in {"2xx", "3xx", "4xx", "5xx", "unknown"}:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "http_status_class is invalid"
            )
        if self.response_data_present not in {"true", "false", "unknown"}:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "response_data_present is invalid"
            )
        for name, value in {
            "result_unknown": self.result_unknown,
            "has_error_code": self.has_error_code,
        }.items():
            if type(value) is not bool:
                raise LiveVerificationLiveOrderRejectClassificationError(
                    f"{name} must be bool"
                )
        for name, value in {
            "error_code": self.error_code,
            "message_code": self.message_code,
        }.items():
            if not isinstance(value, str):
                raise LiveVerificationLiveOrderRejectClassificationError(
                    f"{name} must be str"
                )
        for name, value in {
            "order_attempt_count": self.order_attempt_count,
            "open_positions_count_after": self.open_positions_count_after,
            "active_orders_count_after": self.active_orders_count_after,
        }.items():
            _require_non_negative_int(name, value)
        if self.has_error_code and not _sanitized_code(self):
            raise LiveVerificationLiveOrderRejectClassificationError(
                "has_error_code requires a sanitized code"
            )
        if not self.has_error_code and _sanitized_code(self):
            raise LiveVerificationLiveOrderRejectClassificationError(
                "sanitized code requires has_error_code=true"
            )


@dataclass(frozen=True)
class LiveOrderRejectClassification:
    classification_id: str
    reject_category: str
    confidence: str
    is_retry_allowed: bool
    requires_user_account_check: bool
    requires_code_review: bool
    requires_spec_review: bool
    requires_next_day_or_new_ledger: bool
    safe_to_retry_today: bool
    reason_summary: str
    recommended_next_action: str

    def __post_init__(self) -> None:
        _require_non_empty("classification_id", self.classification_id)
        if self.reject_category not in {category.value for category in LiveOrderRejectCategory}:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "reject_category is invalid"
            )
        if self.confidence not in {"low", "medium", "high"}:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "confidence is invalid"
            )
        for name, value in {
            "is_retry_allowed": self.is_retry_allowed,
            "requires_user_account_check": self.requires_user_account_check,
            "requires_code_review": self.requires_code_review,
            "requires_spec_review": self.requires_spec_review,
            "requires_next_day_or_new_ledger": self.requires_next_day_or_new_ledger,
            "safe_to_retry_today": self.safe_to_retry_today,
        }.items():
            if type(value) is not bool:
                raise LiveVerificationLiveOrderRejectClassificationError(
                    f"{name} must be bool"
                )
        if self.is_retry_allowed:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "reject classification cannot allow retry"
            )
        if self.safe_to_retry_today:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "reject classification cannot allow same-day retry"
            )
        if not self.requires_next_day_or_new_ledger:
            raise LiveVerificationLiveOrderRejectClassificationError(
                "reject classification requires next day or new ledger"
            )
        _require_safe_summary("reason_summary", self.reason_summary)
        _require_safe_summary("recommended_next_action", self.recommended_next_action)


def classify_live_order_reject(
    input_data: LiveOrderRejectClassificationInput,
) -> LiveOrderRejectClassification:
    if not isinstance(input_data, LiveOrderRejectClassificationInput):
        raise LiveVerificationLiveOrderRejectClassificationError(
            "input_data must be LiveOrderRejectClassificationInput"
        )
    category = _classify_category(input_data)
    flags = _classification_flags(category)
    confidence = "low" if category is LiveOrderRejectCategory.UNKNOWN_API_REJECTED else "medium"
    return LiveOrderRejectClassification(
        classification_id=make_live_order_reject_classification_id(input_data, category),
        reject_category=category.value,
        confidence=confidence,
        is_retry_allowed=False,
        requires_user_account_check=flags["requires_user_account_check"],
        requires_code_review=flags["requires_code_review"],
        requires_spec_review=flags["requires_spec_review"],
        requires_next_day_or_new_ledger=True,
        safe_to_retry_today=False,
        reason_summary=_reason_summary(category, input_data),
        recommended_next_action=_recommended_next_action(category),
    )


def make_live_order_reject_classification_id(
    input_data: LiveOrderRejectClassificationInput,
    category: LiveOrderRejectCategory,
) -> str:
    canonical = "|".join(
        (
            input_data.transport_result,
            input_data.api_status_success,
            str(input_data.result_unknown),
            input_data.http_status_class,
            str(input_data.has_error_code),
            input_data.error_code,
            input_data.message_code,
            input_data.response_data_present,
            str(input_data.order_attempt_count),
            str(input_data.open_positions_count_after),
            str(input_data.active_orders_count_after),
            category.value,
        )
    )
    return "reject_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _classify_category(
    input_data: LiveOrderRejectClassificationInput,
) -> LiveOrderRejectCategory:
    code = _sanitized_code(input_data).upper()
    if input_data.transport_result != "api_rejected":
        return LiveOrderRejectCategory.UNKNOWN_API_REJECTED
    if not code:
        return LiveOrderRejectCategory.UNKNOWN_API_REJECTED
    if code.startswith(("AUTH_", "PERMISSION_", "API_PERMISSION_")):
        return LiveOrderRejectCategory.AUTH_OR_PERMISSION
    if code.startswith(("SIGNATURE_", "SIGN_")):
        return LiveOrderRejectCategory.INVALID_SIGNATURE
    if code.startswith(("TIMESTAMP_", "TIME_")):
        return LiveOrderRejectCategory.INVALID_TIMESTAMP
    if code.startswith(("BODY_", "REQUEST_BODY_")):
        return LiveOrderRejectCategory.INVALID_REQUEST_BODY
    if code.startswith(("SIZE_", "ORDER_SIZE_")):
        return LiveOrderRejectCategory.INVALID_ORDER_SIZE
    if code.startswith(
        (
            "DUPLICATE_CLIENT_ORDER_ID_",
            "CLIENT_ORDER_ID_DUPLICATE",
            "REUSED_CLIENT_ORDER_ID_",
        )
    ):
        return LiveOrderRejectCategory.DUPLICATE_OR_REUSED_CLIENT_ORDER_ID
    if code.startswith("CLIENT_ORDER_ID_"):
        return LiveOrderRejectCategory.INVALID_CLIENT_ORDER_ID
    if code.startswith(("MARGIN_", "ACCOUNT_", "INSUFFICIENT_MARGIN")):
        return LiveOrderRejectCategory.INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE
    if code.startswith(("MARKET_", "SERVICE_", "MAINTENANCE_")):
        return LiveOrderRejectCategory.MARKET_OR_SERVICE_UNAVAILABLE
    if code.startswith(("RATE_LIMIT_", "USAGE_")):
        return LiveOrderRejectCategory.RATE_LIMIT_OR_USAGE_RESTRICTION
    return LiveOrderRejectCategory.UNKNOWN_API_REJECTED


def _classification_flags(category: LiveOrderRejectCategory) -> dict[str, bool]:
    user_check_categories = {
        LiveOrderRejectCategory.UNKNOWN_API_REJECTED,
        LiveOrderRejectCategory.AUTH_OR_PERMISSION,
        LiveOrderRejectCategory.INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE,
        LiveOrderRejectCategory.RATE_LIMIT_OR_USAGE_RESTRICTION,
    }
    code_review_categories = {
        LiveOrderRejectCategory.UNKNOWN_API_REJECTED,
        LiveOrderRejectCategory.INVALID_SIGNATURE,
        LiveOrderRejectCategory.INVALID_TIMESTAMP,
        LiveOrderRejectCategory.INVALID_REQUEST_BODY,
        LiveOrderRejectCategory.INVALID_CLIENT_ORDER_ID,
        LiveOrderRejectCategory.DUPLICATE_OR_REUSED_CLIENT_ORDER_ID,
    }
    spec_review_categories = {
        LiveOrderRejectCategory.UNKNOWN_API_REJECTED,
        LiveOrderRejectCategory.INVALID_REQUEST_BODY,
        LiveOrderRejectCategory.INVALID_ORDER_SIZE,
        LiveOrderRejectCategory.MARKET_OR_SERVICE_UNAVAILABLE,
    }
    return {
        "requires_user_account_check": category in user_check_categories,
        "requires_code_review": category in code_review_categories,
        "requires_spec_review": category in spec_review_categories,
    }


def _reason_summary(
    category: LiveOrderRejectCategory,
    input_data: LiveOrderRejectClassificationInput,
) -> str:
    if category is LiveOrderRejectCategory.UNKNOWN_API_REJECTED:
        return "API reject was observed, but no sanitized code is available."
    if input_data.order_attempt_count >= 1:
        return f"{category.value} was inferred from a sanitized code; same-day retry is blocked."
    return f"{category.value} was inferred from a sanitized code; retry remains blocked."


def _recommended_next_action(category: LiveOrderRejectCategory) -> str:
    if category is LiveOrderRejectCategory.AUTH_OR_PERMISSION:
        return (
            "User should confirm FX API key scope, order permission, "
            "and IP restriction settings."
        )
    if category is LiveOrderRejectCategory.INSUFFICIENT_MARGIN_OR_ACCOUNT_STATE:
        return "User should confirm account status, trading restrictions, and available margin."
    if category is LiveOrderRejectCategory.RATE_LIMIT_OR_USAGE_RESTRICTION:
        return "User should confirm API usage restrictions before any future attempt."
    if category is LiveOrderRejectCategory.INVALID_ORDER_SIZE:
        return "Review current symbol trading rules before any future attempt."
    if category in {
        LiveOrderRejectCategory.INVALID_SIGNATURE,
        LiveOrderRejectCategory.INVALID_TIMESTAMP,
        LiveOrderRejectCategory.INVALID_REQUEST_BODY,
        LiveOrderRejectCategory.INVALID_CLIENT_ORDER_ID,
        LiveOrderRejectCategory.DUPLICATE_OR_REUSED_CLIENT_ORDER_ID,
    }:
        return (
            "Review local signing, timing, body, and one-shot id construction "
            "before any future attempt."
        )
    if category is LiveOrderRejectCategory.MARKET_OR_SERVICE_UNAVAILABLE:
        return (
            "Review market hours, maintenance, and service availability "
            "before any future attempt."
        )
    return "Collect only sanitized code on a future attempt and complete user account checks first."


def _sanitized_code(input_data: LiveOrderRejectClassificationInput) -> str:
    return (input_data.error_code or input_data.message_code).strip()


def _require_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationLiveOrderRejectClassificationError(
            f"{name} must be non-negative int"
        )


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationLiveOrderRejectClassificationError(f"{name} is required")


def _require_safe_summary(name: str, value: str) -> None:
    _require_non_empty(name, value)
    forbidden_markers = (
        "raw response",
        "raw request",
        "header value",
        "credential value",
        "api key value",
        "secret value",
        "signature value",
    )
    normalized = value.lower()
    if any(marker in normalized for marker in forbidden_markers):
        raise LiveVerificationLiveOrderRejectClassificationError(
            f"{name} contains unsafe detail"
        )
