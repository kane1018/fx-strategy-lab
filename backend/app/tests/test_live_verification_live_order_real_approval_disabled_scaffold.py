from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_disabled_scaffold import (
    DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_DISABLED_REASONS,
    DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_FUTURE_ENABLEMENT_REQUIREMENTS,
    LIVE_ORDER_REAL_APPROVAL_DISABLED_SCAFFOLD_ID_PREFIX,
    LiveOrderRealApprovalDisabledScaffoldBlockReason,
    LiveOrderRealApprovalDisabledScaffoldStatus,
    build_live_order_real_approval_disabled_scaffold,
    render_live_order_real_approval_disabled_scaffold_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_implementation_readiness import (
    _review as _implementation_readiness_review,
)

ScaffoldStatus = LiveOrderRealApprovalDisabledScaffoldStatus
BlockReason = LiveOrderRealApprovalDisabledScaffoldBlockReason


def _scaffold(*, review=None, **overrides: object):
    actual_review = review or _implementation_readiness_review().review
    return build_live_order_real_approval_disabled_scaffold(
        implementation_readiness_review=actual_review,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalDisabledScaffoldBlockReason | str,
    *,
    review=None,
    **overrides: object,
) -> None:
    result = _scaffold(review=review, **overrides)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert (
        result.scaffold_status
        is ScaffoldStatus.BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD
    )
    assert result.scaffold_ready is False
    assert result.eligible_for_future_enablement_planning is False
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


def test_ready_readiness_review_builds_disabled_scaffold_only() -> None:
    result = _scaffold()
    scaffold = result.scaffold

    assert scaffold.scaffold_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_DISABLED_SCAFFOLD_ID_PREFIX
    )
    assert (
        scaffold.scaffold_status
        is ScaffoldStatus.READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW
    )
    assert scaffold.scaffold_ready is True
    assert scaffold.eligible_for_future_enablement_planning is True
    assert scaffold.allowed_for_live is False
    assert scaffold.approval_gate_enabled is False
    assert scaffold.blocked_reasons == ()
    assert result.recommended_next_step == (
        "review_disabled_scaffold_then_stop_before_any_real_approval_artifact_generation"
    )


def test_ready_scaffold_never_authorizes_real_approval_artifacts_or_post() -> None:
    scaffold = _scaffold().scaffold

    assert scaffold.allowed_for_live is False
    assert scaffold.approval_gate_enabled is False
    assert scaffold.approval_gate_required is True
    assert scaffold.approval_gate_planned is True
    assert scaffold.approval_gate_issued is False
    assert scaffold.approval_id_generation_planned is True
    assert scaffold.approval_id_generation_deferred_to_future_step is True
    assert scaffold.approval_id_generated is False
    assert scaffold.approval_command_generation_planned is True
    assert scaffold.approval_command_generation_deferred_to_future_step is True
    assert scaffold.approval_command_generated is False
    assert scaffold.approval_command_template_only is True
    assert scaffold.approval_command_copyable is False
    assert scaffold.approval_command_executable is False
    assert scaffold.usable_approval_artifacts_generated is False
    assert scaffold.real_approval_artifacts_available is False
    assert scaffold.requires_human_approval is True
    assert scaffold.explicit_user_confirmation_required is True
    assert scaffold.fresh_preflight_before_gate_required is True
    assert scaffold.post_approval_final_dynamic_preflight_required is True
    assert scaffold.one_shot_post_separate_step_required is True
    assert scaffold.post_reconciliation_separate_step_required is True
    assert scaffold.final_report_separate_step_required is True
    assert scaffold.dry_run_only is True
    assert scaffold.post_attempt_limit == 1
    assert scaffold.post_executed is False
    assert scaffold.live_order_once_called is False
    assert scaffold.private_api_called is False
    assert scaffold.broker_called is False
    assert scaffold.read_only_api_called is False
    assert scaffold.public_api_called is False
    assert scaffold.retry_allowed is False
    assert scaffold.loop_allowed is False
    assert scaffold.add_order_allowed is False
    assert scaffold.change_order_allowed is False
    assert scaffold.cancel_order_allowed is False
    assert scaffold.close_order_allowed is False
    assert scaffold.post_reconciliation_required is True


def test_scaffold_constraints_are_fixed_to_step5w_spec() -> None:
    scaffold = _scaffold().scaffold

    assert scaffold.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert scaffold.exact_match_required is True
    assert scaffold.same_session_required is True
    assert scaffold.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert scaffold.future_enablement_requirements == (
        DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_FUTURE_ENABLEMENT_REQUIREMENTS
    )
    assert scaffold.disabled_reasons == (
        DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_DISABLED_REASONS
    )


