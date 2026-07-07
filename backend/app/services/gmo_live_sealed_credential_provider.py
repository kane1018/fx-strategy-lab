"""No-POST sealed credential provider boundary for GMO live execution.

This module models WHERE real credentials would eventually be supplied from,
without ever reading, storing, printing, or otherwise touching a real value.

Hard rules enforced by construction:

- A provider only ever answers a presence *safe boolean* (PRESENT / MISSING).
  It never returns, stores, or logs the credential value, its length, hash,
  fingerprint, prefix, or suffix.
- This module never reads the process environment or dotenv files. A future
  real sealed provider that does so lives in a separate, explicitly reviewed
  module; it is intentionally absent here so this file has no
  environment-read surface at all.
- ``credential_actual_use_ready`` is fail-closed: it can only become true
  when an ephemeral current-turn actual-use authorization is present for
  this one turn. It is never true by default and is never banked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class GmoSealedCredentialPresenceStatus(str, Enum):
    """Safe labels for credential presence. Never a value, only presence."""

    SEALED_PROVIDER_NOT_CONFIGURED = "SEALED_PROVIDER_NOT_CONFIGURED"
    SEALED_PROVIDER_PRESENT_VALUES_UNTOUCHED = (
        "SEALED_PROVIDER_PRESENT_VALUES_UNTOUCHED"
    )
    SEALED_PROVIDER_MISSING = "SEALED_PROVIDER_MISSING"


class SealedCredentialProvider(Protocol):
    """A credential source that only ever answers a presence safe boolean.

    Deliberately has no method that returns a credential value. A real
    implementation would resolve a sealed secret internally at the actual
    transport boundary; it must still never hand a value back to callers.
    """

    def presence_safe_boolean(self) -> bool:
        """Return True only if a credential is present. Never a value."""


@dataclass(frozen=True)
class FakeSealedCredentialProvider:
    """Test-only provider carrying only a presence boolean, never a value."""

    present: bool = False

    def presence_safe_boolean(self) -> bool:
        return self.present


@dataclass(frozen=True)
class GmoSealedCredentialPresence:
    """Safe-only credential presence snapshot.

    Every exposure-related field is hardcoded false; there is no field on
    this type that could carry a value, length, hash, fingerprint, prefix,
    or suffix. ``__bool__`` stays false so the snapshot cannot become an
    allow-bridge.
    """

    presence_status: GmoSealedCredentialPresenceStatus
    credential_present_safe_boolean: bool
    credential_actual_use_ready: bool
    credential_value_touched: bool = False
    credential_length_exposed: bool = False
    credential_hash_exposed: bool = False
    credential_fingerprint_exposed: bool = False
    credential_prefix_or_suffix_exposed: bool = False
    env_read_performed: bool = False
    os_environ_read_performed: bool = False

    def __bool__(self) -> bool:
        return False


def build_gmo_sealed_credential_presence(
    *,
    provider: SealedCredentialProvider,
    current_turn_actual_use_authorization_present: bool = False,
) -> GmoSealedCredentialPresence:
    """Build a presence snapshot from a provider's presence safe boolean.

    ``current_turn_actual_use_authorization_present`` must be an ephemeral,
    current-turn operator authorization supplied for this one turn only; it
    is never read from a file, history, or prior report by this function.
    Actual-use readiness is fail-closed: present credential AND current-turn
    authorization, otherwise false.
    """

    present = bool(provider.presence_safe_boolean())
    if not present:
        return GmoSealedCredentialPresence(
            presence_status=GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_MISSING,
            credential_present_safe_boolean=False,
            credential_actual_use_ready=False,
        )

    return GmoSealedCredentialPresence(
        presence_status=(
            GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_PRESENT_VALUES_UNTOUCHED
        ),
        credential_present_safe_boolean=True,
        credential_actual_use_ready=bool(
            current_turn_actual_use_authorization_present
        ),
    )


def build_gmo_sealed_credential_presence_not_configured() -> GmoSealedCredentialPresence:
    """Default fail-closed snapshot used when no provider is wired yet."""

    return GmoSealedCredentialPresence(
        presence_status=GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_NOT_CONFIGURED,
        credential_present_safe_boolean=False,
        credential_actual_use_ready=False,
    )
