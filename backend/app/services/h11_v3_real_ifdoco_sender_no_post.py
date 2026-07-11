"""H-11 v3 real IFDOCO sender (no-POST scaffold, structurally unbindable).

Mirrors the reviewed `gmo_live_actual_entry_sender.py` pattern: a concrete,
fully real sender implementation (real HTTP client protocol, real GMO
HMAC signing via ``app.private_api.auth``, real Keychain credential
unsealing) that nonetheless cannot execute anywhere in this build:

- The only binding class that currently exists
  (``H11V3DisabledTransportBinding`` in
  ``h11_v3_actual_transport_binding_no_post.py``) structurally refuses any
  sender whose ``fake_only`` is not ``True``; this class does not set that
  attribute at all, so it cannot satisfy that check. No call site anywhere
  in this build constructs or invokes this class with a real HTTP client.
- The default timestamp factory returns ``"0"``, an inert value that can
  never sign a broker-valid request. A real millisecond-epoch factory must
  be explicitly injected, and none is injected anywhere in this build.
- Exactly one send attempt is allowed; a second call raises.

This module performs no network access itself. Building it now (ahead of
the broker-native pending-expiry and partial-fill answers) is deliberate:
those answers affect reconcile/timeout *policy* in a future activation
step, not this transport/signing scaffold, which is independent of them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.private_api.auth import build_auth_headers
from app.private_api.order_builders import (
    GMO_FX_IFDOCO_ORDER_PATH,
    REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
    GmoFxPrivateRequestPlan,
)
from app.services.h11_v3_keychain_credential_no_post import (
    H11V3KeychainError,
    read_h11_v3_keychain_secret,
)

_SENDER_REPR = "H11V3IfdocoOneShotHttpSender(<sanitized>)"

H11_V3_API_KEY_SERVICE = "h11_v3_gmo_fx_api_key"
H11_V3_API_SECRET_SERVICE = "h11_v3_gmo_fx_api_secret"
H11_V3_CREDENTIAL_ACCOUNT = "h11_v3"


class H11V3RealSenderError(RuntimeError):
    """Fail-closed error containing safe labels only. Never a raw value."""


class H11V3IfdocoPostOutcome(str, Enum):
    """Sanitized outcome categories. Values align with H11V3FakeOutcome so
    a future real-cycle function can map 1:1 without inventing new labels.
    """

    ACCEPTED_SANITIZED = "ACCEPTED_SANITIZED"
    REJECTED_SANITIZED = "REJECTED_SANITIZED"
    UNKNOWN_SANITIZED = "UNKNOWN_SANITIZED"
    TIMEOUT_SANITIZED = "TIMEOUT_SANITIZED"
    NETWORK_ERROR_SANITIZED = "NETWORK_ERROR_SANITIZED"
    CLIENT_ERROR_SANITIZED = "CLIENT_ERROR_SANITIZED"
    SERVER_ERROR_SANITIZED = "SERVER_ERROR_SANITIZED"


@runtime_checkable
class H11V3IfdocoHttpClient(Protocol):
    """Minimal injected protocol for a real IFDOCO HTTP client."""

    def request(
        self, method: str, path: str, *, headers: Mapping[str, str], body_json: str
    ) -> object:
        """Issue exactly one request for this sender boundary."""


@runtime_checkable
class H11V3SealedCredentialPair(Protocol):
    """Protocol for an injected credential source; never exposes raw values."""

    def unseal_for_actual_ifdoco(self) -> tuple[str, str]:
        """Return ``(api_key, api_secret)`` for internal signing only."""


@dataclass(frozen=True)
class H11V3KeychainCredentialPair:
    """Reads both GMO credential halves from macOS Keychain per call.

    Values are read fresh on each unseal call and never cached on the
    instance, minimizing how long they exist in process memory.
    """

    def unseal_for_actual_ifdoco(self) -> tuple[str, str]:
        try:
            api_key = read_h11_v3_keychain_secret(
                service=H11_V3_API_KEY_SERVICE, account=H11_V3_CREDENTIAL_ACCOUNT
            )
            api_secret = read_h11_v3_keychain_secret(
                service=H11_V3_API_SECRET_SERVICE, account=H11_V3_CREDENTIAL_ACCOUNT
            )
        except H11V3KeychainError as error:
            raise H11V3RealSenderError(
                "H-11 v3 sealed credential unavailable"
            ) from error
        return api_key.reveal_once(), api_secret.reveal_once()

    def __bool__(self) -> bool:
        return False


def _inert_timestamp() -> str:
    # Same fail-closed default as the reviewed entry sender: "0" can never
    # sign a broker-valid request. A real millisecond-epoch factory must be
    # explicitly injected, and no call site in this build injects one.
    return "0"


def map_ifdoco_post_exception_to_safe_outcome(
    *, error: Exception
) -> H11V3IfdocoPostOutcome:
    """Map transport or construction exceptions to sanitized categories."""

    if isinstance(error, TimeoutError):
        return H11V3IfdocoPostOutcome.TIMEOUT_SANITIZED
    if isinstance(error, OSError):
        return H11V3IfdocoPostOutcome.NETWORK_ERROR_SANITIZED
    if isinstance(error, ValueError):
        return H11V3IfdocoPostOutcome.CLIENT_ERROR_SANITIZED
    return H11V3IfdocoPostOutcome.UNKNOWN_SANITIZED


def map_ifdoco_post_response_to_safe_outcome(
    *, response: object
) -> H11V3IfdocoPostOutcome:
    """Map an HTTP-like response to sanitized outcomes without storing body data."""

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int):
        return H11V3IfdocoPostOutcome.UNKNOWN_SANITIZED
    if status_code == 200:
        return H11V3IfdocoPostOutcome.ACCEPTED_SANITIZED
    if status_code == 409:
        return H11V3IfdocoPostOutcome.REJECTED_SANITIZED
    if status_code == 408:
        return H11V3IfdocoPostOutcome.TIMEOUT_SANITIZED
    if 400 <= status_code < 500:
        return H11V3IfdocoPostOutcome.CLIENT_ERROR_SANITIZED
    if 500 <= status_code < 600:
        return H11V3IfdocoPostOutcome.SERVER_ERROR_SANITIZED
    return H11V3IfdocoPostOutcome.UNKNOWN_SANITIZED


class H11V3IfdocoOneShotHttpSender:
    """Concrete real-shaped IFDOCO sender.

    No call site in this build constructs this class with a real HTTP
    client: it exists as reviewed scaffolding for the future
    ``H11_V3_ACTUAL_ACTIVATION_STEP``. One send attempt only; no raw
    request/response or secret material is ever stored or returned.
    """

    def __init__(
        self,
        *,
        http_client: H11V3IfdocoHttpClient,
        sealed_credential: H11V3SealedCredentialPair,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        self.http_client = http_client
        self.sealed_credential = sealed_credential
        self.timestamp_factory = timestamp_factory or _inert_timestamp
        self.send_attempt_count = 0

    def __repr__(self) -> str:
        return _SENDER_REPR

    def __str__(self) -> str:
        return _SENDER_REPR

    def send_ifdoco_once(
        self, plan: GmoFxPrivateRequestPlan
    ) -> H11V3IfdocoPostOutcome:
        if plan.request_kind != REQUEST_KIND_IFDOCO_PROTECTED_ENTRY:
            raise H11V3RealSenderError("IFDOCO protected-entry plan is required")
        if plan.path != GMO_FX_IFDOCO_ORDER_PATH:
            raise H11V3RealSenderError("IFDOCO route is required")
        if self.send_attempt_count:
            raise H11V3RealSenderError(
                "H-11 v3 IFDOCO sender supports one attempt only: "
                "retry/repost/second attempt is forbidden"
            )

        self.send_attempt_count += 1
        try:
            response = self._attempt_send_once(plan)
        except Exception as error:  # noqa: BLE001
            return map_ifdoco_post_exception_to_safe_outcome(error=error)
        return map_ifdoco_post_response_to_safe_outcome(response=response)

    def _attempt_send_once(self, plan: GmoFxPrivateRequestPlan) -> object:
        headers = self._build_headers(plan)
        return self.http_client.request(
            plan.method,
            plan.path,
            headers=headers,
            body_json=plan.body_json,
        )

    def _build_headers(self, plan: GmoFxPrivateRequestPlan) -> dict[str, str]:
        api_key, api_secret = self.sealed_credential.unseal_for_actual_ifdoco()
        return build_auth_headers(
            api_key=api_key,
            api_secret=api_secret,
            timestamp=self.timestamp_factory(),
            method=plan.method,
            path=plan.path,
            body=plan.body_json,
        )
