import pytest

from app.private_api.errors import (
    PrivateApiConnectionDisabledError,
    PrivateApiResponseError,
)
from app.private_api.readonly_client import (
    GET_ACCOUNT_ASSETS,
    PrivateReadonlyClient,
    ReadOnlyRequest,
)
from app.private_api.schemas import PrivateApiError, private_api_error_from_payload


def test_private_api_error_from_payload_keeps_only_sanitized_fields() -> None:
    error = private_api_error_from_payload(
        {
            "status": 1,
            "messages": [
                {
                    "message_code": "ERR-001",
                    "message_string": "mocked error",
                    "API-KEY": "<API_KEY>",
                }
            ],
            "API-SIGN": "<SIGNATURE>",
            "API-TIMESTAMP": "1700000000000",
            "api_secret": "<API_SECRET>",
            "authorization": "Bearer sample",
        }
    )

    dumped = error.model_dump()
    assert dumped == {"code": "ERR-001", "message": "mocked error", "status": 1}
    assert "API-KEY" not in dumped
    assert "API-SIGN" not in dumped
    assert "API-TIMESTAMP" not in dumped
    assert "api_secret" not in dumped
    assert "authorization" not in dumped


def test_client_raises_response_error_with_sanitized_api_error() -> None:
    calls: list[ReadOnlyRequest] = []

    def provider(request: ReadOnlyRequest):
        calls.append(request)
        return {
            "status": 1,
            "messages": [{"message_code": "ERR-001", "message_string": "mocked error"}],
            "API-SIGN": "<SIGNATURE>",
        }

    client = PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
        response_provider=provider,
    )

    with pytest.raises(PrivateApiResponseError) as raised:
        client.get_account_assets()

    assert len(calls) == 1
    assert isinstance(raised.value.api_error, PrivateApiError)
    assert raised.value.api_error.code == "ERR-001"
    assert raised.value.api_error.message == "mocked error"
    assert raised.value.api_error.status == 1


def test_error_response_does_not_retry_after_mocked_provider_failure() -> None:
    calls: list[ReadOnlyRequest] = []

    def provider(request: ReadOnlyRequest):
        calls.append(request)
        return {"status": 7, "messages": [{"message_code": "ERR-RETRY"}]}

    client = PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
        response_provider=provider,
    )

    with pytest.raises(PrivateApiResponseError):
        client.get_account_assets()

    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].path == GET_ACCOUNT_ASSETS


def test_provider_missing_still_fails_closed_before_connection() -> None:
    client = PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
    )

    with pytest.raises(PrivateApiConnectionDisabledError):
        client.get_account_assets()
