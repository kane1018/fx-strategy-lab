from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_final_dynamic_preflight import (
    LiveOrderFinalDynamicPreflightDecision,
)
from app.live_verification.live_order_one_shot_boundary import (
    LIVE_ORDER_ONE_SHOT_BOUNDARY_ID_PREFIX,
    ONE_SHOT_BODY_FIELDS_ALLOWLIST,
    ONE_SHOT_BODY_FIELDS_FORBIDDEN,
    ONE_SHOT_POST_ATTEMPT_LIMIT,
    REQUEST_BODY_FINGERPRINT_LABEL,
    SIGNING_BODY_FINGERPRINT_LABEL,
    LiveOrderOneShotBoundaryBlockReason,
    LiveOrderOneShotBoundaryStatus,
    build_live_order_one_shot_boundary,
    render_live_order_one_shot_boundary_markdown,
)
from app.tests.test_live_verification_live_order_final_dynamic_preflight import (
    CREATED_AT,
    _evaluate,
    _unchecked,
)


def _preflight(**overrides: object) -> LiveOrderFinalDynamicPreflightDecision:
    decision = _evaluate().decision
    return _unchecked(decision, **overrides)


def _boundary(
    *,
    preflight: LiveOrderFinalDynamicPreflightDecision | None = None,
    **overrides: object,
):
    return build_live_order_one_shot_boundary(
        final_dynamic_preflight_decision=preflight or _preflight(),
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderOneShotBoundaryBlockReason | str,
    *,
    preflight: LiveOrderFinalDynamicPreflightDecision | None = None,
    **overrides: object,
) -> None:
    result = _boundary(preflight=preflight, **overrides)
    expected = (
        reason.value if isinstance(reason, LiveOrderOneShotBoundaryBlockReason) else reason
    )

    assert (
        result.boundary_status
        is LiveOrderOneShotBoundaryStatus.BLOCKED_ONE_SHOT_LIVE_BOUNDARY
    )
    assert result.boundary_passed is False
    assert result.eligible_for_future_one_shot_live_review is False
    assert result.allowed_for_live is False
    assert expected in result.blocked_reasons


def test_passed_final_dynamic_preflight_and_safe_settings_are_boundary_ready() -> None:
    result = _boundary()
    decision = result.decision

    assert decision.boundary_id.startswith(LIVE_ORDER_ONE_SHOT_BOUNDARY_ID_PREFIX)
    assert (
        decision.boundary_status
        is LiveOrderOneShotBoundaryStatus.READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
    )
    assert decision.boundary_passed is True
    assert decision.eligible_for_future_one_shot_live_review is True
    assert decision.allowed_for_live is False
    assert decision.post_attempt_limit == ONE_SHOT_POST_ATTEMPT_LIMIT
    assert decision.post_executed is False
    assert decision.blocked_reasons == ()
    assert result.recommended_next_step == (
        "prepare_future_real_approval_gate_or_one_shot_execution_plan_separate_step_no_post"
    )


def test_safety_defaults_are_fixed_and_pass_is_not_post_permission() -> None:
    decision = _boundary().decision

    assert decision.allowed_for_live is False
    assert decision.requires_human_approval is True
    assert decision.approval_gate_required is True
    assert decision.approval_gate_issued is False
    assert decision.approval_id_generated is False
    assert decision.approval_command_generated is False
    assert decision.approval_command_template_only is True
    assert decision.approval_command_copyable is False
    assert decision.final_dynamic_preflight_required is True
    assert decision.dry_run_only is True
    assert decision.live_order_once_called is False
    assert decision.private_api_called is False
    assert decision.broker_called is False
    assert decision.read_only_api_called is False


def test_blocked_final_dynamic_preflight_blocks_and_preserves_reasons() -> None:
    blocked_preflight = _evaluate(spread_jpy=0.02).decision
    result = _boundary(preflight=blocked_preflight)

    assert (
        result.boundary_status
        is LiveOrderOneShotBoundaryStatus.BLOCKED_ONE_SHOT_LIVE_BOUNDARY
    )
    assert "spread_too_wide" in result.blocked_reasons
    assert (
        LiveOrderOneShotBoundaryBlockReason.FINAL_DYNAMIC_PREFLIGHT_NOT_READY.value
        in result.blocked_reasons
    )
    assert result.recommended_next_step == "fix_final_dynamic_preflight_blockers_no_post"


