"""G074-only sealed credential adapter for the one-use read-only transaction."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.h11_v4_gmo_actual_transport import (
    V4GmoSealedSecret,
    read_v4_gmo_keychain_secret,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowSealedSecret,
)

G074_KEYCHAIN_SERVICE = "fx-strategy-lab-h11-v4-actual"
G074_API_KEY_ACCOUNT = "gmo-fx-api-key"
G074_API_SECRET_ACCOUNT = "gmo-fx-api-secret"


class G074KeychainError(RuntimeError):
    """Safe-label-only G074 credential boundary failure."""


@dataclass(frozen=True, repr=False)
class G074PrivateGetKeychainCredentialPair:
    """Read two existing items once and adapt them without exposing values."""

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4UnattendedShadowSealedSecret, V4UnattendedShadowSealedSecret]:
        try:
            key = read_v4_gmo_keychain_secret(G074_KEYCHAIN_SERVICE, G074_API_KEY_ACCOUNT)
            secret = read_v4_gmo_keychain_secret(
                G074_KEYCHAIN_SERVICE, G074_API_SECRET_ACCOUNT
            )
        except Exception as error:
            raise G074KeychainError("G074_KEYCHAIN_INTERNAL_READ_FAILED") from error
        if not isinstance(key, V4GmoSealedSecret) or not isinstance(
            secret, V4GmoSealedSecret
        ):
            raise G074KeychainError("G074_KEYCHAIN_CONTRACT_INVALID")
        return (
            V4UnattendedShadowSealedSecret(key.reveal_for_internal_request_only()),
            V4UnattendedShadowSealedSecret(secret.reveal_for_internal_request_only()),
        )

    def __repr__(self) -> str:
        return "G074PrivateGetKeychainCredentialPair(***)"

    def __bool__(self) -> bool:
        return False


__all__ = ["G074KeychainError", "G074PrivateGetKeychainCredentialPair"]
