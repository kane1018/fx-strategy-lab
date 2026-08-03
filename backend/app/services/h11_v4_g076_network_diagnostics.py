"""Credential-free, one-attempt network classification for G076.

This module exposes only fixed safe labels and counts.  It never reads a
credential, calls a Private API, sends a broker write, retries, or exposes a
request/response body.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from enum import StrEnum

from app.services.h11_v4_g076_runtime import G076FakeOnlyPort

G076_PUBLIC_STATUS_URL = "https://forex-api.coin.z.com/public/v1/status"


class G076NetworkFailureClass(StrEnum):
    DNS_FAILURE = "DNS_FAILURE"
    TCP_CONNECT_FAILURE = "TCP_CONNECT_FAILURE"
    TLS_HANDSHAKE_FAILURE = "TLS_HANDSHAKE_FAILURE"
    TLS_CERTIFICATE_FAILURE = "TLS_CERTIFICATE_FAILURE"
    CONNECT_TIMEOUT = "CONNECT_TIMEOUT"
    READ_TIMEOUT = "READ_TIMEOUT"
    PRIVATE_REQUEST_BUILD_FAILURE = "PRIVATE_REQUEST_BUILD_FAILURE"
    AUTH_HEADER_BUILD_FAILURE = "AUTH_HEADER_BUILD_FAILURE"
    HTTP_STATUS_FAILURE = "HTTP_STATUS_FAILURE"
    RESPONSE_SCHEMA_FAILURE = "RESPONSE_SCHEMA_FAILURE"
    UNKNOWN_NETWORK_FAILURE = "UNKNOWN_NETWORK_FAILURE"


@dataclass(frozen=True)
class G076NetworkDiagnostic:
    status: str
    failure_class: G076NetworkFailureClass | None
    public_get_count: int
    broker_post_count: int
    private_api_read_count: int
    credential_read_count: int

    def __bool__(self) -> bool:
        return False


class G076PublicClient(G076FakeOnlyPort):
    """Synthetic-only public client port used by local tests."""

    def get(self, url: str) -> object:
        raise NotImplementedError("G076_FAKE_ONLY_PUBLIC_CLIENT_REQUIRED")


def classify_g076_network_failure(error: BaseException) -> G076NetworkFailureClass:
    """Map transport failures to fixed labels without exposing exception text."""

    if isinstance(error, ssl.SSLCertVerificationError):
        return G076NetworkFailureClass.TLS_CERTIFICATE_FAILURE
    if isinstance(error, ssl.SSLError):
        return G076NetworkFailureClass.TLS_HANDSHAKE_FAILURE
    if isinstance(error, TimeoutError):
        return G076NetworkFailureClass.READ_TIMEOUT
    if isinstance(error, ConnectionError):
        return G076NetworkFailureClass.TCP_CONNECT_FAILURE
    if isinstance(error, TypeError | ValueError):
        return G076NetworkFailureClass.PRIVATE_REQUEST_BUILD_FAILURE
    return G076NetworkFailureClass.UNKNOWN_NETWORK_FAILURE


def run_g076_public_preflight(*, client: G076PublicClient) -> G076NetworkDiagnostic:
    """Perform exactly one credential-free same-origin public status GET.

    Production invocation remains outside the current no-POST policy.  Tests
    inject a fake client and verify the one-attempt contract.
    """

    if not isinstance(client, G076PublicClient):
        raise TypeError("G076_FAKE_ONLY_PUBLIC_CLIENT_REQUIRED")
    try:
        response = client.get(G076_PUBLIC_STATUS_URL)
    except BaseException as error:
        return G076NetworkDiagnostic(
            status="FAILED",
            failure_class=classify_g076_network_failure(error),
            public_get_count=1,
            broker_post_count=0,
            private_api_read_count=0,
            credential_read_count=0,
        )
    if getattr(response, "status_code", None) != 200:
        return G076NetworkDiagnostic(
            status="FAILED",
            failure_class=G076NetworkFailureClass.HTTP_STATUS_FAILURE,
            public_get_count=1,
            broker_post_count=0,
            private_api_read_count=0,
            credential_read_count=0,
        )
    return G076NetworkDiagnostic(
        status="PASSED",
        failure_class=None,
        public_get_count=1,
        broker_post_count=0,
        private_api_read_count=0,
        credential_read_count=0,
    )


__all__ = [
    "G076NetworkDiagnostic",
    "G076NetworkFailureClass",
    "G076_PUBLIC_STATUS_URL",
    "classify_g076_network_failure",
    "run_g076_public_preflight",
]
