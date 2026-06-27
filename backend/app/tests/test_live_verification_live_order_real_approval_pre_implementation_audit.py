from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_pre_implementation_audit import (
    LIVE_ORDER_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_ID_PREFIX,
    LiveOrderRealApprovalPreImplementationAuditBlockReason,
    LiveOrderRealApprovalPreImplementationAuditStatus,
    build_live_order_real_approval_pre_implementation_audit,
    render_live_order_real_approval_pre_implementation_audit_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_gate_generation_package import (
    _package,
)

AuditStatus = LiveOrderRealApprovalPreImplementationAuditStatus
BlockReason = LiveOrderRealApprovalPreImplementationAuditBlockReason


def _audit(*, package=None, **overrides: object):
    actual_package = package or _package().package
    return build_live_order_real_approval_pre_implementation_audit(
        generation_package=actual_package,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalPreImplementationAuditBlockReason | str,
    *,
    package=None,
    **overrides: object,
) -> None:
    result = _audit(package=package, **overrides)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.audit_status is AuditStatus.BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT
    assert result.audit_ready is False
    assert (
        result.eligible_for_future_real_approval_gate_implementation_review
        is False
    )
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert expected in result.blocked_reasons


def test_ready_generation_package_builds_pre_implementation_audit_review_only() -> None:
    result = _audit()
    audit = result.audit

    assert audit.audit_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_ID_PREFIX
    )
    assert (
        audit.audit_status
        is AuditStatus.READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW
    )
    assert audit.audit_ready is True
    assert audit.eligible_for_future_real_approval_gate_implementation_review is True
    assert audit.allowed_for_live is False
    assert audit.blocked_reasons == ()
    assert result.recommended_next_step == (
        "review_audit_then_wait_for_explicit_user_instruction_for_future_real_approval_gate_implementation_no_post"
    )


def test_ready_audit_still_never_authorizes_post_or_approval_artifacts() -> None:
    audit = _audit().audit

    assert audit.allowed_for_live is False
    assert audit.requires_human_approval is True
    assert audit.explicit_user_confirmation_required is True
    assert audit.approval_gate_required is True
    assert audit.approval_gate_planned is True
    assert audit.approval_gate_issued is False
    assert audit.approval_id_generation_planned is True
    assert audit.approval_id_generation_deferred_to_future_step is True
    assert audit.approval_id_generated is False
    assert audit.approval_command_generation_planned is True
    assert audit.approval_command_generation_deferred_to_future_step is True
    assert audit.approval_command_generated is False
    assert audit.approval_command_template_only is True
    assert audit.approval_command_copyable is False
    assert audit.fresh_preflight_before_gate_required is True
    assert audit.post_approval_final_dynamic_preflight_required is True
    assert audit.one_shot_post_separate_step_required is True
    assert audit.post_reconciliation_separate_step_required is True
    assert audit.final_report_separate_step_required is True
    assert audit.dry_run_only is True
    assert audit.post_attempt_limit == 1
    assert audit.post_executed is False
    assert audit.live_order_once_called is False
    assert audit.private_api_called is False
    assert audit.broker_called is False
    assert audit.read_only_api_called is False
    assert audit.public_api_called is False
    assert audit.retry_allowed is False
    assert audit.loop_allowed is False
    assert audit.add_order_allowed is False
    assert audit.change_order_allowed is False
    assert audit.cancel_order_allowed is False
    assert audit.close_order_allowed is False
    assert audit.post_reconciliation_required is True


def test_audit_constraints_are_fixed_to_step5u_spec() -> None:
    audit = _audit().audit

    assert audit.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert audit.exact_match_required is True
    assert audit.same_session_required is True
    assert audit.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert audit.residual_risks
    assert audit.manual_confirmation_items
    assert audit.implementation_blockers


def test_blocked_generation_package_blocks_and_preserves_reasons() -> None:
    package = _package(approval_gate_issued=True).package
    result = _audit(package=package)

    assert result.audit_status is AuditStatus.BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT
    assert result.audit_ready is False
    assert "approval_gate_already_issued" in result.blocked_reasons
    assert result.recommended_next_step == "fix_generation_package_blockers_no_post"


def test_missing_generation_package_blocks() -> None:
    result = build_live_order_real_approval_pre_implementation_audit(
        generation_package=None,
        created_at=CREATED_AT,
    )

    assert BlockReason.MISSING_GENERATION_PACKAGE.value in result.blocked_reasons
    assert result.audit_status is AuditStatus.BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT


