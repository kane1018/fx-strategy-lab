from __future__ import annotations

from dataclasses import asdict, replace

from app.live_verification.live_order_execution_runbook import (
    LIVE_ORDER_ONE_SHOT_EXECUTION_RUNBOOK_ID_PREFIX,
    REQUIRED_GO_CONDITIONS,
    REQUIRED_NO_GO_CONDITIONS,
    REQUIRED_PHASE_NAMES,
    REQUIRED_STOP_CONDITIONS,
    LiveOrderOneShotExecutionRunbookBlockReason,
    LiveOrderOneShotExecutionRunbookStatus,
    build_default_one_shot_execution_runbook_phases,
    build_live_order_one_shot_execution_runbook,
    render_live_order_one_shot_execution_runbook_markdown,
)
from app.live_verification.live_order_one_shot_boundary import (
    LiveOrderOneShotBoundaryDecision,
)
from app.tests.test_live_verification_live_order_final_dynamic_preflight import (
    CREATED_AT,
    _evaluate,
    _unchecked,
)
from app.tests.test_live_verification_live_order_one_shot_boundary import _boundary


def _ready_boundary(**overrides: object) -> LiveOrderOneShotBoundaryDecision:
    decision = _boundary().decision
    return _unchecked(decision, **overrides)


def _runbook(
    *,
    boundary: LiveOrderOneShotBoundaryDecision | None = None,
    **overrides: object,
):
    return build_live_order_one_shot_execution_runbook(
        one_shot_boundary_decision=boundary or _ready_boundary(),
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderOneShotExecutionRunbookBlockReason | str,
    *,
    boundary: LiveOrderOneShotBoundaryDecision | None = None,
    **overrides: object,
) -> None:
    result = _runbook(boundary=boundary, **overrides)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderOneShotExecutionRunbookBlockReason)
        else reason
    )

    assert (
        result.runbook_status
        is LiveOrderOneShotExecutionRunbookStatus.BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK
    )
    assert result.runbook_ready is False
    assert result.eligible_for_future_execution_planning is False
    assert result.allowed_for_live is False
    assert expected in result.blocked_reasons


def test_passed_boundary_and_safe_constraints_are_runbook_ready() -> None:
    result = _runbook()
    runbook = result.runbook

    assert runbook.runbook_id.startswith(LIVE_ORDER_ONE_SHOT_EXECUTION_RUNBOOK_ID_PREFIX)
    assert (
        runbook.runbook_status
        is LiveOrderOneShotExecutionRunbookStatus.READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW
    )
    assert runbook.runbook_ready is True
    assert runbook.eligible_for_future_execution_planning is True
    assert runbook.allowed_for_live is False
    assert runbook.post_attempt_limit == 1
    assert runbook.post_executed is False
    assert runbook.blocked_reasons == ()
    assert result.recommended_next_step == (
        "review_runbook_then_prepare_future_real_approval_gate_separate_step_no_post"
    )


def test_safety_defaults_are_fixed_and_ready_is_not_post_permission() -> None:
    runbook = _runbook().runbook

    assert runbook.allowed_for_live is False
    assert runbook.requires_human_approval is True
    assert runbook.approval_gate_required is True
    assert runbook.approval_gate_issued is False
    assert runbook.approval_id_generated is False
    assert runbook.approval_command_generated is False
    assert runbook.approval_command_template_only is True
    assert runbook.approval_command_copyable is False
    assert runbook.final_dynamic_preflight_required is True
    assert runbook.dry_run_only is True
    assert runbook.live_order_once_called is False
    assert runbook.private_api_called is False
    assert runbook.broker_called is False
    assert runbook.read_only_api_called is False
    assert runbook.retry_allowed is False
    assert runbook.loop_allowed is False
    assert runbook.add_order_allowed is False
    assert runbook.change_order_allowed is False
    assert runbook.cancel_order_allowed is False
    assert runbook.close_order_allowed is False
    assert runbook.post_reconciliation_required is True


def test_blocked_boundary_blocks_and_preserves_boundary_reasons() -> None:
    blocked_boundary = _boundary(preflight=_evaluate(spread_jpy=0.02).decision).decision
    result = _runbook(boundary=blocked_boundary)

    assert (
        result.runbook_status
        is LiveOrderOneShotExecutionRunbookStatus.BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK
    )
    assert "spread_too_wide" in result.blocked_reasons
    assert (
        LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_NOT_READY.value
        in result.blocked_reasons
    )
    assert result.recommended_next_step == "fix_one_shot_boundary_blockers_no_post"


