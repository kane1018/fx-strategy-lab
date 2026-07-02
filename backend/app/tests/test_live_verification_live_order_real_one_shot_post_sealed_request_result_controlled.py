from __future__ import annotations

from dataclasses import asdict

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealExecutableOrderPreviewInput,
    build_live_order_real_executable_order_preview,
)
from app.live_verification.live_order_real_one_shot_post_sealed_request_result_controlled import (  # noqa: E501
    SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL,
    SAFE_SEALED_BODY_LABEL,
    SAFE_SEALED_ENDPOINT_LABEL,
    SAFE_SEALED_REQUEST_LABEL,
    SAFE_SEALED_REQUEST_RESULT_LABEL,
    LiveOrderRealOneShotPostSealedRequestResultControlledInput,
    LiveOrderRealOneShotPostSealedRequestResultControlledStatus,
    LiveOrderRealSealedResultMappingStatus,
    LiveOrderRealSealedTransportResultMappingInput,
    LiveOrderRealSealedTransportSafeCategory,
    build_live_order_real_one_shot_post_sealed_request_result_controlled,
    map_live_order_real_one_shot_post_sealed_transport_result,
    render_live_order_real_one_shot_post_sealed_request_result_markdown,
    render_live_order_real_one_shot_post_sealed_result_mapping_markdown,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
    SafeReconciliationStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

SealedStatus = LiveOrderRealOneShotPostSealedRequestResultControlledStatus
MappingStatus = LiveOrderRealSealedResultMappingStatus
TransportSafeCategory = LiveOrderRealSealedTransportSafeCategory

RAW_BODY_SENTINEL = "RAW_BODY_SHOULD_NOT_SURFACE"
ENDPOINT_SENTINEL = "ENDPOINT_VALUE_SHOULD_NOT_SURFACE"
HEADERS_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
CREDENTIAL_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"

FORBIDDEN_SENTINELS = (
    RAW_BODY_SENTINEL,
    ENDPOINT_SENTINEL,
    HEADERS_SENTINEL,
    SIGNATURE_SENTINEL,
    CREDENTIAL_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    ID_SENTINEL,
    BROKER_RESPONSE_SENTINEL,
)


def _safe_result_payload(result: object) -> str:
    return repr(asdict(result))


def _assert_no_sentinel_exposure(*payloads: str) -> None:
    joined = "\n".join(payloads)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in joined


def test_sealed_request_summary_is_safe_only_and_does_not_post() -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled()
    rendered = render_live_order_real_one_shot_post_sealed_request_result_markdown(
        result,
    )

    assert result.status is SealedStatus.SEALED_REQUEST_RESULT_READY_NO_POST
    assert result.sealed_request_model_ready is True
    assert result.sealed_body_builder_ready is True
    assert result.sealed_endpoint_label_ready is True
    assert result.safe_result_mapper_ready is True
    assert result.sealed_request_result_label == SAFE_SEALED_REQUEST_RESULT_LABEL
    assert result.sealed_request_label == SAFE_SEALED_REQUEST_LABEL
    assert result.sealed_body_label == SAFE_SEALED_BODY_LABEL
    assert result.sealed_endpoint_label == SAFE_SEALED_ENDPOINT_LABEL
    assert result.source_owned_client_order_id_strategy_ready is True
    assert result.source_owned_client_order_id_strategy_label == (
        SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL
    )
    assert result.approved_primitive_actual_source_available is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False
    assert "actual_http_post_executed: false" in rendered
    _assert_no_sentinel_exposure(rendered, _safe_result_payload(result))


def test_sealed_request_repr_asdict_and_renderer_do_not_expose_sentinels() -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(
            sealed_request_result_label=RAW_BODY_SENTINEL,
            sealed_request_label=ENDPOINT_SENTINEL,
            sealed_body_label=HEADERS_SENTINEL,
            sealed_endpoint_label=SIGNATURE_SENTINEL,
            source_owned_client_order_id_strategy_label=CREDENTIAL_SENTINEL,
            safe_preview_label=ID_SENTINEL,
            environment_label=RAW_RESPONSE_SENTINEL,
            risk_label=BROKER_RESPONSE_SENTINEL,
        ),
    )
    rendered = render_live_order_real_one_shot_post_sealed_request_result_markdown(
        result,
    )

    assert result.status is SealedStatus.SEALED_REQUEST_RESULT_READY_NO_POST
    _assert_no_sentinel_exposure(repr(result), _safe_result_payload(result), rendered)
    assert result.sealed_request_label == "UNSUPPORTED_REDACTED"
    assert result.sealed_body_label == "UNSUPPORTED_REDACTED"
    assert result.sealed_endpoint_label == "UNSUPPORTED_REDACTED"
    assert result.environment_label == "UNSUPPORTED_REDACTED"
    assert result.risk_label == "UNSUPPORTED_REDACTED"


