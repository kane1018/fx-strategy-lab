from __future__ import annotations

from dataclasses import asdict

import pytest

from app.live_verification.live_order_real_credential_presence_controlled import (
    LiveOrderRealCredentialPresenceControlledInput,
    build_live_order_real_credential_presence_controlled,
)
from app.live_verification.live_order_real_one_shot_post_sealed_credential_signing_controlled import (  # noqa: E501
    SAFE_CREDENTIAL_PRESENCE_LABEL,
    SAFE_SEALED_CREDENTIAL_PROVIDER_LABEL,
    SAFE_SEALED_CREDENTIAL_SIGNING_PROVIDER_LABEL,
    SAFE_SEALED_HEADERS_LABEL,
    SAFE_SEALED_SIGNING_PROVIDER_LABEL,
    LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
    LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus,
    build_live_order_real_one_shot_post_sealed_credential_signing_controlled,
    build_live_order_real_one_shot_post_sealed_credential_signing_from_foundation,
    render_live_order_real_one_shot_post_sealed_credential_signing_markdown,
)
from app.live_verification.live_order_real_one_shot_post_sealed_request_result_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedRequestResultControlledInput,
    build_live_order_real_one_shot_post_sealed_request_result_controlled,
)

SealedProviderStatus = LiveOrderRealOneShotPostSealedCredentialSigningControlledStatus

CREDENTIAL_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
CREDENTIAL_LENGTH_SENTINEL = "CREDENTIAL_LENGTH_SHOULD_NOT_SURFACE"
CREDENTIAL_HASH_SENTINEL = "CREDENTIAL_HASH_SHOULD_NOT_SURFACE"
CREDENTIAL_FINGERPRINT_SENTINEL = "CREDENTIAL_FINGERPRINT_SHOULD_NOT_SURFACE"
CREDENTIAL_METADATA_SENTINEL = "CREDENTIAL_METADATA_SHOULD_NOT_SURFACE"
SIGNING_SENTINEL = "SIGNING_VALUE_SHOULD_NOT_SURFACE"
SIGNING_LENGTH_SENTINEL = "SIGNING_LENGTH_SHOULD_NOT_SURFACE"
SIGNING_HASH_SENTINEL = "SIGNING_HASH_SHOULD_NOT_SURFACE"
SIGNING_FINGERPRINT_SENTINEL = "SIGNING_FINGERPRINT_SHOULD_NOT_SURFACE"
HEADERS_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
HEADERS_METADATA_SENTINEL = "HEADERS_METADATA_SHOULD_NOT_SURFACE"
HEADERS_COUNT_SENTINEL = "HEADERS_COUNT_SHOULD_NOT_SURFACE"
RAW_BODY_SENTINEL = "RAW_BODY_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"

FORBIDDEN_SENTINELS = (
    CREDENTIAL_SENTINEL,
    CREDENTIAL_LENGTH_SENTINEL,
    CREDENTIAL_HASH_SENTINEL,
    CREDENTIAL_FINGERPRINT_SENTINEL,
    CREDENTIAL_METADATA_SENTINEL,
    SIGNING_SENTINEL,
    SIGNING_LENGTH_SENTINEL,
    SIGNING_HASH_SENTINEL,
    SIGNING_FINGERPRINT_SENTINEL,
    HEADERS_SENTINEL,
    HEADERS_METADATA_SENTINEL,
    HEADERS_COUNT_SENTINEL,
    RAW_BODY_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    ID_SENTINEL,
)


def _safe_payload(result: object) -> str:
    return repr(asdict(result))


def _assert_no_sentinel_exposure(*payloads: str) -> None:
    joined = "\n".join(payloads)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in joined


def test_sealed_credential_signing_summary_is_safe_only_and_does_not_post() -> None:
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled()
    rendered = render_live_order_real_one_shot_post_sealed_credential_signing_markdown(
        result,
    )

    assert result.status is SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST
    assert result.sealed_credential_signing_provider_ready is True
    assert result.sealed_credential_provider_ready is True
    assert result.sealed_signing_provider_ready is True
    assert result.sealed_headers_ready is True
    assert result.sealed_credential_signing_provider_label == (
        SAFE_SEALED_CREDENTIAL_SIGNING_PROVIDER_LABEL
    )
    assert result.sealed_credential_provider.sealed_credential_provider_label == (
        SAFE_SEALED_CREDENTIAL_PROVIDER_LABEL
    )
    assert result.sealed_signing_provider.sealed_signing_provider_label == (
        SAFE_SEALED_SIGNING_PROVIDER_LABEL
    )
    assert result.sealed_headers_object.sealed_headers_label == (
        SAFE_SEALED_HEADERS_LABEL
    )
    assert result.credential_presence_safe_label == SAFE_CREDENTIAL_PRESENCE_LABEL
    assert result.credential_values_loaded_internal is False
    assert result.actual_post_allowed is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_allowed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_update_allowed is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_allowed is False
    assert result.actual_receipt_handoff_executed is False
    assert result.approved_primitive_actual_source_available is False
    assert "actual_http_post_executed: false" in rendered
    _assert_no_sentinel_exposure(rendered, _safe_payload(result), repr(result))


