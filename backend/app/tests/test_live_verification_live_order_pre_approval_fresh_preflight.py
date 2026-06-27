from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_pre_approval_fresh_preflight import (
    LIVE_ORDER_PRE_APPROVAL_FRESH_PREFLIGHT_ID_PREFIX,
    PRE_APPROVAL_FRESH_PREFLIGHT_MAX_SPREAD_JPY,
    LiveOrderPreApprovalFreshPreflightBlockReason,
    LiveOrderPreApprovalFreshPreflightSnapshot,
    LiveOrderPreApprovalFreshPreflightStatus,
    evaluate_live_order_pre_approval_fresh_preflight,
    render_live_order_pre_approval_fresh_preflight_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_gate_plan import (
    _plan,
)


def _snapshot(
    *,
    plan=None,
    **overrides: object,
) -> LiveOrderPreApprovalFreshPreflightSnapshot:
    actual_plan = plan or _plan().plan
    values = {
        "snapshot_id": "pre_approval_fresh_preflight_snapshot_step5s_001",
        "created_at": CREATED_AT,
        "plan_id": actual_plan.plan_id,
        "checkpoint_id": actual_plan.checkpoint_id,
        "chain_id": actual_plan.chain_id,
        "runbook_id": actual_plan.runbook_id,
        "boundary_id": actual_plan.boundary_id,
        "preflight_decision_id": actual_plan.preflight_decision_id,
        "simulation_id": actual_plan.simulation_id,
        "preview_id": actual_plan.preview_id,
        "design_id": actual_plan.design_id,
        "handoff_id": actual_plan.handoff_id,
        "operator_review_id": actual_plan.operator_review_id,
        "bundle_id": actual_plan.bundle_id,
        "review_id": actual_plan.review_id,
        "candidate_id": actual_plan.candidate_id,
        "risk_decision_id": actual_plan.risk_decision_id,
        "trace_id": actual_plan.trace_id,
        "session_policy_decision_id": actual_plan.session_policy_decision_id,
        "source_signal_id": actual_plan.source_signal_id,
        "source_type": actual_plan.source_type,
        "strategy_name": actual_plan.strategy_name,
        "symbol": "USD_JPY",
        "side": "BUY",
        "size": 100,
        "execution_type": "MARKET",
        "account_assets_status": "success",
        "open_positions_count": 0,
        "active_orders_count": 0,
        "min_open_order_size": 100,
        "size_step": 1,
        "ticker_available": True,
        "spread_jpy": 0.005,
        "ticker_age_seconds": 0.5,
        "ticker_age_threshold_seconds": 30,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
        "api_scope_checked": True,
        "order_permission_checked": True,
        "ip_account_check_passed": True,
        "previous_result_confirmed": True,
        "result_unknown": False,
        "session_attempt_count_today": 0,
        "max_sessions_per_day": 2,
        "daily_live_size_total": 0,
        "max_daily_size_total": 200,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "outbound_body_allowlist_matched": True,
        "request_body_equals_signing_body": True,
        "pre_approval_fresh_preflight_age_seconds": 0.5,
        "pre_approval_fresh_preflight_age_threshold_seconds": 30,
        "allowed_for_live": False,
        "requires_human_approval": True,
        "explicit_user_confirmation_required": True,
        "approval_gate_required": True,
        "approval_gate_planned": True,
        "approval_gate_issued": False,
        "approval_id_generation_planned": True,
        "approval_id_generated": False,
        "approval_command_generation_planned": True,
        "approval_command_generated": False,
        "approval_command_template_only": True,
        "approval_command_copyable": False,
        "fresh_preflight_before_gate_required": True,
        "post_approval_final_dynamic_preflight_required": True,
        "dry_run_only": True,
    }
    values.update(overrides)
    return LiveOrderPreApprovalFreshPreflightSnapshot(**values)


def _evaluate(
    *,
    plan=None,
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot | None = None,
    **snapshot_overrides: object,
):
    actual_plan = plan or _plan().plan
    actual_snapshot = snapshot or _snapshot(plan=actual_plan, **snapshot_overrides)
    return evaluate_live_order_pre_approval_fresh_preflight(
        real_approval_gate_plan=actual_plan,
        snapshot=actual_snapshot,
        created_at=CREATED_AT,
    )


def _assert_blocked(
    reason: LiveOrderPreApprovalFreshPreflightBlockReason | str,
    *,
    plan=None,
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot | None = None,
    **snapshot_overrides: object,
) -> None:
    result = _evaluate(plan=plan, snapshot=snapshot, **snapshot_overrides)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderPreApprovalFreshPreflightBlockReason)
        else reason
    )

    assert (
        result.preflight_status
        is LiveOrderPreApprovalFreshPreflightStatus.BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT
    )
    assert result.preflight_passed is False
    assert result.eligible_for_future_real_approval_gate_generation is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step in {
        "fix_real_approval_gate_plan_blockers_no_post",
        "fix_pre_approval_fresh_preflight_snapshot_no_post",
    }