def test_sealed_body_builder_uses_only_repo_defined_safe_candidate() -> None:
    preview = build_live_order_real_executable_order_preview(
        LiveOrderRealExecutableOrderPreviewInput(),
    )
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        preview=preview,
    )

    assert result.status is SealedStatus.SEALED_REQUEST_RESULT_READY_NO_POST
    assert result.safe_order_candidate_available is True
    assert result.symbol == SUPPORTED_SYMBOL
    assert result.side == LiveOrderCandidateSide.BUY.value
    assert result.order_type == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
    assert result.size == LIVE_ORDER_CANDIDATE_SIZE
    assert result.codex_inferred_symbol is False
    assert result.codex_inferred_side is False
    assert result.codex_inferred_size is False
    assert result.codex_inferred_order_type is False


def test_sealed_body_builder_blocks_missing_candidate() -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(
            safe_order_candidate_available=False,
        ),
    )

    assert result.status is (
        SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_MISSING_CANDIDATE
    )
    assert result.sealed_body_builder_ready is False
    assert result.order_ambiguity is True
    assert "safe_order_candidate_missing" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"order_ambiguity": True}, "order_ambiguity"),
        ({"codex_inferred_symbol": True}, "codex_inferred_symbol"),
        ({"codex_inferred_side": True}, "codex_inferred_side"),
        ({"codex_inferred_size": True}, "codex_inferred_size"),
        ({"codex_inferred_order_type": True}, "codex_inferred_order_type"),
    ],
)
def test_sealed_body_builder_blocks_ambiguous_candidate(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(**override),
    )

    assert result.status is (
        SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_AMBIGUOUS_CANDIDATE
    )
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"symbol": "UNSUPPORTED_SYMBOL"},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SYMBOL,
            "unsupported_symbol",
        ),
        (
            {"side": "UNKNOWN"},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_SIDE,
            "unsupported_side",
        ),
        (
            {"order_type": "LIMIT"},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_UNKNOWN_ORDER_TYPE,
            "unsupported_order_type",
        ),
        (
            {"size": LIVE_ORDER_CANDIDATE_SIZE + 1},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_INVALID_SIZE,
            "unsupported_size",
        ),
    ],
)
def test_sealed_body_builder_blocks_unsupported_candidate_fields(
    override: dict[str, object],
    expected_status: SealedStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.sealed_body_builder_ready is False


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"raw_body_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE,
            "raw_body_exposure_attempted",
        ),
        (
            {"endpoint_actual_value_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE,
            "endpoint_actual_value_exposure_attempted",
        ),
        (
            {"raw_response_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE,
            "raw_response_exposure_attempted",
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_RAW_EXPOSURE,
            "broker_api_response_exposure_attempted",
        ),
        (
            {"id_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"client_order_id_actual_value_generated": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE,
            "client_order_id_actual_value_generated",
        ),
        (
            {"client_order_id_actual_value_exposed": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_ID_EXPOSURE,
            "client_order_id_actual_value_exposed",
        ),
        (
            {"credential_value_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE,
            "credential_value_exposure_attempted",
        ),
        (
            {"signature_value_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE,
            "signature_value_exposure_attempted",
        ),
        (
            {"headers_value_exposure_attempted": True},
            SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_VALUE_EXPOSURE,
            "headers_value_exposure_attempted",
        ),
    ],
)
def test_sealed_request_blocks_unsafe_field_exposure(
    override: dict[str, object],
    expected_status: SealedStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.raw_body_exposed is False
    assert result.credential_value_exposed is False
    assert result.client_order_id_actual_value_exposed is False


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"actual_http_post_executed": True}, "actual_http_post_executed"),
        ({"post_execution_count": 1}, "post_execution_count_nonzero"),
        ({"order_endpoint_executed": True}, "order_endpoint_executed"),
        ({"live_order_once_executed": True}, "live_order_once_executed"),
    ],
)
def test_sealed_request_blocks_execution_attempts(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(**override),
    )

    assert result.status is (
        SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_POST_OR_ORDER_EXECUTION
    )
    assert reason in result.blocked_reasons
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"retry_attempted": True}, "retry_attempted"),
        ({"second_post_attempted": True}, "second_post_attempted"),
        ({"ledger_update_attempted": True}, "ledger_update_attempted"),
        ({"attempt_counter_persisted": True}, "attempt_counter_persisted"),
        ({"receipt_handoff_attempted": True}, "receipt_handoff_attempted"),
        (
            {"client_order_id_strategy_non_ledger": False},
            "client_order_id_strategy_ledger_coupled",
        ),
    ],
)
def test_sealed_request_blocks_lifecycle_coupling(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(**override),
    )

    assert result.status is (
        SealedStatus.SEALED_REQUEST_RESULT_BLOCKED_LEDGER_RECEIPT_RETRY
    )
    assert reason in result.blocked_reasons
    assert result.retry_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


