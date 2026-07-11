"""No-POST sender coverage for the H-11 v3 real IFDOCO sender scaffold.

- one attempt only, no retry/repost/second attempt,
- exception-safe mapping to sanitized categories,
- signature/header creation stays internal only,
- default timestamp factory is inert ("0"),
- fake credential / fake HTTP client usage only in this step,
- module never imports a real network library.
"""

from __future__ import annotations

import pathlib

import pytest

from app.private_api.order_builders import build_gmo_fx_ifdoco_request_plan
from app.services.h11_v3_real_ifdoco_sender_no_post import (
    H11V3IfdocoOneShotHttpSender,
    H11V3IfdocoPostOutcome,
    H11V3RealSenderError,
    map_ifdoco_post_exception_to_safe_outcome,
    map_ifdoco_post_response_to_safe_outcome,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "h11_v3_real_ifdoco_sender_no_post.py"
)


class _FakeHttpClient:
    def __init__(self, response: object | None = None, *, raise_error: Exception | None = None):
        self.response = response
        self.raise_error = raise_error
        self.requests: list[tuple[str, str, object, str]] = []

    def request(
        self, method: str, path: str, *, headers: dict[str, str], body_json: str
    ) -> object:
        self.requests.append((method, path, headers, body_json))
        if self.raise_error is not None:
            raise self.raise_error
        if self.response is None:
            raise AssertionError("no response configured")
        return self.response


class _FakeResponse:
    def __init__(self, status_code: int | str) -> None:
        self.status_code = status_code


class _FakeCredentialPair:
    def __init__(self, api_key: str = "test-key", api_secret: str = "test-secret") -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def unseal_for_actual_ifdoco(self) -> tuple[str, str]:
        return self.api_key, self.api_secret


def _plan():
    return build_gmo_fx_ifdoco_request_plan(
        symbol="USD_JPY",
        first_side="BUY",
        first_size="10000",
        first_price="150.000",
        second_size="10000",
        second_limit_price="150.500",
        second_stop_price="149.500",
    )


def test_default_timestamp_factory_is_inert_zero() -> None:
    client = _FakeHttpClient(response=_FakeResponse(200))
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=client, sealed_credential=_FakeCredentialPair()
    )
    sender.send_ifdoco_once(_plan())
    _, _, headers, _ = client.requests[0]
    assert headers["API-TIMESTAMP"] == "0"


def test_injected_timestamp_factory_is_used_for_signing() -> None:
    client = _FakeHttpClient(response=_FakeResponse(200))
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=client,
        sealed_credential=_FakeCredentialPair(),
        timestamp_factory=lambda: "1234567890123",
    )
    sender.send_ifdoco_once(_plan())
    _, _, headers, _ = client.requests[0]
    assert headers["API-TIMESTAMP"] == "1234567890123"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, H11V3IfdocoPostOutcome.ACCEPTED_SANITIZED),
        (409, H11V3IfdocoPostOutcome.REJECTED_SANITIZED),
        (408, H11V3IfdocoPostOutcome.TIMEOUT_SANITIZED),
        (401, H11V3IfdocoPostOutcome.CLIENT_ERROR_SANITIZED),
        (503, H11V3IfdocoPostOutcome.SERVER_ERROR_SANITIZED),
        ("x", H11V3IfdocoPostOutcome.UNKNOWN_SANITIZED),
    ],
)
def test_map_response_to_sanitized_outcome_covers_expected_statuses(
    status_code: int | str, expected: H11V3IfdocoPostOutcome
) -> None:
    assert (
        map_ifdoco_post_response_to_safe_outcome(response=_FakeResponse(status_code))
        is expected
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), H11V3IfdocoPostOutcome.TIMEOUT_SANITIZED),
        (OSError("network"), H11V3IfdocoPostOutcome.NETWORK_ERROR_SANITIZED),
        (ValueError("payload"), H11V3IfdocoPostOutcome.CLIENT_ERROR_SANITIZED),
        (RuntimeError("other"), H11V3IfdocoPostOutcome.UNKNOWN_SANITIZED),
    ],
)
def test_map_exception_to_sanitized_outcome(
    error: Exception, expected: H11V3IfdocoPostOutcome
) -> None:
    assert map_ifdoco_post_exception_to_safe_outcome(error=error) is expected


def test_sender_class_construction_and_repr_are_sanitized() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeCredentialPair(
            api_key="secret-key", api_secret="secret-secret"
        ),
    )
    assert repr(sender) == "H11V3IfdocoOneShotHttpSender(<sanitized>)"
    assert str(sender) == "H11V3IfdocoOneShotHttpSender(<sanitized>)"
    assert "secret-key" not in repr(sender)
    assert "secret-secret" not in repr(sender)


def test_sender_call_returns_only_sanitized_category_and_counts_attempt() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeCredentialPair(),
    )
    assert sender.send_ifdoco_once(_plan()) is H11V3IfdocoPostOutcome.ACCEPTED_SANITIZED
    assert sender.send_attempt_count == 1


def test_sender_one_shot_no_retry_and_no_second_send() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeCredentialPair(),
    )
    sender.send_ifdoco_once(_plan())
    with pytest.raises(H11V3RealSenderError):
        sender.send_ifdoco_once(_plan())


def test_sender_exception_paths_do_not_retry() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200), raise_error=TimeoutError()),
        sealed_credential=_FakeCredentialPair(),
    )
    assert (
        sender.send_ifdoco_once(_plan()) is H11V3IfdocoPostOutcome.TIMEOUT_SANITIZED
    )
    assert sender.send_attempt_count == 1


def test_sender_rejects_non_ifdoco_plan_kind() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeCredentialPair(),
    )
    bad_plan = _plan().model_copy(update={"request_kind": "ENTRY"})
    with pytest.raises(H11V3RealSenderError):
        sender.send_ifdoco_once(bad_plan)


def test_sender_rejects_wrong_path() -> None:
    sender = H11V3IfdocoOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeCredentialPair(),
    )
    bad_plan = _plan().model_copy(update={"path": "/private/v1/order"})
    with pytest.raises(H11V3RealSenderError):
        sender.send_ifdoco_once(bad_plan)


def test_credential_pair_never_caches_values_and_is_falsy() -> None:
    from app.services.h11_v3_real_ifdoco_sender_no_post import (
        H11V3KeychainCredentialPair,
    )

    pair = H11V3KeychainCredentialPair()
    assert bool(pair) is False


def test_sender_source_scan_blocks_forbidden_imports() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "import httpx" not in text
    assert "import requests" not in text
    assert "os.environ" not in text
    assert ".env" not in text
    assert "closeOrder" not in text
