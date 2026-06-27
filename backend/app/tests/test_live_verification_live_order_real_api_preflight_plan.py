from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_api_preflight_plan import (
    DEFAULT_STEP6D_MARKET_HOURS_MAX_AGE_SECONDS,
    DEFAULT_STEP6D_SOURCE_VALIDATION_MAX_AGE_SECONDS,
    REQUIRED_PLANNED_CHECK_NAMES,
    STEP6D_REQUEST_SCOPE_LABEL,
    LiveOrderRealApiPreflightPlanBlockReason,
    LiveOrderRealApiPreflightPlanRequestSnapshot,
    LiveOrderRealApiPreflightPlanSafetySnapshot,
    LiveOrderRealApiPreflightPlanStatus,
    build_live_order_real_api_preflight_plan,
    default_live_order_real_api_preflight_data_policy,
    render_live_order_real_api_preflight_plan_markdown,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_artifact_validation import (
    _validation as _source_validation,
)

PlanStatus = LiveOrderRealApiPreflightPlanStatus
BlockReason = LiveOrderRealApiPreflightPlanBlockReason
_DEFAULT_VALIDATION = object()
_DEFAULT_REQUEST = object()
_DEFAULT_SAFETY = object()


def _request(**overrides: object) -> LiveOrderRealApiPreflightPlanRequestSnapshot:
    values = {
        "request_id": "step6d_request_001",
        "created_at": CREATED_AT,
        "explicit_step6d_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_api_execution_in_step6d": True,
        "operator_understands_no_post_in_step6d": True,
        "operator_understands_no_live_order_once_in_step6d": True,
        "operator_understands_planning_only": True,
        "operator_understands_step6e_required_for_real_api_preflight": True,
        "operator_understands_step6f_or_later_required_for_post": True,
        "operator_understands_raw_response_not_saved_or_displayed": True,
        "operator_understands_unknown_means_stop": True,
        "request_scope_label": STEP6D_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightPlanRequestSnapshot(**values)


def _safety(**overrides: object) -> LiveOrderRealApiPreflightPlanSafetySnapshot:
    values = {
        "safety_snapshot_id": "step6d_safety_snapshot_001",
        "created_at": CREATED_AT,
        "source_validation_age_seconds": 0.5,
        "source_validation_max_age_seconds": (
            DEFAULT_STEP6D_SOURCE_VALIDATION_MAX_AGE_SECONDS
        ),
        "approval_gate_enabled": True,
        "approval_artifact_validated": True,
        "eligible_for_step6d_api_preflight_planning": True,
        "allowed_for_live": False,
        "approval_gate_issued": False,
        "approval_command_copyable": False,
        "approval_command_displayed": False,
        "approval_command_persisted": False,
        "approval_command_copied_to_clipboard": False,
        "approval_command_executable": False,
        "timezone": MARKET_HOURS_TIMEZONE,
        "market_hours_source": MARKET_HOURS_SOURCE,
        "market_session_state": MARKET_HOURS_OPEN_STATE,
        "is_weekend_jst": False,
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "holiday_or_special_close_unknown": False,
        "market_hours_unknown": False,
        "market_hours_snapshot_age_seconds": 0.5,
        "market_hours_snapshot_max_age_seconds": (
            DEFAULT_STEP6D_MARKET_HOURS_MAX_AGE_SECONDS
        ),
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "raw_request_saved": False,
        "headers_displayed": False,
        "signature_displayed": False,
        "secret_scan_passed": True,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "post_executed": False,
        "live_order_once_called": False,
        "private_api_called": False,
        "broker_called": False,
        "read_only_api_called": False,
        "public_api_called": False,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightPlanSafetySnapshot(**values)


def _ready_validation():
    return _source_validation().validation


def _plan(
    *,
    validation: object = _DEFAULT_VALIDATION,
    request: object = _DEFAULT_REQUEST,
    safety: object = _DEFAULT_SAFETY,
    **overrides: object,
):
    actual_validation = _ready_validation() if validation is _DEFAULT_VALIDATION else validation
    actual_request = _request() if request is _DEFAULT_REQUEST else request
    actual_safety = _safety() if safety is _DEFAULT_SAFETY else safety
    return build_live_order_real_api_preflight_plan(
        source_validation=actual_validation,
        plan_request_snapshot=actual_request,
        plan_safety_snapshot=actual_safety,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApiPreflightPlanBlockReason,
    *,
    expected_status: LiveOrderRealApiPreflightPlanStatus | None = None,
    **kwargs: object,
) -> None:
    result = _plan(**kwargs)

    assert result.plan_ready is False
    assert result.eligible_for_step6e_real_api_preflight_execution is False
    assert result.allowed_for_live is False
    assert result.api_preflight_executed is False
    assert result.read_only_api_called is False
    assert result.public_api_called is False
    assert result.private_api_called is False
    assert result.broker_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert reason.value in result.blocked_reasons
    if expected_status is not None:
        assert result.plan_status is expected_status


def test_ready_validation_request_and_safety_create_api_preflight_plan_only() -> None:
    result = _plan()
    plan = result.plan

    assert plan.plan_status is PlanStatus.API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST
    assert plan.plan_ready is True
    assert plan.eligible_for_step6e_real_api_preflight_execution is True
    assert plan.allowed_for_live is False
    assert plan.approval_gate_enabled is True
    assert plan.approval_artifact_validated is True
    assert plan.approval_gate_issued is False
    assert plan.approval_command_copyable is False
    assert plan.approval_command_displayed is False
    assert plan.approval_command_executable is False
    assert plan.api_preflight_planned is True
    assert plan.api_preflight_executed is False
    assert plan.real_api_execution_deferred_to_step6e is True
    assert plan.read_only_api_called is False
    assert plan.public_api_called is False
    assert plan.private_api_called is False
    assert plan.broker_called is False
    assert plan.live_order_once_called is False
    assert plan.post_allowed_this_step is False
    assert plan.post_attempt_limit == 1
    assert plan.post_executed is False
    assert plan.retry_allowed is False
    assert plan.loop_allowed is False
    assert plan.add_order_allowed is False
    assert plan.change_order_allowed is False
    assert plan.cancel_order_allowed is False
    assert plan.close_order_allowed is False
    assert result.api_preflight_planned is True
    assert result.api_preflight_executed is False
    assert result.blocked_reasons == ()


def test_request_missing_blocks_request() -> None:
    _assert_blocked(
        BlockReason.MISSING_PLAN_REQUEST_SNAPSHOT,
        expected_status=PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST,
        request=None,
    )


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    (
        (
            "explicit_step6d_user_instruction_received",
            BlockReason.EXPLICIT_STEP6D_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_api_execution_in_step6d",
            BlockReason.OPERATOR_NO_API_EXECUTION_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6d",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6d",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_planning_only",
            BlockReason.OPERATOR_PLANNING_ONLY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6e_required_for_real_api_preflight",
            BlockReason.OPERATOR_STEP6E_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6f_or_later_required_for_post",
            BlockReason.OPERATOR_STEP6F_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_raw_response_not_saved_or_displayed",
            BlockReason.OPERATOR_RAW_RESPONSE_POLICY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
    ),
)
def test_operator_acknowledgement_missing_blocks_request(
    field_name: str,
    expected_reason: LiveOrderRealApiPreflightPlanBlockReason,
) -> None:
    _assert_blocked(
        expected_reason,
        expected_status=PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST,
        request=_request(**{field_name: False}),
    )


def test_invalid_request_scope_blocks_request() -> None:
    _assert_blocked(
        BlockReason.INVALID_REQUEST_SCOPE_LABEL,
        expected_status=PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST,
        request=_request(request_scope_label="other_scope"),
    )


def test_source_validation_blocked_blocks_source_validation() -> None:
    blocked_validation = _unchecked(_ready_validation(), validation_ready=False)
    _assert_blocked(
        BlockReason.SOURCE_VALIDATION_NOT_READY,
        expected_status=PlanStatus.BLOCKED_STEP6D_SOURCE_VALIDATION,
        validation=blocked_validation,
    )


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "expected_reason"),
    (
        ("allowed_for_live", True, BlockReason.SOURCE_VALIDATION_ALLOWS_LIVE),
        ("approval_gate_enabled", False, BlockReason.SOURCE_GATE_NOT_ENABLED),
        ("approval_gate_issued", True, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            "approval_command_copyable",
            True,
            BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            "approval_command_displayed",
            True,
            BlockReason.SOURCE_APPROVAL_COMMAND_DISPLAYED,
        ),
        (
            "approval_command_persisted",
            True,
            BlockReason.SOURCE_APPROVAL_COMMAND_PERSISTED,
        ),
        (
            "approval_command_copied_to_clipboard",
            True,
            BlockReason.SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            "approval_command_executable",
            True,
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        ("post_executed", True, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        ("live_order_once_called", True, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        ("private_api_called", True, BlockReason.PRIVATE_API_ALREADY_CALLED),
        ("broker_called", True, BlockReason.BROKER_ALREADY_CALLED),
        ("read_only_api_called", True, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        ("public_api_called", True, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ("symbol", "EUR_USD", BlockReason.UNSUPPORTED_SYMBOL),
        ("side", "NO_TRADE", BlockReason.UNSUPPORTED_SIDE),
        ("size", LIVE_ORDER_CANDIDATE_SIZE + 1, BlockReason.UNSUPPORTED_SIZE),
        ("execution_type", "LIMIT", BlockReason.UNSUPPORTED_EXECUTION_TYPE),
    ),
)
def test_unsafe_source_validation_mismatch_blocks_fail_closed(
    field_name: str,
    unsafe_value: object,
    expected_reason: LiveOrderRealApiPreflightPlanBlockReason,
) -> None:
    validation = _unchecked(_ready_validation(), **{field_name: unsafe_value})
    _assert_blocked(
        expected_reason,
        expected_status=PlanStatus.BLOCKED_STEP6D_UNSAFE_MISMATCH,
        validation=validation,
    )


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "expected_reason"),
    (
        (
            "source_validation_age_seconds",
            DEFAULT_STEP6D_SOURCE_VALIDATION_MAX_AGE_SECONDS + 1,
            BlockReason.SOURCE_VALIDATION_STALE,
        ),
        ("is_weekend_jst", True, BlockReason.WEEKEND_JST),
        ("market_session_state", "CLOSED", BlockReason.MARKET_SESSION_NOT_OPEN),
        ("market_window_allowed", False, BlockReason.MARKET_WINDOW_NOT_ALLOWED),
        (
            "broker_maintenance_active",
            True,
            BlockReason.BROKER_MAINTENANCE_ACTIVE,
        ),
        ("holiday_or_special_close", True, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE),
        ("market_hours_unknown", True, BlockReason.MARKET_HOURS_UNKNOWN),
        ("raw_response_saved", True, BlockReason.RAW_RESPONSE_SAVED),
        ("raw_response_displayed", True, BlockReason.RAW_RESPONSE_DISPLAYED),
        ("raw_request_saved", True, BlockReason.RAW_REQUEST_SAVED),
        ("headers_displayed", True, BlockReason.HEADERS_DISPLAYED),
        ("signature_displayed", True, BlockReason.SIGNATURE_DISPLAYED),
        ("secret_scan_passed", False, BlockReason.SECRET_SCAN_NOT_PASSED),
        ("git_clean", False, BlockReason.GIT_NOT_CLEAN),
        ("tests_passed", False, BlockReason.TESTS_NOT_PASSED),
        ("ruff_passed", False, BlockReason.RUFF_NOT_PASSED),
    ),
)
def test_unsafe_safety_snapshot_blocks_fail_closed(
    field_name: str,
    unsafe_value: object,
    expected_reason: LiveOrderRealApiPreflightPlanBlockReason,
) -> None:
    _assert_blocked(
        expected_reason,
        expected_status=PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_SAFETY_SNAPSHOT,
        safety=_safety(**{field_name: unsafe_value}),
    )


def test_planned_checks_cover_required_future_preflight_categories() -> None:
    result = _plan()
    names = {check.name for check in result.plan.planned_checks}

    assert set(REQUIRED_PLANNED_CHECK_NAMES).issubset(names)
    for check in result.plan.planned_checks:
        assert check.future_step == "Step 6E or later"
        assert check.api_classification == "future_read_only_or_preflight_only"
        assert check.must_be_read_only is True
        assert check.must_not_post is True
        assert check.raw_response_policy == (
            "extract_sanitized_fields_only_no_save_no_display"
        )
        assert check.display_policy == "sanitized_summary_only"
        assert check.store_policy == "do_not_store_raw"


def test_data_handling_policy_forbids_raw_headers_signature_ids_and_credentials() -> None:
    policy = default_live_order_real_api_preflight_data_policy()

    assert policy.raw_request_saved is False
    assert policy.raw_request_displayed is False
    assert policy.raw_response_saved is False
    assert policy.raw_response_displayed is False
    assert policy.headers_saved is False
    assert policy.headers_displayed is False
    assert policy.signature_saved is False
    assert policy.signature_displayed is False
    assert policy.order_id_display_allowed is False
    assert policy.execution_id_display_allowed is False
    assert policy.position_id_display_allowed is False
    assert policy.client_order_id_display_allowed is False
    assert policy.credential_display_allowed is False
    assert policy.credential_storage_allowed is False
    assert policy.sanitized_fields_only is True
    assert "raw response" in policy.forbidden_display_fields
    assert "headers" in policy.forbidden_display_fields
    assert "request signing digest" in policy.forbidden_display_fields
    assert "order ID" in policy.forbidden_display_fields
    assert "clientOrderId" in policy.forbidden_display_fields


def test_markdown_rendering_includes_no_api_no_post_no_raw_response_warnings() -> None:
    markdown = render_live_order_real_api_preflight_plan_markdown(_plan().plan)

    for required in (
        "This Step 6D API preflight plan is dry-run only.",
        "This Step 6D plan does not call read-only API.",
        "This Step 6D plan does not call public API.",
        "This Step 6D plan does not call Private API.",
        "This Step 6D plan does not call broker code.",
        "This Step 6D plan does not call live_order_once.",
        "This Step 6D plan does not execute HTTP POST.",
        "This Step 6D plan does not authorize live POST.",
        "This Step 6D plan keeps allowed_for_live=false.",
        "This Step 6D plan does not display or save raw request/response.",
    ):
        assert required in markdown
    for forbidden_actual in (
        "forbidden_marker_alpha",
        "forbidden_marker_beta",
        "forbidden_marker_gamma",
        "forbidden_marker_delta",
        "forbidden_marker_epsilon",
        "forbidden_marker_zeta",
        "STEP4_APPROVE",
        "STEP4F-",
        "pbcopy ",
    ):
        assert forbidden_actual not in markdown


def test_future_step6e_handoff_and_blockers_are_present() -> None:
    plan = _plan().plan

    assert plan.future_step6e_handoff_conditions
    assert plan.future_step6e_blockers
    assert any("Step 6E" in item for item in plan.future_step6e_handoff_conditions)
    assert any("no explicit Step 6E request" in item for item in plan.future_step6e_blockers)


def test_serialization_repr_and_asdict_do_not_include_actual_sensitive_values() -> None:
    plan = _plan().plan
    serialized = repr(asdict(plan))

    for forbidden_actual in (
        "forbidden_marker_alpha",
        "forbidden_marker_beta",
        "forbidden_marker_gamma",
        "forbidden_marker_delta",
        "forbidden_marker_epsilon",
        "forbidden_marker_zeta",
        "forbidden_marker_eta",
    ):
        assert forbidden_actual not in serialized


def test_plan_preserves_symbol_side_size_and_execution_type_constraints() -> None:
    plan = _plan().plan

    assert plan.symbol == SUPPORTED_SYMBOL
    assert plan.side in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}
    assert plan.size == LIVE_ORDER_CANDIDATE_SIZE
    assert plan.execution_type == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE


def test_plan_file_has_no_private_api_broker_live_order_once_or_http_dependencies() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_api_preflight_plan.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
    blocked_calls = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "read_text",
        "write_text",
        "pbcopy",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Call):
            call = node.func
            if isinstance(call, ast.Name):
                assert call.id not in blocked_calls
            if isinstance(call, ast.Attribute):
                assert call.attr not in blocked_calls
