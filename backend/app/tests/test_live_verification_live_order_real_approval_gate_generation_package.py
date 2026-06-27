from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_real_approval_gate_generation_package import (
    APPROVAL_COMMAND_DISPLAY_MODE,
    APPROVAL_COMMAND_TEMPLATE_LABEL,
    APPROVAL_ID_PLACEHOLDER_LABEL,
    LIVE_ORDER_REAL_APPROVAL_GATE_GENERATION_PACKAGE_ID_PREFIX,
    REQUIRED_REAL_APPROVAL_GATE_GENERATION_PACKAGE_PHASE_IDS,
    LiveOrderRealApprovalGateGenerationPackageBlockReason,
    LiveOrderRealApprovalGateGenerationPackageStatus,
    build_default_real_approval_gate_generation_package_phases,
    build_live_order_real_approval_gate_generation_package,
    render_live_order_real_approval_gate_generation_package_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_pre_approval_fresh_preflight import (
    _evaluate,
)

PackageStatus = LiveOrderRealApprovalGateGenerationPackageStatus


def _package(*, decision=None, **overrides: object):
    actual_decision = decision or _evaluate().decision
    return build_live_order_real_approval_gate_generation_package(
        pre_approval_fresh_preflight_decision=actual_decision,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalGateGenerationPackageBlockReason | str,
    *,
    decision=None,
    **overrides: object,
) -> None:
    result = _package(decision=decision, **overrides)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderRealApprovalGateGenerationPackageBlockReason)
        else reason
    )

    assert (
        result.package_status
        is PackageStatus.BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE
    )
    assert result.package_ready is False
    assert result.eligible_for_future_real_approval_gate_generation is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert expected in result.blocked_reasons


def test_ready_pre_approval_decision_builds_generation_package_review_only() -> None:
    result = _package()
    package = result.package

    assert package.package_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_GATE_GENERATION_PACKAGE_ID_PREFIX
    )
    assert (
        package.package_status
        is PackageStatus.READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
    )
    assert package.package_ready is True
    assert package.eligible_for_future_real_approval_gate_generation is True
    assert package.allowed_for_live is False
    assert package.blocked_reasons == ()
    assert result.recommended_next_step == (
        "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_generation_step"
    )


def test_ready_package_still_never_authorizes_post_or_approval_artifacts() -> None:
    package = _package().package

    assert package.allowed_for_live is False
    assert package.requires_human_approval is True
    assert package.explicit_user_confirmation_required is True
    assert package.approval_gate_required is True
    assert package.approval_gate_planned is True
    assert package.approval_gate_issued is False
    assert package.approval_id_generation_planned is True
    assert package.approval_id_generation_deferred_to_future_step is True
    assert package.approval_id_generated is False
    assert package.approval_command_generation_planned is True
    assert package.approval_command_generation_deferred_to_future_step is True
    assert package.approval_command_generated is False
    assert package.approval_command_template_only is True
    assert package.approval_command_copyable is False
    assert package.fresh_preflight_before_gate_required is True
    assert package.post_approval_final_dynamic_preflight_required is True
    assert package.one_shot_post_separate_step_required is True
    assert package.post_reconciliation_separate_step_required is True
    assert package.final_report_separate_step_required is True
    assert package.dry_run_only is True
    assert package.post_executed is False
    assert package.live_order_once_called is False
    assert package.private_api_called is False
    assert package.broker_called is False
    assert package.read_only_api_called is False
    assert package.public_api_called is False


def test_generation_constraints_are_fixed_to_step5t_spec() -> None:
    package = _package().package

    assert package.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert package.exact_match_required is True
    assert package.same_session_required is True
    assert package.required_ack_tokens == APPROVAL_ACK_TOKENS
    assert package.approval_id_placeholder_label == APPROVAL_ID_PLACEHOLDER_LABEL
    assert package.approval_command_template_label == APPROVAL_COMMAND_TEMPLATE_LABEL
    assert package.approval_command_display_mode == APPROVAL_COMMAND_DISPLAY_MODE


def test_blocked_pre_approval_decision_blocks_and_preserves_reasons() -> None:
    blocked_decision = _evaluate(open_positions_count=1, spread_jpy=0.02).decision
    result = _package(decision=blocked_decision)

    assert (
        result.package_status
        is PackageStatus.BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE
    )
    assert result.package_ready is False
    assert "open_positions_exist" in result.blocked_reasons
    assert "spread_too_wide" in result.blocked_reasons
    assert result.recommended_next_step == (
        "fix_pre_approval_fresh_preflight_blockers_no_post"
    )


def test_missing_pre_approval_decision_blocks() -> None:
    result = build_live_order_real_approval_gate_generation_package(
        pre_approval_fresh_preflight_decision=None,
        created_at=CREATED_AT,
    )

    assert (
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_DECISION.value
        in result.blocked_reasons
    )


