from __future__ import annotations

from dataclasses import asdict

import pytest

from app.live_verification.live_order_real_approval_readiness import (
    DEFAULT_REAL_APPROVAL_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_NO_GO_CONDITIONS,
    DEFAULT_REAL_APPROVAL_STOP_CONDITIONS,
    LIVE_ORDER_REAL_APPROVAL_READINESS_ID_PREFIX,
    LiveOrderRealApprovalReadinessBlockReason,
    LiveOrderRealApprovalReadinessStatus,
    build_live_order_real_approval_readiness_checkpoint,
    render_live_order_real_approval_readiness_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _chain,
    _unchecked,
)


def _ready_kwargs() -> dict[str, bool]:
    return {
        "operator_reviewed_chain": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_auto_post": True,
        "operator_understands_future_steps_are_separate": True,
        "operator_understands_unknown_means_stop": True,
    }


def _checkpoint(chain_review=None, **overrides: object):
    if chain_review is None:
        chain_review = _chain().chain_review
    kwargs: dict[str, object] = {
        "e2e_chain_review": chain_review,
        "created_at": CREATED_AT,
        **_ready_kwargs(),
    }
    kwargs.update(overrides)
    return build_live_order_real_approval_readiness_checkpoint(**kwargs)


def _assert_blocked(
    reason: LiveOrderRealApprovalReadinessBlockReason | str,
    **overrides: object,
) -> None:
    result = _checkpoint(**overrides)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderRealApprovalReadinessBlockReason)
        else reason
    )

    assert (
        result.readiness_status
        is LiveOrderRealApprovalReadinessStatus.BLOCKED_REAL_APPROVAL_READINESS
    )
    assert result.readiness_ready is False
    assert result.eligible_for_future_real_approval_gate_planning is False
    assert result.allowed_for_live is False
    assert expected in result.blocked_reasons


def test_ready_e2e_chain_with_all_acknowledgements_is_readiness_ready_only() -> None:
    result = _checkpoint()
    checkpoint = result.checkpoint

    assert checkpoint.checkpoint_id.startswith(LIVE_ORDER_REAL_APPROVAL_READINESS_ID_PREFIX)
    assert (
        checkpoint.readiness_status
        is LiveOrderRealApprovalReadinessStatus.READY_FOR_REAL_APPROVAL_READINESS_REVIEW
    )
    assert checkpoint.readiness_ready is True
    assert checkpoint.eligible_for_future_real_approval_gate_planning is True
    assert checkpoint.allowed_for_live is False
    assert checkpoint.post_executed is False
    assert checkpoint.live_order_once_called is False
    assert checkpoint.recommended_next_step == (
        "stop_and_ask_user_before_future_real_approval_gate_step"
    )


def test_readiness_ready_safety_defaults_do_not_authorize_post_or_approval() -> None:
    checkpoint = _checkpoint().checkpoint

    assert checkpoint.allowed_for_live is False
    assert checkpoint.requires_human_approval is True
    assert checkpoint.explicit_user_confirmation_required is True
    assert checkpoint.real_approval_gate_separate_step_required is True
    assert checkpoint.fresh_preflight_separate_step_required is True
    assert checkpoint.one_shot_post_separate_step_required is True
    assert checkpoint.post_reconciliation_separate_step_required is True
    assert checkpoint.final_report_separate_step_required is True
    assert checkpoint.approval_gate_required is True
    assert checkpoint.approval_gate_issued is False
    assert checkpoint.approval_id_generated is False
    assert checkpoint.approval_command_generated is False
    assert checkpoint.approval_command_template_only is True
    assert checkpoint.approval_command_copyable is False
    assert checkpoint.final_dynamic_preflight_required is True
    assert checkpoint.dry_run_only is True
    assert checkpoint.post_attempt_limit == 1
    assert checkpoint.private_api_called is False
    assert checkpoint.broker_called is False
    assert checkpoint.read_only_api_called is False
    assert checkpoint.retry_allowed is False
    assert checkpoint.loop_allowed is False
    assert checkpoint.add_order_allowed is False
    assert checkpoint.change_order_allowed is False
    assert checkpoint.cancel_order_allowed is False
    assert checkpoint.close_order_allowed is False
    assert checkpoint.post_reconciliation_required is True