def test_preflight_safety_flags_block() -> None:
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.PREFLIGHT_ALLOWS_LIVE,
        preflight=_unchecked(_preflight(), allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.PREFLIGHT_NOT_DRY_RUN,
        preflight=_unchecked(_preflight(), dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        preflight=_unchecked(_preflight(), approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        preflight=_unchecked(_preflight(), approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        preflight=_unchecked(_preflight(), approval_command_generated=True),
    )


def test_unsupported_order_shape_blocks() -> None:
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SYMBOL,
        preflight=_unchecked(_preflight(), symbol="EUR_USD"),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SIDE,
        preflight=_unchecked(_preflight(), side="NO_TRADE"),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SIZE,
        preflight=_unchecked(_preflight(), size=200),
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        preflight=_unchecked(_preflight(), execution_type="LIMIT"),
    )


def test_one_shot_execution_boundary_blocks_unsafe_flags() -> None:
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        post_attempt_limit=2,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.POST_ALREADY_EXECUTED,
        post_executed=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        live_order_once_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.PRIVATE_API_ALREADY_CALLED,
        private_api_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.BROKER_ALREADY_CALLED,
        broker_called=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.READ_ONLY_API_ALREADY_CALLED,
        read_only_api_called=True,
    )


def test_no_retry_loop_or_order_mutation_flags_block() -> None:
    _assert_blocked(LiveOrderOneShotBoundaryBlockReason.RETRY_ALLOWED, retry_allowed=True)
    _assert_blocked(LiveOrderOneShotBoundaryBlockReason.LOOP_ALLOWED, loop_allowed=True)
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.ADD_ORDER_ALLOWED,
        add_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.CHANGE_ORDER_ALLOWED,
        change_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.CANCEL_ORDER_ALLOWED,
        cancel_order_allowed=True,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.CLOSE_ORDER_ALLOWED,
        close_order_allowed=True,
    )


def test_body_and_reconciliation_boundary_blocks() -> None:
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
        outbound_body_allowlist_matched=False,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
        request_body_equals_signing_body=False,
    )
    _assert_blocked(
        LiveOrderOneShotBoundaryBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        post_reconciliation_required=False,
    )


def test_body_allowlist_and_forbidden_fields_are_sanitized_field_names_only() -> None:
    decision = _boundary().decision

    assert decision.body_fields_allowlist == ONE_SHOT_BODY_FIELDS_ALLOWLIST
    assert decision.body_fields_forbidden == ONE_SHOT_BODY_FIELDS_FORBIDDEN
    assert decision.request_body_fingerprint_label == REQUEST_BODY_FINGERPRINT_LABEL
    assert decision.signing_body_fingerprint_label == SIGNING_BODY_FINGERPRINT_LABEL
    assert "symbol" in decision.body_fields_allowlist
    assert "side" in decision.body_fields_allowlist
    assert "size" in decision.body_fields_allowlist
    assert "executionType" in decision.body_fields_allowlist
    assert "secret" in decision.body_fields_forbidden
    assert "rawResponse" in decision.body_fields_forbidden
    assert "orderId" in decision.body_fields_forbidden
    assert "cancelOrder" in decision.body_fields_forbidden


def test_reconciliation_plan_requires_later_read_only_checks_without_executing() -> None:
    plan = _boundary().decision.post_reconciliation_plan

    assert plan.required is True
    assert plan.read_only_after_post_required is True
    assert plan.account_assets_check_required is True
    assert plan.open_positions_check_required is True
    assert plan.active_orders_check_required is True
    assert plan.result_unknown_check_required is True
    assert plan.raw_response_storage_forbidden is True
    assert plan.raw_response_display_forbidden is True
    assert plan.order_id_display_forbidden is True
    assert plan.execution_id_display_forbidden is True
    assert plan.position_id_display_forbidden is True


def test_check_results_cover_one_shot_body_and_reconciliation_checks() -> None:
    check_names = {check.name for check in _boundary().decision.check_results}

    assert "final_dynamic_preflight_decision" in check_names
    assert "post_attempt_limit" in check_names
    assert "post_not_executed" in check_names
    assert "live_order_once_not_called" in check_names
    assert "private_api_not_called" in check_names
    assert "broker_not_called" in check_names
    assert "read_only_api_not_called" in check_names
    assert "no_retry" in check_names
    assert "no_loop" in check_names
    assert "no_add_order" in check_names
    assert "no_change_order" in check_names
    assert "no_cancel_order" in check_names
    assert "no_close_order" in check_names
    assert "outbound_body_allowlist" in check_names
    assert "request_body_equals_signing_body" in check_names
    assert "post_reconciliation_required" in check_names


def test_markdown_rendering_includes_required_dry_run_warnings() -> None:
    markdown = render_live_order_one_shot_boundary_markdown(_boundary().decision)

    assert "This one-shot live boundary model is dry-run only." in markdown
    assert "This model does not call read-only API." in markdown
    assert "This model does not call Private API." in markdown
    assert "This model does not call live_order_once." in markdown
    assert "This model does not execute HTTP POST." in markdown
    assert "This model does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_one_shot_boundary_markdown(_boundary().decision)
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
    decision = _boundary().decision
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
        "pbcopy": True,
        "ledger_path": "x",
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_one_shot_boundary(
                final_dynamic_preflight_decision=_preflight(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_boundary_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_one_shot_boundary as module

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
