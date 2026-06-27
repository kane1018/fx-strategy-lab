from __future__ import annotations

import re
from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_COMMAND_TEMPLATE_PREFIX,
    APPROVAL_GATE_TTL_SECONDS,
    APPROVAL_ID_PLACEHOLDER,
    LiveOrderApprovalGateDesignBlockReason,
)
from app.live_verification.live_order_approval_gate_preview import (
    LIVE_ORDER_APPROVAL_GATE_PREVIEW_ID_PREFIX,
    LiveOrderApprovalGatePreviewBlockReason,
    LiveOrderApprovalGatePreviewStatus,
    build_live_order_approval_gate_preview,
    render_live_order_approval_gate_preview_markdown,
)
from app.tests.test_live_verification_live_order_approval_gate_design import (
    CREATED_AT,
    _design,
    _handoff_package,
    _unchecked,
)


def _preview(*, design=None):
    return build_live_order_approval_gate_preview(
        approval_gate_design=design or _design().design,
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    reason: LiveOrderApprovalGatePreviewBlockReason | str,
    design=None,
) -> None:
    result = _preview(design=design)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderApprovalGatePreviewBlockReason)
        else reason
    )

    assert (
        result.preview_status
        is LiveOrderApprovalGatePreviewStatus.BLOCKED_APPROVAL_GATE_PREVIEW
    )
    assert result.preview.preview_status is result.preview_status
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_template_only is True
    assert result.approval_command_copyable is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_approval_gate_design_blockers_no_post"


def test_ready_design_builds_ready_fake_approval_gate_preview() -> None:
    result = _preview()
    preview = result.preview

    assert preview.preview_id.startswith(LIVE_ORDER_APPROVAL_GATE_PREVIEW_ID_PREFIX)
    assert (
        preview.preview_status
        is LiveOrderApprovalGatePreviewStatus.READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
    )
    assert preview.design_status == "READY_FOR_APPROVAL_GATE_DESIGN_REVIEW"
    assert preview.allowed_for_live is False
    assert preview.approval_gate_issued is False
    assert preview.approval_id_generated is False
    assert preview.approval_command_generated is False
    assert preview.approval_command_template_only is True
    assert preview.approval_command_copyable is False
    assert preview.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert preview.exact_match_required is True
    assert preview.same_session_required is True
    assert preview.final_dynamic_preflight_required is True
    assert preview.dry_run_only is True
    assert preview.symbol == "USD_JPY"
    assert preview.side == "BUY"
    assert preview.size == 100
    assert preview.execution_type == "MARKET"
    assert preview.blocked_reasons == ()
    assert result.recommended_next_step == "review_fake_approval_gate_preview_no_post"


def test_approval_gate_preview_safety_defaults_are_always_fixed() -> None:
    preview = _preview().preview

    assert preview.allowed_for_live is False
    assert preview.requires_human_approval is True
    assert preview.approval_gate_required is True
    assert preview.approval_gate_issued is False
    assert preview.approval_id_generated is False
    assert preview.approval_command_generated is False
    assert preview.approval_command_template_only is True
    assert preview.approval_command_copyable is False
    assert preview.ttl_seconds == 300
    assert preview.exact_match_required is True
    assert preview.same_session_required is True
    assert preview.final_dynamic_preflight_required is True
    assert preview.dry_run_only is True


def test_blocked_design_builds_blocked_preview() -> None:
    blocked_handoff = _handoff_package(
        operator_review=None,
        allowed_for_live=True,
    )
    blocked_design = _design(handoff_package=blocked_handoff).design

    _assert_blocked(
        design=blocked_design,
        reason=LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_READY,
    )
    assert LiveOrderApprovalGateDesignBlockReason.HANDOFF_ALLOWS_LIVE.value in _preview(
        design=blocked_design
    ).blocked_reasons


def test_blocked_reasons_are_preserved() -> None:
    blocked_handoff = _handoff_package(
        operator_review=None,
        allowed_for_live=True,
    )
    result = _preview(design=_design(handoff_package=blocked_handoff).design)

    assert "handoff_allows_live" in result.blocked_reasons


def test_design_allowed_for_live_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, allowed_for_live=True),
        reason=LiveOrderApprovalGatePreviewBlockReason.DESIGN_ALLOWS_LIVE,
    )


def test_design_not_dry_run_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, dry_run_only=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, requires_human_approval=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_gate_required=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_existing_approval_gate_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_gate_issued=True),
        reason=LiveOrderApprovalGatePreviewBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
    )


def test_existing_approval_id_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_id_generated=True),
        reason=LiveOrderApprovalGatePreviewBlockReason.APPROVAL_ID_ALREADY_GENERATED,
    )


def test_existing_approval_command_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_command_generated=True),
        reason=LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
    )


def test_non_template_approval_command_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_command_template_only=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
    )


def test_copyable_approval_command_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, approval_command_copyable=True),
        reason=LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_COPYABLE,
    )


def test_missing_final_dynamic_preflight_requirement_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, final_dynamic_preflight_required=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
    )


def test_invalid_ttl_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, ttl_seconds=301),
        reason=LiveOrderApprovalGatePreviewBlockReason.INVALID_TTL_SECONDS,
    )


def test_missing_exact_match_requirement_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, exact_match_required=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.EXACT_MATCH_NOT_REQUIRED,
    )


