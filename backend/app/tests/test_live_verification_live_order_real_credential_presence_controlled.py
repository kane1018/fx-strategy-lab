from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_controlled import (
    DEFAULT_REQUIRED_CREDENTIAL_LABELS,
    LiveOrderRealCredentialPresenceControlledInput,
    LiveOrderRealCredentialPresenceControlledStatus,
    build_live_order_real_credential_presence_controlled,
    render_live_order_real_credential_presence_controlled_markdown,
)

Status = LiveOrderRealCredentialPresenceControlledStatus
DUMMY_VALUE = "DUMMY_CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"


def _env_name(*parts: str) -> str:
    return "_".join(parts)


SAFE_ENV_NAMES = (
    _env_name("GMO", "FX", "API", "KEY"),
    _env_name("GMO", "FX", "API", "SECRET"),
)


class RaisingEnv(Mapping[str, str]):
    def __getitem__(self, key: str) -> str:
        raise RuntimeError("presence source unavailable")

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def get(self, key: str, default: object = None) -> str | object:
        raise RuntimeError("presence source unavailable")


def _input(
    **overrides: object,
) -> LiveOrderRealCredentialPresenceControlledInput:
    base = LiveOrderRealCredentialPresenceControlledInput()
    return replace(base, **overrides)


def _env(*, present: bool = True, whitespace: bool = False) -> dict[str, str]:
    if not present:
        return {}
    value = "   " if whitespace else DUMMY_VALUE
    return {name: value for name in SAFE_ENV_NAMES}


def _build(
    *,
    env_snapshot: Mapping[str, str] | None = None,
    **overrides: object,
):
    return build_live_order_real_credential_presence_controlled(
        input_snapshot=_input(**overrides),
        env_snapshot=_env() if env_snapshot is None else env_snapshot,
    )


def _serialized_text(payload: object) -> str:
    return repr(payload)


def test_present_process_env_presence_only_ready_no_post() -> None:
    result = _build()

    assert result.status is Status.CREDENTIAL_PRESENCE_PRESENT_NO_POST
    assert result.credential_presence_controlled_ready is True
    assert result.process_env_checked_for_presence_only is True
    assert result.required_credentials_present is True
    assert result.all_required_credentials_present is True
    assert result.required_credential_labels == DEFAULT_REQUIRED_CREDENTIAL_LABELS
    assert all(item.present for item in result.credential_presence_results)
    assert result.env_file_read is False
    assert result.env_example_file_read is False
    assert result.env_actual_names_present is False
    assert result.credential_values_present is False
    assert result.credential_lengths_present is False
    assert result.credential_hashes_present is False
    assert result.credential_fingerprints_present is False
    assert result.credential_metadata_present is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.api_call_allowed is False
    assert result.live_order_once_called is False


def test_missing_process_env_presence_fails_closed_no_post() -> None:
    result = _build(env_snapshot=_env(present=False))

    assert result.status is Status.CREDENTIAL_PRESENCE_MISSING_NO_POST
    assert result.credential_presence_controlled_ready is False
    assert result.required_credentials_present is False
    assert result.all_required_credentials_present is False
    assert result.presence_missing is True
    assert "credential_presence_missing" in result.blocked_reasons
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_whitespace_only_process_env_presence_is_missing_without_length() -> None:
    result = _build(env_snapshot=_env(whitespace=True))

    assert result.status is Status.CREDENTIAL_PRESENCE_MISSING_NO_POST
    assert result.presence_missing is True
    assert result.credential_lengths_present is False


def test_presence_not_requested_does_not_check_process_env() -> None:
    result = _build(presence_check_requested=False)

    assert result.status is Status.CREDENTIAL_PRESENCE_NOT_CHECKED
    assert result.process_env_checked_for_presence_only is False
    assert result.credential_presence_controlled_ready is False


