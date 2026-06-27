from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_enablement_criteria import (
    DEFAULT_REAL_APPROVAL_COMMAND_GENERATION_CONDITIONS,
    DEFAULT_REAL_APPROVAL_ENABLEMENT_CRITERIA_FUTURE_ENABLEMENT_REQUIREMENTS,
    DEFAULT_REAL_APPROVAL_ENABLEMENT_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_ENABLEMENT_KILL_SWITCH_CONDITIONS,
    DEFAULT_REAL_APPROVAL_ENABLEMENT_NO_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_ID_GENERATION_CONDITIONS,
    LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_CRITERIA_ID_PREFIX,
    LiveOrderRealApprovalEnablementCriteriaBlockReason,
    LiveOrderRealApprovalEnablementCriteriaStatus,
    build_live_order_real_approval_enablement_criteria,
    render_live_order_real_approval_enablement_criteria_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_disabled_scaffold import (
    _scaffold as _disabled_scaffold,
)

CriteriaStatus = LiveOrderRealApprovalEnablementCriteriaStatus
BlockReason = LiveOrderRealApprovalEnablementCriteriaBlockReason


def _criteria(*, scaffold=None, **overrides: object):
    actual_scaffold = scaffold or _disabled_scaffold().scaffold
    return build_live_order_real_approval_enablement_criteria(
        disabled_scaffold=actual_scaffold,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalEnablementCriteriaBlockReason | str,
    *,
    scaffold=None,
    **overrides: object,
) -> None:
    result = _criteria(scaffold=scaffold, **overrides)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.criteria_status is CriteriaStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA
    assert result.criteria_ready is False
    assert (
        result.eligible_for_future_real_approval_gate_enablement_planning is False
    )
    assert result.allowed_for_live is False
    assert result.approval_gate_enabled is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.approval_command_executable is False
    assert result.usable_approval_artifacts_generated is False
    assert result.real_approval_artifacts_available is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert expected in result.blocked_reasons


def test_ready_disabled_scaffold_builds_enablement_criteria_only() -> None:
    result = _criteria()
    criteria = result.criteria

    assert criteria.criteria_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_CRITERIA_ID_PREFIX
    )
    assert (
        criteria.criteria_status
        is CriteriaStatus.READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW
    )
    assert criteria.criteria_ready is True
    assert (
        criteria.eligible_for_future_real_approval_gate_enablement_planning is True
    )
    assert criteria.allowed_for_live is False
    assert criteria.approval_gate_enabled is False
    assert criteria.blocked_reasons == ()
    assert result.recommended_next_step == (
        "review_enablement_criteria_then_stop_before_any_real_enablement_or_approval_artifact_generation"
    )


def test_ready_criteria_never_enables_gate_or_real_approval_artifacts() -> None:
    criteria = _criteria().criteria

    assert criteria.allowed_for_live is False
    assert criteria.approval_gate_enabled is False
    assert criteria.approval_gate_enablement_planned is True
    assert criteria.approval_gate_enablement_deferred_to_future_step is True
    assert criteria.approval_gate_issued is False
    assert criteria.approval_id_generation_planned is True
    assert criteria.approval_id_generation_deferred_to_future_step is True
    assert criteria.approval_id_generated is False
    assert criteria.approval_command_generation_planned is True
    assert criteria.approval_command_generation_deferred_to_future_step is True
    assert criteria.approval_command_generated is False
    assert criteria.approval_command_template_only is True
    assert criteria.approval_command_copyable is False
    assert criteria.approval_command_executable is False
    assert criteria.usable_approval_artifacts_generated is False
    assert criteria.real_approval_artifacts_available is False
    assert criteria.requires_human_approval is True
    assert criteria.explicit_user_confirmation_required is True
    assert criteria.fresh_preflight_before_enablement_required is True
    assert criteria.implementation_readiness_review_required is True
    assert criteria.post_enablement_safety_review_required is True
    assert criteria.post_approval_final_dynamic_preflight_required is True
    assert criteria.one_shot_post_separate_step_required is True
    assert criteria.post_reconciliation_separate_step_required is True
    assert criteria.final_report_separate_step_required is True
    assert criteria.dry_run_only is True
    assert criteria.post_attempt_limit == 1
    assert criteria.post_executed is False
    assert criteria.live_order_once_called is False
    assert criteria.private_api_called is False
    assert criteria.broker_called is False
    assert criteria.read_only_api_called is False
    assert criteria.public_api_called is False
    assert criteria.retry_allowed is False
    assert criteria.loop_allowed is False
    assert criteria.add_order_allowed is False
    assert criteria.change_order_allowed is False
    assert criteria.cancel_order_allowed is False
    assert criteria.close_order_allowed is False
    assert criteria.post_reconciliation_required is True


