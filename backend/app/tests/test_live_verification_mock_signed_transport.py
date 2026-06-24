from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from app.live_verification.actual_headers_signature import (
    ActualHeadersSignatureBundle,
    _get_sensitive_signed_headers,
    build_actual_headers_signature_bundle,
)
from app.live_verification.errors import LiveVerificationMockSignedTransportError
from app.live_verification.mock_signed_transport import (
    MOCK_SIGNED_TRANSPORT_MODE,
    MockSignedOrderTransportResult,
    make_mock_signed_order_transport_result_id,
    run_mock_signed_order_transport,
)
from app.tests.test_live_verification_actual_headers_signature import (
    DUMMY_API_KEY,
    DUMMY_API_SECRET,
    DUMMY_TIMESTAMP,
)
from app.tests.test_live_verification_actual_order_body import _body

EXPECTED_TRANSPORT_FIELDS = {
    "mock_transport_result_id",
    "bundle_id",
    "actual_order_body_id",
    "verification_run_id",
    "transport_mode",
    "network_enabled",
    "http_client_enabled",
    "http_post_enabled",
    "real_order_attempted",
    "raw_request_saved",
    "raw_response_saved",
    "credential_values_logged",
    "bundle_passed",
    "transport_passed",
    "header_names_summary",
    "signature_algorithm_summary",
    "fail_reasons",
}
BLOCKED_TRANSPORT_FIELDS = {
    "headers",
    "actual_headers",
    "header_values",
    "api_key",
    "api_secret",
    "secret",
    "token",
    "credential",
    "credentials",
    "authorization",
    "signature",
    "actual_signature",
    "signature_value",
    "api_sign",
    "hmac_digest",
    "raw_headers",
    "raw_signature",
    "raw_request",
    "raw_response",
    "http_client",
    "response",
    "endpoint",
    "method",
    "path",
    "url",
    "status_code",
    "response_body",
    "request_body",
    "request_headers",
    "body",
    "payload",
}


def _bundle() -> ActualHeadersSignatureBundle:
    return build_actual_headers_signature_bundle(
        actual_order_body=_body(),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp=DUMMY_TIMESTAMP,
    )


def test_mock_signed_transport_accepts_passed_bundle_without_network() -> None:
    bundle = _bundle()

    result = run_mock_signed_order_transport(bundle=bundle)
    same = run_mock_signed_order_transport(bundle=bundle)

    assert isinstance(result, MockSignedOrderTransportResult)
    assert result.mock_transport_result_id == same.mock_transport_result_id
    assert result.mock_transport_result_id == make_mock_signed_order_transport_result_id(
        bundle_id=bundle.bundle_id,
        actual_order_body_id=bundle.actual_order_body_id,
        verification_run_id=bundle.verification_run_id,
    )
    assert result.bundle_id == bundle.bundle_id
    assert result.actual_order_body_id == bundle.actual_order_body_id
    assert result.verification_run_id == bundle.verification_run_id
    assert result.transport_mode == MOCK_SIGNED_TRANSPORT_MODE
    assert result.network_enabled is False
    assert result.http_client_enabled is False
    assert result.http_post_enabled is False
    assert result.real_order_attempted is False
    assert result.raw_request_saved is False
    assert result.raw_response_saved is False
    assert result.credential_values_logged is False
    assert result.bundle_passed is True
    assert result.transport_passed is True
    assert result.header_names_summary == bundle.header_names_summary
    assert result.signature_algorithm_summary == bundle.signature_algorithm_summary
    assert result.fail_reasons == ()


def test_mock_signed_transport_does_not_expose_sensitive_values() -> None:
    bundle = _bundle()
    result = run_mock_signed_order_transport(bundle=bundle)
    public_views = (
        repr(result),
        str(result),
        repr(asdict(result)),
        str(asdict(result)),
        repr(result.header_names_summary),
        result.signature_algorithm_summary,
    )

    assert _get_sensitive_signed_headers(bundle) is not None
    for view in public_views:
        assert DUMMY_API_KEY not in view
        assert DUMMY_API_SECRET not in view
    assert set(asdict(result)) == EXPECTED_TRANSPORT_FIELDS
    assert {field.name for field in fields(MockSignedOrderTransportResult)} == (
        EXPECTED_TRANSPORT_FIELDS
    )
    assert set(asdict(result)).isdisjoint(BLOCKED_TRANSPORT_FIELDS)
    assert all(not hasattr(result, field_name) for field_name in BLOCKED_TRANSPORT_FIELDS)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"transport_mode": "network_transport"},
        {"network_enabled": True},
        {"http_client_enabled": True},
        {"http_post_enabled": True},
        {"real_order_attempted": True},
        {"raw_request_saved": True},
        {"raw_response_saved": True},
        {"credential_values_logged": True},
    ],
)
def test_mock_signed_transport_fails_closed_for_unsafe_flags(
    kwargs: dict[str, object],
) -> None:
    result = run_mock_signed_order_transport(bundle=_bundle(), **kwargs)

    assert result.transport_passed is False
    assert result.fail_reasons


def test_mock_signed_transport_collects_multiple_fail_reasons() -> None:
    result = run_mock_signed_order_transport(
        bundle=_bundle(),
        network_enabled=True,
        http_client_enabled=True,
        http_post_enabled=True,
        real_order_attempted=True,
        raw_request_saved=True,
        raw_response_saved=True,
        credential_values_logged=True,
    )

    assert result.transport_passed is False
    assert set(result.fail_reasons) >= {
        "network_enabled",
        "http_client_enabled",
        "http_post_enabled",
        "real_order_attempted",
        "raw_request_saved",
        "raw_response_saved",
        "credential_values_logged",
    }


def test_mock_signed_transport_rejects_wrong_input_type() -> None:
    with pytest.raises(LiveVerificationMockSignedTransportError):
        run_mock_signed_order_transport(bundle=object())  # type: ignore[arg-type]
