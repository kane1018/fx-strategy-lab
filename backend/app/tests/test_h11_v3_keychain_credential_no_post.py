"""H-11 v3 Keychain wrapper tests (macOS only, disposable test entries)."""

from __future__ import annotations

import platform

import pytest

from app.services.h11_v3_keychain_credential_no_post import (
    H11V3KeychainError,
    H11V3SealedSecret,
    delete_h11_v3_keychain_secret_for_test_only,
    read_h11_v3_keychain_secret,
    write_h11_v3_keychain_secret_for_test_only,
)

pytestmark = pytest.mark.skipif(
    platform.system() != "Darwin", reason="Keychain is macOS-only"
)

SERVICE = "h11_v3_test_only_ephemeral"
ACCOUNT = "h11_v3_pytest"


@pytest.fixture
def ephemeral_secret():
    write_h11_v3_keychain_secret_for_test_only(
        service=SERVICE, account=ACCOUNT, value="not-a-real-credential-42"
    )
    try:
        yield
    finally:
        delete_h11_v3_keychain_secret_for_test_only(service=SERVICE, account=ACCOUNT)


def test_read_roundtrip(ephemeral_secret):
    secret = read_h11_v3_keychain_secret(service=SERVICE, account=ACCOUNT)
    assert isinstance(secret, H11V3SealedSecret)
    assert secret.reveal_once() == "not-a-real-credential-42"


def test_secret_never_leaks_via_repr_or_str(ephemeral_secret):
    secret = read_h11_v3_keychain_secret(service=SERVICE, account=ACCOUNT)
    assert "not-a-real-credential-42" not in repr(secret)
    assert "not-a-real-credential-42" not in str(secret)
    assert bool(secret) is False


def test_missing_item_raises():
    with pytest.raises(H11V3KeychainError):
        read_h11_v3_keychain_secret(
            service="h11_v3_test_only_missing_item", account="nobody"
        )


def test_empty_service_or_account_rejected():
    with pytest.raises(H11V3KeychainError):
        read_h11_v3_keychain_secret(service="", account=ACCOUNT)
    with pytest.raises(H11V3KeychainError):
        read_h11_v3_keychain_secret(service=SERVICE, account="")


def test_non_positive_read_timeout_rejected():
    with pytest.raises(H11V3KeychainError):
        read_h11_v3_keychain_secret(
            service=SERVICE,
            account=ACCOUNT,
            timeout_seconds=0,
        )


def test_write_helper_refuses_non_test_service_names():
    with pytest.raises(H11V3KeychainError):
        write_h11_v3_keychain_secret_for_test_only(
            service="production_gmo_credential", account=ACCOUNT, value="x"
        )
