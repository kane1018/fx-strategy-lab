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
from app.live_verification.live_order_real_api_preflight_execution import (
    PREFLIGHT_PASSED_SANITIZED_STATUS,
    STEP6E_MAX_SPREAD_JPY,
    STEP6E_MAX_TICKER_AGE_SECONDS,
    STEP6E_MIN_TICKER_AGE_SECONDS,
    STEP6E_REQUEST_SCOPE_LABEL,
    STEP6E_ROUTE_TYPE,
    LiveOrderRealApiPreflightExecutionBlockReason,
    LiveOrderRealApiPreflightExecutionEnvironmentCheck,
    LiveOrderRealApiPreflightExecutionRequestSnapshot,
    LiveOrderRealApiPreflightExecutionStatus,
    LiveOrderRealApiPreflightSanitizedResult,
    build_live_order_real_api_preflight_execution,
    render_live_order_real_api_preflight_execution_markdown,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_api_preflight_plan import (
    _plan as _source_plan,
)

ExecutionStatus = LiveOrderRealApiPreflightExecutionStatus
BlockReason = LiveOrderRealApiPreflightExecutionBlockReason
_DEFAULT_PLAN = object()
_DEFAULT_REQUEST = object()
_DEFAULT_ENVIRONMENT = object()
_DEFAULT_RESULT = object()


def _ready_source_plan():
    return _source_plan().plan


def _request(
    **overrides: object,
) -> LiveOrderRealApiPreflightExecutionRequestSnapshot:
    values = {
        "request_id": "step6e_request_001",
        "created_at": CREATED_AT,
        "explicit_step6e_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_read_only_preflight_only": True,
        "operator_understands_no_post_in_step6e": True,
        "operator_understands_no_order_endpoint_in_step6e": True,
        "operator_understands_no_live_order_once_in_step6e": True,
        "operator_understands_no_raw_response_display": True,
        "operator_understands_no_raw_response_save": True,
        "operator_understands_step6f_required_for_post_readiness": True,
        "operator_understands_unknown_means_stop": True,
        "request_scope_label": STEP6E_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightExecutionRequestSnapshot(**values)


def _environment(
    **overrides: object,
) -> LiveOrderRealApiPreflightExecutionEnvironmentCheck:
    values = {
        "environment_check_id": "step6e_environment_001",
        "created_at": CREATED_AT,
        "git_clean": True,
        "tests_recently_passed": True,
        "ruff_recently_passed": True,
        "secret_scan_passed": True,
        "current_timezone": MARKET_HOURS_TIMEZONE,
        "is_weekend_jst": False,
        "local_market_hours_prefilter_passed": True,
        "safe_read_only_route_found": True,
        "safe_read_only_route_name": "safe_existing_readonly_preflight_route",
        "safe_read_only_route_verified_no_post": True,
        "safe_read_only_route_verified_no_order_endpoint": True,
        "safe_read_only_route_verified_no_live_order_once": True,
        "safe_read_only_route_verified_no_raw_output": True,
        "safe_read_only_route_verified_sanitized_output_only": True,
        "env_values_displayed": False,
        "env_file_displayed": False,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightExecutionEnvironmentCheck(**values)


def _sanitized_result(**overrides: object) -> LiveOrderRealApiPreflightSanitizedResult:
    values = {
        "result_id": "step6e_sanitized_result_001",
        "created_at": CREATED_AT,
        "api_preflight_executed": True,
        "api_preflight_route_name": "safe_existing_readonly_preflight_route",
        "api_preflight_route_type": STEP6E_ROUTE_TYPE,
        "api_preflight_result_status": PREFLIGHT_PASSED_SANITIZED_STATUS,
        "market_session_state": MARKET_HOURS_OPEN_STATE,
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "market_hours_unknown": False,
        "account_asset_status": "asset_status_sanitized_ok",
        "account_asset_check_passed": True,
        "open_positions_count": 0,
        "open_positions_check_passed": True,
        "active_orders_count": 0,
        "active_orders_check_passed": True,
        "instrument_symbol": SUPPORTED_SYMBOL,
        "instrument_min_open_order_size": LIVE_ORDER_CANDIDATE_SIZE,
        "instrument_size_step": 1,
        "instrument_rule_check_passed": True,
        "ticker_symbol": SUPPORTED_SYMBOL,
        "ticker_spread_jpy": 0.005,
        "ticker_age_seconds": 1.0,
        "ticker_check_passed": True,
        "permission_scope_check_passed": True,
        "ip_account_binding_check_passed": True,
        "previous_result_unknown_check_passed": True,
        "raw_request_saved": False,
        "raw_request_displayed": False,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "headers_saved": False,
        "headers_displayed": False,
        "signature_saved": False,
        "signature_displayed": False,
        "credentials_displayed": False,
        "order_ids_displayed": False,
        "execution_ids_displayed": False,
        "position_ids_displayed": False,
        "client_order_ids_displayed": False,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightSanitizedResult(**values)


def _execution(
    *,
    source_plan: object = _DEFAULT_PLAN,
    request: object = _DEFAULT_REQUEST,
    environment: object = _DEFAULT_ENVIRONMENT,
    sanitized_result: object = _DEFAULT_RESULT,
    **overrides: object,
):
    actual_plan = _ready_source_plan() if source_plan is _DEFAULT_PLAN else source_plan
    actual_request = _request() if request is _DEFAULT_REQUEST else request
    actual_environment = (
        _environment() if environment is _DEFAULT_ENVIRONMENT else environment
    )
    actual_result = (
        _sanitized_result() if sanitized_result is _DEFAULT_RESULT else sanitized_result
    )
    return build_live_order_real_api_preflight_execution(
        source_plan=actual_plan,
        request_snapshot=actual_request,
        environment_check=actual_environment,
        sanitized_result=actual_result,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApiPreflightExecutionBlockReason,
    *,
    expected_status: LiveOrderRealApiPreflightExecutionStatus | None = None,
    **kwargs: object,
) -> None:
    result = _execution(**kwargs)

    assert result.execution_ready is False
    assert result.api_preflight_passed is False
    assert result.eligible_for_step6f_post_readiness_planning is False
    assert result.allowed_for_live is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.order_endpoint_called is False
    assert result.order_payload_generated is False
    assert result.order_payload_sent is False
    assert result.live_order_once_called is False
    assert result.raw_response_saved is False
    assert result.raw_response_displayed is False
    assert reason.value in result.blocked_reasons
    if expected_status is not None:
        assert result.execution_status is expected_status


def test_ready_source_plan_request_environment_and_result_pass_preflight_no_post() -> None:
    result = _execution()
    execution = result.execution

    assert execution.execution_status is ExecutionStatus.REAL_API_PREFLIGHT_PASSED_NO_POST
    assert execution.execution_ready is True
    assert execution.api_preflight_executed is True
    assert execution.api_preflight_passed is True
    assert execution.eligible_for_step6f_post_readiness_planning is True
    assert execution.allowed_for_live is False
    assert execution.approval_gate_enabled is True
    assert execution.approval_artifact_validated is True
    assert execution.approval_gate_issued is False
    assert execution.approval_command_displayed is False
    assert execution.approval_command_copyable is False
    assert execution.read_only_api_called is True
    assert execution.public_api_called is False
    assert execution.private_api_called is False
    assert execution.broker_called is False
    assert execution.order_endpoint_called is False
    assert execution.order_payload_generated is False
    assert execution.order_payload_sent is False
    assert execution.live_order_once_called is False
    assert execution.post_allowed_this_step is False
    assert execution.post_attempt_limit == 1
    assert execution.post_executed is False
    assert execution.retry_allowed is False
    assert execution.loop_allowed is False
    assert execution.add_order_allowed is False
    assert execution.change_order_allowed is False
    assert execution.cancel_order_allowed is False
    assert execution.close_order_allowed is False
    assert execution.raw_request_saved is False
    assert execution.raw_request_displayed is False
    assert execution.raw_response_saved is False
    assert execution.raw_response_displayed is False
    assert execution.headers_saved is False
    assert execution.headers_displayed is False
    assert execution.signature_saved is False
    assert execution.signature_displayed is False
    assert execution.blocked_reasons == ()


def test_request_missing_blocks_request() -> None:
    _assert_blocked(
        BlockReason.MISSING_REQUEST_SNAPSHOT,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_PREFLIGHT_REQUEST,
        request=None,
    )


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    (
        (
            "explicit_step6e_user_instruction_received",
            BlockReason.EXPLICIT_STEP6E_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_read_only_preflight_only",
            BlockReason.OPERATOR_READ_ONLY_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6e",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_order_endpoint_in_step6e",
            BlockReason.OPERATOR_NO_ORDER_ENDPOINT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6e",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_raw_response_display",
            BlockReason.OPERATOR_NO_RAW_RESPONSE_DISPLAY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_raw_response_save",
            BlockReason.OPERATOR_NO_RAW_RESPONSE_SAVE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6f_required_for_post_readiness",
            BlockReason.OPERATOR_STEP6F_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
    ),
)
def test_request_acknowledgement_missing_blocks_request(
    field_name: str,
    expected_reason: LiveOrderRealApiPreflightExecutionBlockReason,
) -> None:
    _assert_blocked(
        expected_reason,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_PREFLIGHT_REQUEST,
        request=_request(**{field_name: False}),
    )


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    (
        ("is_weekend_jst", BlockReason.WEEKEND_JST),
        ("local_market_hours_prefilter_passed", BlockReason.MARKET_PREFILTER_FAILED),
        ("safe_read_only_route_found", BlockReason.SAFE_READ_ONLY_ROUTE_NOT_FOUND),
        (
            "safe_read_only_route_verified_no_post",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_POST_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_order_endpoint",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_ORDER_ENDPOINT_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_live_order_once",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_LIVE_ORDER_ONCE_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_raw_output",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_RAW_OUTPUT_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_sanitized_output_only",
            BlockReason.SAFE_READ_ONLY_ROUTE_SANITIZED_ONLY_NOT_VERIFIED,
        ),
        ("env_values_displayed", BlockReason.ENV_VALUES_DISPLAYED),
        ("env_file_displayed", BlockReason.ENV_FILE_DISPLAYED),
    ),
)
def test_environment_safety_failure_blocks_before_preflight_result(
    field_name: str,
    expected_reason: LiveOrderRealApiPreflightExecutionBlockReason,
) -> None:
    value = False
    if field_name in {"is_weekend_jst", "env_values_displayed", "env_file_displayed"}:
        value = True
    _assert_blocked(
        expected_reason,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT,
        environment=_environment(**{field_name: value}),
    )


def test_source_plan_blocked_blocks_step6e() -> None:
    blocked_plan = _unchecked(
        _ready_source_plan(),
        plan_ready=False,
    )

    _assert_blocked(
        BlockReason.SOURCE_PLAN_NOT_READY,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_SOURCE_PLAN,
        source_plan=blocked_plan,
    )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    (
        ({"market_session_state": "CLOSED"}, BlockReason.MARKET_SESSION_NOT_OPEN),
        ({"market_window_allowed": False}, BlockReason.MARKET_WINDOW_NOT_ALLOWED),
        ({"broker_maintenance_active": True}, BlockReason.BROKER_MAINTENANCE_ACTIVE),
        ({"holiday_or_special_close": True}, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE),
        ({"market_hours_unknown": True}, BlockReason.MARKET_HOURS_UNKNOWN),
        (
            {"account_asset_check_passed": False},
            BlockReason.ACCOUNT_ASSET_CHECK_FAILED,
        ),
        ({"open_positions_count": 1}, BlockReason.OPEN_POSITIONS_NOT_ZERO),
        ({"active_orders_count": 1}, BlockReason.ACTIVE_ORDERS_NOT_ZERO),
        (
            {"instrument_rule_check_passed": False},
            BlockReason.INSTRUMENT_RULE_CHECK_FAILED,
        ),
        (
            {"ticker_spread_jpy": STEP6E_MAX_SPREAD_JPY + 0.001},
            BlockReason.TICKER_SPREAD_TOO_WIDE,
        ),
        (
            {"ticker_age_seconds": STEP6E_MAX_TICKER_AGE_SECONDS + 1},
            BlockReason.TICKER_AGE_STALE,
        ),
        (
            {"ticker_age_seconds": STEP6E_MIN_TICKER_AGE_SECONDS - 1},
            BlockReason.TICKER_AGE_STALE,
        ),
        (
            {"permission_scope_check_passed": False},
            BlockReason.PERMISSION_SCOPE_CHECK_FAILED,
        ),
        (
            {"ip_account_binding_check_passed": False},
            BlockReason.IP_ACCOUNT_BINDING_CHECK_FAILED,
        ),
        (
            {"previous_result_unknown_check_passed": False},
            BlockReason.PREVIOUS_RESULT_UNKNOWN_CHECK_FAILED,
        ),
        ({"raw_request_saved": True}, BlockReason.RAW_REQUEST_SAVED),
        ({"raw_request_displayed": True}, BlockReason.RAW_REQUEST_DISPLAYED),
        ({"raw_response_saved": True}, BlockReason.RAW_RESPONSE_SAVED),
        ({"raw_response_displayed": True}, BlockReason.RAW_RESPONSE_DISPLAYED),
        ({"headers_saved": True}, BlockReason.HEADERS_SAVED),
        ({"headers_displayed": True}, BlockReason.HEADERS_DISPLAYED),
        ({"signature_saved": True}, BlockReason.SIGNATURE_SAVED),
        ({"signature_displayed": True}, BlockReason.SIGNATURE_DISPLAYED),
        ({"credentials_displayed": True}, BlockReason.CREDENTIALS_DISPLAYED),
        ({"order_ids_displayed": True}, BlockReason.ORDER_IDS_DISPLAYED),
        ({"execution_ids_displayed": True}, BlockReason.EXECUTION_IDS_DISPLAYED),
        ({"position_ids_displayed": True}, BlockReason.POSITION_IDS_DISPLAYED),
        ({"client_order_ids_displayed": True}, BlockReason.CLIENT_ORDER_IDS_DISPLAYED),
    ),
)
def test_sanitized_preflight_result_failure_blocks_step6e(
    overrides: dict[str, object],
    expected_reason: LiveOrderRealApiPreflightExecutionBlockReason,
) -> None:
    _assert_blocked(
        expected_reason,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_REAL_API_PREFLIGHT_RESULT,
        sanitized_result=_sanitized_result(**overrides),
    )


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    (
        ("allowed_for_live", BlockReason.EXECUTION_ALLOWS_LIVE),
        ("order_endpoint_called", BlockReason.ORDER_ENDPOINT_CALLED),
        ("order_payload_generated", BlockReason.ORDER_PAYLOAD_GENERATED),
        ("order_payload_sent", BlockReason.ORDER_PAYLOAD_SENT),
        ("live_order_once_called", BlockReason.LIVE_ORDER_ONCE_CALLED),
        ("post_allowed_this_step", BlockReason.POST_ALLOWED_THIS_STEP),
        ("post_executed", BlockReason.POST_EXECUTED),
        ("retry_allowed", BlockReason.RETRY_ALLOWED),
        ("loop_allowed", BlockReason.LOOP_ALLOWED),
        ("add_order_allowed", BlockReason.ADD_ORDER_ALLOWED),
        ("change_order_allowed", BlockReason.CHANGE_ORDER_ALLOWED),
        ("cancel_order_allowed", BlockReason.CANCEL_ORDER_ALLOWED),
        ("close_order_allowed", BlockReason.CLOSE_ORDER_ALLOWED),
    ),
)
def test_unsafe_execution_flags_block_step6e(
    field_name: str,
    expected_reason: LiveOrderRealApiPreflightExecutionBlockReason,
) -> None:
    _assert_blocked(
        expected_reason,
        expected_status=ExecutionStatus.BLOCKED_STEP6E_UNSAFE_MISMATCH,
        **{field_name: True},
    )


def test_ready_execution_keeps_supported_order_shape_only() -> None:
    execution = _execution().execution

    assert execution.symbol == SUPPORTED_SYMBOL
    assert execution.side in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }
    assert execution.size == LIVE_ORDER_CANDIDATE_SIZE
    assert execution.execution_type == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE


