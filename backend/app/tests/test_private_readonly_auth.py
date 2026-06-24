import hashlib
import hmac

from app.private_api.auth import build_auth_headers, create_signature


def test_create_signature_for_get_uses_timestamp_method_and_path() -> None:
    timestamp = "1700000000000"
    api_secret = "<API_SECRET>"
    expected = hmac.new(
        api_secret.encode("utf-8"),
        b"1700000000000GET/private/v1/account/assets",
        hashlib.sha256,
    ).hexdigest()

    assert (
        create_signature(
            api_secret=api_secret,
            timestamp=timestamp,
            method="GET",
            path="/private/v1/account/assets",
        )
        == expected
    )


def test_create_signature_includes_body_when_provided() -> None:
    timestamp = "1700000000000"
    api_secret = "<API_SECRET>"
    body = '{"symbol":"USD_JPY"}'
    expected = hmac.new(
        api_secret.encode("utf-8"),
        f"{timestamp}POST/private/v1/example{body}".encode(),
        hashlib.sha256,
    ).hexdigest()

    assert (
        create_signature(
            api_secret=api_secret,
            timestamp=timestamp,
            method="post",
            path="/private/v1/example",
            body=body,
        )
        == expected
    )


def test_build_auth_headers_contains_required_keys() -> None:
    headers = build_auth_headers(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp="1700000000000",
        method="GET",
        path="/private/v1/account/assets",
    )

    assert set(headers) == {"API-KEY", "API-TIMESTAMP", "API-SIGN"}
    assert headers["API-KEY"] == "<API_KEY>"
    assert headers["API-TIMESTAMP"] == "1700000000000"
    assert len(headers["API-SIGN"]) == 64
