"""No-POST tests for the official settlement one-shot sender.

Synthetic values only. No network, no real credentials, no `.env`.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

import pytest

from app.services import gmo_live_official_settlement_sender as module
from app.services.gmo_live_official_settlement_execution_boundary import (
    GmoOfficialSettlementExecutionBoundaryError,
    OfficialSettlementOneShotSender,
    SettlementPostSafeOutcome,
)
from app.services.gmo_live_official_settlement_sender import (
    GmoOfficialSettlementOneShotHttpSender,
    map_settlement_post_exception_to_safe_outcome,
    map_settlement_post_response_to_safe_outcome,
)

SYNTHETIC_KEY = "synthetic-test-key"
SYNTHETIC_SECRET = "synthetic-test-secret"


@dataclass
class _FakeResponse:
    status_code: object = 200


@dataclass
class _RecordingFakeHttpClient:
    response: object = field(default_factory=_FakeResponse)
    call_count: int = 0
    raise_error: Exception | None = None

    def request(self, method, path, *, headers, body_json):
        self.call_count += 1
        if self.raise_error is not None:
            raise self.raise_error
        return self.response


@dataclass(frozen=True)
class _FakeSealedCredential:
    def unseal_for_official_settlement(self) -> tuple[str, str]:
        return (SYNTHETIC_KEY, SYNTHETIC_SECRET)


def _sender(client=None) -> GmoOfficialSettlementOneShotHttpSender:
    return GmoOfficialSettlementOneShotHttpSender(
        http_client=client or _RecordingFakeHttpClient(),
        sealed_credential=_FakeSealedCredential(),
    )


class TestResponseMapping:
    @pytest.mark.parametrize(
        ("status_code", "outcome"),
        [
            (200, SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED),
            (409, SettlementPostSafeOutcome.RESULT_REJECTED_SANITIZED),
            (408, SettlementPostSafeOutcome.RESULT_TIMEOUT_SANITIZED),
            (400, SettlementPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED),
            (404, SettlementPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED),
            (500, SettlementPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED),
            (503, SettlementPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED),
            (302, SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED),
            ("weird", SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED),
            (None, SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED),
        ],
    )
    def test_status_codes_map_to_sanitized_categories(
        self, status_code, outcome
    ) -> None:
        assert (
            map_settlement_post_response_to_safe_outcome(
                response=_FakeResponse(status_code=status_code)
            )
            is outcome
        )


class TestExceptionMapping:
    @pytest.mark.parametrize(
        ("error", "outcome"),
        [
            (TimeoutError(), SettlementPostSafeOutcome.RESULT_TIMEOUT_SANITIZED),
            (OSError(), SettlementPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED),
            (ValueError(), SettlementPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED),
            (RuntimeError(), SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED),
        ],
    )
    def test_exceptions_map_to_sanitized_categories(self, error, outcome) -> None:
        assert (
            map_settlement_post_exception_to_safe_outcome(error=error) is outcome
        )


class TestOneShotSender:
    def test_satisfies_boundary_sender_protocol(self) -> None:
        assert isinstance(_sender(), OfficialSettlementOneShotSender)

    def test_sends_exactly_once_and_maps_response(self) -> None:
        client = _RecordingFakeHttpClient(response=_FakeResponse(status_code=200))
        sender = _sender(client)
        outcome = sender.send_settlement_once_sanitized(
            method="POST", path="/private/v1/closeOrder", body_json="{}"
        )
        assert client.call_count == 1
        assert outcome is SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED

    def test_second_attempt_is_structurally_forbidden(self) -> None:
        sender = _sender()
        sender.send_settlement_once_sanitized(
            method="POST", path="/private/v1/closeOrder", body_json="{}"
        )
        with pytest.raises(GmoOfficialSettlementExecutionBoundaryError):
            sender.send_settlement_once_sanitized(
                method="POST", path="/private/v1/closeOrder", body_json="{}"
            )

    def test_transport_exception_returns_sanitized_category_no_retry(self) -> None:
        client = _RecordingFakeHttpClient(raise_error=OSError("socket detail"))
        sender = _sender(client)
        outcome = sender.send_settlement_once_sanitized(
            method="POST", path="/private/v1/closeOrder", body_json="{}"
        )
        assert client.call_count == 1
        assert outcome is SettlementPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED

    def test_default_timestamp_factory_is_inert(self) -> None:
        assert _sender().timestamp_factory() == "0"

    def test_repr_never_contains_secret_material(self) -> None:
        sender = _sender()
        for rendered in (repr(sender), str(sender)):
            assert SYNTHETIC_KEY not in rendered
            assert SYNTHETIC_SECRET not in rendered

    def test_headers_are_built_from_sealed_credential_internally(self) -> None:
        captured: dict[str, str] = {}

        @dataclass
        class _CapturingClient:
            def request(self, method, path, *, headers, body_json):
                captured.update(headers)
                return _FakeResponse(status_code=200)

        sender = GmoOfficialSettlementOneShotHttpSender(
            http_client=_CapturingClient(),
            sealed_credential=_FakeSealedCredential(),
        )
        sender.send_settlement_once_sanitized(
            method="POST", path="/private/v1/closeOrder", body_json="{}"
        )
        # Signing happened internally; the sanitized outcome path never
        # returns these headers to a caller of the boundary.
        assert captured["API-KEY"] == SYNTHETIC_KEY
        assert "API-SIGN" in captured


class TestModuleIsolation:
    def test_module_has_no_direct_network_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