def test_future_enablement_requirements_and_disabled_reasons_are_recorded() -> None:
    scaffold = _scaffold().scaffold

    assert "explicit future user instruction required" in (
        scaffold.future_enablement_requirements
    )
    assert "fresh pre-approval preflight must be re-run in a future separate step" in (
        scaffold.future_enablement_requirements
    )
    assert "real approval_id generation must be a separate step" in (
        scaffold.future_enablement_requirements
    )
    assert "real approval command generation must be a separate step" in (
        scaffold.future_enablement_requirements
    )
    assert "post-approval final dynamic preflight required" in (
        scaffold.future_enablement_requirements
    )
    assert "one-shot POST remains a separate step" in (
        scaffold.future_enablement_requirements
    )
    assert "scaffold intentionally disabled" in scaffold.disabled_reasons
    assert "approval command is not copyable" in scaffold.disabled_reasons
    assert "live POST is not authorized" in scaffold.disabled_reasons
    assert scaffold.scaffold_ready is True
    assert scaffold.blocked_reasons == ()


def test_blocked_readiness_review_blocks_and_preserves_reasons() -> None:
    review = _implementation_readiness_review(post_attempt_limit=2).review
    result = _scaffold(review=review)

    assert (
        result.scaffold_status
        is ScaffoldStatus.BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD
    )
    assert result.scaffold_ready is False
    assert "invalid_post_attempt_limit" in result.blocked_reasons
    assert result.recommended_next_step == "fix_implementation_readiness_blockers_no_post"


def test_missing_implementation_readiness_review_blocks() -> None:
    result = build_live_order_real_approval_disabled_scaffold(
        implementation_readiness_review=None,
        created_at=CREATED_AT,
    )

    assert (
        BlockReason.MISSING_IMPLEMENTATION_READINESS_REVIEW.value
        in result.blocked_reasons
    )
    assert (
        result.scaffold_status
        is ScaffoldStatus.BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD
    )


def test_readiness_and_safety_flags_block() -> None:
    review = _implementation_readiness_review().review

    _assert_blocked(
        BlockReason.IMPLEMENTATION_READINESS_REVIEW_NOT_READY,
        review=_implementation_readiness_review(post_attempt_limit=2).review,
    )
    _assert_blocked(
        BlockReason.IMPLEMENTATION_READINESS_REVIEW_NOT_ELIGIBLE,
        review=_unchecked(
            review,
            eligible_for_future_real_approval_gate_implementation_step=False,
        ),
    )
    _assert_blocked(
        BlockReason.REVIEW_ALLOWS_LIVE,
        review=_unchecked(review, allowed_for_live=True),
    )
    _assert_blocked(
        BlockReason.REVIEW_NOT_DRY_RUN,
        review=_unchecked(review, dry_run_only=False),
    )


