"""H-11 v3 macOS Keychain credential wrapper (generic infra, no-POST).

Reads a named secret from the local macOS login Keychain via the `security`
CLI. The value lives only in process memory; ``H11V3SealedSecret`` never
exposes it through ``repr``/``str``/logging, and no caller in this build
prints or persists ``reveal_once()``'s return value.

This module is not GMO/broker specific: it takes an explicit service/account
pair. The accompanying tests exercise it against disposable, clearly-marked
test entries only -- never a real API credential. Sealed credential
provisioning for the actual GMO account happens at a later, separately
authorized activation step, not here.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass


class H11V3KeychainError(RuntimeError):
    """Fail-closed error containing safe labels only. Never includes a value."""


@dataclass(frozen=True)
class H11V3SealedSecret:
    """Holds a secret value without ever exposing it via repr/str/logging."""

    _value: str

    def reveal_once(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "H11V3SealedSecret(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return False


def _require_darwin(action: str) -> None:
    if platform.system() != "Darwin":
        raise H11V3KeychainError(f"Keychain {action} is only supported on macOS")


def read_h11_v3_keychain_secret(
    *, service: str, account: str, timeout_seconds: float = 5.0
) -> H11V3SealedSecret:
    """Read a generic-password item. Raises if unavailable; never logs the value."""

    _require_darwin("read")
    if not service or not account:
        raise H11V3KeychainError("service and account are required")
    if timeout_seconds <= 0:
        raise H11V3KeychainError("timeout_seconds must be positive")
    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise H11V3KeychainError("Keychain read failed: process error") from error
    if completed.returncode != 0:
        raise H11V3KeychainError("Keychain item not found or inaccessible")
    value = completed.stdout.rstrip("\n")
    if not value:
        raise H11V3KeychainError("Keychain item is empty")
    return H11V3SealedSecret(value)


def write_h11_v3_keychain_secret_for_test_only(
    *, service: str, account: str, value: str
) -> None:
    """Test-only helper. Never call with a real credential value."""

    _require_darwin("write")
    if not service.startswith("h11_v3_test_only_"):
        raise H11V3KeychainError(
            "test helper refuses non-test service names as a safety rail"
        )
    try:
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
                value,
                "-U",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        raise H11V3KeychainError("Keychain test write failed") from error


def delete_h11_v3_keychain_secret_for_test_only(*, service: str, account: str) -> None:
    """Best-effort cleanup for the test helper above. Never raises."""

    if platform.system() != "Darwin":
        return
    if not service.startswith("h11_v3_test_only_"):
        return
    subprocess.run(
        ["security", "delete-generic-password", "-s", service, "-a", account],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
