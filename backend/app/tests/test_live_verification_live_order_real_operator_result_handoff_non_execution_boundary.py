from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)
from app.live_verification.live_order_real_operator_result_handoff_non_execution_boundary import (
    LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
    LiveOrderRealOperatorResultHandoffNonExecutionBoundaryMode,
    LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus,
    build_live_order_real_operator_result_handoff_non_execution_boundary,
    render_live_order_real_operator_result_handoff_non_execution_boundary_markdown,
)

Status = LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus
Mode = LiveOrderRealOperatorResultHandoffNonExecutionBoundaryMode
Category = LiveOrderRealOperatorExecutionResultCategory
UNSUPPORTED_RAW_LABEL = "RAW_NON_EXECUTION_LABEL_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_LABEL = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput:
    base = LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_result_handoff_non_execution_boundary(
        input_snapshot=_input(**overrides),
    )


def test_default_boundary_ready_without_actual_handoff_or_post() -> None:
    result = _build()

    assert result.status is Status.NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF
    assert result.operator_result_handoff_non_execution_boundary_ready is True
    assert result.boundary_mode == (
        Mode.OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_SKELETON_ONLY.value
    )
    assert result.boundary_declared is True
    assert result.receipt_contract_ready is True
    assert result.policy_contract_ready is True
    assert result.lifecycle_contract_ready is True
    assert result.receipt_ready is True
    assert result.policy_ready is True
    assert result.lifecycle_ready is True
    assert result.actual_handoff_prohibited is True
    assert result.actual_receipt_prohibited is True
    assert result.actual_checker_execution_prohibited is True
    assert result.env_access_prohibited is True
    assert result.credential_read_prohibited is True
    assert result.credential_injection_prohibited is True
    assert result.api_prohibited is True
    assert result.post_prohibited is True
    assert result.live_order_once_prohibited is True
    assert result.fresh_preflight_prohibited is True
    assert result.final_confirmation_prohibited is True
    assert result.ready_flags_are_not_post_permission is True
    assert result.ready_flags_are_not_actual_handoff_permission is True
    assert result.operator_result_category == Category.NOT_PROVIDED.value
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.env_access_allowed is False
    assert result.credential_read_allowed is False
    assert result.credential_injection_allowed is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False
    assert result.blocked_reasons == ()