def test_blocked_e2e_chain_blocks_readiness_and_preserves_chain_reason() -> None:
    blocked_chain = _chain(candidate=None).chain_review
    result = _checkpoint(chain_review=blocked_chain)

    assert (
        result.readiness_status
        is LiveOrderRealApprovalReadinessStatus.BLOCKED_REAL_APPROVAL_READINESS
    )
    assert LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_READY.value in result.blocked_reasons
    assert "missing_required_stage" in result.blocked_reasons
    assert result.recommended_next_step == "fix_e2e_chain_blockers_no_post"


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    (
        (
            "allowed_for_live",
            True,
            LiveOrderRealApprovalReadinessBlockReason.CHAIN_ALLOWS_LIVE,
        ),
        ("dry_run_only", False, LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_DRY_RUN),
        (
            "approval_gate_issued",
            True,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_id_generated",
            True,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_command_generated",
            True,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_command_copyable",
            True,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        ("post_executed", True, LiveOrderRealApprovalReadinessBlockReason.POST_ALREADY_EXECUTED),
        (
            "live_order_once_called",
            True,
            LiveOrderRealApprovalReadinessBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "private_api_called",
            True,
            LiveOrderRealApprovalReadinessBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        ("broker_called", True, LiveOrderRealApprovalReadinessBlockReason.BROKER_ALREADY_CALLED),
        (
            "read_only_api_called",
            True,
            LiveOrderRealApprovalReadinessBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        ("symbol", "EUR_USD", LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SYMBOL),
        ("side", "NO_TRADE", LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SIDE),
        ("size", 200, LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SIZE),
        (
            "execution_type",
            "LIMIT",
            LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        ),
        (
            "post_attempt_limit",
            2,
            LiveOrderRealApprovalReadinessBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        ),
        ("retry_allowed", True, LiveOrderRealApprovalReadinessBlockReason.RETRY_ALLOWED),
        ("loop_allowed", True, LiveOrderRealApprovalReadinessBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", True, LiveOrderRealApprovalReadinessBlockReason.ADD_ORDER_ALLOWED),
        (
            "change_order_allowed",
            True,
            LiveOrderRealApprovalReadinessBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            "cancel_order_allowed",
            True,
            LiveOrderRealApprovalReadinessBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            "close_order_allowed",
            True,
            LiveOrderRealApprovalReadinessBlockReason.CLOSE_ORDER_ALLOWED,
        ),
        (
            "post_reconciliation_required",
            False,
            LiveOrderRealApprovalReadinessBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        ),
    ),
)
def test_chain_mismatch_or_unsafe_flag_blocks_readiness(
    field_name: str,
    value: object,
    reason: LiveOrderRealApprovalReadinessBlockReason,
) -> None:
    unsafe_chain = _unchecked(_chain().chain_review, **{field_name: value})

    _assert_blocked(reason, chain_review=unsafe_chain)


@pytest.mark.parametrize(
    ("flag_name", "reason"),
    (
        (
            "operator_reviewed_chain",
            LiveOrderRealApprovalReadinessBlockReason.OPERATOR_REVIEW_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            LiveOrderRealApprovalReadinessBlockReason.REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_auto_post",
            LiveOrderRealApprovalReadinessBlockReason.NO_AUTO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_future_steps_are_separate",
            LiveOrderRealApprovalReadinessBlockReason.FUTURE_STEPS_SEPARATION_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            LiveOrderRealApprovalReadinessBlockReason.UNKNOWN_STOP_RULE_NOT_ACKNOWLEDGED,
        ),
        (
            "real_approval_gate_separate_step_required",
            LiveOrderRealApprovalReadinessBlockReason.REAL_APPROVAL_GATE_NOT_SEPARATE_STEP,
        ),
        (
            "fresh_preflight_separate_step_required",
            LiveOrderRealApprovalReadinessBlockReason.FRESH_PREFLIGHT_NOT_SEPARATE_STEP,
        ),
        (
            "one_shot_post_separate_step_required",
            LiveOrderRealApprovalReadinessBlockReason.ONE_SHOT_POST_NOT_SEPARATE_STEP,
        ),
        (
            "post_reconciliation_separate_step_required",
            LiveOrderRealApprovalReadinessBlockReason.POST_RECONCILIATION_NOT_SEPARATE_STEP,
        ),
        (
            "final_report_separate_step_required",
            LiveOrderRealApprovalReadinessBlockReason.FINAL_REPORT_NOT_SEPARATE_STEP,
        ),
    ),
)
def test_acknowledgement_or_future_step_separation_missing_blocks_readiness(
    flag_name: str,
    reason: LiveOrderRealApprovalReadinessBlockReason,
) -> None:
    _assert_blocked(reason, **{flag_name: False})


def test_go_no_go_and_stop_conditions_include_required_constraints() -> None:
    checkpoint = _checkpoint().checkpoint

    assert DEFAULT_REAL_APPROVAL_GO_CONDITIONS == checkpoint.go_conditions
    assert DEFAULT_REAL_APPROVAL_NO_GO_CONDITIONS == checkpoint.no_go_conditions
    assert DEFAULT_REAL_APPROVAL_STOP_CONDITIONS == checkpoint.stop_conditions
    assert "operator reviewed full chain" in checkpoint.go_conditions
    assert "explicit user confirmation is required before future real approval gate step" in (
        checkpoint.go_conditions
    )
    assert "any API/broker/live_order_once called" in checkpoint.no_go_conditions
    assert "any secret/raw response/ID exposure risk" in checkpoint.stop_conditions
    assert "any need to exceed one POST attempt" in checkpoint.stop_conditions


def test_check_results_include_required_readiness_checks() -> None:
    check_names = {check.name for check in _checkpoint().checkpoint.check_results}

    assert "e2e_chain_ready" in check_names
    assert "allowed_for_live_false" in check_names
    assert "approval_artifacts_not_generated" in check_names
    assert "post_not_executed" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "one_shot_constraints_preserved" in check_names
    assert "future_steps_separated" in check_names
    assert "operator_acknowledgements_present" in check_names
    assert "explicit_user_confirmation_required" in check_names
    assert "unknown_means_stop" in check_names


def test_markdown_rendering_includes_required_dry_run_warnings() -> None:
    markdown = render_live_order_real_approval_readiness_markdown(_checkpoint().checkpoint)

    assert "This real approval readiness checkpoint is dry-run only." in markdown
    assert "This checkpoint does not call read-only API." in markdown
    assert "This checkpoint does not call Private API." in markdown
    assert "This checkpoint does not call live_order_once." in markdown
    assert "This checkpoint does not execute HTTP POST." in markdown
    assert "This checkpoint does not issue a real approval gate." in markdown
    assert "This checkpoint does not generate a real approval command." in markdown
    assert "This checkpoint does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_real_approval_readiness_markdown(_checkpoint().checkpoint)
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
    checkpoint = _checkpoint().checkpoint
    serialized = str(asdict(checkpoint))
    rendered = repr(checkpoint)
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


def test_readiness_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_real_approval_readiness as module

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