def test_ticker_age_future_skew_within_limit_can_pass_step6e_execution() -> None:
    result = _execution(
        sanitized_result=_sanitized_result(
            ticker_age_seconds=STEP6E_MIN_TICKER_AGE_SECONDS,
        ),
    )

    assert result.execution_status is ExecutionStatus.REAL_API_PREFLIGHT_PASSED_NO_POST
    assert result.execution_ready is True
    assert result.blocked_reasons == ()


def test_future_step6f_handoff_conditions_and_blockers_are_present() -> None:
    execution = _execution().execution

    assert execution.future_step6f_handoff_conditions
    assert execution.future_step6f_blockers
    assert any("Step 6F" in item for item in execution.future_step6f_handoff_conditions)
    assert any("raw response" in item for item in execution.future_step6f_blockers)


def test_markdown_renderer_includes_warnings_and_sanitized_fields_only() -> None:
    markdown = render_live_order_real_api_preflight_execution_markdown(
        _execution().execution,
    )

    assert "read-only/preflight only" in markdown
    assert "does not authorize live POST" in markdown
    assert "allowed_for_live=false" in markdown
    assert "does not call any order endpoint" in markdown
    assert "does not execute HTTP POST" in markdown
    assert "does not call live_order_once" in markdown
    assert "does not display raw request or raw response" in markdown
    assert "ticker_spread_jpy" in markdown
    assert "open_positions_count" in markdown

    for forbidden_marker in (
        "forbidden_marker_alpha",
        "forbidden_marker_beta",
        "forbidden_marker_gamma",
    ):
        assert forbidden_marker not in markdown


def test_serialization_repr_asdict_do_not_include_forbidden_marker_values() -> None:
    execution = _execution().execution
    payload = str(asdict(execution))
    repr_payload = repr(execution)

    for forbidden_marker in (
        "forbidden_marker_alpha",
        "forbidden_marker_beta",
        "forbidden_marker_gamma",
    ):
        assert forbidden_marker not in payload
        assert forbidden_marker not in repr_payload


def test_new_step6e_module_has_no_http_private_broker_or_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_api_preflight_execution.py"
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
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}

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
