"""Official settlement one-shot sender no-POST implementation for runtime injection.

Mirror of ``gmo_live_actual_entry_sender`` for the dedicated official
settlement route. The sender is intentionally narrow:

- settlement-only plan friendly shape (method/path/body only),
- at most one send attempt,
- deterministic mapping of outcomes to sanitized categories,
- no raw request/response, raw IDs/values, credentials, signatures, or
  headers are exposed outside this boundary.

This step is no-POST: no real credential value read, no real network
execution, and no `.env` access are performed here. A real HTTP client, a
sealed credential, and a real timestamp factory are injected only at the
reviewed actual settlement execution step.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, runtime_checkable

from app.private_api.auth import build_auth_headers
from app.services.gmo_live_official_settlement_execution_boundary import (
    GmoOfficialSettlementExecutionBoundaryError,
    OfficialSettlementOneShotSender,
    SettlementPostSafeOutcome,
)

_SENDER_REPR = "GmoOfficialSettlementOneShotHttpSender(<sanitized>)"


@runtime_checkable
class OfficialSettlementSenderHttpClient(Protocol):
    """Minimal injected protocol for a settlement-sender HTTP client."""

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str],
        body_json: str,
    ) -> object:
        """Issue exactly one request for this sender boundary."""


@runtime_checkable
class SealedCredentialForOfficialSettlement(Protocol):
    """Protocol for runtime-injected sealed credential holder."""

    def unseal_for_official_settlement(self) -> tuple[str, str]:
        """Return ``(api_key, api_secret)`` for internal signing only."""


class SignedSettlementRequestFactory:
    """Request factory for signed settlement-only request payloads."""

    @staticmethod
    def build_headers(
        *,
        api_key: str,
        api_secret: str,
        method: str,
        path: str,
        body_json: str,
        timestamp: str,
    ) -> dict[str, str]:
        return build_auth_headers(
            api_key=api_key,
            api_secret=api_secret,
            timestamp=timestamp,
            method=method,
            path=path,
            body=body_json,
        )


def _safe_timestamp() -> str:
    # Inert no-POST default. "0" can never be a broker-valid API timestamp,
    # so a sender left with this default cannot produce an acceptable signed
    # request. A real millisecond-epoch timestamp factory is injected only at
    # the reviewed actual settlement execution step, alongside the real HTTP
    # client and the sealed credential.
    return "0"


def map_settlement_post_exception_to_safe_outcome(
    *,
    error: Exception,
) -> SettlementPostSafeOutcome:
    """Map transport or construction exceptions to sanitized categories."""

    if isinstance(error, TimeoutError):
        return SettlementPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    if isinstance(error, OSError):
        return SettlementPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED
    if isinstance(error, ValueError):
        return SettlementPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED
    return SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED


def map_settlement_post_response_to_safe_outcome(
    *,
    response: object,
) -> SettlementPostSafeOutcome:
    """Map HTTP-like response to sanitized outcomes without storing body data."""

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int):
        return SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED
    if status_code == 200:
        return SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
    if status_code == 409:
        return SettlementPostSafeOutcome.RESULT_REJECTED_SANITIZED
    if status_code == 408:
        return SettlementPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    if 400 <= status_code < 500:
        return SettlementPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED
    if 500 <= status_code < 600:
        return SettlementPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED
    return SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED


class GmoOfficialSettlementOneShotHttpSender:
    """Concrete injected sender for the official settlement execution boundary.

    - one send attempt only,
    - no raw request/response or secret material stored or returned.
    """

    def __init__(
        self,
        *,
        http_client: OfficialSettlementSenderHttpClient,
        sealed_credential: SealedCredentialForOfficialSettlement,
        request_factory: SignedSettlementRequestFactory | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        self.http_client = http_client
        self.sealed_credential = sealed_credential
        self.request_factory = request_factory or SignedSettlementRequestFactory()
        # Defaults to the inert "0" factory: without an explicitly injected
        # real timestamp factory this sender cannot sign a broker-valid
        # request, keeping the default state fail-closed.
        self.timestamp_factory = timestamp_factory or _safe_timestamp
        self.send_attempt_count = 0

    def __repr__(self) -> str:
        return _SENDER_REPR

    def __str__(self) -> str:
        return _SENDER_REPR

    def send_settlement_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> SettlementPostSafeOutcome:
        if self.send_attempt_count:
            raise GmoOfficialSettlementExecutionBoundaryError(
                "official settlement sender supports one attempt only: retry/"
                "repost/second attempt is forbidden"
            )

        self.send_attempt_count += 1
        try:
            response = self._attempt_send_once(
                method=method,
                path=path,
                body_json=body_json,
            )
        except Exception as error:  # noqa: BLE001
            return map_settlement_post_exception_to_safe_outcome(error=error)

        return map_settlement_post_response_to_safe_outcome(response=response)

    def _attempt_send_once(self, *, method: str, path: str, body_json: str) -> object:
        headers = self._build_headers(method=method, path=path, body_json=body_json)
        return self.http_client.request(
            method=method,
            path=path,
            headers=headers,
            body_json=body_json,
        )

    def _build_headers(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> dict[str, str]:
        api_key, api_secret = self.sealed_credential.unseal_for_official_settlement()
        return self.request_factory.build_headers(
            api_key=api_key,
            api_secret=api_secret,
            method=method,
            path=path,
            body_json=body_json,
            timestamp=self.timestamp_factory(),
        )


class GmoOfficialSettlementOneShotHttpSenderAsOfficialSettlementOneShotSender(
    GmoOfficialSettlementOneShotHttpSender,
    OfficialSettlementOneShotSender,
):
    """Alias class for protocol clarity at call sites."""
