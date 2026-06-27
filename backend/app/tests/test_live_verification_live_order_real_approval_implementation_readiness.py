from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_implementation_readiness import (
    DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_BLOCKERS,
    LIVE_ORDER_REAL_APPROVAL_IMPLEMENTATION_READINESS_ID_PREFIX,
    LiveOrderRealApprovalImplementationReadinessBlockReason,
    LiveOrderRealApprovalImplementationReadinessStatus,
    build_live_order_real_approval_implementation_readiness_review,
    render_live_order_real_approval_implementation_readiness_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_pre_implementation_audit import (
    _audit as _pre_implementation_audit,
)

ReadinessStatus = LiveOrderRealApprovalImplementationReadinessStatus
BlockReason = LiveOrderRealApprovalImplementationReadinessBlockReason


def _review(*, audit=None, **overrides: object):
    actual_audit = audit or _pre_implementation_audit().audit
    return build_live_order_real_approval_implementation_readiness_review(
        pre_implementation_audit=actual_audit,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalImplementationReadinessBlockReason | str,
    *,
    audit=None,
    **overrides: object,
) -> None:
    result = _review(audit=audit, **overrides)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert (
        result.readiness_status
        is ReadinessStatus.BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS
    )
    assert result.readiness_ready is False
    assert result.eligible_for_future_real_approval_gate_implementation_step is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert expected in result.blocked_reasons


def test_ready_audit_builds_real_approval_implementation_readiness_review_only() -> None:
    result = _review()
    review = result.review

    assert review.review_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_IMPLEMENTATION_READINESS_ID_PREFIX
    )
    assert (
        review.readiness_status
        is ReadinessStatus.READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW
    )
    assert review.readiness_ready is True
    assert review.eligible_for_future_real_approval_gate_implementation_step is True
    assert review.allowed_for_live is False
    assert review.blocked_reasons == ()
    assert result.recommended_next_step == (
        "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_implementation_step_no_post"
    )


def test_ready_review_never_authorizes_post_or_real_approval_artifacts() -> None:
    review = _review().review

    assert review.allowed_for_live is False
    assert review.requires_human_approval is True
    assert review.explicit_user_confirmation_required is True
    assert review.approval_gate_required is True
    assert review.approval_gate_planned is True
    assert review.approval_gate_issued is False
    assert review.approval_id_generation_planned is True
    assert review.approval_id_generation_deferred_to_future_step is True
    assert review.approval_id_generated is False
    assert review.approval_command_generation_planned is True
    assert review.approval_command_generation_deferred_to_future_step is True
    assert review.approval_command_generated is False
    assert review.approval_command_template_only is True
    assert review.approval_command_copyable is False
    assert review.fresh_preflight_before_gate_required is True
    assert review.post_approval_final_dynamic_preflight_required is True
    assert review.one_shot_post_separate_step_required is True
    assert review.post_reconciliation_separate_step_required is True
    assert review.final_report_separate_step_required is True
    assert review.dry_run_only is True
    assert review.post_attempt_limit == 1
    assert review.post_executed is False
    assert review.live_order_once_called is False
    assert review.private_api_called is False
    assert review.broker_called is False
    assert review.read_only_api_called is False
    assert review.public_api_called is False
    assert review.retry_allowed is False
    assert review.loop_allowed is False
    assert review.add_order_allowed is False
    assert review.change_order_allowed is False
    assert review.cancel_order_allowed is False
    assert review.close_order_allowed is False
    assert review.post_reconciliation_required is True


def test_readiness_constraints_are_fixed_to_step5v_spec() -> None:
    review = _review().review

    assert review.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert review.exact_match_required is True
    assert review.same_session_required is True
    assert review.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert review.prompt_truncation_risk_reviewed is True
    assert review.step5u_test_coverage_reviewed is True
    assert review.step5u_docs_reviewed is True
    assert review.residual_risks
    assert review.manual_confirmation_items
    assert review.implementation_blockers
    assert review.implementation_readiness_blockers == (
        DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_BLOCKERS
    )


