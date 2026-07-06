"""No-POST credential boundary skeleton for GMO live execution.

This module defines a typed, value-less boundary model used only for readiness
classification. It intentionally never reads credentials or secret configuration
from runtime environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoLiveCredentialBoundaryStatus(str, Enum):
    """Safe labels used to classify credential boundary readiness."""

    CREDENTIAL_BOUNDARY_NOT_READY = "CREDENTIAL_BOUNDARY_NOT_READY"
    CREDENTIAL_BOUNDARY_READY_FOR_FUTURE_SEALED_PROVIDER = (
        "CREDENTIAL_BOUNDARY_READY_FOR_FUTURE_SEALED_PROVIDER"
    )
    CREDENTIAL_VALUES_NOT_TOUCHED = "CREDENTIAL_VALUES_NOT_TOUCHED"
    ENV_READ_NOT_ALLOWED = "ENV_READ_NOT_ALLOWED"
    PRIVATE_API_CONNECTION_NOT_ALLOWED = "PRIVATE_API_CONNECTION_NOT_ALLOWED"
    BROKER_WRITE_NOT_ALLOWED = "BROKER_WRITE_NOT_ALLOWED"


@dataclass(frozen=True)
class GmoLiveCredentialBoundary:
    """Safe-boundary snapshot for credential handling readiness."""

    credential_boundary_ready: bool
    status: GmoLiveCredentialBoundaryStatus
    credential_values_touched: bool = False
    env_read: bool = False
    os_environ_read: bool = False
    private_api_connected: bool = False
    broker_write_allowed: bool = False
    sealed_provider_ready: bool = False
    credential_boundary_ready_for_actual_post: bool = False


def build_gmo_live_credential_boundary_snapshot(
    *,
    sealed_provider_ready: bool = False,
) -> GmoLiveCredentialBoundary:
    """Build the credential boundary snapshot without touching any secrets."""

    if sealed_provider_ready:
        return GmoLiveCredentialBoundary(
            credential_boundary_ready=True,
            status=GmoLiveCredentialBoundaryStatus.CREDENTIAL_BOUNDARY_READY_FOR_FUTURE_SEALED_PROVIDER,
            sealed_provider_ready=True,
            credential_boundary_ready_for_actual_post=False,
        )
    return GmoLiveCredentialBoundary(
        credential_boundary_ready=False,
        status=GmoLiveCredentialBoundaryStatus.CREDENTIAL_BOUNDARY_NOT_READY,
        credential_boundary_ready_for_actual_post=False,
        env_read=False,
        os_environ_read=False,
        private_api_connected=False,
        broker_write_allowed=False,
    )


def build_gmo_live_credential_boundary_not_ready() -> GmoLiveCredentialBoundary:
    """Default boundary snapshot used in this sprint."""

    return build_gmo_live_credential_boundary_snapshot()


def build_gmo_live_credential_boundary_ready_for_future_provider(
    *,
    sealed_provider_ready: bool = True,
) -> GmoLiveCredentialBoundary:
    """Optional future snapshot helper after provider sealing design is finalized."""

    return build_gmo_live_credential_boundary_snapshot(
        sealed_provider_ready=sealed_provider_ready,
    )