def test_boundary_unsafe_flags_block() -> None:
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_ALLOWS_LIVE,
        boundary=_ready_boundary(allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_NOT_DRY_RUN,
        boundary=_ready_boundary(dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        boundary=_ready_boundary(approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        boundary=_ready_boundary(approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        boundary=_ready_boundary(approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.POST_ALREADY_EXECUTED,
        boundary=_ready_boundary(post_executed=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        boundary=_ready_boundary(live_order_once_called=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.PRIVATE_API_ALREADY_CALLED,
        boundary=_ready_boundary(private_api_called=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.BROKER_ALREADY_CALLED,
        boundary=_ready_boundary(broker_called=True),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.READ_ONLY_API_ALREADY_CALLED,
        boundary=_ready_boundary(read_only_api_called=True),
    )


def test_unsupported_order_shape_blocks() -> None:
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SYMBOL,
        boundary=_ready_boundary(symbol="EUR_USD"),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SIDE,
        boundary=_ready_boundary(side="NO_TRADE"),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SIZE,
        boundary=_ready_boundary(size=200),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        boundary=_ready_boundary(execution_type="LIMIT"),
    )


def test_runbook_one_shot_mutation_flags_block() -> None:
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        post_attempt_limit=2,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.POST_ALREADY_EXECUTED,
        post_executed=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        live_order_once_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.PRIVATE_API_ALREADY_CALLED,
        private_api_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.BROKER_ALREADY_CALLED,
        broker_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.READ_ONLY_API_ALREADY_CALLED,
        read_only_api_called=True,
    )


def test_retry_loop_and_order_mutation_flags_block() -> None:
    _assert_blocked(LiveOrderOneShotExecutionRunbookBlockReason.RETRY_ALLOWED, retry_allowed=True)
    _assert_blocked(LiveOrderOneShotExecutionRunbookBlockReason.LOOP_ALLOWED, loop_allowed=True)
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.ADD_ORDER_ALLOWED,
        add_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.CHANGE_ORDER_ALLOWED,
        change_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.CANCEL_ORDER_ALLOWED,
        cancel_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.CLOSE_ORDER_ALLOWED,
        close_order_allowed=True,
    )


def test_post_reconciliation_requirement_blocks_when_missing() -> None:
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        post_reconciliation_required=False,
    )


def test_required_phases_are_generated() -> None:
    runbook = _runbook().runbook
    phase_names = {phase.name for phase in runbook.phases}

    assert set(REQUIRED_PHASE_NAMES).issubset(phase_names)


def test_missing_required_phase_blocks() -> None:
    phases = tuple(
        phase
        for phase in build_default_one_shot_execution_runbook_phases()
        if phase.name != "final_report_and_stop"
    )

    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_REQUIRED_PHASE,
        phases=phases,
    )


def test_phase_with_forbidden_allowed_action_blocks() -> None:
    phases = build_default_one_shot_execution_runbook_phases()
    unsafe_phase = replace(phases[0], allowed_actions=("execute_http_post",))

    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.PHASE_CONTAINS_FORBIDDEN_ACTION,
        phases=(unsafe_phase, *phases[1:]),
    )


def test_missing_phase_go_no_go_or_stop_conditions_block() -> None:
    phases = build_default_one_shot_execution_runbook_phases()

    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_GO_CONDITIONS,
        phases=(replace(phases[0], go_conditions=()), *phases[1:]),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_NO_GO_CONDITIONS,
        phases=(replace(phases[0], no_go_conditions=()), *phases[1:]),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_STOP_CONDITIONS,
        phases=(replace(phases[0], stop_conditions=()), *phases[1:]),
    )


def test_missing_global_go_no_go_or_stop_conditions_block() -> None:
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_GO_CONDITIONS,
        go_conditions=(),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_NO_GO_CONDITIONS,
        no_go_conditions=(),
    )
    _assert_blocked(
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_STOP_CONDITIONS,
        stop_conditions=(),
    )


def test_go_no_go_and_stop_conditions_include_required_constraints() -> None:
    runbook = _runbook().runbook

    assert set(REQUIRED_GO_CONDITIONS).issubset(set(runbook.go_conditions))
    assert set(REQUIRED_NO_GO_CONDITIONS).issubset(set(runbook.no_go_conditions))
    assert set(REQUIRED_STOP_CONDITIONS).issubset(set(runbook.stop_conditions))


def test_check_results_cover_boundary_phases_conditions_and_execution_flags() -> None:
    check_names = {check.name for check in _runbook().runbook.check_results}

    assert "one_shot_boundary_decision" in check_names
    assert "boundary_allowed_for_live" in check_names
    assert "post_attempt_limit" in check_names
    assert "post_not_executed" in check_names
    assert "live_order_once_not_called" in check_names
    assert "private_api_not_called" in check_names
    assert "broker_not_called" in check_names
    assert "read_only_api_not_called" in check_names
    assert "required_phases" in check_names
    assert "phase_allowed_actions_safe" in check_names
    assert "go_conditions" in check_names
    assert "no_go_conditions" in check_names
    assert "stop_conditions" in check_names


def test_markdown_rendering_includes_required_dry_run_warnings() -> None:
    markdown = render_live_order_one_shot_execution_runbook_markdown(_runbook().runbook)

    assert "This one-shot execution runbook is dry-run only." in markdown
    assert "This runbook does not call read-only API." in markdown
    assert "This runbook does not call Private API." in markdown
    assert "This runbook does not call live_order_once." in markdown
    assert "This runbook does not execute HTTP POST." in markdown
    assert "This runbook does not issue a real approval gate." in markdown
    assert "This runbook does not generate a real approval command." in markdown
    assert "This runbook does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_one_shot_execution_runbook_markdown(_runbook().runbook)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_signing_marker",
        "forbidden_header_marker",
        "forbidden_response_marker",
        "forbidden_order_marker",
        "forbidden_approval_marker",
        "forbidden_clipboard_marker",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    runbook = _runbook().runbook
    serialized = str(asdict(runbook))
    rendered = repr(runbook)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_signing_marker",
        "forbidden_header_marker",
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
        "clipboard_copy_command": True,
        "ledger_path": "x",
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_one_shot_execution_runbook(
                one_shot_boundary_decision=_ready_boundary(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_runbook_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_execution_runbook as module

    module_names = set(module.__dict__)

    assert "requests" not in module_names
    assert "httpx" not in module_names
    assert "aiohttp" not in module_names
    assert "urllib" not in module_names
    assert "socket" not in module_names
    assert "subprocess" not in module_names
    assert "private_api" not in module_names
    assert "brokers" not in module_names
    assert "pbcopy" not in module_names