def test_sealed_provider_repr_asdict_and_renderer_do_not_expose_sentinels() -> None:
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(
            sealed_credential_signing_provider_label=CREDENTIAL_SENTINEL,
            sealed_credential_provider_label=SIGNING_SENTINEL,
            sealed_signing_provider_label=HEADERS_SENTINEL,
            sealed_headers_label=RAW_BODY_SENTINEL,
            credential_presence_safe_label=ID_SENTINEL,
            credential_presence_safe_status=RAW_RESPONSE_SENTINEL,
        ),
    )
    rendered = render_live_order_real_one_shot_post_sealed_credential_signing_markdown(
        result,
    )

    assert result.status is SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST
    assert result.sealed_credential_signing_provider_label == "UNSUPPORTED_REDACTED"
    assert result.sealed_credential_provider.sealed_credential_provider_label == (
        "UNSUPPORTED_REDACTED"
    )
    assert result.sealed_signing_provider.sealed_signing_provider_label == (
        "UNSUPPORTED_REDACTED"
    )
    assert result.sealed_headers_object.sealed_headers_label == "UNSUPPORTED_REDACTED"
    assert result.credential_presence_safe_label == "UNSUPPORTED_REDACTED"
    assert result.credential_presence_safe_status == "UNSUPPORTED_REDACTED"
    _assert_no_sentinel_exposure(repr(result), _safe_payload(result), rendered)


