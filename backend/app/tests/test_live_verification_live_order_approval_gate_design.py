from __future__ import annotations

import re
from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_COMMAND_TEMPLATE_PREFIX,
    APPROVAL_GATE_TTL_SECONDS,
    APPROVAL_ID_PLACEHOLDER,
    APPROVAL_SIDE_PLACEHOLDER,
    LIVE_ORDER_APPROVAL_GATE_DESIGN_ID_PREFIX,
    LiveOrderApprovalGateDesignBlockReason,
    LiveOrderApprovalGateDesignStatus,
    build_live_order_approval_gate_design,
    render_live_order_approval_gate_design_markdown,
)
from app.live_verification.live_order_approval_handoff import (
    LiveOrderApprovalHandoffPackage,
    build_live_order_approval_handoff_package,
)
from app.live_verification.live_order_candidate import (
    LiveOrderCandidate,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
)
from app.live_verification.live_order_candidate_review import (
    LiveOrderCandidateReviewReport,
    build_live_order_candidate_review_report,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskSnapshot,
    evaluate_live_order_candidate_risk_gate,
)
from app.live_verification.live_order_candidate_trace import (
    build_live_order_candidate_trace_record,
)
from app.live_verification.live_order_operator_review import (
    LiveOrderOperatorReviewProcedure,
    build_live_order_operator_review_procedure,
)
from app.live_verification.live_order_review_session_bundle import (
    ReviewGatedSessionBundle,
    build_review_gated_session_bundle,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
    ReviewGatedSessionPolicySnapshot,
    evaluate_review_gated_session_policy,
)

CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _unchecked(base: object, **overrides: object):
    values = {field.name: getattr(base, field.name) for field in fields(base)}
    values.update(overrides)
    instance = object.__new__(type(base))
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5j_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized approval gate design fixture",
        market_snapshot_ref="snapshot_ref_001",
        paper_trade_ref="paper_ref_001",
        shadow_run_ref="shadow_ref_001",
        created_at=CREATED_AT,
        expires_at=CREATED_AT + timedelta(minutes=10),
    )
    candidate = build_live_order_candidate_dry_run(signal).candidate
    assert candidate is not None
    return _unchecked(candidate, **overrides)


def _risk_snapshot(**overrides: object) -> LiveOrderCandidateRiskSnapshot:
    values = {
        "snapshot_id": "risk_snapshot_step5j_001",
        "created_at": CREATED_AT,
        "account_assets_success": True,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "symbol_min_open_order_size": 100,
        "symbol_size_step": 1,
        "spread_jpy": 0.005,
        "ticker_age_seconds": 0.5,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
        "ledger_unused": True,
        "daily_live_attempt_count": 0,
        "session_live_attempt_count": 0,
        "result_unknown": False,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
    }
    values.update(overrides)
    return LiveOrderCandidateRiskSnapshot(**values)


def _review(
    *,
    candidate: LiveOrderCandidate | None = None,
    risk_snapshot: LiveOrderCandidateRiskSnapshot | None = None,
    **overrides: object,
) -> LiveOrderCandidateReviewReport:
    actual_candidate = candidate or _candidate()
    risk_decision = evaluate_live_order_candidate_risk_gate(
        candidate=actual_candidate,
        snapshot=risk_snapshot or _risk_snapshot(),
    )
    trace = build_live_order_candidate_trace_record(
        candidate=actual_candidate,
        risk_decision=risk_decision,
        created_at=CREATED_AT,
    ).trace_record
    report = build_live_order_candidate_review_report(
        candidate=actual_candidate,
        risk_decision=risk_decision,
        trace_record=trace,
        created_at=CREATED_AT,
    ).review_report
    return _unchecked(report, **overrides)


