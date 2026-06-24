from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from app.live_verification.actual_headers_signature import (
    BODY_SERIALIZATION_SUMMARY,
    HEADER_NAMES_SUMMARY,
    ORDER_CREATE_METHOD,
    ORDER_CREATE_PATH,
    SIGNATURE_ALGORITHM_SUMMARY,
    ActualHeadersSignatureBundle,
    _get_sensitive_signed_headers,
    build_actual_headers_signature_bundle,
    make_actual_headers_signature_bundle_id,
    serialize_actual_order_body_for_signing,
)
from app.live_verification.actual_order_body import ActualOrderRequestBody
from app.live_verification.errors import LiveVerificationActualHeadersSignatureError
from app.tests.test_live_verification_actual_order_body import _body

DUMMY_API_KEY = "dummy_api_key_for_unit_test"
DUMMY_API_SECRET = "dummy_api_secret_for_unit_test"
DUMMY_TIMESTAMP = "1700000000000"
EXPECTED_BUNDLE_FIELDS = {
    "bundle_id",
    "actual_order_body_id",
    "verification_run_id",
    "headers_created",
    "signature_created",
    "hmac_used",
    "http_post_enabled",
    "raw_headers_saved",
    "raw_signature_saved",
    "raw_request_saved",
    "raw_response_saved",
    "credential_values_logged",
    "api_key_value_exposed",
    "api_secret_value_exposed",
    "signature_value_exposed",
    "header_names_summary",
    "signature_algorithm_summary",
    "body_serialization_summary",
    "bundle_passed",
    "fail_reasons",
}
BLOCKED_PUBLIC_FIELDS = {
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


def _bundle(
    *,
    actual_order_body: ActualOrderRequestBody | None = None,
    **overrides: object,
) -> ActualHeadersSignatureBundle:
    kwargs = {
        "actual_order_body": actual_order_body or _body(),
        "api_key": DUMMY_API_KEY,
        "api_secret": DUMMY_API_SECRET,
        "timestamp": DUMMY_TIMESTAMP,
    }
    kwargs.update(overrides)
    return build_actual_headers_signature_bundle(**kwargs)


def _unchecked_body(**overrides: object) -> ActualOrderRequestBody:
    values = asdict(_body())
    values.update(overrides)
    body = object.__new__(ActualOrderRequestBody)
    for field_name, value in values.items():
        object.__setattr__(body, field_name, value)
    return body


def test_serialize_actual_order_body_for_signing_is_stable_json() -> None:
    body = _body()

    serialized = serialize_actual_order_body_for_signing(body)
    same = serialize_actual_order_body_for_signing(body)

    assert serialized == same
    assert serialized == (
        '{"executionType":"MARKET","settleType":"OPEN","side":"BUY",'
        '"size":100,"symbol":"USD_JPY","timeInForce":"FAK"}'
    )


def test_actual_headers_signature_bundle_builds_redacted_summary() -> None:
    body = _body()
    bundle = _bundle(actual_order_body=body)
    same = _bundle(actual_order_body=body)
    body_serialization = serialize_actual_order_body_for_signing(body)

    assert isinstance(bundle, ActualHeadersSignatureBundle)
    assert bundle.bundle_id == same.bundle_id
    assert bundle.bundle_id == make_actual_headers_signature_bundle_id(
        actual_order_body_id=body.actual_order_body_id,
        verification_run_id=body.verification_run_id,
        timestamp=DUMMY_TIMESTAMP,
        method=ORDER_CREATE_METHOD,
        path=ORDER_CREATE_PATH,
        body_serialization=body_serialization,
    )
    assert bundle.actual_order_body_id == body.actual_order_body_id
    assert bundle.verification_run_id == body.verification_run_id
    assert bundle.headers_created is True
    assert bundle.signature_created is True
    assert bundle.hmac_used is True
    assert bundle.http_post_enabled is False
    assert bundle.raw_headers_saved is False
    assert bundle.raw_signature_saved is False
    assert bundle.raw_request_saved is False
    assert bundle.raw_response_saved is False
    assert bundle.credential_values_logged is False
    assert bundle.api_key_value_exposed is False
    assert bundle.api_secret_value_exposed is False
    assert bundle.signature_value_exposed is False
    assert bundle.header_names_summary == HEADER_NAMES_SUMMARY
    assert bundle.signature_algorithm_summary == SIGNATURE_ALGORITHM_SUMMARY
    assert bundle.body_serialization_summary == BODY_SERIALIZATION_SUMMARY
    assert bundle.bundle_passed is True
    assert bundle.fail_reasons == ()


def test_actual_headers_signature_bundle_uses_hmac_without_public_signature() -> None:
    body = _body()
    bundle = _bundle(actual_order_body=body)
    material = _get_sensitive_signed_headers(bundle)

    assert material is not None
    assert material.has_required_headers()
    assert material.matches_body_serialization(serialize_actual_order_body_for_signing(body))
    assert material.verify_signature(
        api_secret=DUMMY_API_SECRET,
        timestamp=DUMMY_TIMESTAMP,
        method=ORDER_CREATE_METHOD,
        path=ORDER_CREATE_PATH,
        body_serialization=serialize_actual_order_body_for_signing(body),
    )
    assert not material.verify_signature(
        api_secret="wrong_dummy_api_secret",
        timestamp=DUMMY_TIMESTAMP,
        method=ORDER_CREATE_METHOD,
        path=ORDER_CREATE_PATH,
        body_serialization=serialize_actual_order_body_for_signing(body),
    )


def test_actual_headers_signature_bundle_does_not_leak_sensitive_values() -> None:
    bundle = _bundle()
    public_views = (
        repr(bundle),
        str(bundle),
        repr(asdict(bundle)),
        str(asdict(bundle)),
        repr(bundle.header_names_summary),
        bundle.signature_algorithm_summary,
        bundle.body_serialization_summary,
    )
    material = _get_sensitive_signed_headers(bundle)

    assert material is not None
    assert repr(material) == "_SensitiveSignedHeaders(<redacted>)"
    assert str(material) == "_SensitiveSignedHeaders(<redacted>)"
    for view in public_views:
        assert DUMMY_API_KEY not in view
        assert DUMMY_API_SECRET not in view
        assert "wrong_dummy_api_secret" not in view
        assert "USD_JPY" not in bundle.body_serialization_summary
        assert "BUY" not in bundle.body_serialization_summary
    assert set(asdict(bundle)) == EXPECTED_BUNDLE_FIELDS
    assert {field.name for field in fields(ActualHeadersSignatureBundle)} == (
        EXPECTED_BUNDLE_FIELDS
    )
    assert set(asdict(bundle)).isdisjoint(BLOCKED_PUBLIC_FIELDS)
    assert all(not hasattr(bundle, field_name) for field_name in BLOCKED_PUBLIC_FIELDS)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"api_key": ""},
        {"api_secret": ""},
        {"timestamp": ""},
        {"method": "GET"},
        {"path": "/private/v1/activeOrders"},
        {"http_post_enabled": True},
        {"raw_headers_saved": True},
        {"raw_signature_saved": True},
        {"raw_request_saved": True},
        {"raw_response_saved": True},
        {"credential_values_logged": True},
    ],
)
def test_actual_headers_signature_bundle_rejects_unsafe_inputs(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationActualHeadersSignatureError):
        _bundle(**kwargs)


