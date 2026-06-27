from __future__ import annotations

import ast
from dataclasses import asdict

import pytest

from app.live_verification.live_order_candidate import LIVE_ORDER_CANDIDATE_SIZE
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_MAX_AGE_SECONDS,
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.live_order_real_approval_gate_enablement_state import (
    APPROVAL_GATE_ENABLEMENT_SCOPE,
    DEFAULT_FUTURE_STEP6B_BLOCKERS,
    DEFAULT_FUTURE_STEP6B_HANDOFF_CONDITIONS,
    FRESH_PREFLIGHT_MAX_AGE_SECONDS,
    FRESH_PREFLIGHT_READY_STATUS,
    FRESH_PREFLIGHT_SOURCE,
    LIVE_ORDER_REAL_APPROVAL_GATE_ENABLEMENT_STATE_ID_PREFIX,
    STEP6A_REQUEST_SCOPE_LABEL,
    LiveOrderRealApprovalGateEnablementRequestSnapshot,
    LiveOrderRealApprovalGateEnablementSafetySnapshot,
    LiveOrderRealApprovalGateEnablementStateBlockReason,
    LiveOrderRealApprovalGateEnablementStateStatus,
    build_live_order_real_approval_gate_enablement_state,
    render_live_order_real_approval_gate_enablement_state_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_enablement_dry_run_plan import (
    _plan as _enablement_plan,
)

StateStatus = LiveOrderRealApprovalGateEnablementStateStatus
BlockReason = LiveOrderRealApprovalGateEnablementStateBlockReason
_DEFAULT_PLAN = object()
_DEFAULT_REQUEST = object()
_DEFAULT_SAFETY = object()


def _request(
    **overrides: object,
) -> LiveOrderRealApprovalGateEnablementRequestSnapshot:
    values = {
        "request_id": "step6a_request_001",
        "created_at": CREATED_AT,
        "explicit_step6a_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_post_in_step6a": True,
        "operator_understands_no_approval_id_in_step6a": True,
        "operator_understands_no_approval_command_in_step6a": True,
        "operator_understands_no_copyable_text_in_step6a": True,
        "operator_understands_unknown_means_stop": True,
        "operator_understands_step6b_required_for_artifacts": True,
        "operator_understands_step6c_or_later_required_for_api_preflight": True,
        "operator_understands_step6d_or_later_required_for_post": True,
        "request_scope_label": STEP6A_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealApprovalGateEnablementRequestSnapshot(**values)


def _safety(
    **overrides: object,
) -> LiveOrderRealApprovalGateEnablementSafetySnapshot:
    values = {
        "safety_snapshot_id": "step6a_safety_snapshot_001",
        "created_at": CREATED_AT,
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
        "market_hours_snapshot_max_age_seconds": MARKET_HOURS_MAX_AGE_SECONDS,
        "fresh_pre_approval_preflight_source": FRESH_PREFLIGHT_SOURCE,
        "fresh_pre_approval_preflight_status": FRESH_PREFLIGHT_READY_STATUS,
        "fresh_pre_approval_preflight_passed": True,
        "fresh_pre_approval_preflight_unknown": False,
        "fresh_pre_approval_preflight_age_seconds": 0.5,
        "fresh_pre_approval_preflight_max_age_seconds": FRESH_PREFLIGHT_MAX_AGE_SECONDS,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "result_unknown": False,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "secret_scan_passed": True,
    }
    values.update(overrides)
    return LiveOrderRealApprovalGateEnablementSafetySnapshot(**values)


def _state(
    *,
    plan=_DEFAULT_PLAN,
    request=_DEFAULT_REQUEST,
    safety=_DEFAULT_SAFETY,
    **overrides: object,
):
    actual_plan = _enablement_plan().plan if plan is _DEFAULT_PLAN else plan
    actual_request = _request() if request is _DEFAULT_REQUEST else request
    actual_safety = _safety() if safety is _DEFAULT_SAFETY else safety
    return build_live_order_real_approval_gate_enablement_state(
        enablement_dry_run_plan=actual_plan,
        enablement_request_snapshot=actual_request,
        enablement_safety_snapshot=actual_safety,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalGateEnablementStateBlockReason | str,
    *,
    expected_status: StateStatus | None = None,
    **kwargs: object,
) -> None:
    result = _state(**kwargs)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.enablement_state_ready is False
    assert result.eligible_for_future_step6b_approval_artifact_generation is False
    assert result.approval_gate_enabled is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.approval_command_executable is False
    assert result.usable_approval_artifacts_generated is False
    assert result.real_approval_artifacts_available is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert result.private_api_called is False
    assert result.broker_called is False
    assert result.read_only_api_called is False
    assert result.public_api_called is False
    assert expected in result.blocked_reasons
    if expected_status is not None:
        assert result.enablement_status is expected_status


def test_ready_step6a_state_enables_gate_state_only() -> None:
    result = _state()
    state = result.state

    assert state.enablement_state_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_GATE_ENABLEMENT_STATE_ID_PREFIX
    )
    assert state.enablement_status is StateStatus.REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
    assert state.enablement_state_ready is True
    assert state.eligible_for_future_step6b_approval_artifact_generation is True
    assert state.approval_gate_enabled is True
    assert state.approval_gate_enablement_scope == APPROVAL_GATE_ENABLEMENT_SCOPE
    assert state.allowed_for_live is False
    assert state.blocked_reasons == ()
    assert state.recommended_next_step == (
        "stop_and_wait_for_explicit_step6b_approval_artifact_generation_request_no_api_no_post"
    )


def test_ready_state_never_generates_real_approval_artifacts_or_posts() -> None:
    state = _state().state

    assert state.approval_gate_issued is False
    assert state.approval_id_generated is False
    assert state.approval_command_generated is False
    assert state.approval_command_copyable is False
    assert state.approval_command_executable is False
    assert state.usable_approval_artifacts_generated is False
    assert state.real_approval_artifacts_available is False
    assert state.dry_run_only is True
    assert state.requires_human_approval is True
    assert state.explicit_user_confirmation_required is True
    assert state.fresh_preflight_before_enablement_required is True
    assert state.post_enablement_safety_review_required is True
    assert state.post_approval_final_dynamic_preflight_required is True
    assert state.one_shot_post_separate_step_required is True
    assert state.post_reconciliation_separate_step_required is True
    assert state.final_report_separate_step_required is True
    assert state.post_attempt_limit == 1
    assert state.post_allowed_this_step is False
    assert state.post_executed is False
    assert state.live_order_once_called is False
    assert state.private_api_called is False
    assert state.broker_called is False
    assert state.read_only_api_called is False
    assert state.public_api_called is False
    assert state.retry_allowed is False
    assert state.loop_allowed is False
    assert state.add_order_allowed is False
    assert state.change_order_allowed is False
    assert state.cancel_order_allowed is False
    assert state.close_order_allowed is False


def test_missing_request_snapshot_blocks_request_status() -> None:
    _assert_blocked(
        BlockReason.MISSING_ENABLEMENT_REQUEST_SNAPSHOT,
        request=None,
        expected_status=StateStatus.BLOCKED_STEP6A_ENABLEMENT_REQUEST,
    )


@pytest.mark.parametrize(
    ("field_name", "reason"),
    (
        (
            "explicit_step6a_user_instruction_received",
            BlockReason.EXPLICIT_STEP6A_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6a",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_approval_id_in_step6a",
            BlockReason.OPERATOR_NO_APPROVAL_ID_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_approval_command_in_step6a",
            BlockReason.OPERATOR_NO_APPROVAL_COMMAND_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_copyable_text_in_step6a",
            BlockReason.OPERATOR_NO_COPYABLE_TEXT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6b_required_for_artifacts",
            BlockReason.OPERATOR_STEP6B_ARTIFACTS_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6c_or_later_required_for_api_preflight",
            BlockReason.OPERATOR_STEP6C_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6d_or_later_required_for_post",
            BlockReason.OPERATOR_STEP6D_POST_NOT_ACKNOWLEDGED,
        ),
    ),
)
def test_request_acknowledgement_blockers_fail_closed(
    field_name: str,
    reason: BlockReason,
) -> None:
    _assert_blocked(
        reason,
        request=_request(**{field_name: False}),
        expected_status=StateStatus.BLOCKED_STEP6A_ENABLEMENT_REQUEST,
    )


def test_invalid_request_scope_blocks() -> None:
    _assert_blocked(
        BlockReason.INVALID_REQUEST_SCOPE_LABEL,
        request=_request(request_scope_label="generate_real_approval_command"),
        expected_status=StateStatus.BLOCKED_STEP6A_ENABLEMENT_REQUEST,
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"timezone": "UTC"}, BlockReason.INVALID_TIMEZONE),
        ({"market_hours_source": "real_api"}, BlockReason.INVALID_MARKET_HOURS_SOURCE),
        ({"market_session_state": "CLOSED"}, BlockReason.MARKET_SESSION_NOT_OPEN),
        ({"is_weekend_jst": True}, BlockReason.WEEKEND_JST),
        ({"market_window_allowed": False}, BlockReason.MARKET_WINDOW_NOT_ALLOWED),
        ({"broker_maintenance_active": True}, BlockReason.BROKER_MAINTENANCE_ACTIVE),
        ({"holiday_or_special_close": True}, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE),
        (
            {"holiday_or_special_close_unknown": True},
            BlockReason.HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN,
        ),
        ({"market_hours_unknown": True}, BlockReason.MARKET_HOURS_UNKNOWN),
        (
            {"market_hours_snapshot_age_seconds": 31},
            BlockReason.MARKET_HOURS_SNAPSHOT_STALE,
        ),
        (
            {"fresh_pre_approval_preflight_source": "real_api"},
            BlockReason.INVALID_FRESH_PREFLIGHT_SOURCE,
        ),
        (
            {"fresh_pre_approval_preflight_status": "BLOCKED"},
            BlockReason.FRESH_PREFLIGHT_NOT_READY,
        ),
        (
            {"fresh_pre_approval_preflight_passed": False},
            BlockReason.FRESH_PREFLIGHT_NOT_PASSED,
        ),
        (
            {"fresh_pre_approval_preflight_unknown": True},
            BlockReason.FRESH_PREFLIGHT_UNKNOWN,
        ),
        (
            {"fresh_pre_approval_preflight_age_seconds": 31},
            BlockReason.FRESH_PREFLIGHT_STALE,
        ),
        ({"open_positions_count": 1}, BlockReason.OPEN_POSITION_EXISTS),
        ({"active_orders_count": 1}, BlockReason.ACTIVE_ORDER_EXISTS),
        ({"result_unknown": True}, BlockReason.RESULT_UNKNOWN),
        ({"raw_response_saved": True}, BlockReason.RAW_RESPONSE_SAVED),
        ({"raw_response_displayed": True}, BlockReason.RAW_RESPONSE_DISPLAYED),
        ({"secret_scan_passed": False}, BlockReason.SECRET_SCAN_NOT_PASSED),
    ),
)
def test_safety_snapshot_blockers_fail_closed(
    override: dict[str, object],
    reason: BlockReason,
) -> None:
    _assert_blocked(
        reason,
        safety=_safety(**override),
        expected_status=StateStatus.BLOCKED_STEP6A_SAFETY_SNAPSHOT,
    )


