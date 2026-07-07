"""Actual entry one-shot sender no-POST implementation for runtime injection.

This module defines the concrete sender boundary used by the reviewed actual-entry
call site. The sender is intentionally narrow:

- entry-only plan friendly shape (method/path/body only),
- at most one send attempt,
- deterministic mapping of outcomes to sanitized categories,
- no raw request/response, raw IDs/values, credentials, signatures, or headers are
  exposed outside this boundary.

This step is no-POST: no real credential value read, no real network execution,
and no `.env` access are performed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from app.private_api.auth import build_auth_headers
from app.services.gmo_live_actual_entry_execution_boundary import (
    ActualEntryExecutionBoundaryError,
    ActualEntryOneShotSender,
    EntryPostSafeOutcome,
)

_SENDER_REPR = "GmoActualEntryOneShotHttpSender(<sanitized>)"


@runtime_checkable
class ActualEntrySenderHttpClient(Protocol):
    """Minimal injected protocol for an actual-sender HTTP client."""

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
class SealedCredentialForActualEntry(Protocol):
    """Protocol for runtime-injected sealed credential holder."""

    def unseal_for_actual_entry(self) -> tuple[str, str]:
        """Return ``(api_key, api_secret)`` for internal signing only."""


class SignedEntryRequestFactory:
    """Request factory for signed entry-only request payloads."""

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
    # No realtime clock is needed in this no-POST step.
    return "0"


def map_entry_post_exception_to_safe_outcome(
    *,
    error: Exception,
) -> EntryPostSafeOutcome:
    """Map transport or construction exceptions to sanitized categories."""

    if isinstance(error, TimeoutError):
        return EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    if isinstance(error, OSError):
        return EntryPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED
    if isinstance(error, ValueError):
        return EntryPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED
    return EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED


def map_entry_post_response_to_safe_outcome(
    *,
    response: object,
) -> EntryPostSafeOutcome:
    """Map HTTP-like response to sanitized outcomes without storing body data."""

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int):
        return EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED
    if status_code == 200:
        return EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
    if status_code == 409:
        return EntryPostSafeOutcome.RESULT_REJECTED_SANITIZED
    if status_code == 408:
        return EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED
    if 400 <= status_code < 500:
        return EntryPostSafeOutcome.RESULT_CLIENT_ERROR_SANITIZED
    if 500 <= status_code < 600:
        return EntryPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED
    return EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED


class GmoActualEntryOneShotHttpSender:
    """Concrete injected sender used by actual entry execution boundary.

    - one send attempt only,
    - no raw request/response or secret material stored or returned.
    """

    def __init__(
        self,
        *,
        http_client: ActualEntrySenderHttpClient,
        sealed_credential: SealedCredentialForActualEntry,
        request_factory: SignedEntryRequestFactory | None = None,
    ) -> None:
        self.http_client = http_client
        self.sealed_credential = sealed_credential
        self.request_factory = request_factory or SignedEntryRequestFactory()
        self.send_attempt_count = 0

    def __repr__(self) -> str:
        return _SENDER_REPR

    def __str__(self) -> str:
        return _SENDER_REPR

    def send_entry_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> EntryPostSafeOutcome:
        if self.send_attempt_count:
            raise ActualEntryExecutionBoundaryError(
                "actual entry sender supports one attempt only: retry/repost/"
                "second attempt is forbidden"
            )

        self.send_attempt_count += 1
        try:
            response = self._attempt_send_once(
                method=method,
                path=path,
                body_json=body_json,
            )
        except Exception as error:  # noqa: BLE001
            return map_entry_post_exception_to_safe_outcome(error=error)

        return map_entry_post_response_to_safe_outcome(response=response)

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
        api_key, api_secret = self.sealed_credential.unseal_for_actual_entry()
        return self.request_factory.build_headers(
            api_key=api_key,
            api_secret=api_secret,
            method=method,
            path=path,
            body_json=body_json,
            timestamp=_safe_timestamp(),
        )


class GmoActualEntryOneShotHttpSenderAsActualEntryOneShotSender(
    GmoActualEntryOneShotHttpSender,
    ActualEntryOneShotSender,
):
    """Alias class for protocol clarity at call sites."""