def test_actual_headers_signature_bundle_rejects_multiple_unsafe_flags() -> None:
    with pytest.raises(LiveVerificationActualHeadersSignatureError) as excinfo:
        _bundle(
            http_post_enabled=True,
            raw_headers_saved=True,
            raw_signature_saved=True,
            raw_request_saved=True,
            raw_response_saved=True,
            credential_values_logged=True,
        )

    message = str(excinfo.value)
    assert "http_post_enabled" in message
    assert "raw_headers_saved" in message
    assert "raw_signature_saved" in message
    assert "raw_request_saved" in message
    assert "raw_response_saved" in message
    assert "credential_values_logged" in message


@pytest.mark.parametrize(
    "body_overrides",
    [
        {"body_created": False},
        {"http_post_enabled": True},
        {"headers_created": True},
        {"signature_created": True},
        {"raw_request_saved": True},
        {"raw_response_saved": True},
        {"credential_values_logged": True},
        {"real_order_attempted": True},
        {"symbol": "EUR_USD"},
        {"size": 101},
        {"executionType": "LIMIT"},
        {"timeInForce": "FOK"},
        {"settleType": "CLOSE"},
    ],
)
def test_actual_headers_signature_bundle_rejects_unsafe_body(
    body_overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationActualHeadersSignatureError):
        _bundle(actual_order_body=_unchecked_body(**body_overrides))