def test_missing_safety_snapshot_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_ENABLEMENT_SAFETY_SNAPSHOT,
        safety=None,
        expected_status=StateStatus.BLOCKED_STEP6A_SAFETY_SNAPSHOT,
    )


def test_missing_or_blocked_source_plan_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_SOURCE_PLAN,
        plan=None,
        expected_status=StateStatus.BLOCKED_STEP6A_SOURCE_PLAN,
    )
    blocked_plan = _enablement_plan(snapshot=None).plan
    _assert_blocked(
        BlockReason.SOURCE_PLAN_NOT_READY,
        plan=blocked_plan,
        expected_status=StateStatus.BLOCKED_STEP6A_SOURCE_PLAN,
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"allowed_for_live": True}, BlockReason.SOURCE_PLAN_ALLOWS_LIVE),
        (
            {"approval_gate_enabled": True},
            BlockReason.SOURCE_PLAN_GATE_ALREADY_ENABLED,
        ),
        ({"dry_run_only": False}, BlockReason.SOURCE_PLAN_NOT_DRY_RUN),
        (
            {"approval_gate_issued": True},
            BlockReason.SOURCE_PLAN_GATE_ALREADY_ISSUED,
        ),
        (
            {"approval_id_generated": True},
            BlockReason.SOURCE_PLAN_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            {"approval_command_generated": True},
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            {"approval_command_copyable": True},
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            {"approval_command_executable": True},
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            {"usable_approval_artifacts_generated": True},
            BlockReason.SOURCE_PLAN_USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            {"real_approval_artifacts_available": True},
            BlockReason.SOURCE_PLAN_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
        ({"symbol": "EUR_USD"}, BlockReason.UNSUPPORTED_SYMBOL),
        ({"side": "NO_TRADE"}, BlockReason.UNSUPPORTED_SIDE),
        ({"size": 200}, BlockReason.UNSUPPORTED_SIZE),
        ({"execution_type": "LIMIT"}, BlockReason.UNSUPPORTED_EXECUTION_TYPE),
        ({"post_attempt_limit": 2}, BlockReason.INVALID_POST_ATTEMPT_LIMIT),
        ({"post_executed": True}, BlockReason.POST_ALREADY_EXECUTED),
        (
            {"live_order_once_called": True},
            BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        ({"private_api_called": True}, BlockReason.PRIVATE_API_ALREADY_CALLED),
        ({"broker_called": True}, BlockReason.BROKER_ALREADY_CALLED),
        ({"read_only_api_called": True}, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        ({"public_api_called": True}, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ({"retry_allowed": True}, BlockReason.RETRY_ALLOWED),
        ({"loop_allowed": True}, BlockReason.LOOP_ALLOWED),
        ({"add_order_allowed": True}, BlockReason.ADD_ORDER_ALLOWED),
        ({"change_order_allowed": True}, BlockReason.CHANGE_ORDER_ALLOWED),
        ({"cancel_order_allowed": True}, BlockReason.CANCEL_ORDER_ALLOWED),
        ({"close_order_allowed": True}, BlockReason.CLOSE_ORDER_ALLOWED),
    ),
)
def test_source_plan_unsafe_mismatches_block_without_artifacts(
    override: dict[str, object],
    reason: BlockReason,
) -> None:
    plan = _unchecked(_enablement_plan().plan, **override)
    _assert_blocked(
        reason,
        plan=plan,
        expected_status=StateStatus.BLOCKED_STEP6A_UNSAFE_MISMATCH,
    )


def test_future_step6b_handoff_lists_are_required() -> None:
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6B_HANDOFF_CONDITIONS,
        future_step6b_handoff_conditions=(),
        expected_status=StateStatus.BLOCKED_STEP6A_UNSAFE_MISMATCH,
    )
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6B_BLOCKERS,
        future_step6b_blockers=(),
        expected_status=StateStatus.BLOCKED_STEP6A_UNSAFE_MISMATCH,
    )


