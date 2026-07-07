"""No-POST tests for the GMO sealed credential provider boundary."""

from __future__ import annotations

import pathlib
from dataclasses import fields

from app.services.gmo_live_sealed_credential_provider import (
    FakeSealedCredentialProvider,
    GmoSealedCredentialPresence,
    GmoSealedCredentialPresenceStatus,
    build_gmo_sealed_credential_presence,
    build_gmo_sealed_credential_presence_not_configured,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_sealed_credential_provider.py"
)

FORBIDDEN_SENTINELS = (
    "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE",
    "API_KEY_SHOULD_NOT_SURFACE",
    "API_SECRET_SHOULD_NOT_SURFACE",
    "SIGNATURE_SHOULD_NOT_SURFACE",
)


def test_default_not_configured_is_fail_closed() -> None:
    presence = build_gmo_sealed_credential_presence_not_configured()

    assert presence.credential_present_safe_boolean is False
    assert presence.credential_actual_use_ready is False
    assert (
        presence.presence_status
        is GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_NOT_CONFIGURED
    )
    assert bool(presence) is False


def test_missing_provider_is_fail_closed() -> None:
    presence = build_gmo_sealed_credential_presence(
        provider=FakeSealedCredentialProvider(present=False),
    )

    assert presence.credential_present_safe_boolean is False
    assert presence.credential_actual_use_ready is False
    assert (
        presence.presence_status
        is GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_MISSING
    )


def test_present_provider_without_authorization_is_not_actual_use_ready() -> None:
    presence = build_gmo_sealed_credential_presence(
        provider=FakeSealedCredentialProvider(present=True),
    )

    assert presence.credential_present_safe_boolean is True
    assert presence.credential_actual_use_ready is False
    assert (
        presence.presence_status
        is GmoSealedCredentialPresenceStatus.SEALED_PROVIDER_PRESENT_VALUES_UNTOUCHED
    )


def test_present_provider_with_current_turn_authorization_becomes_ready() -> None:
    presence = build_gmo_sealed_credential_presence(
        provider=FakeSealedCredentialProvider(present=True),
        current_turn_actual_use_authorization_present=True,
    )

    assert presence.credential_present_safe_boolean is True
    assert presence.credential_actual_use_ready is True


def test_presence_has_no_value_carrying_fields() -> None:
    field_names = {field.name for field in fields(GmoSealedCredentialPresence)}
    for banned in ("secret", "api_key", "api_secret", "signature", "token"):
        assert not any(banned in name for name in field_names)
    # Exposure-related fields exist only to pin them false.
    for pinned in (
        "credential_value_touched",
        "credential_length_exposed",
        "credential_hash_exposed",
        "credential_fingerprint_exposed",
        "credential_prefix_or_suffix_exposed",
        "env_read_performed",
        "os_environ_read_performed",
    ):
        assert pinned in field_names


def test_repr_never_exposes_sentinels() -> None:
    presence = build_gmo_sealed_credential_presence(
        provider=FakeSealedCredentialProvider(present=True),
        current_turn_actual_use_authorization_present=True,
    )
    rendered = repr(presence)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in rendered


def test_module_does_not_read_env_or_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_keeps_exposure_fields_hardcoded_false() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "credential_value_touched:bool=False" in text
    assert "env_read_performed:bool=False" in text
    assert "os_environ_read_performed:bool=False" in text