def test_sealed_provider_connects_to_sealed_request_foundation_without_post() -> None:
    sealed_request_result = (
        build_live_order_real_one_shot_post_sealed_request_result_controlled()
    )
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        sealed_request_result=sealed_request_result,
    )
    convenience_result = (
        build_live_order_real_one_shot_post_sealed_credential_signing_from_foundation()
    )

    assert result.status is SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST
    assert convenience_result.status is (
        SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_READY_NO_POST
    )
    assert result.requires_sealed_request is True
    assert result.requires_sealed_body is True
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"sealed_request_model_ready": False},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_REQUEST,
            "sealed_request_model_missing",
        ),
        (
            {"sealed_body_builder_ready": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_BODY,
            "sealed_body_builder_missing",
        ),
        (
            {"credential_presence_checked": False},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_CREDENTIAL_PRESENCE,
            "credential_presence_not_checked",
        ),
        (
            {"credential_presence_available": False},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_UNAVAILABLE,
            "credential_presence_unavailable",
        ),
        (
            {"sealed_credential_provider_declared": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            "sealed_credential_provider_missing",
        ),
        (
            {"sealed_signing_provider_declared": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            "sealed_signing_provider_missing",
        ),
        (
            {"sealed_headers_declared": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            "sealed_headers_missing",
        ),
        (
            {"signing_generation_internal_only": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            "sealed_signing_not_internal_only",
        ),
        (
            {"headers_present": False},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_PROVIDER,
            "sealed_headers_not_present",
        ),
    ],
)
def test_provider_readiness_fails_closed_on_missing_prerequisites(
    override: dict[str, object],
    expected_status: SealedProviderStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(**override),
    )

    assert result.status is expected_status
    assert result.sealed_credential_signing_provider_ready is False
    assert reason in result.blocked_reasons
    assert result.actual_post_allowed is False


def test_missing_credential_presence_from_controlled_result_fails_closed() -> None:
    presence_result = build_live_order_real_credential_presence_controlled(
        input_snapshot=LiveOrderRealCredentialPresenceControlledInput(
            process_env_access_allowed=False,
        ),
    )
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        credential_presence_result=presence_result,
    )

    assert result.status is (
        SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_UNAVAILABLE
    )
    assert result.credential_presence_checked is True
    assert result.credential_presence_available is False
    assert result.actual_post_allowed is False


def test_blocked_sealed_request_foundation_blocks_provider() -> None:
    sealed_request_result = build_live_order_real_one_shot_post_sealed_request_result_controlled(  # noqa: E501
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(
            safe_order_candidate_available=False,
        ),
    )
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        sealed_request_result=sealed_request_result,
    )

    assert result.status is (
        SealedProviderStatus
        .SEALED_CREDENTIAL_SIGNING_BLOCKED_MISSING_SEALED_REQUEST
    )
    assert result.sealed_credential_signing_provider_ready is False
    assert result.actual_post_allowed is False


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"credential_values_loaded_internal": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_values_loaded_internal",
        ),
        (
            {"credential_value_exposure_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_value_exposure_attempted",
        ),
        (
            {"credential_length_exposure_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_length_exposure_attempted",
        ),
        (
            {"credential_hash_exposure_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_hash_exposure_attempted",
        ),
        (
            {"credential_fingerprint_exposure_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_fingerprint_exposure_attempted",
        ),
        (
            {"credential_metadata_exposure_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_CREDENTIAL_EXPOSURE,
            "credential_metadata_exposure_attempted",
        ),
        (
            {"signature_value_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE,
            "signature_value_exposure_attempted",
        ),
        (
            {"signature_length_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE,
            "signature_length_exposure_attempted",
        ),
        (
            {"signature_hash_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE,
            "signature_hash_exposure_attempted",
        ),
        (
            {"signature_fingerprint_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_SIGNING_EXPOSURE,
            "signature_fingerprint_exposure_attempted",
        ),
        (
            {"headers_value_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE,
            "headers_value_exposure_attempted",
        ),
        (
            {"headers_metadata_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE,
            "headers_metadata_exposure_attempted",
        ),
        (
            {"headers_count_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_HEADERS_EXPOSURE,
            "headers_count_exposure_attempted",
        ),
    ],
)
def test_provider_blocks_credential_signing_and_headers_exposure_attempts(
    override: dict[str, object],
    expected_status: SealedProviderStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(**override),
    )

    rendered = render_live_order_real_one_shot_post_sealed_credential_signing_markdown(
        result,
    )
    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    _assert_no_sentinel_exposure(rendered, _safe_payload(result))


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"raw_body_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE,
            "raw_body_exposure_attempted",
        ),
        (
            {"raw_response_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE,
            "raw_response_exposure_attempted",
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_RAW_EXPOSURE,
            "broker_api_response_exposure_attempted",
        ),
        (
            {"id_exposure_attempted": True},
            SealedProviderStatus.SEALED_CREDENTIAL_SIGNING_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"actual_http_post_executed": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION,
            "actual_http_post_executed",
        ),
        (
            {"post_execution_count": 1},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION,
            "post_execution_count_nonzero",
        ),
        (
            {"order_endpoint_executed": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION,
            "order_endpoint_executed",
        ),
        (
            {"live_order_once_executed": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_POST_OR_ORDER_EXECUTION,
            "live_order_once_executed",
        ),
        (
            {"second_post_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            "second_post_attempted",
        ),
        (
            {"retry_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            "retry_attempted",
        ),
        (
            {"ledger_update_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            "ledger_update_attempted",
        ),
        (
            {"attempt_counter_persisted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            "attempt_counter_persisted",
        ),
        (
            {"receipt_handoff_attempted": True},
            SealedProviderStatus
            .SEALED_CREDENTIAL_SIGNING_BLOCKED_LEDGER_RECEIPT_RETRY,
            "receipt_handoff_attempted",
        ),
    ],
)
def test_provider_blocks_raw_id_execution_and_lifecycle_attempts(
    override: dict[str, object],
    expected_status: SealedProviderStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.actual_post_allowed is False
    assert result.retry_allowed is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0


def test_import_construct_and_summary_do_not_post_or_expose_values() -> None:
    input_snapshot = LiveOrderRealOneShotPostSealedCredentialSigningControlledInput()
    result = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        input_snapshot,
    )
    rendered = render_live_order_real_one_shot_post_sealed_credential_signing_markdown(
        result,
    )

    assert input_snapshot.actual_http_post_executed is False
    assert result.actual_http_post_executed is False
    assert result.order_endpoint_executed is False
    assert result.live_order_once_executed is False
    assert result.post_execution_count == 0
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    _assert_no_sentinel_exposure(rendered, repr(input_snapshot), repr(result))