def test_future_step6b_lists_are_preserved_for_handoff() -> None:
    state = _state().state

    assert state.future_step6b_handoff_conditions == (
        DEFAULT_FUTURE_STEP6B_HANDOFF_CONDITIONS
    )
    assert state.future_step6b_blockers == DEFAULT_FUTURE_STEP6B_BLOCKERS
    assert "approval command must not be generated in Step 6A" in (
        state.future_step6b_handoff_conditions
    )
    assert "any API/broker/live_order_once called unexpectedly" in (
        state.future_step6b_blockers
    )


def test_check_results_cover_core_gates() -> None:
    state = _state().state
    names = {check.name for check in state.check_results}

    assert {
        "source_enablement_dry_run_plan_ready",
        "explicit_step6a_request_received",
        "operator_acknowledgements_complete",
        "market_hours_source_sanitized_only",
        "timezone_asia_tokyo",
        "not_weekend",
        "market_session_open",
        "market_window_allowed",
        "maintenance_inactive",
        "market_hours_snapshot_fresh",
        "fresh_pre_approval_preflight_source_sanitized_only",
        "fresh_pre_approval_preflight_ready",
        "fresh_pre_approval_preflight_fresh",
        "no_open_positions",
        "no_active_orders",
        "no_result_unknown",
        "raw_response_not_saved_or_displayed",
        "secret_scan_passed",
        "approval_gate_enabled_true_model_output_only",
        "allowed_for_live_false",
        "approval_gate_not_issued",
        "approval_id_not_generated",
        "approval_command_not_generated",
        "approval_command_not_copyable",
        "approval_command_not_executable",
        "no_usable_approval_artifacts",
        "no_api_broker_live_order_once_called",
        "post_not_allowed_this_step",
        "post_not_executed",
        "one_shot_constraints_preserved",
        "future_step6b_handoff_conditions_present",
        "future_step6b_blockers_present",
    } <= names