def test_missing_same_session_requirement_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, same_session_required=False),
        reason=LiveOrderApprovalGatePreviewBlockReason.SAME_SESSION_NOT_REQUIRED,
    )


def test_unsupported_symbol_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, symbol="EUR_USD"),
        reason=LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, side="NO_TRADE"),
        reason=LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, size=200),
        reason=LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_preview() -> None:
    _assert_blocked(
        design=_unchecked(_design().design, execution_type="LIMIT"),
        reason=LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_preview_template_is_placeholder_only_non_copyable_and_not_real_command() -> None:
    preview = _preview().preview

    assert preview.approval_id_placeholder == APPROVAL_ID_PLACEHOLDER
    assert preview.approval_command_template.startswith(APPROVAL_COMMAND_TEMPLATE_PREFIX)
    assert not preview.approval_command_template.startswith("STEP4_APPROVE")
    assert APPROVAL_ID_PLACEHOLDER in preview.approval_command_template
    assert "STEP4F-" not in preview.approval_command_template
    assert re.search(r"STEP4F-[0-9A-F]{8}", preview.approval_command_template) is None
    assert preview.approval_command_generated is False
    assert preview.approval_command_template_only is True
    assert preview.approval_command_copyable is False


def test_preview_ack_tokens_include_all_required_acknowledgements() -> None:
    preview = _preview().preview

    assert preview.ack_tokens == APPROVAL_ACK_TOKENS
    assert "ACK_ORDER_PERMISSION=YES" in preview.ack_tokens
    assert "ACK_IP_ACCOUNT_CHECK=YES" in preview.ack_tokens
    assert "ACK_STOP_ON_UNKNOWN=YES" in preview.ack_tokens


def test_preview_validation_rules_include_future_real_gate_constraints() -> None:
    rule_ids = {rule.rule_id for rule in _preview().preview.validation_rules}

    assert "future_real_gate_only" in rule_ids
    assert "fresh_preflight_before_id" in rule_ids
    assert "one_line_command" in rule_ids
    assert "exact_match" in rule_ids
    assert "same_codex_session" in rule_ids
    assert "ttl_300_seconds" in rule_ids
    assert "all_ack_tokens" in rule_ids
    assert "no_extra_tokens" in rule_ids
    assert "no_line_breaks" in rule_ids
    assert "no_extra_spaces" in rule_ids
    assert "not_from_preview" in rule_ids
    assert "final_preflight_after_approval" in rule_ids
    assert "no_live_post_before_final_preflight" in rule_ids


def test_display_allowed_fields_are_sanitized_preview_fields() -> None:
    fields_set = set(_preview().preview.display_allowed_fields)

    assert "preview_id" in fields_set
    assert "design_id" in fields_set
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
    assert "validation_rules" in fields_set


def test_display_forbidden_fields_include_credential_raw_id_and_real_approval_terms() -> None:
    fields_set = set(_preview().preview.display_forbidden_fields)

    assert "API key value" in fields_set
    assert "secret value" in fields_set
    assert "signature value" in fields_set
    assert "headers value" in fields_set
    assert "raw response" in fields_set
    assert "order ID" in fields_set
    assert "execution ID" in fields_set
    assert "position ID" in fields_set
    assert "clientOrderId" in fields_set
    assert "real approval_id" in fields_set
    assert "real approval command" in fields_set
    assert "copyable approval command" in fields_set
    assert "clipboard approval command" in fields_set
    assert "approval command file" in fields_set


def test_final_dynamic_preflight_items_are_previewed_from_design() -> None:
    items = set(_preview().preview.final_dynamic_preflight_items)

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


def test_markdown_rendering_includes_required_warnings_and_non_copyable_boundary() -> None:
    markdown = render_live_order_approval_gate_preview_markdown(_preview().preview)

    assert "This approval gate preview is dry-run only." in markdown
    assert "This preview is not a real approval gate." in markdown
    assert "This preview does not generate a real approval_id." in markdown
    assert "This preview does not generate a real approval command." in markdown
    assert "This preview is not copyable approval text." in markdown
    assert "This preview does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "This is a non-copyable template." in markdown
    assert "Do not paste this into Codex." in markdown
    assert "approval_command_template" in markdown


def test_markdown_rendering_lists_preview_rules_ack_tokens_and_final_preflight() -> None:
    markdown = render_live_order_approval_gate_preview_markdown(_preview().preview)

    assert "## ACK Tokens" in markdown
    assert "## Validation Rules" in markdown
    assert "## Display Allowed Fields" in markdown
    assert "## Display Forbidden Fields" in markdown
    assert "## Final Dynamic Preflight Items" in markdown
    assert "ACK_ORDER_PERMISSION=YES" in markdown
    assert "exact_match: approval command must be exact match" in markdown
    assert "same_codex_session" in markdown
    assert "request body == signing body" in markdown


def test_markdown_rendering_omits_forbidden_actual_values_and_real_command() -> None:
    markdown = render_live_order_approval_gate_preview_markdown(_preview().preview)
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


def test_preview_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    preview = _preview().preview
    serialized = str(asdict(preview))
    rendered = repr(preview)
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


def test_preview_builder_does_not_accept_forbidden_order_credential_or_approval_fields() -> None:
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
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_approval_gate_preview(
                approval_gate_design=_design().design,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_approval_gate_preview_module_has_no_ordering_api_or_real_approval_dependencies() -> None:
    import app.live_verification.live_order_approval_gate_preview as module

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
    assert "pbcopy" not in module_names
