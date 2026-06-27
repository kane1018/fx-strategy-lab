from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_ID_PREFIX,
    MARKET_HOURS_MAX_AGE_SECONDS,
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
    LiveOrderRealApprovalEnablementDryRunPlanBlockReason,
    LiveOrderRealApprovalEnablementDryRunPlanStatus,
    LiveOrderRealApprovalMarketHoursGuardSnapshot,
    LiveOrderRealApprovalMarketHoursGuardStatus,
    LiveOrderRealApprovalPreEnableGoNoGoStatus,
    build_live_order_real_approval_enablement_dry_run_plan,
    render_live_order_real_approval_enablement_dry_run_plan_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_enablement_criteria import (
    _criteria as _enablement_criteria,
)

PlanStatus = LiveOrderRealApprovalEnablementDryRunPlanStatus
MarketStatus = LiveOrderRealApprovalMarketHoursGuardStatus
GoNoGoStatus = LiveOrderRealApprovalPreEnableGoNoGoStatus
BlockReason = LiveOrderRealApprovalEnablementDryRunPlanBlockReason
_DEFAULT_SNAPSHOT = object()


def _snapshot(**overrides: object) -> LiveOrderRealApprovalMarketHoursGuardSnapshot:
    values = {
        "snapshot_id": "market_hours_snapshot_step5yz_001",
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
    }
    values.update(overrides)
    return LiveOrderRealApprovalMarketHoursGuardSnapshot(**values)


def _plan(*, criteria=None, snapshot=_DEFAULT_SNAPSHOT, **overrides: object):
    return build_live_order_real_approval_enablement_dry_run_plan(
        enablement_criteria=criteria or _enablement_criteria().criteria,
        market_hours_snapshot=_snapshot() if snapshot is _DEFAULT_SNAPSHOT else snapshot,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalEnablementDryRunPlanBlockReason | str,
    *,
    criteria=None,
    snapshot=None,
    **overrides: object,
) -> None:
    result = _plan(criteria=criteria, snapshot=snapshot, **overrides)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.plan_ready is False
    assert result.eligible_for_future_step6a_enablement_planning is False
    assert result.allowed_for_live is False
    assert result.approval_gate_enabled is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.approval_command_executable is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert expected in result.blocked_reasons


def test_ready_criteria_and_market_hours_snapshot_build_plan_only() -> None:
    result = _plan()
    plan = result.plan

    assert plan.plan_id.startswith(LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_ID_PREFIX)
    assert plan.plan_status is PlanStatus.READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW
    assert result.plan_ready is True
    assert (
        plan.pre_enable_go_no_go_status
        is GoNoGoStatus.GO_FOR_FUTURE_STEP6A_PLANNING_ONLY
    )
    assert plan.eligible_for_future_step6a_enablement_planning is True
    assert plan.allowed_for_live is False
    assert plan.approval_gate_enabled is False
    assert plan.blocked_reasons == ()
    assert plan.recommended_next_step == (
        "stop_and_wait_for_explicit_user_instruction_for_step6a_real_approval_gate_enablement_no_post"
    )


def test_ready_plan_never_enables_gate_or_real_approval_artifacts() -> None:
    plan = _plan().plan

    assert plan.allowed_for_live is False
    assert plan.approval_gate_enabled is False
    assert plan.approval_gate_enablement_planned is True
    assert plan.approval_gate_enablement_deferred_to_future_step is True
    assert plan.approval_gate_issued is False
    assert plan.approval_id_generated is False
    assert plan.approval_command_generated is False
    assert plan.approval_command_copyable is False
    assert plan.approval_command_executable is False
    assert plan.usable_approval_artifacts_generated is False
    assert plan.real_approval_artifacts_available is False
    assert plan.dry_run_only is True
    assert plan.requires_human_approval is True
    assert plan.explicit_user_confirmation_required is True
    assert plan.fresh_preflight_before_enablement_required is True
    assert plan.implementation_readiness_review_required is True
    assert plan.market_hours_guard_required is True
    assert plan.weekend_blocker_required is True
    assert plan.post_enablement_safety_review_required is True
    assert plan.post_approval_final_dynamic_preflight_required is True
    assert plan.one_shot_post_separate_step_required is True
    assert plan.post_reconciliation_separate_step_required is True
    assert plan.final_report_separate_step_required is True
    assert plan.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert plan.exact_match_required is True
    assert plan.same_session_required is True
    assert plan.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert plan.post_attempt_limit == 1
    assert plan.post_executed is False
    assert plan.live_order_once_called is False
    assert plan.private_api_called is False
    assert plan.broker_called is False
    assert plan.read_only_api_called is False
    assert plan.public_api_called is False
    assert plan.retry_allowed is False
    assert plan.loop_allowed is False
    assert plan.add_order_allowed is False
    assert plan.change_order_allowed is False
    assert plan.cancel_order_allowed is False
    assert plan.close_order_allowed is False
    assert plan.post_reconciliation_required is True