def test_ready_confirmed_boundary_still_does_not_allow_handoff_or_post() -> None:
    result = _build(operator_result_category=Category.READY_CONFIRMED.value)

    assert result.status is Status.NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF
    assert result.operator_result_handoff_non_execution_boundary_ready is True
    assert result.operator_result_category == Category.READY_CONFIRMED.value
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.env_access_allowed is False
    assert result.credential_read_allowed is False
    assert result.credential_injection_allowed is False
    assert result.real_signing_allowed is False
    assert result.real_transport_allowed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        (
            {"boundary_mode": "UNSUPPORTED_RAW_MODE"},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED,
        ),
        (
            {"operator_result_category": UNSUPPORTED_RAW_LABEL},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED,
        ),
        ({"boundary_declared": False}, Status.NON_EXECUTION_BOUNDARY_NOT_READY),
        (
            {"actual_handoff_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"actual_receipt_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"actual_checker_execution_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        ({"env_access_prohibited": False}, Status.NON_EXECUTION_BOUNDARY_NOT_READY),
        (
            {"credential_read_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"credential_injection_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        ({"api_prohibited": False}, Status.NON_EXECUTION_BOUNDARY_NOT_READY),
        ({"post_prohibited": False}, Status.NON_EXECUTION_BOUNDARY_NOT_READY),
        (
            {"live_order_once_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"fresh_preflight_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"final_confirmation_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        ({"safe_category_only": False}, Status.NON_EXECUTION_BOUNDARY_NOT_READY),
        (
            {"raw_detail_identifier_prohibited": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"ready_flags_are_not_post_permission": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"ready_flags_are_not_actual_handoff_permission": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"operator_result_category_is_safe_label": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"operator_result_category_is_allowed": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"ready_confirmed_is_not_post_permission": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
        (
            {"not_provided_is_not_actual_receipt": False},
            Status.NON_EXECUTION_BOUNDARY_NOT_READY,
        ),
    ],
)
def test_input_or_unsupported_state_blocks(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_non_execution_boundary_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        (
            {"receipt_contract_ready": False},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_RECEIPT_NOT_READY,
        ),
        ({"receipt_ready": False}, Status.NON_EXECUTION_BOUNDARY_BLOCKED_RECEIPT_NOT_READY),
        (
            {"policy_contract_ready": False},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_POLICY_NOT_READY,
        ),
        ({"policy_ready": False}, Status.NON_EXECUTION_BOUNDARY_BLOCKED_POLICY_NOT_READY),
        (
            {"lifecycle_contract_ready": False},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_LIFECYCLE_NOT_READY,
        ),
        (
            {"lifecycle_ready": False},
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_LIFECYCLE_NOT_READY,
        ),
    ],
)
def test_receipt_policy_lifecycle_not_ready_blocks(
    overrides: dict[str, object],
    status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is status
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    "field_name",
    [
        "receipt_raw_value_present",
        "receipt_detail_present",
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "checker_result_detail_present",
        "sentinel_value_present",
    ],
)
def test_raw_detail_identifier_exposure_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is (
        Status.NON_EXECUTION_BOUNDARY_BLOCKED_RAW_OR_DETAIL_OR_IDENTIFIER
    )
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    ("field_name", "status"),
    [
        (
            "actual_receipt_handoff_executed",
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_HANDOFF,
        ),
        (
            "actual_result_receipt_received",
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_RECEIPT,
        ),
        (
            "actual_checker_execution_performed",
            Status.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION,
        ),
        ("actual_execution_performed", Status.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION),
        ("codex_execution_performed", Status.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION),
    ],
)
def test_actual_handoff_receipt_or_execution_blocks(
    field_name: str,
    status: Status,
) -> None:
    result = _build(**{field_name: True})

    assert result.status is status
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    "field_name",
    [
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "env_access_allowed",
        "credential_read_performed",
        "credential_read_allowed",
        "credential_injection_allowed",
    ],
)
def test_env_or_credential_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.NON_EXECUTION_BOUNDARY_BLOCKED_ENV_OR_CREDENTIAL
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    "field_name",
    [
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "real_signing_allowed",
        "real_transport_allowed",
        "api_call_attempted",
        "read_only_api_call_attempted",
        "public_api_call_attempted",
        "private_api_call_attempted",
        "http_post_executed",
        "order_endpoint_called",
        "post_allowed_this_step",
        "post_executed",
    ],
)
def test_api_or_post_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.NON_EXECUTION_BOUNDARY_BLOCKED_API_OR_POST
    assert result.operator_result_handoff_non_execution_boundary_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_live_order_once_blocks_separately() -> None:
    result = _build(live_order_once_called=True)

    assert result.status is Status.NON_EXECUTION_BOUNDARY_BLOCKED_LIVE_ORDER_ONCE
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    "field_name",
    ["fresh_preflight_executed", "final_confirmation_received"],
)
def test_final_confirmation_or_fresh_preflight_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is (
        Status.NON_EXECUTION_BOUNDARY_BLOCKED_FINAL_CONFIRMATION_OR_PREFLIGHT
    )
    assert result.operator_result_handoff_non_execution_boundary_ready is False


@pytest.mark.parametrize(
    "category",
    [
        Category.BLOCKED_UNKNOWN.value,
        Category.BLOCKED_FAILED.value,
        Category.BLOCKED_UNAVAILABLE.value,
        Category.BLOCKED_STALE.value,
        Category.BLOCKED_TIMEOUT.value,
        Category.BLOCKED_REUSED.value,
        Category.BLOCKED_PREVIOUS_TURN.value,
        Category.BLOCKED_UNSAFE_DETAIL.value,
        Category.BLOCKED_UNSUPPORTED.value,
    ],
)
def test_blocked_categories_fail_closed(category: str) -> None:
    result = _build(operator_result_category=category)

    assert result.status is Status.NON_EXECUTION_BOUNDARY_NOT_READY
    assert result.blocked_category_present is True
    assert result.operator_result_handoff_non_execution_boundary_ready is False


def test_unsupported_labels_are_redacted_in_render_and_asdict() -> None:
    result = _build(
        boundary_mode=UNSUPPORTED_RAW_LABEL,
        operator_result_category=UNSUPPORTED_RAW_LABEL,
    )
    rendered = render_live_order_real_operator_result_handoff_non_execution_boundary_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED
    assert result.boundary_mode == UNSUPPORTED_SAFE_LABEL
    assert result.operator_result_category == UNSUPPORTED_SAFE_LABEL
    assert UNSUPPORTED_RAW_LABEL not in rendered
    assert UNSUPPORTED_RAW_LABEL not in payload


def test_renderer_states_non_execution_boundary_and_no_post() -> None:
    rendered = render_live_order_real_operator_result_handoff_non_execution_boundary_markdown(
        _build(operator_result_category=Category.READY_CONFIRMED.value),
    )

    assert "skeleton-only" in rendered
    assert "does not perform actual receipt handoff" in rendered
    assert "does not receive actual result receipts" in rendered
    assert "does not execute the checker" in rendered
    assert "does not access env or .env" in rendered
    assert "READY_CONFIRMED does not allow POST" in rendered
    assert "NOT_PROVIDED is not an actual result receipt" in rendered
    assert "Future env access requires a separate decision gate" in rendered
    assert "post_allowed_this_step: false" in rendered
    assert "post_executed: false" in rendered


def test_module_has_no_api_order_env_or_live_once_dependencies() -> None:
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
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_operator_result_handoff_non_execution_boundary.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(
        module == blocked or module.startswith(f"{blocked}.")
        for blocked in blocked_modules
    )