def test_criteria_constraints_are_fixed_to_step5x_spec() -> None:
    criteria = _criteria().criteria

    assert criteria.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert criteria.exact_match_required is True
    assert criteria.same_session_required is True
    assert criteria.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert criteria.future_enablement_requirements == (
        DEFAULT_REAL_APPROVAL_ENABLEMENT_CRITERIA_FUTURE_ENABLEMENT_REQUIREMENTS
    )
    assert criteria.enablement_go_conditions == (
        DEFAULT_REAL_APPROVAL_ENABLEMENT_GO_CONDITIONS
    )
    assert criteria.enablement_no_go_conditions == (
        DEFAULT_REAL_APPROVAL_ENABLEMENT_NO_GO_CONDITIONS
    )
    assert criteria.kill_switch_conditions == (
        DEFAULT_REAL_APPROVAL_ENABLEMENT_KILL_SWITCH_CONDITIONS
    )
    assert criteria.approval_id_generation_conditions == (
        DEFAULT_REAL_APPROVAL_ID_GENERATION_CONDITIONS
    )
    assert criteria.approval_command_generation_conditions == (
        DEFAULT_REAL_APPROVAL_COMMAND_GENERATION_CONDITIONS
    )


def test_future_enablement_conditions_are_specific_and_separate() -> None:
    criteria = _criteria().criteria

    assert "explicit future user instruction required" in (
        criteria.future_enablement_requirements
    )
    assert "fresh pre-approval preflight must be re-run" in (
        criteria.future_enablement_requirements
    )
    assert "disabled scaffold must be rechecked" in (
        criteria.future_enablement_requirements
    )
    assert "approval_gate_enabled may only change in a future explicit step" in (
        criteria.future_enablement_requirements
    )
    assert "disabled scaffold ready" in criteria.enablement_go_conditions
    assert "approval_gate_enabled already true" in criteria.enablement_no_go_conditions
    assert "TTL cannot be enforced" in criteria.kill_switch_conditions
    assert "future explicit approval gate enablement step only" in (
        criteria.approval_id_generation_conditions
    )
    assert "no extra tokens / no line breaks / no copyable text before future step" in (
        criteria.approval_command_generation_conditions
    )


def test_blocked_disabled_scaffold_blocks_and_preserves_reasons() -> None:
    scaffold = _disabled_scaffold(post_attempt_limit=2).scaffold
    result = _criteria(scaffold=scaffold)

    assert result.criteria_status is CriteriaStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA
    assert result.criteria_ready is False
    assert "invalid_post_attempt_limit" in result.blocked_reasons
    assert result.recommended_next_step == "fix_disabled_scaffold_blockers_no_post"


def test_missing_disabled_scaffold_blocks() -> None:
    result = build_live_order_real_approval_enablement_criteria(
        disabled_scaffold=None,
        created_at=CREATED_AT,
    )

    assert BlockReason.MISSING_DISABLED_SCAFFOLD.value in result.blocked_reasons
    assert result.criteria_status is CriteriaStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA


def test_scaffold_readiness_and_safety_flags_block() -> None:
    scaffold = _disabled_scaffold().scaffold

    _assert_blocked(
        BlockReason.DISABLED_SCAFFOLD_NOT_READY,
        scaffold=_disabled_scaffold(post_attempt_limit=2).scaffold,
    )
    _assert_blocked(
        BlockReason.DISABLED_SCAFFOLD_NOT_ELIGIBLE,
        scaffold=_unchecked(scaffold, eligible_for_future_enablement_planning=False),
    )
    _assert_blocked(
        BlockReason.SCAFFOLD_ALLOWS_LIVE,
        scaffold=_unchecked(scaffold, allowed_for_live=True),
    )
    _assert_blocked(
        BlockReason.SCAFFOLD_APPROVAL_GATE_ENABLED,
        scaffold=_unchecked(scaffold, approval_gate_enabled=True),
    )
    _assert_blocked(
        BlockReason.SCAFFOLD_NOT_DRY_RUN,
        scaffold=_unchecked(scaffold, dry_run_only=False),
    )