def _snapshot(**overrides: object) -> ReviewGatedSessionPolicySnapshot:
    values = {
        "snapshot_id": "session_snapshot_step5j_001",
        "created_at": CREATED_AT,
        "policy_date": "2026-01-01",
        "initial_micro_live_completed": True,
        "previous_order_result_confirmed": True,
        "previous_result_unknown": False,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "session_count_today": 0,
        "daily_live_size_total": 0,
        "last_session_completed_at": None,
        "minutes_since_last_session": None,
        "session_size": 100,
        "max_sessions_per_day": 2,
        "min_minutes_between_sessions": 120,
        "max_daily_size_total": 200,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
    }
    values.update(overrides)
    return ReviewGatedSessionPolicySnapshot(**values)


def _policy_decision(
    *,
    review_report: LiveOrderCandidateReviewReport | None = None,
    snapshot: ReviewGatedSessionPolicySnapshot | None = None,
    **overrides: object,
) -> ReviewGatedSessionPolicyDecision:
    decision = evaluate_review_gated_session_policy(
        review_report=review_report or _review(),
        snapshot=snapshot or _snapshot(),
    )
    return _unchecked(decision, **overrides)


def _bundle(
    *,
    review_report: LiveOrderCandidateReviewReport | None = None,
    policy_decision: ReviewGatedSessionPolicyDecision | None = None,
    session_count_today: int | None = 0,
    daily_live_size_total: int | None = 0,
    **overrides: object,
) -> ReviewGatedSessionBundle:
    actual_review = review_report or _review()
    actual_policy = policy_decision or _policy_decision(review_report=actual_review)
    bundle = build_review_gated_session_bundle(
        review_report=actual_review,
        session_policy_decision=actual_policy,
        created_at=CREATED_AT,
        session_count_today=session_count_today,
        daily_live_size_total=daily_live_size_total,
    ).bundle
    return _unchecked(bundle, **overrides)


def _operator_review(
    *,
    bundle: ReviewGatedSessionBundle | None = None,
    **overrides: object,
) -> LiveOrderOperatorReviewProcedure:
    procedure = build_live_order_operator_review_procedure(
        bundle=bundle or _bundle(),
        created_at=CREATED_AT,
    ).procedure
    return _unchecked(procedure, **overrides)


def _handoff_package(
    *,
    operator_review: LiveOrderOperatorReviewProcedure | None = None,
    **overrides: object,
) -> LiveOrderApprovalHandoffPackage:
    package = build_live_order_approval_handoff_package(
        operator_review=operator_review or _operator_review(),
        created_at=CREATED_AT,
    ).package
    return _unchecked(package, **overrides)


def _design(*, handoff_package: LiveOrderApprovalHandoffPackage | None = None):
    return build_live_order_approval_gate_design(
        handoff_package=handoff_package or _handoff_package(),
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    reason: LiveOrderApprovalGateDesignBlockReason | str,
    handoff_package: LiveOrderApprovalHandoffPackage | None = None,
) -> None:
    result = _design(handoff_package=handoff_package)
    expected = (
        reason.value if isinstance(reason, LiveOrderApprovalGateDesignBlockReason) else reason
    )

    assert (
        result.design_status
        is LiveOrderApprovalGateDesignStatus.BLOCKED_APPROVAL_GATE_DESIGN
    )
    assert result.design.design_status is result.design_status
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_template_only is True
    assert result.approval_command_copyable is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_handoff_blockers_no_post"


def test_ready_handoff_builds_ready_fake_approval_gate_design() -> None:
    result = _design()
    design = result.design

    assert design.design_id.startswith(LIVE_ORDER_APPROVAL_GATE_DESIGN_ID_PREFIX)
    assert (
        design.design_status
        is LiveOrderApprovalGateDesignStatus.READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
    )
    assert design.eligible_for_operator_review is True
    assert design.allowed_for_live is False
    assert design.approval_gate_issued is False
    assert design.approval_id_generated is False
    assert design.approval_command_generated is False
    assert design.approval_command_template_only is True
    assert design.approval_command_copyable is False
    assert design.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert design.exact_match_required is True
    assert design.same_session_required is True
    assert design.final_dynamic_preflight_required is True
    assert design.dry_run_only is True
    assert design.symbol == "USD_JPY"
    assert design.side == "BUY"
    assert design.size == 100
    assert design.execution_type == "MARKET"
    assert design.blocked_reasons == ()
    assert result.recommended_next_step == "prepare_future_fake_approval_gate_review_no_post"