def test_readiness_blockers_are_recorded_but_do_not_block_ready_review() -> None:
    review = _review().review

    assert "future explicit user instruction required" in (
        review.implementation_readiness_blockers
    )
    assert "real approval gate implementation not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert "real approval_id generation not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert "real approval command generation not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert "runtime exact match validation not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert "post-approval final dynamic preflight not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert "one-shot POST not yet performed" in review.implementation_readiness_blockers
    assert "post reconciliation not yet performed" in (
        review.implementation_readiness_blockers
    )
    assert review.readiness_ready is True
    assert review.blocked_reasons == ()


def test_blocked_pre_implementation_audit_blocks_and_preserves_reasons() -> None:
    audit = _pre_implementation_audit(post_attempt_limit=2).audit
    result = _review(audit=audit)

    assert (
        result.readiness_status
        is ReadinessStatus.BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS
    )
    assert result.readiness_ready is False
    assert "invalid_post_attempt_limit" in result.blocked_reasons
    assert result.recommended_next_step == "fix_pre_implementation_audit_blockers_no_post"


def test_missing_pre_implementation_audit_blocks() -> None:
    result = build_live_order_real_approval_implementation_readiness_review(
        pre_implementation_audit=None,
        created_at=CREATED_AT,
    )

    assert BlockReason.MISSING_PRE_IMPLEMENTATION_AUDIT.value in result.blocked_reasons
    assert (
        result.readiness_status
        is ReadinessStatus.BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS
    )


def test_audit_readiness_and_safety_flags_block() -> None:
    audit = _pre_implementation_audit().audit

    _assert_blocked(
        BlockReason.PRE_IMPLEMENTATION_AUDIT_NOT_READY,
        audit=_pre_implementation_audit(post_attempt_limit=2).audit,
    )
    _assert_blocked(
        BlockReason.PRE_IMPLEMENTATION_AUDIT_NOT_ELIGIBLE,
        audit=_unchecked(
            audit,
            eligible_for_future_real_approval_gate_implementation_review=False,
        ),
    )
    _assert_blocked(
        BlockReason.AUDIT_ALLOWS_LIVE,
        audit=_unchecked(audit, allowed_for_live=True),
    )
    _assert_blocked(
        BlockReason.AUDIT_NOT_DRY_RUN,
        audit=_unchecked(audit, dry_run_only=False),
    )