def test_env_source_exception_blocks_as_failed_without_value_exposure() -> None:
    result = _build(env_snapshot=RaisingEnv())

    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_FAILED
    assert result.credential_presence_controlled_ready is False
    assert result.presence_failed is True
    assert result.credential_values_present is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"presence_unknown": True}, Status.CREDENTIAL_PRESENCE_BLOCKED_UNKNOWN),
        ({"presence_failed": True}, Status.CREDENTIAL_PRESENCE_BLOCKED_FAILED),
        (
            {"presence_unavailable": True},
            Status.CREDENTIAL_PRESENCE_BLOCKED_UNAVAILABLE,
        ),
        ({"presence_timeout": True}, Status.CREDENTIAL_PRESENCE_BLOCKED_TIMEOUT),
    ],
)
def test_unknown_failed_unavailable_timeout_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.credential_presence_controlled_ready is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_file_read": True},
        {"env_example_file_read": True},
        {"env_actual_names_present": True},
        {"credential_values_present": True},
        {"credential_lengths_present": True},
        {"credential_hashes_present": True},
        {"credential_fingerprints_present": True},
        {"credential_metadata_present": True},
        {"unsafe_exposure_attempted": True},
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_unsafe_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_UNSAFE_EXPOSURE
    assert result.credential_presence_controlled_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_checker_execution_performed": True},
        {"actual_result_receipt_received": True},
        {"actual_receipt_handoff_executed": True},
    ],
)
def test_actual_execution_or_receipt_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.CREDENTIAL_PRESENCE_BLOCKED_ACTUAL_EXECUTION_OR_RECEIPT
    )
    assert result.credential_presence_controlled_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"can_execute_http_post": True},
        {"api_call_allowed": True},
        {"api_call_attempted": True},
        {"http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
        {"post_allowed_this_step": True},
        {"post_executed": True},
        {"fresh_preflight_executed": True},
        {"final_confirmation_received": True},
    ],
)
def test_api_post_or_preflight_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_API_OR_POST
    assert result.credential_presence_controlled_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"can_generate_real_signature": True},
        {"can_generate_real_headers": True},
        {"real_signing_allowed": True},
        {"real_headers_generation_allowed": True},
        {"real_transport_allowed": True},
    ],
)
def test_signing_or_transport_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_SIGNING_OR_TRANSPORT
    assert result.credential_presence_controlled_ready is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False


def test_unsupported_mode_or_safe_label_blocks() -> None:
    result = _build(presence_mode="UNSUPPORTED")
    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED

    result = _build(required_credential_labels=("UNSUPPORTED_LABEL",))
    assert result.status is Status.CREDENTIAL_PRESENCE_BLOCKED_UNSUPPORTED
    assert result.required_credential_labels == ("UNSUPPORTED_REDACTED",)


def test_renderer_and_asdict_do_not_expose_values_or_env_names() -> None:
    result = _build()
    rendered = render_live_order_real_credential_presence_controlled_markdown(result)
    serialized = _serialized_text(asdict(result))

    for forbidden in (*SAFE_ENV_NAMES, DUMMY_VALUE):
        assert forbidden not in rendered
        assert forbidden not in serialized
    assert "Credential present does not allow POST." in rendered
    assert "does not read .env or .env.example files" in rendered
    assert "does not expose env actual names" in rendered
    assert "credential_values_present: false" in rendered
    assert "credential_lengths_present: false" in rendered
    assert "credential_hashes_present: false" in rendered
    assert "credential_fingerprints_present: false" in rendered
    assert "post_allowed_this_step: false" in rendered


def test_module_imports_no_api_post_private_broker_or_dotenv() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_presence_controlled.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_calls = {
        "getenv",
        "read_text",
        "write_text",
        "print",
        "post",
        "request",
        "execute_one_shot_live_order",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            attr = func.attr if isinstance(func, ast.Attribute) else None
            assert name not in blocked_calls
            assert attr not in blocked_calls