def test_approval_gate_design_safety_defaults_are_always_fixed() -> None:
    design = _design().design

    assert design.allowed_for_live is False
    assert design.requires_human_approval is True
    assert design.approval_gate_required is True
    assert design.approval_gate_issued is False
    assert design.approval_id_generated is False
    assert design.approval_command_generated is False
    assert design.approval_command_template_only is True
    assert design.approval_command_copyable is False
    assert design.ttl_seconds == 300
    assert design.exact_match_required is True
    assert design.same_session_required is True
    assert design.final_dynamic_preflight_required is True
    assert design.dry_run_only is True


def test_blocked_handoff_builds_blocked_design() -> None:
    blocked_handoff = _handoff_package(
        operator_review=_operator_review(bundle=_bundle(remaining_sessions_today=0))
    )

    _assert_blocked(
        handoff_package=blocked_handoff,
        reason=LiveOrderApprovalGateDesignBlockReason.HANDOFF_NOT_READY,
    )


def test_blocked_reasons_are_preserved() -> None:
    blocked_handoff = _handoff_package(
        operator_review=_operator_review(bundle=_bundle(remaining_daily_size=99))
    )
    result = _design(handoff_package=blocked_handoff)

    assert "insufficient_remaining_daily_size" in result.blocked_reasons


def test_handoff_allowed_for_live_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(allowed_for_live=True),
        reason=LiveOrderApprovalGateDesignBlockReason.HANDOFF_ALLOWS_LIVE,
    )


def test_handoff_not_dry_run_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(dry_run_only=False),
        reason=LiveOrderApprovalGateDesignBlockReason.HANDOFF_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(requires_human_approval=False),
        reason=LiveOrderApprovalGateDesignBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(approval_gate_required=False),
        reason=LiveOrderApprovalGateDesignBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_existing_approval_gate_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(approval_gate_issued=True),
        reason=LiveOrderApprovalGateDesignBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
    )


def test_existing_approval_command_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(approval_command_generated=True),
        reason=LiveOrderApprovalGateDesignBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
    )


def test_missing_final_dynamic_preflight_requirement_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(final_dynamic_preflight_required=False),
        reason=LiveOrderApprovalGateDesignBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
    )