def test_real_artifact_generation_flags_block() -> None:
    audit = _pre_implementation_audit().audit

    _assert_blocked(
        BlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        audit=_unchecked(audit, approval_gate_issued=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_ALREADY_GENERATED,
        audit=_unchecked(audit, approval_id_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        audit=_unchecked(audit, approval_command_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_COPYABLE,
        audit=_unchecked(audit, approval_command_copyable=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        audit=_unchecked(audit, approval_id_generation_deferred_to_future_step=False),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        audit=_unchecked(audit, approval_command_generation_deferred_to_future_step=False),
    )


def test_unsupported_order_shape_blocks() -> None:
    audit = _pre_implementation_audit().audit

    _assert_blocked(BlockReason.UNSUPPORTED_SYMBOL, audit=_unchecked(audit, symbol="EUR_USD"))
    _assert_blocked(BlockReason.UNSUPPORTED_SIDE, audit=_unchecked(audit, side="NO_TRADE"))
    _assert_blocked(BlockReason.UNSUPPORTED_SIZE, audit=_unchecked(audit, size=200))
    _assert_blocked(
        BlockReason.UNSUPPORTED_EXECUTION_TYPE,
        audit=_unchecked(audit, execution_type="LIMIT"),
    )


def test_ttl_match_session_ack_and_display_constraints_block_when_unsafe() -> None:
    audit = _pre_implementation_audit().audit

    _assert_blocked(BlockReason.INVALID_TTL_SECONDS, audit=_unchecked(audit, ttl_seconds=301))
    _assert_blocked(
        BlockReason.EXACT_MATCH_NOT_REQUIRED,
        audit=_unchecked(audit, exact_match_required=False),
    )
    _assert_blocked(
        BlockReason.SAME_SESSION_NOT_REQUIRED,
        audit=_unchecked(audit, same_session_required=False),
    )
    _assert_blocked(
        BlockReason.MISSING_ACK_TOKEN,
        audit=_unchecked(audit, required_ack_tokens=APPROVAL_ACK_TOKENS[:-1]),
    )
    _assert_blocked(
        BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE,
        audit=_unchecked(audit, display_forbidden_fields=("raw response",)),
    )


def test_no_api_post_and_one_shot_constraints_block_when_unsafe() -> None:
    audit = _pre_implementation_audit().audit

    _assert_blocked(BlockReason.POST_ALREADY_EXECUTED, audit=_unchecked(audit, post_executed=True))
    _assert_blocked(
        BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        audit=_unchecked(audit, live_order_once_called=True),
    )
    _assert_blocked(
        BlockReason.PRIVATE_API_ALREADY_CALLED,
        audit=_unchecked(audit, private_api_called=True),
    )
    _assert_blocked(BlockReason.BROKER_ALREADY_CALLED, audit=_unchecked(audit, broker_called=True))
    _assert_blocked(
        BlockReason.READ_ONLY_API_ALREADY_CALLED,
        audit=_unchecked(audit, read_only_api_called=True),
    )
    _assert_blocked(
        BlockReason.PUBLIC_API_ALREADY_CALLED,
        audit=_unchecked(audit, public_api_called=True),
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


def test_residual_manual_blocker_and_review_flags_are_required() -> None:
    _assert_blocked(BlockReason.MISSING_RESIDUAL_RISKS, residual_risks=())
    _assert_blocked(
        BlockReason.MISSING_MANUAL_CONFIRMATION_ITEMS,
        manual_confirmation_items=(),
    )
    _assert_blocked(
        BlockReason.MISSING_IMPLEMENTATION_BLOCKERS,
        implementation_readiness_blockers=(),
    )
    _assert_blocked(
        BlockReason.PROMPT_TRUNCATION_RISK_NOT_REVIEWED,
        prompt_truncation_risk_reviewed=False,
    )
    _assert_blocked(
        BlockReason.STEP5U_TEST_COVERAGE_NOT_REVIEWED,
        step5u_test_coverage_reviewed=False,
    )
    _assert_blocked(BlockReason.STEP5U_DOCS_NOT_REVIEWED, step5u_docs_reviewed=False)


def test_check_results_cover_required_implementation_readiness_checks() -> None:
    check_names = {check.name for check in _review().review.check_results}

    assert "pre_implementation_audit_ready" in check_names
    assert "prompt_truncation_risk_reviewed" in check_names
    assert "step5u_test_coverage_reviewed" in check_names
    assert "step5u_docs_reviewed" in check_names
    assert "allowed_for_live_false" in check_names
    assert "approval_gate_not_issued" in check_names
    assert "approval_id_not_generated" in check_names
    assert "approval_command_not_generated" in check_names
    assert "approval_command_not_copyable" in check_names
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
    assert "residual_risks_present" in check_names
    assert "manual_confirmation_items_present" in check_names
    assert "implementation_blockers_present" in check_names
    assert "future_explicit_user_instruction_required" in check_names


def test_display_forbidden_fields_include_credential_raw_id_and_real_command_terms() -> None:
    fields_text = " ".join(_review().review.display_forbidden_fields).lower()

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


def test_markdown_rendering_includes_required_no_api_no_real_approval_warnings() -> None:
    markdown = render_live_order_real_approval_implementation_readiness_markdown(
        _review().review
    )

    assert "This real approval implementation readiness review is dry-run only." in markdown
    assert "This review does not call read-only API." in markdown
    assert "This review does not call Private API." in markdown
    assert "This review does not call live_order_once." in markdown
    assert "This review does not execute HTTP POST." in markdown
    assert "This review does not issue a real approval gate." in markdown
    assert "This review does not generate a real approval_id." in markdown
    assert "This review does not generate a real approval command." in markdown
    assert "This review does not provide copyable approval text." in markdown
    assert "This review does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_implementation_readiness_markdown(
        _review().review
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
    review = _review().review
    serialized = str(asdict(review))
    rendered = repr(review)
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
            build_live_order_real_approval_implementation_readiness_review(
                pre_implementation_audit=_pre_implementation_audit().audit,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_implementation_readiness_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_real_approval_implementation_readiness as module

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
