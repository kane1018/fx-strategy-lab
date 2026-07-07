"""No-POST sender coverage for actual entry one-shot injection boundary.

These tests verify the concrete sender that is intended for actual execution
injection:

- one attempt only,
- no retry/repost/second POST path,
- exception-safe mapping to sanitized categories,
- signature/header creation remains internal only,
- fake credential / fake HTTP client usage only in this step.
"""

from __future__ import annotations

import pathlib

import pytest

from app.private_api.order_builders import build_gmo_fx_entry_request_plan
from app.services.gmo_live_actual_entry_execution_boundary import (
    ActualEntryExecutionBoundaryError,
    ActualEntryOperatorCurrentTurnInput,
    EntryPostSafeOutcome,
    build_actual_entry_execution_activation,
    send_actual_entry_post_once,
)
from app.services.gmo_live_actual_entry_sender import (
    GmoActualEntryOneShotHttpSender,
    map_entry_post_exception_to_safe_outcome,
    map_entry_post_response_to_safe_outcome,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_actual_entry_sender.py"
)


class _FakeHttpClient:
    def __init__(self, response: object | None = None, *, raise_error: Exception | None = None):
        self.response = response
        self.raise_error = raise_error
        self.call_count = 0
        self.requests: list[tuple[str, str, object, object]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body_json: str,
    ) -> object:
        self.call_count += 1
        self.requests.append((method, path, headers, body_json))
        if self.raise_error is not None:
            raise self.raise_error
        if self.response is None:
            raise AssertionError("no response configured")
        return self.response


class _FakeResponse:
    def __init__(self, status_code: int | str) -> None:
        self.status_code = status_code


def test_default_timestamp_factory_is_inert_zero() -> None:
    # Without an explicitly injected real timestamp factory the sender signs
    # with "0", which can never be a broker-valid API timestamp: the default
    # sender state stays fail-closed for actual execution.
    client = _FakeHttpClient(response=_FakeResponse(200))
    sender = GmoActualEntryOneShotHttpSender(
        http_client=client,
        sealed_credential=_FakeSealedCredential(),
    )
    sender.send_entry_once_sanitized(
        method="POST", path="/private/v1/order", body_json="{}"
    )
    _, _, headers, _ = client.requests[0]
    assert headers["API-TIMESTAMP"] == "0"


def test_injected_timestamp_factory_is_used_for_signing() -> None:
    client = _FakeHttpClient(response=_FakeResponse(200))
    sender = GmoActualEntryOneShotHttpSender(
        http_client=client,
        sealed_credential=_FakeSealedCredential(),
        timestamp_factory=lambda: "1234567890123",
    )
    sender.send_entry_once_sanitized(
        method="POST", path="/private/v1/order", body_json="{}"
    )
    _, _, headers, _ = client.requests[0]
    assert headers["API-TIMESTAMP"] == "1234567890123"


class _FakeSealedCredential:
    def __init__(self, api_key: str = "test-key", api_secret: str = "test-secret") -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def unseal_for_actual_entry(self) -> tuple[str, str]:
        return self.api_key, self.api_secret


def _granted_activation() -> object:
    base = dict(
        operator_input=ActualEntryOperatorCurrentTurnInput(
            signal_type_safe_label="ENTRY_BUY",
            exact_confirmation="CONFIRM_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST_NO_SETTLEMENT",
            readiness="OPERATOR_READY_FOR_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST",
            understands_risk="OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK",
        ),
        final_preflight_ready=True,
        fresh_runtime_gate_ready=True,
        written_signoff_recorded=True,
        paper_evidence_confirmed=True,
        anomaly_evidence_confirmed=True,
        one_use_entry_permit_usable=True,
        hard_guard_controlled_supply_default_deny_present=True,
        sanitized_preview_ready=True,
        credential_presence_safe_boolean=True,
        entry_request_plan_bound_safe=True,
        market_open_safe_label_confirmed=True,
        ticker_fresh_safe_label_confirmed=True,
        spread_within_limit_safe_label_confirmed=True,
    )
    return build_actual_entry_execution_activation(**base)  # type: ignore[arg-type]


