from __future__ import annotations

from dataclasses import asdict
from inspect import signature

import pytest

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_gate_plan import (
    DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS,
    LIVE_ORDER_REAL_APPROVAL_GATE_PLAN_ID_PREFIX,
    REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS,
    LiveOrderRealApprovalGatePlanBlockReason,
    LiveOrderRealApprovalGatePlanStatus,
    build_default_real_approval_gate_plan_phases,
    build_live_order_real_approval_gate_plan,
    render_live_order_real_approval_gate_plan_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _chain,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_readiness import (
    _checkpoint,
)

_DEFAULT_CHECKPOINT = object()


def _plan(real_approval_readiness_checkpoint=_DEFAULT_CHECKPOINT, **overrides: object):
    checkpoint = (
        _checkpoint().checkpoint
        if real_approval_readiness_checkpoint is _DEFAULT_CHECKPOINT
        else real_approval_readiness_checkpoint
    )
    return build_live_order_real_approval_gate_plan(
        real_approval_readiness_checkpoint=checkpoint,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalGatePlanBlockReason | str,
    **overrides: object,
) -> None:
    result = _plan(**overrides)
    expected = (
        reason.value if isinstance(reason, LiveOrderRealApprovalGatePlanBlockReason) else reason
    )

    assert (
        result.plan_status
        is LiveOrderRealApprovalGatePlanStatus.BLOCKED_REAL_APPROVAL_GATE_PLAN
    )
    assert result.plan_ready is False
    assert result.eligible_for_future_real_approval_gate_implementation is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert expected in result.blocked_reasons


def test_ready_readiness_checkpoint_builds_real_approval_gate_plan_review_only() -> None:
    result = _plan()
    plan = result.plan

    assert plan.plan_id.startswith(LIVE_ORDER_REAL_APPROVAL_GATE_PLAN_ID_PREFIX)
    assert (
        plan.plan_status
        is LiveOrderRealApprovalGatePlanStatus.READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW
    )
    assert plan.plan_ready is True
    assert plan.eligible_for_future_real_approval_gate_implementation is True
    assert plan.allowed_for_live is False
    assert result.allowed_for_live is False
    assert plan.recommended_next_step == (
        "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_step"
    )


def test_ready_plan_safety_defaults_do_not_issue_approval_or_post() -> None:
    plan = _plan().plan

    assert plan.requires_human_approval is True
    assert plan.explicit_user_confirmation_required is True
    assert plan.real_approval_gate_separate_step_required is True
    assert plan.fresh_preflight_before_gate_required is True
    assert plan.approval_id_generation_after_fresh_preflight_required is True
    assert plan.approval_command_generation_after_fresh_preflight_required is True
    assert plan.post_approval_final_dynamic_preflight_required is True
    assert plan.one_shot_post_separate_step_required is True
    assert plan.post_reconciliation_separate_step_required is True
    assert plan.final_report_separate_step_required is True
    assert plan.approval_gate_required is True
    assert plan.approval_gate_planned is True
    assert plan.approval_gate_issued is False
    assert plan.approval_id_generation_planned is True
    assert plan.approval_id_generated is False
    assert plan.approval_command_generation_planned is True
    assert plan.approval_command_generated is False
    assert plan.approval_command_template_only is True
    assert plan.approval_command_copyable is False
    assert plan.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert plan.exact_match_required is True
    assert plan.same_session_required is True
    assert plan.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert plan.dry_run_only is True
    assert plan.post_attempt_limit == 1
    assert plan.post_executed is False
    assert plan.live_order_once_called is False
    assert plan.private_api_called is False
    assert plan.broker_called is False
    assert plan.read_only_api_called is False
    assert plan.retry_allowed is False
    assert plan.loop_allowed is False
    assert plan.add_order_allowed is False
    assert plan.change_order_allowed is False
    assert plan.cancel_order_allowed is False
    assert plan.close_order_allowed is False
    assert plan.post_reconciliation_required is True


def test_blocked_readiness_checkpoint_blocks_plan_and_preserves_reason() -> None:
    blocked_checkpoint = _checkpoint(chain_review=_chain(candidate=None).chain_review).checkpoint
    result = _plan(real_approval_readiness_checkpoint=blocked_checkpoint)

    assert (
        result.plan_status
        is LiveOrderRealApprovalGatePlanStatus.BLOCKED_REAL_APPROVAL_GATE_PLAN
    )
    assert LiveOrderRealApprovalGatePlanBlockReason.READINESS_NOT_READY.value in (
        result.blocked_reasons
    )
    assert "missing_required_stage" in result.blocked_reasons
    assert result.recommended_next_step == "fix_real_approval_readiness_blockers_no_post"


def test_missing_readiness_checkpoint_blocks_plan() -> None:
    _assert_blocked(
        LiveOrderRealApprovalGatePlanBlockReason.MISSING_READINESS_CHECKPOINT,
        real_approval_readiness_checkpoint=None,
    )


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    (
        (
            "allowed_for_live",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_ALLOWS_LIVE,
        ),
        ("dry_run_only", False, LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_NOT_DRY_RUN),
        (
            "approval_gate_issued",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_id_generated",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_command_generated",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_command_copyable",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        (
            "post_executed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            "live_order_once_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "private_api_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        ("broker_called", True, LiveOrderRealApprovalGatePlanBlockReason.BROKER_ALREADY_CALLED),
        (
            "read_only_api_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        ("symbol", "EUR_USD", LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SYMBOL),
        ("side", "NO_TRADE", LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SIDE),
        ("size", 200, LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SIZE),
        (
            "execution_type",
            "LIMIT",
            LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        ),
        (
            "post_attempt_limit",
            2,
            LiveOrderRealApprovalGatePlanBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        ),
        ("retry_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.RETRY_ALLOWED),
        ("loop_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.ADD_ORDER_ALLOWED),
        (
            "change_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            "cancel_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            "close_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CLOSE_ORDER_ALLOWED,
        ),
        (
            "post_reconciliation_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        ),
    ),
)
def test_checkpoint_mismatch_or_unsafe_flag_blocks_plan(
    field_name: str,
    value: object,
    reason: LiveOrderRealApprovalGatePlanBlockReason,
) -> None:
    unsafe_checkpoint = _unchecked(_checkpoint().checkpoint, **{field_name: value})

    _assert_blocked(reason, real_approval_readiness_checkpoint=unsafe_checkpoint)


@pytest.mark.parametrize(
    ("override_name", "value", "reason"),
    (
        (
            "explicit_user_confirmation_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.EXPLICIT_USER_CONFIRMATION_NOT_REQUIRED,
        ),
        (
            "real_approval_gate_separate_step_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.REAL_APPROVAL_GATE_NOT_SEPARATE_STEP,
        ),
        (
            "fresh_preflight_before_gate_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        ),
        (
            "approval_id_generation_after_fresh_preflight_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        ),
        (
            "approval_command_generation_after_fresh_preflight_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        ),
        (
            "post_approval_final_dynamic_preflight_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.POST_APPROVAL_FINAL_PREFLIGHT_NOT_REQUIRED,
        ),
        (
            "one_shot_post_separate_step_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.ONE_SHOT_POST_NOT_SEPARATE_STEP,
        ),
        (
            "post_reconciliation_separate_step_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.POST_RECONCILIATION_NOT_SEPARATE_STEP,
        ),
        (
            "final_report_separate_step_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.FINAL_REPORT_NOT_SEPARATE_STEP,
        ),
        (
            "approval_gate_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            "approval_gate_issued",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_id_generated",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_command_generated",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_command_template_only",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
        ),
        (
            "approval_command_copyable",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        ("ttl_seconds", 301, LiveOrderRealApprovalGatePlanBlockReason.INVALID_TTL_SECONDS),
        (
            "exact_match_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.EXACT_MATCH_NOT_REQUIRED,
        ),
        (
            "same_session_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.SAME_SESSION_NOT_REQUIRED,
        ),
        (
            "required_ack_tokens",
            APPROVAL_ACK_TOKENS[:-1],
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_REQUIRED_ACK_TOKEN,
        ),
        ("dry_run_only", False, LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_NOT_DRY_RUN),
        (
            "post_attempt_limit",
            2,
            LiveOrderRealApprovalGatePlanBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        ),
        (
            "post_executed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            "live_order_once_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "private_api_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        ("broker_called", True, LiveOrderRealApprovalGatePlanBlockReason.BROKER_ALREADY_CALLED),
        (
            "read_only_api_called",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        ("retry_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.RETRY_ALLOWED),
        ("loop_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", True, LiveOrderRealApprovalGatePlanBlockReason.ADD_ORDER_ALLOWED),
        (
            "change_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            "cancel_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            "close_order_allowed",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CLOSE_ORDER_ALLOWED,
        ),
        (
            "post_reconciliation_required",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        ),
    ),
)
def test_plan_safety_constraint_failure_blocks(
    override_name: str,
    value: object,
    reason: LiveOrderRealApprovalGatePlanBlockReason,
) -> None:
    _assert_blocked(reason, **{override_name: value})


def test_missing_required_phase_blocks_without_removing_output_default_phases() -> None:
    phases = tuple(
        phase
        for phase in build_default_real_approval_gate_plan_phases()
        if phase.phase_id != "future_post_reconciliation"
    )
    result = _plan(phases=phases)

    assert LiveOrderRealApprovalGatePlanBlockReason.MISSING_REQUIRED_PHASE.value in (
        result.blocked_reasons
    )
    assert {phase.phase_id for phase in result.plan.phases} == set(
        REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS
    )


@pytest.mark.parametrize(
    ("override_name", "reason"),
    (
        (
            "go_conditions",
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_GO_CONDITIONS,
        ),
        (
            "no_go_conditions",
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_NO_GO_CONDITIONS,
        ),
        (
            "stop_conditions",
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_STOP_CONDITIONS,
        ),
    ),
)
def test_missing_plan_conditions_block_but_output_defaults_remain(
    override_name: str,
    reason: LiveOrderRealApprovalGatePlanBlockReason,
) -> None:
    result = _plan(**{override_name: ()})

    assert reason.value in result.blocked_reasons
    assert result.plan.go_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS
    assert result.plan.no_go_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS
    assert result.plan.stop_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS


def test_go_no_go_stop_conditions_and_phases_include_required_future_sequence() -> None:
    plan = _plan().plan

    assert plan.go_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS
    assert plan.no_go_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS
    assert plan.stop_conditions == DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS
    assert {phase.phase_id for phase in plan.phases} == set(
        REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS
    )
    assert "fresh preflight before gate is required" in plan.go_conditions
    assert "any approval artifact already generated" in plan.no_go_conditions
    assert "any need to exceed one POST attempt" in plan.stop_conditions


def test_check_results_include_required_real_approval_gate_plan_checks() -> None:
    check_names = {check.name for check in _plan().plan.check_results}

    assert "readiness_checkpoint_ready" in check_names
    assert "allowed_for_live_false" in check_names
    assert "real_approval_gate_separate_step" in check_names
    assert "fresh_preflight_before_gate_required" in check_names
    assert "approval_id_generation_deferred" in check_names
    assert "approval_command_generation_deferred" in check_names
    assert "exact_match_required" in check_names
    assert "same_session_required" in check_names
    assert "ttl_300" in check_names
    assert "required_ack_tokens_present" in check_names
    assert "final_dynamic_preflight_after_approval_required" in check_names
    assert "one_shot_constraints_preserved" in check_names
    assert "no_approval_artifacts_generated" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "post_not_executed" in check_names


def test_markdown_rendering_includes_required_no_api_no_approval_warnings() -> None:
    markdown = render_live_order_real_approval_gate_plan_markdown(_plan().plan)

    assert "This real approval gate plan is dry-run only." in markdown
    assert "This plan does not call read-only API." in markdown
    assert "This plan does not call Private API." in markdown
    assert "This plan does not call live_order_once." in markdown
    assert "This plan does not execute HTTP POST." in markdown
    assert "This plan does not issue a real approval gate." in markdown
    assert "This plan does not generate a real approval_id." in markdown
    assert "This plan does not generate a real approval command." in markdown
    assert "This plan does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_gate_plan_markdown(_plan().plan)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_response_marker",
        "forbidden_order_marker",
        "forbidden_approval_marker",
        "forbidden_clipboard_marker",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    plan = _plan().plan
    serialized = str(asdict(plan))
    rendered = repr(plan)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_response_marker",
        "forbidden_order_marker",
        "forbidden_approval_marker",
        "forbidden_clipboard_marker",
    )

    for value in forbidden_values:
        assert value not in serialized
        assert value not in rendered


def test_builder_does_not_accept_forbidden_real_api_or_approval_fields() -> None:
    forbidden_kwargs = {
        "api_key": "x",
        "secret": "x",
        "headers": {"x": "y"},
        "raw_request": "x",
        "raw_response": "x",
        "order_id": "x",
        "execution_id": "x",
        "position_id": "x",
        "clientOrderId": "x",
        "approval_id": "x",
        "approval_command": "x",
        "pbcopy": True,
        "ledger_path": "x",
    }
    params = set(signature(build_live_order_real_approval_gate_plan).parameters)

    for key in forbidden_kwargs:
        assert key not in params


def test_plan_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_real_approval_gate_plan as module

    module_names = set(module.__dict__)

    assert "requests" not in module_names
    assert "httpx" not in module_names
    assert "aiohttp" not in module_names
    assert "urllib" not in module_names
    assert "socket" not in module_names
    assert "subprocess" not in module_names
    assert "private_api" not in module_names
    assert "brokers" not in module_names
    assert "live_order_once" not in module_names
    assert "pbcopy" not in module_names