def test_package_safety_flags_block() -> None:
    package = _package().package

    _assert_blocked(
        BlockReason.PACKAGE_ALLOWS_LIVE,
        package=_unchecked(package, allowed_for_live=True),
    )
    _assert_blocked(
        BlockReason.PACKAGE_NOT_DRY_RUN,
        package=_unchecked(package, dry_run_only=False),
    )
    _assert_blocked(
        BlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        package=_unchecked(package, approval_gate_issued=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_ALREADY_GENERATED,
        package=_unchecked(package, approval_id_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        package=_unchecked(package, approval_command_generated=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_COPYABLE,
        package=_unchecked(package, approval_command_copyable=True),
    )
    _assert_blocked(
        BlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        package=_unchecked(package, approval_id_generation_deferred_to_future_step=False),
    )
    _assert_blocked(
        BlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        package=_unchecked(
            package,
            approval_command_generation_deferred_to_future_step=False,
        ),
    )


def test_unsupported_order_shape_blocks() -> None:
    package = _package().package

    _assert_blocked(BlockReason.UNSUPPORTED_SYMBOL, package=_unchecked(package, symbol="EUR_USD"))
    _assert_blocked(BlockReason.UNSUPPORTED_SIDE, package=_unchecked(package, side="NO_TRADE"))
    _assert_blocked(BlockReason.UNSUPPORTED_SIZE, package=_unchecked(package, size=200))
    _assert_blocked(
        BlockReason.UNSUPPORTED_EXECUTION_TYPE,
        package=_unchecked(package, execution_type="LIMIT"),
    )


def test_ttl_match_session_ack_and_display_constraints_block_when_unsafe() -> None:
    package = _package().package

    _assert_blocked(
        BlockReason.INVALID_TTL_SECONDS,
        package=_unchecked(package, ttl_seconds=301),
    )
    _assert_blocked(
        BlockReason.EXACT_MATCH_NOT_REQUIRED,
        package=_unchecked(package, exact_match_required=False),
    )
    _assert_blocked(
        BlockReason.SAME_SESSION_NOT_REQUIRED,
        package=_unchecked(package, same_session_required=False),
    )
    _assert_blocked(
        BlockReason.MISSING_ACK_TOKEN,
        package=_unchecked(package, required_ack_tokens=APPROVAL_ACK_TOKENS[:-1]),
    )
    _assert_blocked(
        BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE,
        package=_unchecked(package, display_forbidden_fields=("raw response",)),
    )


def test_no_api_post_and_one_shot_constraints_block_when_unsafe() -> None:
    package = _package().package

    _assert_blocked(
        BlockReason.POST_ALREADY_EXECUTED,
        package=_unchecked(package, post_executed=True),
    )
    _assert_blocked(
        BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        package=_unchecked(package, live_order_once_called=True),
    )
    _assert_blocked(
        BlockReason.PRIVATE_API_ALREADY_CALLED,
        package=_unchecked(package, private_api_called=True),
    )
    _assert_blocked(
        BlockReason.BROKER_ALREADY_CALLED,
        package=_unchecked(package, broker_called=True),
    )
    _assert_blocked(
        BlockReason.READ_ONLY_API_ALREADY_CALLED,
        package=_unchecked(package, read_only_api_called=True),
    )
    _assert_blocked(
        BlockReason.PUBLIC_API_ALREADY_CALLED,
        package=_unchecked(package, public_api_called=True),
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


def test_residual_manual_and_blocker_sections_are_required() -> None:
    _assert_blocked(BlockReason.MISSING_RESIDUAL_RISKS, residual_risks=())
    _assert_blocked(
        BlockReason.MISSING_MANUAL_CONFIRMATION_ITEMS,
        manual_confirmation_items=(),
    )
    _assert_blocked(
        BlockReason.MISSING_IMPLEMENTATION_BLOCKERS,
        implementation_blockers=(),
    )


def test_check_results_cover_required_pre_implementation_audit_checks() -> None:
    check_names = {check.name for check in _audit().audit.check_results}

    assert "generation_package_ready" in check_names
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


def test_display_forbidden_fields_include_credential_raw_id_and_real_command_terms() -> None:
    fields_text = " ".join(_audit().audit.display_forbidden_fields).lower()

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


def test_markdown_rendering_includes_required_no_api_no_real_approval_warnings() -> None:
    markdown = render_live_order_real_approval_pre_implementation_audit_markdown(
        _audit().audit
    )

    assert "This real approval pre-implementation audit is dry-run only." in markdown
    assert "This audit does not call read-only API." in markdown
    assert "This audit does not call Private API." in markdown
    assert "This audit does not call live_order_once." in markdown
    assert "This audit does not execute HTTP POST." in markdown
    assert "This audit does not issue a real approval gate." in markdown
    assert "This audit does not generate a real approval_id." in markdown
    assert "This audit does not generate a real approval command." in markdown
    assert "This audit does not provide copyable approval text." in markdown
    assert "This audit does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_pre_implementation_audit_markdown(
        _audit().audit
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
    audit = _audit().audit
    serialized = str(asdict(audit))
    rendered = repr(audit)
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
            build_live_order_real_approval_pre_implementation_audit(
                generation_package=_package().package,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_pre_implementation_audit_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_real_approval_pre_implementation_audit as module

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
