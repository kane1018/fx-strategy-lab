"""Narrow G026 Keychain reader with no permit or broker transport capability."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowSealedSecret,
)

_SERVICE = "fx-strategy-lab-h11-v4-actual"
_API_KEY_ACCOUNT = "gmo-fx-api-key"
_API_SECRET_ACCOUNT = "gmo-fx-api-secret"
_TIMEOUT_SECONDS = 120.0


class V4G026PrivateGetKeychainError(RuntimeError):
    """Fixed safe credential-read failure."""


SecretReader = Callable[[str, str], V4UnattendedShadowSealedSecret]


def read_g026_private_get_secret(
    service: str,
    account: str,
) -> V4UnattendedShadowSealedSecret:
    if platform.system() != "Darwin":
        raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_PLATFORM_UNSUPPORTED")
    if service != _SERVICE or account not in {_API_KEY_ACCOUNT, _API_SECRET_ACCOUNT}:
        raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_ITEM_NOT_ALLOWED")
    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_READ_FAILED") from None
    if completed.returncode != 0:
        raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_ITEM_UNAVAILABLE")
    value = completed.stdout.rstrip("\n")
    if not value:
        raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_ITEM_EMPTY")
    return V4UnattendedShadowSealedSecret(value)


@dataclass(frozen=True, repr=False)
class V4G026PrivateGetKeychainCredentialPair:
    reader: SecretReader = read_g026_private_get_secret

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4UnattendedShadowSealedSecret, V4UnattendedShadowSealedSecret]:
        key = self.reader(_SERVICE, _API_KEY_ACCOUNT)
        secret = self.reader(_SERVICE, _API_SECRET_ACCOUNT)
        if not isinstance(key, V4UnattendedShadowSealedSecret) or not isinstance(
            secret, V4UnattendedShadowSealedSecret
        ):
            raise V4G026PrivateGetKeychainError("G026_KEYCHAIN_CONTRACT_INVALID")
        return key, secret

    def __repr__(self) -> str:
        return "V4G026PrivateGetKeychainCredentialPair(***)"

    def __bool__(self) -> bool:
        return False