def _entry_plan():
    return build_gmo_fx_entry_request_plan(symbol="USD_JPY", side="BUY", size="1")


def test_map_response_to_sanitized_outcome_covers_expected_statuses() -> None:
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse(200))
        is EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
    )
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse(409))
        is EntryPostSafeOutcome.RESULT_REJECTED_SANITIZED
    )
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse(408))
        is EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    )
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse(401))
        is EntryPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED
    )
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse(503))
        is EntryPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED
    )
    assert (
        map_entry_post_response_to_safe_outcome(response=_FakeResponse("x"))
        is EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED),
        (OSError("network"), EntryPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED),
        (ValueError("payload"), EntryPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED),
        (RuntimeError("other"), EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED),
    ],
)
def test_map_exception_to_sanitized_outcome(
    error: Exception, expected: EntryPostSafeOutcome
) -> None:
    assert map_entry_post_exception_to_safe_outcome(error=error) is expected


def test_sender_class_construction_and_repr_are_sanitized() -> None:
    sender = GmoActualEntryOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeSealedCredential(api_key="secret-key", api_secret="secret-secret"),
    )
    assert repr(sender) == "GmoActualEntryOneShotHttpSender(<sanitized>)"
    assert str(sender) == "GmoActualEntryOneShotHttpSender(<sanitized>)"
    assert "secret-key" not in repr(sender)
    assert "secret-secret" not in repr(sender)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED),
        (409, EntryPostSafeOutcome.RESULT_REJECTED_SANITIZED),
        (408, EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED),
        (400, EntryPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED),
        (500, EntryPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED),
    ],
)
def test_sender_call_returns_only_sanitized_category(
    status_code: int, expected: EntryPostSafeOutcome
) -> None:
    sender = GmoActualEntryOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(status_code)),
        sealed_credential=_FakeSealedCredential(),
    )
    assert sender.send_entry_once_sanitized(
        method="POST",
        path="/private/v1/order",
        body_json='{"symbol":"USD_JPY","side":"BUY","size":"1","executionType":"MARKET"}',
    ) is expected
    assert sender.send_attempt_count == 1


def test_sender_one_shot_no_retry_and_no_second_send_route() -> None:
    sender = GmoActualEntryOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeSealedCredential(),
    )
    sender.send_entry_once_sanitized(
        method="POST", path="/private/v1/order", body_json="{}"
    )
    with pytest.raises(ActualEntryExecutionBoundaryError):
        # We only assert failure behavior; no second send may be attempted.
        sender.send_entry_once_sanitized(
            method="POST", path="/private/v1/order", body_json="{}"
        )

def test_sender_exception_paths_do_not_retry() -> None:
    sender = GmoActualEntryOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200), raise_error=TimeoutError()),
        sealed_credential=_FakeSealedCredential(),
    )
    assert sender.send_entry_once_sanitized(
        method="POST",
        path="/private/v1/order",
        body_json="{}",
    ) is EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    assert sender.send_attempt_count == 1


def test_no_post_fake_http_client_reaches_execution_boundary_once() -> None:
    sender = GmoActualEntryOneShotHttpSender(
        http_client=_FakeHttpClient(response=_FakeResponse(200)),
        sealed_credential=_FakeSealedCredential(),
    )
    result = send_actual_entry_post_once(
        activation=_granted_activation(),
        request_plan=_entry_plan(),
        sender=sender,
    )
    assert result.outcome_category is EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
    assert result.post_attempted is True
    assert result.post_attempt_count == 1
    assert result.retry_performed is False
    assert result.repost_performed is False
    assert result.second_post_performed is False
    assert result.raw_response_exposed is False
    assert result.raw_ids_exposed is False
    assert result.raw_price_or_size_values_exposed is False
    assert result.credential_value_exposed is False


def test_sender_source_scan_blocks_forbidden_paths() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "live_order_once" not in text
    assert "closeOrder" not in text
    assert "settlePosition" not in text
    assert "httpx" not in text