def test_decision_safety_flags_block() -> None:
    decision = _evaluate().decision

    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.DECISION_ALLOWS_LIVE,
        decision=_unchecked(decision, allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.DECISION_NOT_DRY_RUN,
        decision=_unchecked(decision, dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        decision=_unchecked(decision, approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        decision=_unchecked(decision, approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        decision=_unchecked(decision, approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_COPYABLE,
        decision=_unchecked(decision, approval_command_copyable=True),
    )


def test_unsupported_order_shape_blocks() -> None:
    decision = _evaluate().decision

    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SYMBOL,
        decision=_unchecked(decision, symbol="EUR_USD"),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SIDE,
        decision=_unchecked(decision, side="NO_TRADE"),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SIZE,
        decision=_unchecked(decision, size=200),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        decision=_unchecked(decision, execution_type="LIMIT"),
    )


def test_package_constraint_flags_block_without_changing_safe_output_flags() -> None:
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        approval_id_generation_deferred_to_future_step=False,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        approval_command_generation_deferred_to_future_step=False,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        approval_gate_issued=True,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        approval_id_generated=True,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        approval_command_generated=True,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_COPYABLE,
        approval_command_copyable=True,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.POST_ALREADY_EXECUTED,
        post_executed=True,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        live_order_once_called=True,
    )


def test_ttl_match_session_ack_and_placeholder_constraints_block_when_unsafe() -> None:
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.INVALID_TTL_SECONDS,
        ttl_seconds=301,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.EXACT_MATCH_NOT_REQUIRED,
        exact_match_required=False,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.SAME_SESSION_NOT_REQUIRED,
        same_session_required=False,
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_ACK_TOKEN,
        required_ack_tokens=APPROVAL_ACK_TOKENS[:-1],
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_APPROVAL_ID_PLACEHOLDER_LABEL,
        approval_id_placeholder_label="",
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_APPROVAL_COMMAND_TEMPLATE_LABEL,
        approval_command_template_label="",
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_DISPLAY_MODE_NOT_SAFE,
        approval_command_display_mode="copyable",
    )


def test_required_phases_are_generated_and_missing_phase_blocks() -> None:
    package = _package().package
    phase_ids = {phase.phase_id for phase in package.phases}

    assert set(REQUIRED_REAL_APPROVAL_GATE_GENERATION_PACKAGE_PHASE_IDS).issubset(
        phase_ids
    )

    missing_first_phase = build_default_real_approval_gate_generation_package_phases()[1:]
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_REQUIRED_PHASE,
        phases=missing_first_phase,
    )


def test_go_no_go_and_stop_conditions_cover_required_terms() -> None:
    package = _package().package
    go_text = " ".join(package.go_conditions)
    no_go_text = " ".join(package.no_go_conditions)
    stop_text = " ".join(package.stop_conditions)

    for marker in (
        "explicit future user instruction",
        "approval_id generation is deferred",
        "approval command generation is deferred",
        "exact match",
        "TTL is 300 seconds",
        "all ACK tokens",
        "final dynamic preflight",
    ):
        assert marker in go_text
    for marker in (
        "pre-approval fresh preflight is blocked",
        "stale pre-approval fresh preflight",
        "approval artifact already generated",
        "any API/broker/live_order_once already called",
        "post already executed",
        "mismatch",
        "raw response",
        "retry/loop/add/change/cancel/close needed",
    ):
        assert marker in no_go_text
    for marker in (
        "no explicit future request",
        "stale pre-approval fresh preflight",
        "approval id or command would be generated before the future explicit step",
        "exact match or same session cannot be guaranteed",
        "secret, raw data, or real ID exposure risk",
    ):
        assert marker in stop_text


def test_empty_condition_groups_block() -> None:
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_GO_CONDITIONS,
        go_conditions=(),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_NO_GO_CONDITIONS,
        no_go_conditions=(),
    )
    _assert_blocked(
        LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_STOP_CONDITIONS,
        stop_conditions=(),
    )


def test_check_results_cover_required_generation_package_checks() -> None:
    check_names = {check.name for check in _package().package.check_results}

    assert "pre_approval_fresh_preflight_ready" in check_names
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
    assert "display_forbidden_fields_include_sensitive_terms" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "post_not_executed" in check_names


def test_display_forbidden_fields_include_credential_raw_id_and_real_command_terms() -> None:
    fields_text = " ".join(_package().package.display_forbidden_fields).lower()

    assert "api key" in fields_text
    assert "secret" in fields_text
    assert "signature" in fields_text
    assert "headers" in fields_text
    assert "raw response" in fields_text
    assert "order id" in fields_text
    assert "execution id" in fields_text
    assert "position id" in fields_text
    assert "clientorderid" in fields_text
    assert "real approval_id" in fields_text
    assert "real approval command" in fields_text
    assert "copyable approval command" in fields_text


def test_markdown_rendering_includes_required_no_api_no_real_approval_warnings() -> None:
    markdown = render_live_order_real_approval_gate_generation_package_markdown(
        _package().package
    )

    assert "This real approval gate generation package is dry-run only." in markdown
    assert "This package does not call read-only API." in markdown
    assert "This package does not call public API." in markdown
    assert "This package does not call Private API." in markdown
    assert "This package does not call live_order_once." in markdown
    assert "This package does not execute HTTP POST." in markdown
    assert "This package does not issue a real approval gate." in markdown
    assert "This package does not generate a real approval_id." in markdown
    assert "This package does not generate a real approval command." in markdown
    assert "This package does not provide copyable approval text." in markdown
    assert "This package does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_gate_generation_package_markdown(
        _package().package
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
        "actual_copyable_command_value",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    package = _package().package
    serialized = str(asdict(package))
    rendered = repr(package)
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
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
            build_live_order_real_approval_gate_generation_package(
                pre_approval_fresh_preflight_decision=_evaluate().decision,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_real_approval_gate_generation_package_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_real_approval_gate_generation_package as module

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