def test_ready_plan_and_safe_snapshot_are_future_gate_generation_eligible_only() -> None:
    result = _evaluate()
    decision = result.decision

    assert decision.decision_id.startswith(
        LIVE_ORDER_PRE_APPROVAL_FRESH_PREFLIGHT_ID_PREFIX
    )
    assert (
        decision.preflight_status
        is LiveOrderPreApprovalFreshPreflightStatus.READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
    )
    assert decision.preflight_passed is True
    assert decision.eligible_for_future_real_approval_gate_generation is True
    assert decision.allowed_for_live is False
    assert decision.approval_gate_issued is False
    assert decision.approval_id_generated is False
    assert decision.approval_command_generated is False
    assert decision.approval_command_copyable is False
    assert decision.blocked_reasons == ()
    assert result.recommended_next_step == (
        "prepare_future_real_approval_gate_generation_separate_step_no_post"
    )


def test_safety_defaults_are_always_fixed_on_decision() -> None:
    decision = _evaluate().decision

    assert decision.allowed_for_live is False
    assert decision.requires_human_approval is True
    assert decision.explicit_user_confirmation_required is True
    assert decision.approval_gate_required is True
    assert decision.approval_gate_planned is True
    assert decision.approval_gate_issued is False
    assert decision.approval_id_generation_planned is True
    assert decision.approval_id_generated is False
    assert decision.approval_command_generation_planned is True
    assert decision.approval_command_generated is False
    assert decision.approval_command_template_only is True
    assert decision.approval_command_copyable is False
    assert decision.fresh_preflight_before_gate_required is True
    assert decision.post_approval_final_dynamic_preflight_required is True
    assert decision.dry_run_only is True


def test_missing_plan_blocks_pre_approval_fresh_preflight() -> None:
    result = evaluate_live_order_pre_approval_fresh_preflight(
        real_approval_gate_plan=None,
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )

    assert (
        result.preflight_status
        is LiveOrderPreApprovalFreshPreflightStatus.BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT
    )
    assert (
        LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_REAL_APPROVAL_GATE_PLAN.value
        in result.blocked_reasons
    )
    assert result.recommended_next_step == "fix_real_approval_gate_plan_blockers_no_post"


def test_blocked_plan_blocks_and_preserves_plan_reasons() -> None:
    blocked_plan = _plan(approval_gate_issued=True).plan
    result = _evaluate(plan=blocked_plan, snapshot=_snapshot(plan=blocked_plan))

    assert (
        result.preflight_status
        is LiveOrderPreApprovalFreshPreflightStatus.BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT
    )
    assert (
        LiveOrderPreApprovalFreshPreflightBlockReason.REAL_APPROVAL_GATE_PLAN_NOT_READY.value
        in result.blocked_reasons
    )
    assert "approval_gate_already_issued" in result.blocked_reasons
    assert result.recommended_next_step == "fix_real_approval_gate_plan_blockers_no_post"