def test_real_artifact_generation_flags_block() -> None:
    scaffold = _disabled_scaffold().scaffold

    _assert_blocked(
        BlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        scaffold=_unchecked(scaffold, approval_gate_issued=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_ALREADY_GENERATED,
        scaffold=_unchecked(scaffold, approval_id_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        scaffold=_unchecked(scaffold, approval_command_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_COPYABLE,
        scaffold=_unchecked(scaffold, approval_command_copyable=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_EXECUTABLE,
        scaffold=_unchecked(scaffold, approval_command_executable=True),
    )
    _assert_blocked(
        BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED,
        scaffold=_unchecked(scaffold, usable_approval_artifacts_generated=True),
    )
    _assert_blocked(
        BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        scaffold=_unchecked(scaffold, real_approval_artifacts_available=True),
    )


def test_unsupported_order_shape_blocks() -> None:
    scaffold = _disabled_scaffold().scaffold

    _assert_blocked(
        BlockReason.UNSUPPORTED_SYMBOL,
        scaffold=_unchecked(scaffold, symbol="EUR_USD"),
    )
    _assert_blocked(
        BlockReason.UNSUPPORTED_SIDE,
        scaffold=_unchecked(scaffold, side="NO_TRADE"),
    )
    _assert_blocked(BlockReason.UNSUPPORTED_SIZE, scaffold=_unchecked(scaffold, size=200))
    _assert_blocked(
        BlockReason.UNSUPPORTED_EXECUTION_TYPE,
        scaffold=_unchecked(scaffold, execution_type="LIMIT"),
    )


def test_ttl_match_session_ack_and_display_constraints_block_when_unsafe() -> None:
    scaffold = _disabled_scaffold().scaffold

    _assert_blocked(
        BlockReason.INVALID_TTL_SECONDS,
        scaffold=_unchecked(scaffold, ttl_seconds=301),
    )
    _assert_blocked(
        BlockReason.EXACT_MATCH_NOT_REQUIRED,
        scaffold=_unchecked(scaffold, exact_match_required=False),
    )
    _assert_blocked(
        BlockReason.SAME_SESSION_NOT_REQUIRED,
        scaffold=_unchecked(scaffold, same_session_required=False),
    )
    _assert_blocked(
        BlockReason.MISSING_ACK_TOKEN,
        scaffold=_unchecked(scaffold, required_ack_tokens=APPROVAL_ACK_TOKENS[:-1]),
    )
    _assert_blocked(
        BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE,
        scaffold=_unchecked(scaffold, display_forbidden_fields=("raw response",)),
    )


def test_no_api_post_and_one_shot_constraints_block_when_unsafe() -> None:
    scaffold = _disabled_scaffold().scaffold

    _assert_blocked(
        BlockReason.POST_ALREADY_EXECUTED,
        scaffold=_unchecked(scaffold, post_executed=True),
    )
    _assert_blocked(
        BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        scaffold=_unchecked(scaffold, live_order_once_called=True),
    )
    _assert_blocked(
        BlockReason.PRIVATE_API_ALREADY_CALLED,
        scaffold=_unchecked(scaffold, private_api_called=True),
    )
    _assert_blocked(
        BlockReason.BROKER_ALREADY_CALLED,
        scaffold=_unchecked(scaffold, broker_called=True),
    )
    _assert_blocked(
        BlockReason.READ_ONLY_API_ALREADY_CALLED,
        scaffold=_unchecked(scaffold, read_only_api_called=True),
    )
    _assert_blocked(
        BlockReason.PUBLIC_API_ALREADY_CALLED,
        scaffold=_unchecked(scaffold, public_api_called=True),
    )
    _assert_blocked(BlockReason.INVALID_POST_ATTEMPT_LIMIT, post_attempt_limit=2)
    _assert_blocked(BlockReason.RETRY_ALLOWED, retry_allowed=True)
    _assert_blocked(BlockReason.LOOP_ALLOWED, loop_allowed=True)
    _assert_blocked(BlockReason.ADD_ORDER_ALLOWED, add_order_allowed=True)
    _assert_blocked(BlockReason.CHANGE_ORDER_ALLOWED, change_order_allowed=True)
    _assert_blocked(BlockReason.CANCEL_ORDER_ALLOWED, cancel_order_allowed=True)
    _assert_blocked(BlockReason.CLOSE_ORDER_ALLOWED, close_order_allowed=True)
    _assert_blocked(
        BlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        post_reconciliation_required=False,
    )


def test_enablement_flags_block_but_output_stays_disabled() -> None:
    result = _criteria(
        approval_gate_enabled=True,
        approval_gate_enablement_deferred_to_future_step=False,
    )

    assert BlockReason.APPROVAL_GATE_ENABLED.value in result.blocked_reasons
    assert (
        BlockReason.APPROVAL_GATE_ENABLEMENT_NOT_DEFERRED.value
        in result.blocked_reasons
    )
    assert result.approval_gate_enabled is False
    assert result.criteria.approval_gate_enablement_deferred_to_future_step is True


def test_condition_lists_are_required() -> None:
    _assert_blocked(
        BlockReason.MISSING_FUTURE_ENABLEMENT_REQUIREMENTS,
        future_enablement_requirements=(),
    )
    _assert_blocked(
        BlockReason.MISSING_ENABLEMENT_GO_CONDITIONS,
        enablement_go_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_ENABLEMENT_NO_GO_CONDITIONS,
        enablement_no_go_conditions=(),
    )
    _assert_blocked(BlockReason.MISSING_KILL_SWITCH_CONDITIONS, kill_switch_conditions=())
    _assert_blocked(
        BlockReason.MISSING_APPROVAL_ID_GENERATION_CONDITIONS,
        approval_id_generation_conditions=(),
    )
    _assert_blocked(
        BlockReason.MISSING_APPROVAL_COMMAND_GENERATION_CONDITIONS,
        approval_command_generation_conditions=(),
    )


def test_check_results_cover_required_enablement_criteria_checks() -> None:
    check_names = {check.name for check in _criteria().criteria.check_results}

    assert "disabled_scaffold_ready" in check_names
    assert "approval_gate_enabled_false" in check_names
    assert "allowed_for_live_false" in check_names
    assert "no_usable_approval_artifacts" in check_names
    assert "approval_gate_not_issued" in check_names
    assert "approval_id_not_generated" in check_names
    assert "approval_command_not_generated" in check_names
    assert "approval_command_not_copyable" in check_names
    assert "approval_command_not_executable" in check_names
    assert "future_enablement_deferred" in check_names
    assert "approval_id_generation_deferred" in check_names
    assert "approval_command_generation_deferred" in check_names
    assert "ttl_seconds_300" in check_names
    assert "exact_match_required" in check_names
    assert "same_session_required" in check_names
    assert "required_ack_tokens_present" in check_names
    assert "display_forbidden_fields_include_secrets_raw_ids_real_commands" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "post_not_executed" in check_names
    assert "one_shot_constraints_preserved" in check_names
    assert "future_enablement_requirements_present" in check_names
    assert "go_conditions_present" in check_names
    assert "no_go_conditions_present" in check_names
    assert "kill_switch_conditions_present" in check_names
    assert "approval_id_generation_conditions_present" in check_names
    assert "approval_command_generation_conditions_present" in check_names


def test_display_forbidden_fields_include_credential_raw_id_and_real_command_terms() -> None:
    fields_text = " ".join(_criteria().criteria.display_forbidden_fields).lower()

    assert "api key" in fields_text
    assert "secret" in fields_text
    assert "signature" in fields_text
    assert "headers" in fields_text
    assert "raw request" in fields_text
    assert "raw response" in fields_text
    assert "order id" in fields_text
    assert "execution id" in fields_text
    assert "position id" in fields_text
    assert "clientorderid" in fields_text
    assert "real approval_id" in fields_text
    assert "real approval command" in fields_text
    assert "copyable approval command" in fields_text
    assert "approval command file" in fields_text
    assert "clipboard approval command" in fields_text


def test_markdown_rendering_includes_required_disabled_no_api_warnings() -> None:
    markdown = render_live_order_real_approval_enablement_criteria_markdown(
        _criteria().criteria
    )

    assert "This real approval gate enablement criteria model is dry-run only." in markdown
    assert "This criteria model does not enable a real approval gate." in markdown
    assert "This criteria model keeps approval_gate_enabled=false." in markdown
    assert "This criteria model does not call read-only API." in markdown
    assert "This criteria model does not call Private API." in markdown
    assert "This criteria model does not call live_order_once." in markdown
    assert "This criteria model does not execute HTTP POST." in markdown
    assert "This criteria model does not issue a real approval gate." in markdown
    assert "This criteria model does not generate a real approval_id." in markdown
    assert "This criteria model does not generate a real approval command." in markdown
    assert "This criteria model does not provide copyable approval text." in markdown
    assert "This criteria model does not authorize live POST." in markdown
    assert "approval_gate_enabled=false." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_lists_conditions_without_real_approval_command_values() -> None:
    markdown = render_live_order_real_approval_enablement_criteria_markdown(
        _criteria().criteria
    )

    assert "## Enablement Go Conditions" in markdown
    assert "## Enablement No-Go Conditions" in markdown
    assert "## Kill Switch Conditions" in markdown
    assert "## Approval ID Generation Conditions" in markdown
    assert "## Approval Command Generation Conditions" in markdown
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
    criteria = _criteria().criteria
    serialized = str(asdict(criteria))
    rendered = repr(criteria)
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
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_real_approval_enablement_criteria(
                disabled_scaffold=_disabled_scaffold().scaffold,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_enablement_criteria_has_no_ordering_api_or_clipboard_dependencies() -> None:
    import app.live_verification.live_order_real_approval_enablement_criteria as module

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