def test_market_hours_snapshot_is_sanitized_and_snapshot_only() -> None:
    plan = _plan().plan
    snapshot = plan.market_hours_snapshot

    assert snapshot.timezone == MARKET_HOURS_TIMEZONE
    assert snapshot.market_hours_source == MARKET_HOURS_SOURCE
    assert snapshot.market_session_state == MARKET_HOURS_OPEN_STATE
    assert snapshot.market_hours_snapshot_max_age_seconds == MARKET_HOURS_MAX_AGE_SECONDS
    assert plan.market_hours_guard_status is MarketStatus.MARKET_HOURS_GUARD_PASSED
    assert plan.market_hours_block_reasons == ()


def test_market_hours_blockers_fail_closed() -> None:
    _assert_blocked(BlockReason.WEEKEND_JST, snapshot=_snapshot(is_weekend_jst=True))
    _assert_blocked(
        BlockReason.MARKET_SESSION_NOT_OPEN,
        snapshot=_snapshot(market_session_state="CLOSED"),
    )
    _assert_blocked(
        BlockReason.MARKET_WINDOW_NOT_ALLOWED,
        snapshot=_snapshot(market_window_allowed=False),
    )
    _assert_blocked(
        BlockReason.BROKER_MAINTENANCE_ACTIVE,
        snapshot=_snapshot(broker_maintenance_active=True),
    )
    _assert_blocked(
        BlockReason.HOLIDAY_OR_SPECIAL_CLOSE,
        snapshot=_snapshot(holiday_or_special_close=True),
    )
    _assert_blocked(
        BlockReason.HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN,
        snapshot=_snapshot(holiday_or_special_close_unknown=True),
    )
    _assert_blocked(
        BlockReason.MARKET_HOURS_UNKNOWN,
        snapshot=_snapshot(market_hours_unknown=True),
    )
    _assert_blocked(
        BlockReason.MARKET_HOURS_SNAPSHOT_STALE,
        snapshot=_snapshot(market_hours_snapshot_age_seconds=31),
    )
    _assert_blocked(
        BlockReason.INVALID_MARKET_HOURS_SOURCE,
        snapshot=_snapshot(market_hours_source="real_api"),
    )
    _assert_blocked(
        BlockReason.INVALID_TIMEZONE,
        snapshot=_snapshot(timezone="UTC"),
    )


def test_missing_market_hours_snapshot_blocks_as_market_hours_no_go() -> None:
    result = _plan(snapshot=None)

    assert result.plan_status is PlanStatus.BLOCKED_PRE_ENABLE_MARKET_HOURS
    assert result.pre_enable_go_no_go_status is GoNoGoStatus.NO_GO_MARKET_HOURS
    assert BlockReason.MISSING_MARKET_HOURS_SNAPSHOT.value in result.blocked_reasons
    assert result.recommended_next_step == (
        "wait_for_market_open_and_rerun_sanitized_market_hours_guard_no_api_no_post"
    )


def test_blocked_criteria_blocks_plan_and_preserves_reasons() -> None:
    criteria = _enablement_criteria(post_attempt_limit=2).criteria
    result = _plan(criteria=criteria)

    assert result.plan_status is PlanStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN
    assert result.pre_enable_go_no_go_status is GoNoGoStatus.NO_GO_ENABLEMENT_CRITERIA
    assert BlockReason.INVALID_POST_ATTEMPT_LIMIT.value in result.blocked_reasons
    assert result.recommended_next_step == "fix_enablement_criteria_blockers_no_post"


def test_criteria_readiness_and_safety_flags_block() -> None:
    criteria = _enablement_criteria().criteria

    _assert_blocked(
        BlockReason.ENABLEMENT_CRITERIA_NOT_ELIGIBLE,
        criteria=_unchecked(
            criteria,
            eligible_for_future_real_approval_gate_enablement_planning=False,
        ),
    )
    _assert_blocked(
        BlockReason.CRITERIA_ALLOWS_LIVE,
        criteria=_unchecked(criteria, allowed_for_live=True),
    )
    _assert_blocked(
        BlockReason.CRITERIA_APPROVAL_GATE_ENABLED,
        criteria=_unchecked(criteria, approval_gate_enabled=True),
    )
    _assert_blocked(
        BlockReason.CRITERIA_NOT_DRY_RUN,
        criteria=_unchecked(criteria, dry_run_only=False),
    )


