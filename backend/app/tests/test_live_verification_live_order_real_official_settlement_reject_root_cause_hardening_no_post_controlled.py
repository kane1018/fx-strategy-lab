from __future__ import annotations

from dataclasses import asdict

import pytest

from app.live_verification.live_order_real_official_settlement_reject_root_cause_hardening_no_post_controlled import (  # noqa: E501
    FRESH_RETRY_READY_WITH_GATES,
    OPERATOR_UI_SAFE_LABEL_COLLECTION_READY,
    POSITION_SPECIFIC_SAFE_ID_STATUS,
    SAFE_ERROR_CODE_CAPTURE_READY,
    SIZE_BASED_TARGET_CONSISTENCY_READY,
    OfficialSettlementRejectRootCauseHardeningInput,
    OfficialSettlementRejectRootCauseHardeningStatus,
    build_official_settlement_reject_root_cause_hardening_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_safe_rejection_category_no_post_controlled import (  # noqa: E501
    OPERATOR_UI_REJECTION_SAFE_REASON_ACTIVE_ORDER_CONFLICT,
    OPERATOR_UI_REJECTION_SAFE_REASON_NOT_DISPLAYED,
    OPERATOR_UI_REJECTION_SAFE_REASON_PERMISSION,
    SAFE_API_STATUS_NONZERO,
    SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND,
    SAFE_BROKER_ERROR_CODE_FAMILY_SIZE_OR_TARGET_MISMATCH,
    SAFE_HTTP_STATUS_RATE_LIMIT,
    SafeRejectionCategory,
    SafeRejectionCategoryCaptureInput,
    SafeRejectionConfidence,
    SafeRejectionKind,
    SafeRejectionSource,
    build_safe_rejection_category_capture_no_post_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)


def _build(**overrides: object):
    return build_official_settlement_reject_root_cause_hardening_no_post_controlled(
        OfficialSettlementRejectRootCauseHardeningInput(**overrides),
    )


def test_reject_root_cause_hardening_ready_no_post() -> None:
    result = _build()

    assert (
        result.status
        is OfficialSettlementRejectRootCauseHardeningStatus.READY_NO_POST
    )
    assert result.hardening_ready is True
    assert result.no_post_blocker_found is False
    assert result.fresh_retry_readiness == FRESH_RETRY_READY_WITH_GATES
    assert result.safe_error_code_capture_status == SAFE_ERROR_CODE_CAPTURE_READY
    assert result.safe_error_code_capture_ready is True
    assert result.safe_http_status_label_allowed is True
    assert result.safe_api_status_label_allowed is True
    assert result.safe_broker_error_code_label_allowed is True
    assert result.safe_broker_error_code_family_allowed is True
    assert result.raw_response_required_for_exact_cause is True
    assert result.position_specific_safe_id_handling_status == POSITION_SPECIFIC_SAFE_ID_STATUS
    assert result.position_specific_safe_id_handling_required is False
    assert result.position_specific_safe_identifier_handling_ready is False
    assert result.position_specific_actual_path_allowed is False
    assert result.position_specific_identifier_rendered is False
    assert result.position_specific_identifier_persisted is False
    assert result.size_based_target_consistency_status == SIZE_BASED_TARGET_CONSISTENCY_READY
    assert result.size_based_request_uses_size_only is True
    assert result.size_based_request_includes_settle_position is False
    assert result.size_and_settle_position_mutually_exclusive is True
    assert (
        result.operator_ui_safe_label_collection_status
        == OPERATOR_UI_SAFE_LABEL_COLLECTION_READY
    )
    assert OPERATOR_UI_REJECTION_SAFE_REASON_PERMISSION in result.allowed_operator_ui_safe_labels
    assert OPERATOR_UI_REJECTION_SAFE_REASON_ACTIVE_ORDER_CONFLICT in (
        result.allowed_operator_ui_safe_labels
    )
    assert result.actual_post_this_step is False
    assert result.entry_post_this_step is False
    assert result.settlement_post_this_step is False
    assert result.retry_this_step is False
    assert result.raw_id_value_exposure is False
    assert result.env_read is False
    assert result.blocked_reasons == ()


def test_hardening_blocks_execution_exposure_and_position_specific_actual_path() -> None:
    result = _build(
        actual_post_this_step=True,
        position_specific_actual_path_allowed=True,
        position_specific_identifier_rendered=True,
        raw_id_value_exposure=True,
        env_read=True,
    )
    payload = repr(asdict(result))

    assert (
        result.status
        is OfficialSettlementRejectRootCauseHardeningStatus.BLOCKED_NO_POST
    )
    assert result.hardening_ready is False
    assert result.no_post_blocker_found is True
    assert result.actual_post_this_step is False
    assert result.position_specific_actual_path_allowed is True
    assert result.position_specific_identifier_rendered is False
    assert result.raw_id_value_exposure is False
    assert result.env_read is False
    assert "execution_or_exposure_attempt_blocked" in result.blocked_reasons
    assert "position_specific_actual_path_not_allowed_in_no_post" in result.blocked_reasons
    assert "position_specific_identifier_rendered_blocked" in result.blocked_reasons
    assert "POSITION_ID_SHOULD_NOT_SURFACE" not in payload


def test_current_state_not_flat_blocks_fresh_retry_without_post() -> None:
    result = _build(
        runtime_position_status_current=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        position_count_safe_current=1,
    )

    assert result.hardening_ready is True
    assert result.no_post_blocker_found is False
    assert result.fresh_retry_readiness != FRESH_RETRY_READY_WITH_GATES
    assert result.entry_post_this_step is False
    assert result.settlement_post_this_step is False


@pytest.mark.parametrize(
    ("field_name", "label", "category", "kind", "source", "confidence"),
    [
        (
            "safe_api_status_label",
            SAFE_API_STATUS_NONZERO,
            SafeRejectionCategory.BROKER_REJECTED_UNCLASSIFIED,
            SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE,
            SafeRejectionSource.SAFE_API_STATUS_LABEL,
            SafeRejectionConfidence.LOW,
        ),
        (
            "safe_broker_error_code_family",
            SAFE_BROKER_ERROR_CODE_FAMILY_SIZE_OR_TARGET_MISMATCH,
            SafeRejectionCategory.SIZE_OR_TARGET_MISMATCH,
            SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
            SafeRejectionSource.SAFE_BROKER_ERROR_CODE_FAMILY,
            SafeRejectionConfidence.MEDIUM,
        ),
        (
            "safe_broker_code_label",
            SAFE_BROKER_CODE_POSITION_TARGET_NOT_FOUND,
            SafeRejectionCategory.POSITION_STATE_OR_TARGET_NOT_FOUND,
            SafeRejectionKind.SIZE_BASED_TARGET_MISMATCH,
            SafeRejectionSource.SAFE_BROKER_ERROR_CODE_LABEL,
            SafeRejectionConfidence.HIGH,
        ),
        (
            "safe_http_status_label",
            SAFE_HTTP_STATUS_RATE_LIMIT,
            SafeRejectionCategory.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
            SafeRejectionKind.RATE_LIMIT_OR_TEMPORARY_CONSTRAINT,
            SafeRejectionSource.SAFE_HTTP_STATUS_LABEL,
            SafeRejectionConfidence.MEDIUM,
        ),
        (
            "operator_ui_safe_label",
            OPERATOR_UI_REJECTION_SAFE_REASON_NOT_DISPLAYED,
            SafeRejectionCategory.UNKNOWN,
            SafeRejectionKind.BROKER_REJECTED_REASON_UNAVAILABLE,
            SafeRejectionSource.OPERATOR_UI_SAFE_LABEL,
            SafeRejectionConfidence.UNKNOWN,
        ),
    ],
)
def test_safe_rejection_allowlist_maps_new_safe_labels(
    field_name: str,
    label: str,
    category: SafeRejectionCategory,
    kind: SafeRejectionKind,
    source: SafeRejectionSource,
    confidence: SafeRejectionConfidence,
) -> None:
    result = build_safe_rejection_category_capture_no_post_controlled(
        input_snapshot=SafeRejectionCategoryCaptureInput(**{field_name: label}),
    )

    assert result.safe_rejection_category == category.value
    assert result.safe_rejection_kind == kind.value
    assert result.safe_rejection_source == source.value
    assert result.safe_rejection_confidence == confidence.value
    assert result.actual_settlement_post_executed is False
    assert result.transport_call_count == 0
    assert result.real_http_call_count == 0


def test_unknown_raw_like_safe_label_does_not_surface() -> None:
    result = build_safe_rejection_category_capture_no_post_controlled(
        input_snapshot=SafeRejectionCategoryCaptureInput(
            safe_broker_error_code_family="POSITION_ID_SHOULD_NOT_SURFACE",
            safe_api_status_label="RAW_RESPONSE_SHOULD_NOT_SURFACE",
        ),
    )
    payload = repr(asdict(result))

    assert result.safe_rejection_category == SafeRejectionCategory.UNKNOWN.value
    assert result.selected_safe_detail_label != "POSITION_ID_SHOULD_NOT_SURFACE"
    assert "POSITION_ID_SHOULD_NOT_SURFACE" not in payload
    assert "RAW_RESPONSE_SHOULD_NOT_SURFACE" not in payload