def test_real_artifact_generation_flags_block() -> None:
    review = _implementation_readiness_review().review

    _assert_blocked(
        BlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        review=_unchecked(review, approval_gate_issued=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_ALREADY_GENERATED,
        review=_unchecked(review, approval_id_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        review=_unchecked(review, approval_command_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_COPYABLE,
        review=_unchecked(review, approval_command_copyable=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        review=_unchecked(review, approval_id_generation_deferred_to_future_step=False),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        review=_unchecked(
            review,
            approval_command_generation_deferred_to_future_step=False,
        ),
    )


def test_unsupported_order_shape_blocks() -> None:
    review = _implementation_readiness_review().review

    _assert_blocked(
        BlockReason.UNSUPPORTED_SYMBOL,
        review=_unchecked(review, symbol="EUR_USD"),
    )
    _assert_blocked(
        BlockReason.UNSUPPORTED_SIDE,
        review=_unchecked(review, side="NO_TRADE"),
    )
    _assert_blocked(BlockReason.UNSUPPORTED_SIZE, review=_unchecked(review, size=200))
    _assert_blocked(
        BlockReason.UNSUPPORTED_EXECUTION_TYPE,
        review=_unchecked(review, execution_type="LIMIT"),
    )


def test_ttl_match_session_ack_and_display_constraints_block_when_unsafe() -> None:
    review = _implementation_readiness_review().review

    _assert_blocked(
        BlockReason.INVALID_TTL_SECONDS,
        review=_unchecked(review, ttl_seconds=301),
    )
    _assert_blocked(
        BlockReason.EXACT_MATCH_NOT_REQUIRED,
        review=_unchecked(review, exact_match_required=False),
    )
    _assert_blocked(
        BlockReason.SAME_SESSION_NOT_REQUIRED,
        review=_unchecked(review, same_session_required=False),
    )
    _assert_blocked(
        BlockReason.MISSING_ACK_TOKEN,
        review=_unchecked(review, required_ack_tokens=APPROVAL_ACK_TOKENS[:-1]),
    )
    _assert_blocked(
        BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE,
        review=_unchecked(review, display_forbidden_fields=("raw response",)),
    )


def test_no_api_post_and_one_shot_constraints_block_when_unsafe() -> None:
    review = _implementation_readiness_review().review

    _assert_blocked(
        BlockReason.POST_ALREADY_EXECUTED,
        review=_unchecked(review, post_executed=True),
    )
    _assert_blocked(
        BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        review=_unchecked(review, live_order_once_called=True),
    )
    _assert_blocked(
        BlockReason.PRIVATE_API_ALREADY_CALLED,
        review=_unchecked(review, private_api_called=True),
    )
    _assert_blocked(
        BlockReason.BROKER_ALREADY_CALLED,
        review=_unchecked(review, broker_called=True),
    )
    _assert_blocked(
        BlockReason.READ_ONLY_API_ALREADY_CALLED,
        review=_unchecked(review, read_only_api_called=True),
    )
    _assert_blocked(
        BlockReason.PUBLIC_API_ALREADY_CALLED,
        review=_unchecked(review, public_api_called=True),
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


def test_scaffold_specific_enablement_flags_block_but_output_stays_disabled() -> None:
    result = _scaffold(
        approval_gate_enabled=True,
        approval_command_executable=True,
        usable_approval_artifacts_generated=True,
        real_approval_artifacts_available=True,
    )

    assert BlockReason.APPROVAL_GATE_ENABLED.value in result.blocked_reasons
    assert BlockReason.APPROVAL_COMMAND_EXECUTABLE.value in result.blocked_reasons
    assert (
        BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED.value
        in result.blocked_reasons
    )
    assert BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE.value in result.blocked_reasons
    assert result.approval_gate_enabled is False
    assert result.approval_command_executable is False
    assert result.usable_approval_artifacts_generated is False
    assert result.real_approval_artifacts_available is False


def test_future_requirements_and_disabled_reasons_are_required() -> None:
    _assert_blocked(
        BlockReason.MISSING_FUTURE_ENABLEMENT_REQUIREMENTS,
        future_enablement_requirements=(),
    )
    _assert_blocked(BlockReason.MISSING_DISABLED_REASONS, disabled_reasons=())


def test_check_results_cover_required_disabled_scaffold_checks() -> None:
    check_names = {check.name for check in _scaffold().scaffold.check_results}

    assert "implementation_readiness_review_ready" in check_names
    assert "approval_gate_enabled_false" in check_names
    assert "allowed_for_live_false" in check_names
    assert "approval_gate_not_issued" in check_names
    assert "approval_id_not_generated" in check_names
    assert "approval_command_not_generated" in check_names
    assert "approval_command_not_copyable" in check_names
    assert "approval_command_not_executable" in check_names
    assert "no_usable_approval_artifacts_generated" in check_names
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
    assert "disabled_reasons_present" in check_names


def test_display_forbidden_fields_include_credential_raw_id_and_real_command_terms() -> None:
    fields_text = " ".join(_scaffold().scaffold.display_forbidden_fields).lower()

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
    markdown = render_live_order_real_approval_disabled_scaffold_markdown(
        _scaffold().scaffold
    )

    assert "This real approval gate scaffold is disabled and dry-run only." in markdown
    assert "This scaffold does not call read-only API." in markdown
    assert "This scaffold does not call Private API." in markdown
    assert "This scaffold does not call live_order_once." in markdown
    assert "This scaffold does not execute HTTP POST." in markdown
    assert "This scaffold does not issue a real approval gate." in markdown
    assert "This scaffold does not generate a real approval_id." in markdown
    assert "This scaffold does not generate a real approval command." in markdown
    assert "This scaffold does not provide copyable approval text." in markdown
    assert "This scaffold does not authorize live POST." in markdown
    assert "approval_gate_enabled=false." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_disabled_scaffold_markdown(
        _scaffold().scaffold
    )
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
    scaffold = _scaffold().scaffold
    serialized = str(asdict(scaffold))
    rendered = repr(scaffold)
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
            build_live_order_real_approval_disabled_scaffold(
                implementation_readiness_review=_implementation_readiness_review().review,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_disabled_scaffold_has_no_ordering_api_or_clipboard_dependencies() -> None:
    import app.live_verification.live_order_real_approval_disabled_scaffold as module

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