def test_markdown_rendering_is_sanitized_and_warns_no_artifacts_no_post() -> None:
    markdown = render_live_order_real_approval_gate_enablement_state_markdown(
        _state().state,
    )

    for required in (
        "This Step 6A approval gate enablement state is dry-run only.",
        "approval_gate_enabled=true only as a sanitized model output.",
        "This Step 6A state keeps allowed_for_live=false.",
        "This Step 6A state does not issue a real approval gate.",
        "This Step 6A state does not generate a real approval_id.",
        "This Step 6A state does not generate a real approval command.",
        "This Step 6A state does not provide copyable approval text.",
        "This Step 6A state does not call read-only API.",
        "This Step 6A state does not call public API.",
        "This Step 6A state does not call Private API.",
        "This Step 6A state does not call live_order_once.",
        "This Step 6A state does not execute HTTP POST.",
        "This Step 6A state does not authorize live POST.",
    ):
        assert required in markdown
    for forbidden in (
        "sk_live_",
        "api_key_value",
        "secret_value",
        "signature_value",
        "raw request body",
        "raw response body",
        "real_order_id_123",
        "clientOrderId",
        "STEP4_APPROVE ",
        "STEP4F-",
    ):
        assert forbidden not in markdown


def test_serialization_and_repr_do_not_contain_secret_or_real_id_values() -> None:
    state = _state().state
    serialized = f"{asdict(state)} {state!r}"

    for forbidden in (
        "sk_live_",
        "api_key_value",
        "secret_value",
        "signature_value",
        "raw request body",
        "raw response body",
        "real_order_id_123",
        "real_position_id_123",
        "clientOrderId",
        "STEP4_APPROVE ",
        "STEP4F-",
    ):
        assert forbidden not in serialized
    assert state.size == LIVE_ORDER_CANDIDATE_SIZE


