"""G076 fake-only credential boundary.

No Keychain module is imported here.  Real credential loading is outside the
G076 candidate and requires a separately reviewed release boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


class G076KeychainError(RuntimeError):
    """Safe-label-only credential boundary failure."""


@dataclass(frozen=True, repr=False)
class G076PrivateGetKeychainCredentialPair:
    """A deliberately inert placeholder for fake tests only."""

    def unseal_for_internal_request_only(self) -> tuple[object, object]:
        raise G076KeychainError("G076_FAKE_ONLY_CREDENTIAL_REQUIRED")

    def __repr__(self) -> str:
        return "G076PrivateGetKeychainCredentialPair(fake-only)"

    def __bool__(self) -> bool:
        return False


__all__ = ["G076KeychainError", "G076PrivateGetKeychainCredentialPair"]