def test_real_artifact_flags_block() -> None:
    criteria = _enablement_criteria().criteria

    _assert_blocked(
        BlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        criteria=_unchecked(criteria, approval_gate_issued=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_ALREADY_GENERATED,
        criteria=_unchecked(criteria, approval_id_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        criteria=_unchecked(criteria, approval_command_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_COPYABLE,
        criteria=_unchecked(criteria, approval_command_copyable=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_EXECUTABLE,
        criteria=_unchecked(criteria, approval_command_executable=True),
    )
    _assert_blocked(
        BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED,
        criteria=_unchecked(criteria, usable_approval_artifacts_generated=True),
    )
    _assert_blocked(
        BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        criteria=_unchecked(criteria, real_approval_artifacts_available=True),
    )


def test_order_shape_and_approval_validation_constraints_block_when_unsafe() -> None:
    criteria = _enablement_criteria().criteria

    _assert_blocked(
        BlockReason.UNSUPPORTED_SYMBOL,
        criteria=_unchecked(criteria, symbol="EUR_USD"),
    )
    _assert_blocked(
        BlockReason.UNSUPPORTED_SIDE,
        criteria=_unchecked(criteria, side="NO_TRADE"),
    )
    _assert_blocked(
        BlockReason.UNSUPPORTED_SIZE,
        criteria=_unchecked(criteria, size=200),
    )
    _assert_blocked(
        BlockReason.UNSUPPORTED_EXECUTION_TYPE,
        criteria=_unchecked(criteria, execution_type="LIMIT"),
    )
    _assert_blocked(
        BlockReason.INVALID_TTL_SECONDS,
        criteria=_unchecked(criteria, ttl_seconds=301),
    )
    _assert_blocked(
        BlockReason.EXACT_MATCH_NOT_REQUIRED,
        criteria=_unchecked(criteria, exact_match_required=False),
    )
    _assert_blocked(
        BlockReason.SAME_SESSION_NOT_REQUIRED,
        criteria=_unchecked(criteria, same_session_required=False),
    )
    _assert_blocked(
        BlockReason.MISSING_ACK_TOKEN,
        criteria=_unchecked(criteria, required_ack_tokens=APPROVAL_ACK_TOKENS[:-1]),
    )


def test_no_api_post_and_one_shot_constraints_block_when_unsafe() -> None:
    criteria = _enablement_criteria().criteria

    _assert_blocked(
        BlockReason.POST_ALREADY_EXECUTED,
        criteria=_unchecked(criteria, post_executed=True),
    )
    _assert_blocked(
        BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        criteria=_unchecked(criteria, live_order_once_called=True),
    )
    _assert_blocked(
        BlockReason.PRIVATE_API_ALREADY_CALLED,
        criteria=_unchecked(criteria, private_api_called=True),
    )
    _assert_blocked(
        BlockReason.BROKER_ALREADY_CALLED,
        criteria=_unchecked(criteria, broker_called=True),
    )
    _assert_blocked(
        BlockReason.READ_ONLY_API_ALREADY_CALLED,
        criteria=_unchecked(criteria, read_only_api_called=True),
    )
    _assert_blocked(
        BlockReason.PUBLIC_API_ALREADY_CALLED,
        criteria=_unchecked(criteria, public_api_called=True),
    )
    _assert_blocked(
        BlockReason.RETRY_ALLOWED,
        criteria=_unchecked(criteria, retry_allowed=True),
    )
    _assert_blocked(
        BlockReason.LOOP_ALLOWED,
        criteria=_unchecked(criteria, loop_allowed=True),
    )
    _assert_blocked(
        BlockReason.ADD_ORDER_ALLOWED,
        criteria=_unchecked(criteria, add_order_allowed=True),
    )
    _assert_blocked(
        BlockReason.CHANGE_ORDER_ALLOWED,
        criteria=_unchecked(criteria, change_order_allowed=True),
    )
    _assert_blocked(
        BlockReason.CANCEL_ORDER_ALLOWED,
        criteria=_unchecked(criteria, cancel_order_allowed=True),
    )
    _assert_blocked(
        BlockReason.CLOSE_ORDER_ALLOWED,
        criteria=_unchecked(criteria, close_order_allowed=True),
    )
    _assert_blocked(
        BlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        criteria=_unchecked(criteria, post_reconciliation_required=False),
    )


def test_condition_lists_are_required() -> None:
    _assert_blocked(
        BlockReason.MISSING_PRE_ENABLE_GO_CONDITIONS,
        pre_enable_go_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_PRE_ENABLE_NO_GO_CONDITIONS,
        pre_enable_no_go_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_PRE_ENABLE_STOP_CONDITIONS,
        pre_enable_stop_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6A_HANDOFF_CONDITIONS,
        future_step6a_handoff_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6A_BLOCKERS,
        future_step6a_blockers=(),
    )


def test_check_results_cover_required_pre_enable_plan_checks() -> None:
    check_names = {check.name for check in _plan().plan.check_results}

    assert "enablement_criteria_ready" in check_names
    assert "approval_gate_enabled_false" in check_names
    assert "allowed_for_live_false" in check_names
    assert "no_usable_approval_artifacts" in check_names
    assert "approval_gate_not_issued" in check_names
    assert "approval_id_not_generated" in check_names
    assert "approval_command_not_generated" in check_names
    assert "approval_command_not_copyable" in check_names
    assert "approval_command_not_executable" in check_names
    assert "market_hours_guard_source_sanitized_only" in check_names
    assert "timezone_asia_tokyo" in check_names
    assert "not_weekend" in check_names
    assert "market_session_open" in check_names
    assert "market_window_allowed" in check_names
    assert "maintenance_inactive" in check_names
    assert "market_hours_snapshot_fresh" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "post_not_executed" in check_names
    assert "one_shot_constraints_preserved" in check_names
    assert "pre_enable_go_conditions_present" in check_names
    assert "pre_enable_no_go_conditions_present" in check_names
    assert "pre_enable_stop_conditions_present" in check_names
    assert "future_step6a_handoff_conditions_present" in check_names
    assert "future_step6a_blockers_present" in check_names


def test_markdown_rendering_includes_required_no_api_no_real_approval_warnings() -> None:
    markdown = render_live_order_real_approval_enablement_dry_run_plan_markdown(
        _plan().plan
    )

    assert "This Step 5Y-Z enablement dry-run plan is dry-run only." in markdown
    assert "This plan does not enable a real approval gate." in markdown
    assert "This plan keeps approval_gate_enabled=false." in markdown
    assert "This plan keeps allowed_for_live=false." in markdown
    assert "This plan uses sanitized market-hours snapshot only." in markdown
    assert "This plan does not call read-only API." in markdown
    assert "This plan does not call public API." in markdown
    assert "This plan does not call Private API." in markdown
    assert "This plan does not call live_order_once." in markdown
    assert "This plan does not execute HTTP POST." in markdown
    assert "This plan does not issue a real approval gate." in markdown
    assert "This plan does not generate a real approval_id." in markdown
    assert "This plan does not generate a real approval command." in markdown
    assert "This plan does not provide copyable approval text." in markdown
    assert "This plan does not authorize live POST." in markdown


def test_markdown_lists_market_hours_and_step6a_conditions_without_real_values() -> None:
    markdown = render_live_order_real_approval_enablement_dry_run_plan_markdown(
        _plan().plan
    )

    assert "## Sanitized Market-hours Summary" in markdown
    assert "## Pre-enable Go Conditions" in markdown
    assert "## Pre-enable No-Go Conditions" in markdown
    assert "## Pre-enable Stop Conditions" in markdown
    assert "## Future Step 6A Handoff Conditions" in markdown
    assert "## Future Step 6A Blockers" in markdown
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "actual_real_approval_id_value",
        "actual_real_approval_command_value",
        "actual_copyable_command_value",
    )
    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    plan = _plan().plan
    serialized = str(asdict(plan))
    rendered = repr(plan)
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "actual_real_approval_id_value",
        "actual_real_approval_command_value",
        "actual_copyable_command_value",
    )

    for value in forbidden_values:
        assert value not in serialized
        assert value not in rendered


def test_builder_does_not_accept_forbidden_api_approval_clipboard_or_ledger_fields() -> None:
    forbidden_kwargs = {
        "api_key": "x",
        "secret": "x",
        "signature": "x",
        "headers": {},
        "raw_request": {},
        "raw_response": {},
        "clientOrderId": "x",
        "positionId": "x",
        "executionId": "x",
        "approval_id": "x",
        "approval_command": "x",
        "copyable_command": "x",
        "approval_text_file": "x",
        "ledger_path": "x",
        "pbcopy": True,
        "market_hours_api_client": object(),
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_real_approval_enablement_dry_run_plan(
                enablement_criteria=_enablement_criteria().criteria,
                market_hours_snapshot=_snapshot(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_enablement_dry_run_plan_has_no_api_order_or_clipboard_dependencies(
) -> None:
    import app.live_verification.live_order_real_approval_enablement_dry_run_plan as module

    module_names = set(module.__dict__)

    assert "requests" not in module_names
    assert "httpx" not in module_names
    assert "aiohttp" not in module_names
    assert "urllib" not in module_names
    assert "socket" not in module_names
    assert "subprocess" not in module_names
    assert "live_order_once" not in module_names
    assert "private_api" not in module_names
    assert "brokers" not in module_names
    assert "pbcopy" not in module_names