def test_unsupported_symbol_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(symbol="EUR_USD"),
        reason=LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(side="NO_TRADE"),
        reason=LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(size=200),
        reason=LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_design() -> None:
    _assert_blocked(
        handoff_package=_handoff_package(execution_type="LIMIT"),
        reason=LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_fake_approval_id_placeholder_is_not_a_real_step4f_id() -> None:
    template = _design().design.command_template

    assert template.approval_id_placeholder == APPROVAL_ID_PLACEHOLDER
    assert not template.approval_id_placeholder.startswith("STEP4F-")
    assert re.search(r"STEP4F-[0-9A-F]{8}", template.template_text) is None


def test_fake_approval_command_template_is_not_copyable_or_real_command() -> None:
    template = _design().design.command_template

    assert template.template_text.startswith(APPROVAL_COMMAND_TEMPLATE_PREFIX)
    assert not template.template_text.startswith("STEP4_APPROVE")
    assert APPROVAL_ID_PLACEHOLDER in template.template_text
    assert APPROVAL_SIDE_PLACEHOLDER in template.template_text
    assert "STEP4F-" not in template.template_text
    assert template.template_only is True
    assert template.copyable is False


def test_fake_approval_command_template_contains_required_ack_tokens() -> None:
    template = _design().design.command_template

    assert template.ack_tokens == APPROVAL_ACK_TOKENS
    assert "ACK_ORDER_PERMISSION=YES" in template.ack_tokens
    assert "ACK_IP_ACCOUNT_CHECK=YES" in template.ack_tokens
    assert "ACK_STOP_ON_UNKNOWN=YES" in template.ack_tokens


def test_display_allowed_fields_are_sanitized_design_fields() -> None:
    fields_set = set(_design().design.display_allowed_fields)

    assert "design_id" in fields_set
    assert "handoff_id" in fields_set
    assert "candidate_id" in fields_set
    assert "symbol" in fields_set
    assert "side" in fields_set
    assert "size" in fields_set
    assert "executionType" in fields_set
    assert "allowed_for_live=false" in fields_set
    assert "approval_gate_issued=false" in fields_set
    assert "approval_id_generated=false" in fields_set
    assert "approval_command_generated=false" in fields_set
    assert "approval_command_template_only=true" in fields_set
    assert "approval_command_copyable=false" in fields_set


def test_display_forbidden_fields_include_credential_raw_id_and_real_approval_terms() -> None:
    fields_set = set(_design().design.display_forbidden_fields)

    assert "API key value" in fields_set
    assert "secret value" in fields_set
    assert "raw response" in fields_set
    assert "order ID" in fields_set
    assert "execution ID" in fields_set
    assert "position ID" in fields_set
    assert "clientOrderId" in fields_set
    assert "real approval_id" in fields_set
    assert "real approval command" in fields_set
    assert "copyable approval command" in fields_set


def test_final_dynamic_preflight_items_include_required_checks() -> None:
    items = set(_design().design.final_dynamic_preflight_items)

    assert "account/assets: success" in items
    assert "open_positions_count=0" in items
    assert "active_orders_count=0" in items
    assert "spread_jpy <= 0.01" in items
    assert "ledger unused" in items
    assert "Git clean" in items
    assert "tests pass" in items
    assert "secret scan pass" in items
    assert "outbound body allowlist matches" in items
    assert "request body == signing body" in items


def test_markdown_rendering_includes_required_warnings_and_template_boundary() -> None:
    markdown = render_live_order_approval_gate_design_markdown(_design().design)

    assert "This approval gate design is dry-run only." in markdown
    assert "This design is not an approval gate." in markdown
    assert "This design does not generate a real approval_id." in markdown
    assert "This design does not generate a real approval command." in markdown
    assert "This design does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert APPROVAL_ID_PLACEHOLDER in markdown
    assert "copyable: False" in markdown


def test_markdown_rendering_lists_allowed_forbidden_ack_and_final_preflight_sections() -> None:
    markdown = render_live_order_approval_gate_design_markdown(_design().design)

    assert "## Display Allowed Fields" in markdown
    assert "## Display Forbidden Fields" in markdown
    assert "## ACK Tokens" in markdown
    assert "## Final Dynamic Preflight Items" in markdown
    assert "approval_command_template_only=true" in markdown
    assert "real approval command" in markdown
    assert "ACK_ORDER_PERMISSION=YES" in markdown
    assert "request body == signing body" in markdown


def test_markdown_rendering_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_approval_gate_design_markdown(_design().design)
    forbidden_actual_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
    )

    for value in forbidden_actual_values:
        assert value not in markdown


def test_design_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    design = _design().design
    serialized = str(asdict(design))
    rendered = repr(design)
    forbidden_actual_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
    )

    for value in forbidden_actual_values:
        assert value not in serialized
        assert value not in rendered


def test_design_builder_does_not_accept_forbidden_order_credential_or_approval_fields() -> None:
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
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_approval_gate_design(
                handoff_package=_handoff_package(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_approval_gate_design_module_has_no_ordering_api_or_real_approval_dependencies() -> None:
    import app.live_verification.live_order_approval_gate_design as module

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
    assert "build_step4_approval_gate" not in module_names
    assert "evaluate_step4_approval" not in module_names