def test_plan_safety_flags_block() -> None:
    plan = _plan().plan

    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_ALLOWS_LIVE,
        plan=_unchecked(plan, allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_NOT_DRY_RUN,
        plan=_unchecked(plan, dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_GATE_ALREADY_ISSUED,
        plan=_unchecked(plan, approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_ID_ALREADY_GENERATED,
        plan=_unchecked(plan, approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_ALREADY_GENERATED,
        plan=_unchecked(plan, approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_COPYABLE,
        plan=_unchecked(plan, approval_command_copyable=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        plan=_unchecked(plan, fresh_preflight_before_gate_required=False),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        plan=_unchecked(plan, approval_id_generation_after_fresh_preflight_required=False),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        plan=_unchecked(
            plan,
            approval_command_generation_after_fresh_preflight_required=False,
        ),
    )


def test_snapshot_safety_flags_block() -> None:
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.SNAPSHOT_ALLOWS_LIVE,
        snapshot=_unchecked(_snapshot(), allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.SNAPSHOT_NOT_DRY_RUN,
        snapshot=_unchecked(_snapshot(), dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        snapshot=_unchecked(_snapshot(), approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        snapshot=_unchecked(_snapshot(), approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        snapshot=_unchecked(_snapshot(), approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_COMMAND_COPYABLE,
        snapshot=_unchecked(_snapshot(), approval_command_copyable=True),
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        snapshot=_unchecked(_snapshot(), fresh_preflight_before_gate_required=False),
    )


def test_unsupported_order_shape_blocks() -> None:
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SYMBOL,
        symbol="EUR_USD",
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SIDE,
        side="NO_TRADE",
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SIZE,
        size=200,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        execution_type="LIMIT",
    )


def test_account_open_state_rules_and_ticker_blocks() -> None:
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.ACCOUNT_ASSETS_NOT_SUCCESS,
        account_assets_status="failure",
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.OPEN_POSITIONS_EXIST,
        open_positions_count=1,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.ACTIVE_ORDERS_EXIST,
        active_orders_count=1,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_MIN_OPEN_ORDER_SIZE,
        min_open_order_size=101,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_SIZE_STEP,
        size_step=2,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.TICKER_UNAVAILABLE,
        ticker_available=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_SPREAD,
        spread_jpy=None,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.SPREAD_TOO_WIDE,
        spread_jpy=PRE_APPROVAL_FRESH_PREFLIGHT_MAX_SPREAD_JPY + 0.001,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_TICKER_AGE,
        ticker_age_seconds=None,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_TICKER_AGE,
        ticker_age_seconds=-1,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.STALE_TICKER,
        ticker_age_seconds=31,
    )


def test_market_permission_result_session_repo_and_body_blocks() -> None:
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.MARKET_WINDOW_NOT_ALLOWED,
        market_window_allowed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.MAINTENANCE_ACTIVE,
        maintenance_active=True,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.IMPORTANT_EVENT_WINDOW_NOT_OK,
        important_event_window_ok=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.API_SCOPE_NOT_CHECKED,
        api_scope_checked=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.ORDER_PERMISSION_NOT_CHECKED,
        order_permission_checked=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.IP_ACCOUNT_CHECK_NOT_PASSED,
        ip_account_check_passed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.PREVIOUS_RESULT_NOT_CONFIRMED,
        previous_result_confirmed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.RESULT_UNKNOWN,
        result_unknown=True,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.SESSION_ATTEMPT_LIMIT_REACHED,
        session_attempt_count_today=2,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.DAILY_SIZE_LIMIT_EXCEEDED,
        daily_live_size_total=200,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.GIT_NOT_CLEAN,
        git_clean=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.TESTS_NOT_PASSED,
        tests_passed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.RUFF_NOT_PASSED,
        ruff_passed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.SECRET_SCAN_NOT_PASSED,
        secret_scan_passed=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.RAW_RESPONSE_SAVED,
        raw_response_saved=True,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.RAW_RESPONSE_DISPLAYED,
        raw_response_displayed=True,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
        outbound_body_allowlist_matched=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
        request_body_equals_signing_body=False,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_AGE,
        pre_approval_fresh_preflight_age_seconds=None,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_PRE_APPROVAL_FRESH_PREFLIGHT_AGE,
        pre_approval_fresh_preflight_age_seconds=-1,
    )
    _assert_blocked(
        LiveOrderPreApprovalFreshPreflightBlockReason.STALE_PRE_APPROVAL_FRESH_PREFLIGHT,
        pre_approval_fresh_preflight_age_seconds=31,
    )


def test_check_results_cover_required_pre_approval_fresh_preflight_checks() -> None:
    check_names = {check.name for check in _evaluate().decision.check_results}

    assert "real_approval_gate_plan_ready" in check_names
    assert "allowed_for_live_false" in check_names
    assert "approval_artifacts_not_generated" in check_names
    assert "account_assets_success" in check_names
    assert "open_positions_zero" in check_names
    assert "active_orders_zero" in check_names
    assert "instrument_rules" in check_names
    assert "ticker_available" in check_names
    assert "spread_within_threshold" in check_names
    assert "ticker_age_fresh" in check_names
    assert "market_maintenance_event" in check_names
    assert "api_scope_order_permission_ip_account" in check_names
    assert "previous_result_confirmed" in check_names
    assert "result_unknown_false" in check_names
    assert "session_limit" in check_names
    assert "daily_limit" in check_names
    assert "git_tests_ruff_secret_scan" in check_names
    assert "raw_response_not_saved_or_displayed" in check_names
    assert "outbound_body_allowlist" in check_names
    assert "request_body_equals_signing_body" in check_names
    assert "pre_approval_fresh_preflight_age" in check_names


def test_multiple_failures_return_multiple_blocked_reasons() -> None:
    result = _evaluate(
        open_positions_count=1,
        active_orders_count=1,
        spread_jpy=0.02,
        tests_passed=False,
    )

    assert "open_positions_exist" in result.blocked_reasons
    assert "active_orders_exist" in result.blocked_reasons
    assert "spread_too_wide" in result.blocked_reasons
    assert "tests_not_passed" in result.blocked_reasons


def test_markdown_rendering_includes_required_no_api_no_approval_warnings() -> None:
    markdown = render_live_order_pre_approval_fresh_preflight_markdown(
        _evaluate().decision
    )

    assert "This pre-approval fresh preflight model is dry-run only." in markdown
    assert "This model does not call read-only API." in markdown
    assert "This model does not call Private API." in markdown
    assert "This model does not call live_order_once." in markdown
    assert "This model does not execute HTTP POST." in markdown
    assert "This model does not issue a real approval gate." in markdown
    assert "This model does not generate a real approval_id." in markdown
    assert "This model does not generate a real approval command." in markdown
    assert "This model does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_pre_approval_fresh_preflight_markdown(
        _evaluate().decision
    )
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
        "pbcopy",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    decision = _evaluate().decision
    serialized = str(asdict(decision))
    rendered = repr(decision)
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
        "pbcopy",
    )

    for value in forbidden_values:
        assert value not in serialized
        assert value not in rendered


def test_builder_does_not_accept_forbidden_api_approval_or_ledger_fields() -> None:
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
        "ledger_path": "x",
        "pbcopy": True,
    }

    for key, value in forbidden_kwargs.items():
        try:
            evaluate_live_order_pre_approval_fresh_preflight(
                real_approval_gate_plan=_plan().plan,
                snapshot=_snapshot(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_pre_approval_fresh_preflight_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_pre_approval_fresh_preflight as module

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