def test_client_order_id_strategy_returns_safe_label_only_and_is_non_ledger() -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled()
    rendered = render_live_order_real_one_shot_post_sealed_request_result_markdown(
        result,
    )

    assert result.source_owned_client_order_id_strategy_required is True
    assert result.source_owned_client_order_id_strategy_ready is True
    assert result.source_owned_client_order_id_strategy_label == (
        SAFE_CLIENT_ORDER_ID_STRATEGY_LABEL
    )
    assert result.client_order_id_strategy_non_ledger is True
    assert result.client_order_id_actual_value_generated is False
    assert result.client_order_id_actual_value_exposed is False
    assert "client_order_id_actual_value_exposed: false" in rendered


@pytest.mark.parametrize(
    ("category", "expected_status", "expected_sanitized", "reconciliation"),
    [
        (
            TransportSafeCategory.ACCEPTED.value,
            MappingStatus.SEALED_RESULT_MAPPING_ACCEPTED,
            SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value,
            SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value,
        ),
        (
            TransportSafeCategory.REJECTED.value,
            MappingStatus.SEALED_RESULT_MAPPING_REJECTED,
            SafePostResultCategory.RESULT_REJECTED_SANITIZED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
        (
            TransportSafeCategory.FAILED.value,
            MappingStatus.SEALED_RESULT_MAPPING_FAILED_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
        (
            TransportSafeCategory.TIMEOUT.value,
            MappingStatus.SEALED_RESULT_MAPPING_TIMEOUT_FAIL_CLOSED,
            SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
        (
            TransportSafeCategory.UNKNOWN.value,
            MappingStatus.SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
        (
            TransportSafeCategory.UNAVAILABLE.value,
            MappingStatus.SEALED_RESULT_MAPPING_UNAVAILABLE_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
        (
            "unsupported",
            MappingStatus.SEALED_RESULT_MAPPING_UNKNOWN_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
            SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value,
        ),
    ],
)
def test_safe_result_mapper_maps_transport_categories(
    category: str,
    expected_status: MappingStatus,
    expected_sanitized: str,
    reconciliation: str,
) -> None:
    result = map_live_order_real_one_shot_post_sealed_transport_result(
        LiveOrderRealSealedTransportResultMappingInput(
            transport_safe_category=category,
        ),
    )

    assert result.status is expected_status
    assert result.sanitized_result_category == expected_sanitized
    assert result.safe_reconciliation_status == reconciliation
    assert result.retry_allowed is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.raw_response_exposed is False
    assert result.id_exposed is False


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"raw_response_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            "raw_response_exposure_attempted",
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            "broker_api_response_exposure_attempted",
        ),
        (
            {"id_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"retry_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT,
            "retry_attempted",
        ),
        (
            {"ledger_update_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT,
            "ledger_update_attempted",
        ),
        (
            {"receipt_handoff_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RETRY_LEDGER_RECEIPT,
            "receipt_handoff_attempted",
        ),
        (
            {"credential_value_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            "credential_signature_headers_value_exposure_attempted",
        ),
        (
            {"signature_value_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            "credential_signature_headers_value_exposure_attempted",
        ),
        (
            {"headers_value_exposure_attempted": True},
            MappingStatus.SEALED_RESULT_MAPPING_BLOCKED_RAW_EXPOSURE,
            "credential_signature_headers_value_exposure_attempted",
        ),
    ],
)
def test_safe_result_mapper_blocks_exposure_retry_ledger_and_receipt(
    override: dict[str, object],
    expected_status: MappingStatus,
    reason: str,
) -> None:
    result = map_live_order_real_one_shot_post_sealed_transport_result(
        LiveOrderRealSealedTransportResultMappingInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.retry_allowed is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.raw_response_exposed is False
    assert result.id_exposed is False


def test_safe_result_mapper_repr_asdict_and_renderer_do_not_expose_sentinels() -> None:
    result = map_live_order_real_one_shot_post_sealed_transport_result(
        LiveOrderRealSealedTransportResultMappingInput(
            safe_post_result_label=RAW_RESPONSE_SENTINEL,
            safe_reconciliation_label=ID_SENTINEL,
        ),
    )
    rendered = render_live_order_real_one_shot_post_sealed_result_mapping_markdown(
        result,
    )

    assert result.status is MappingStatus.SEALED_RESULT_MAPPING_ACCEPTED
    _assert_no_sentinel_exposure(repr(result), _safe_result_payload(result), rendered)
    assert result.safe_post_result_label == "UNSUPPORTED_REDACTED"
    assert result.safe_reconciliation_label == "UNSUPPORTED_REDACTED"


def test_import_construct_and_summary_do_not_post_or_enable_actual_source() -> None:
    result = build_live_order_real_one_shot_post_sealed_request_result_controlled()
    mapping = map_live_order_real_one_shot_post_sealed_transport_result()

    assert result.actual_http_post_executed is False
    assert result.order_endpoint_executed is False
    assert result.live_order_once_executed is False
    assert result.post_execution_count == 0
    assert result.approved_primitive_actual_source_available is False
    assert mapping.retry_allowed is False
    assert mapping.ledger_update_allowed is False
    assert mapping.receipt_handoff_allowed is False