@pytest.mark.parametrize(
    "forbidden_kwarg",
    (
        "api_key",
        "secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response",
        "clientOrderId",
        "positionId",
        "executionId",
        "approval_id",
        "approval_command",
        "copyable_command",
        "approval_text_file",
        "ledger_path",
        "pbcopy",
        "market_hours_api_client",
    ),
)
def test_builder_does_not_accept_forbidden_inputs(forbidden_kwarg: str) -> None:
    kwargs = {
        "enablement_dry_run_plan": _enablement_plan().plan,
        "enablement_request_snapshot": _request(),
        "enablement_safety_snapshot": _safety(),
        "created_at": CREATED_AT,
        forbidden_kwarg: "forbidden",
    }
    with pytest.raises(TypeError):
        build_live_order_real_approval_gate_enablement_state(**kwargs)


def test_module_does_not_depend_on_api_order_runner_or_clipboard() -> None:
    import app.live_verification.live_order_real_approval_gate_enablement_state as module

    module_source = module.__loader__.get_source(module.__name__)
    assert module_source is not None
    tree = ast.parse(module_source)
    blocked_modules = (
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "http.client",
        "socket",
        "subprocess",
        "app.brokers",
        "app.private_api",
        "live_order_once",
    )
    blocked_call_names = {"pbcopy", "read_text", "write_text"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(
                    alias.name == blocked or alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not any(
                module_name == blocked or module_name.startswith(f"{blocked}.")
                for blocked in blocked_modules
            )
        if isinstance(node, ast.Call):
            func = node.func
            call_name = func.id if isinstance(func, ast.Name) else None
            if isinstance(func, ast.Attribute):
                call_name = func.attr
            assert call_name not in blocked_call_names
