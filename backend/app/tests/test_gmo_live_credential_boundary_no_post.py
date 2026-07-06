"""No-POST tests for GMO live service credential boundary snapshot.

The boundary snapshot must stay safe-label-only: no credentials, no env reads,
no runtime secret exposure, and no HTTP-post capability by default.
"""

from __future__ import annotations

import ast
import pathlib

from app.services.gmo_live_credential_boundary import (
    GmoLiveCredentialBoundary,
    GmoLiveCredentialBoundaryStatus,
    build_gmo_live_credential_boundary_not_ready,
    build_gmo_live_credential_boundary_ready_for_future_provider,
    build_gmo_live_credential_boundary_snapshot,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_credential_boundary.py"
)


def _assert_no_environment_or_http_refs() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                name = alias.name.split(".")[0]
                assert name not in {"os", "dotenv", "httpx", "requests"}

        if isinstance(node, ast.Name):
            assert node.id != "getenv"

        if isinstance(node, ast.Attribute):
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            )


def test_default_snapshot_is_not_ready_and_holds_no_values() -> None:
    result = build_gmo_live_credential_boundary_not_ready()

    assert result.credential_boundary_ready is False
    assert (
        result.status is GmoLiveCredentialBoundaryStatus.CREDENTIAL_BOUNDARY_NOT_READY
    )
    assert result.credential_values_touched is False
    assert result.env_read is False
    assert result.os_environ_read is False
    assert result.private_api_connected is False
    assert result.broker_write_allowed is False
    assert result.credential_boundary_ready_for_actual_post is False



def test_ready_snapshot_marks_future_provider_readiness_without_capability() -> None:
    result = build_gmo_live_credential_boundary_snapshot(sealed_provider_ready=True)

    assert result.credential_boundary_ready is True
    assert (
        result.status
        is GmoLiveCredentialBoundaryStatus.CREDENTIAL_BOUNDARY_READY_FOR_FUTURE_SEALED_PROVIDER
    )
    assert result.sealed_provider_ready is True
    assert result.credential_boundary_ready_for_actual_post is False
    assert result.credential_values_touched is False
    assert result.env_read is False
    assert result.os_environ_read is False
    assert result.private_api_connected is False
    assert result.broker_write_allowed is False


def test_ready_for_future_provider_helper_keeps_safe_flags() -> None:
    result = build_gmo_live_credential_boundary_ready_for_future_provider(
        sealed_provider_ready=True,
    )

    assert result.credential_boundary_ready is True
    assert (
        result.status
        is GmoLiveCredentialBoundaryStatus.CREDENTIAL_BOUNDARY_READY_FOR_FUTURE_SEALED_PROVIDER
    )
    assert isinstance(result, GmoLiveCredentialBoundary)
    assert result.credential_boundary_ready_for_actual_post is False


def test_snapshot_helpers_dont_read_environment_or_allow_post() -> None:
    result = build_gmo_live_credential_boundary_not_ready()

    assert result.env_read is False
    assert result.os_environ_read is False
    assert result.private_api_connected is False
    assert result.broker_write_allowed is False


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_access_environment_or_http_client() -> None:
    _assert_no_environment_or_http_refs()


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
