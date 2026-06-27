from __future__ import annotations

from dataclasses import asdict

from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_COMMAND_TEMPLATE_PREFIX,
    APPROVAL_GATE_TTL_SECONDS,
    APPROVAL_ID_PLACEHOLDER,
    APPROVAL_SIDE_PLACEHOLDER,
)
from app.live_verification.live_order_approval_gate_preview import (
    LiveOrderApprovalGatePreviewBlockReason,
    LiveOrderApprovalGatePreviewStatus,
)
from app.live_verification.live_order_approval_validation_simulator import (
    LIVE_ORDER_APPROVAL_VALIDATION_SIMULATION_ID_PREFIX,
    LiveOrderApprovalValidationSimulationBlockReason,
    LiveOrderApprovalValidationSimulationStatus,
    render_live_order_approval_validation_simulation_markdown,
    simulate_live_order_approval_validation,
)
from app.tests.test_live_verification_live_order_approval_gate_design import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_approval_gate_preview import (
    _preview,
)


def _simulate(
    *,
    preview=None,
    command: str | None = None,
    ttl_seconds: int = APPROVAL_GATE_TTL_SECONDS,
    same_session: bool = True,
    already_used: bool = False,
):
    approval_preview = preview or _preview().preview
    return simulate_live_order_approval_validation(
        approval_gate_preview=approval_preview,
        simulated_command_input=(
            approval_preview.approval_command_template if command is None else command
        ),
        simulated_ttl_seconds=ttl_seconds,
        same_session=same_session,
        already_used=already_used,
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    reason: LiveOrderApprovalValidationSimulationBlockReason | str,
    preview=None,
    command: str | None = None,
    ttl_seconds: int = APPROVAL_GATE_TTL_SECONDS,
    same_session: bool = True,
    already_used: bool = False,
) -> None:
    result = _simulate(
        preview=preview,
        command=command,
        ttl_seconds=ttl_seconds,
        same_session=same_session,
        already_used=already_used,
    )
    expected = (
        reason.value
        if isinstance(reason, LiveOrderApprovalValidationSimulationBlockReason)
        else reason
    )

    assert (
        result.simulation_status
        is LiveOrderApprovalValidationSimulationStatus.BLOCKED_APPROVAL_VALIDATION_SIMULATION
    )
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_template_only is True
    assert result.approval_command_copyable is False
    assert result.final_dynamic_preflight_required is True
    assert expected in result.blocked_reasons


def test_fake_template_exact_match_passes_simulated_validation_only() -> None:
    result = _simulate()
    simulation = result.simulation

    assert simulation.simulation_id.startswith(
        LIVE_ORDER_APPROVAL_VALIDATION_SIMULATION_ID_PREFIX
    )
    assert (
        simulation.simulation_status
        is LiveOrderApprovalValidationSimulationStatus.SIMULATED_APPROVAL_VALIDATION_PASSED
    )
    assert simulation.preview_status == "READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW"
    assert simulation.simulated_command_received is True
    assert simulation.simulated_command_exact_match is True
    assert simulation.simulated_command_template_only is True
    assert simulation.simulated_command_copyable is False
    assert simulation.simulated_ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    assert simulation.same_session is True
    assert simulation.already_used is False
    assert simulation.blocked_reasons == ()
    assert result.recommended_next_step == (
        "prepare_future_final_dynamic_preflight_design_no_post"
    )


def test_simulation_safety_defaults_are_always_fixed() -> None:
    simulation = _simulate().simulation

    assert simulation.allowed_for_live is False
    assert simulation.requires_human_approval is True
    assert simulation.approval_gate_required is True
    assert simulation.approval_gate_issued is False
    assert simulation.approval_id_generated is False
    assert simulation.approval_command_generated is False
    assert simulation.approval_command_template_only is True
    assert simulation.approval_command_copyable is False
    assert simulation.ttl_seconds == 300
    assert simulation.exact_match_required is True
    assert simulation.same_session_required is True
    assert simulation.final_dynamic_preflight_required is True
    assert simulation.dry_run_only is True


def test_blocked_preview_blocks_simulation_and_preserves_preview_reasons() -> None:
    blocked_preview = _unchecked(
        _preview().preview,
        preview_status=LiveOrderApprovalGatePreviewStatus.BLOCKED_APPROVAL_GATE_PREVIEW,
        blocked_reasons=(LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_READY.value,),
    )

    result = _simulate(preview=blocked_preview)

    assert (
        result.simulation_status
        is LiveOrderApprovalValidationSimulationStatus.BLOCKED_APPROVAL_VALIDATION_SIMULATION
    )
    assert (
        LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_NOT_READY.value
        in result.blocked_reasons
    )
    assert LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_READY.value in (
        result.blocked_reasons
    )
    assert result.recommended_next_step == "fix_approval_gate_preview_blockers_no_post"


def test_preview_allowed_for_live_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, allowed_for_live=True),
        reason=LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_ALLOWS_LIVE,
    )


def test_preview_not_dry_run_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, dry_run_only=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_NOT_DRY_RUN,
    )


def test_preview_missing_human_approval_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, requires_human_approval=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_preview_missing_approval_gate_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_gate_required=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_preview_existing_approval_gate_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_gate_issued=True),
        reason=LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
    )


def test_preview_generated_id_or_command_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_id_generated=True),
        reason=LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_ID_ALREADY_GENERATED,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_command_generated=True),
        reason=LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
    )


def test_preview_copyable_or_non_template_command_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_command_template_only=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, approval_command_copyable=True),
        reason=LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_COPYABLE,
    )


def test_preview_missing_final_dynamic_preflight_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, final_dynamic_preflight_required=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
    )


def test_preview_invalid_ttl_or_match_rules_block_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, ttl_seconds=301),
        reason=LiveOrderApprovalValidationSimulationBlockReason.INVALID_PREVIEW_TTL_SECONDS,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, exact_match_required=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.EXACT_MATCH_NOT_REQUIRED,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, same_session_required=False),
        reason=LiveOrderApprovalValidationSimulationBlockReason.SAME_SESSION_NOT_REQUIRED,
    )


def test_preview_unsupported_order_shape_blocks_simulation() -> None:
    _assert_blocked(
        preview=_unchecked(_preview().preview, symbol="EUR_USD"),
        reason=LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SYMBOL,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, side="NO_TRADE"),
        reason=LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SIDE,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, size=200),
        reason=LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SIZE,
    )
    _assert_blocked(
        preview=_unchecked(_preview().preview, execution_type="LIMIT"),
        reason=LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_missing_or_mismatched_simulated_command_blocks() -> None:
    _assert_blocked(
        command="",
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_SIMULATED_COMMAND,
    )
    _assert_blocked(
        command=_preview().preview.approval_command_template.replace("USD_JPY", "EUR_USD"),
        reason=LiveOrderApprovalValidationSimulationBlockReason.SIMULATED_COMMAND_MISMATCH,
    )


def test_ttl_boundary_passes_at_300_and_blocks_after_300() -> None:
    assert _simulate(ttl_seconds=300).simulation_status is (
        LiveOrderApprovalValidationSimulationStatus.SIMULATED_APPROVAL_VALIDATION_PASSED
    )
    _assert_blocked(
        ttl_seconds=301,
        reason=LiveOrderApprovalValidationSimulationBlockReason.EXPIRED_TTL,
    )


def test_different_session_or_used_command_blocks() -> None:
    _assert_blocked(
        same_session=False,
        reason=LiveOrderApprovalValidationSimulationBlockReason.DIFFERENT_SESSION,
    )
    _assert_blocked(
        already_used=True,
        reason=LiveOrderApprovalValidationSimulationBlockReason.ALREADY_USED,
    )


def test_line_breaks_and_extra_spaces_block() -> None:
    template = _preview().preview.approval_command_template

    _assert_blocked(
        command=template.replace(" ", "\n", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_LINE_BREAK,
    )
    _assert_blocked(
        command=f" {template}",
        reason=LiveOrderApprovalValidationSimulationBlockReason.HAS_LEADING_OR_TRAILING_SPACE,
    )
    _assert_blocked(
        command=template.replace(" SYMBOL=", "  SYMBOL=", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_REPEATED_SPACES,
    )


def test_missing_or_duplicate_ack_token_blocks() -> None:
    template = _preview().preview.approval_command_template
    ack_token = "ACK_NO_CLOSE=YES"

    _assert_blocked(
        command=template.replace(f" {ack_token}", ""),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_ACK_TOKEN,
    )
    _assert_blocked(
        command=f"{template} {ack_token}",
        reason=LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
    )


def test_extra_token_and_invalid_prefix_block() -> None:
    template = _preview().preview.approval_command_template

    _assert_blocked(
        command=f"{template} EXTRA=YES",
        reason=LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
    )
    _assert_blocked(
        command=template.replace(APPROVAL_COMMAND_TEMPLATE_PREFIX, "BAD_TEMPLATE", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.INVALID_COMMAND_PREFIX,
    )


def test_real_approval_command_or_id_shape_blocks() -> None:
    template = _preview().preview.approval_command_template

    _assert_blocked(
        command=template.replace(APPROVAL_COMMAND_TEMPLATE_PREFIX, "STEP4_APPROVE", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_COMMAND,
    )
    _assert_blocked(
        command=template.replace(APPROVAL_ID_PLACEHOLDER, "STEP4F-F1007D35", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_ID,
    )


def test_missing_placeholders_or_side_placeholder_blocks() -> None:
    template = _preview().preview.approval_command_template

    _assert_blocked(
        command=template.replace(APPROVAL_ID_PLACEHOLDER, "<MISSING_APPROVAL_ID>", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_APPROVAL_ID_PLACEHOLDER,
    )
    _assert_blocked(
        command=template.replace(APPROVAL_SIDE_PLACEHOLDER, "BUY", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.MISSING_SIDE_PLACEHOLDER,
    )
    _assert_blocked(
        command=template.replace(APPROVAL_SIDE_PLACEHOLDER, "BUY", 1),
        reason=LiveOrderApprovalValidationSimulationBlockReason.NOT_PLACEHOLDER_ONLY,
    )


def test_validation_rule_results_cover_required_approval_rules() -> None:
    rule_ids = {rule.rule_id for rule in _simulate().simulation.validation_rule_results}

    assert "preview_ready" in rule_ids
    assert "exact_match" in rule_ids
    assert "ttl_300_seconds" in rule_ids
    assert "same_codex_session" in rule_ids
    assert "unused_once" in rule_ids
    assert "all_ack_tokens" in rule_ids
    assert "no_extra_tokens" in rule_ids
    assert "no_line_breaks" in rule_ids
    assert "no_extra_spaces" in rule_ids
    assert "template_prefix" in rule_ids
    assert "placeholder_only" in rule_ids


def test_simulation_ack_tokens_match_required_acks() -> None:
    simulation = _simulate().simulation

    assert simulation.ack_tokens == APPROVAL_ACK_TOKENS
    assert "ACK_ORDER_PERMISSION=YES" in simulation.ack_tokens
    assert "ACK_IP_ACCOUNT_CHECK=YES" in simulation.ack_tokens


def test_markdown_rendering_includes_dry_run_no_approval_no_live_warnings() -> None:
    markdown = render_live_order_approval_validation_simulation_markdown(
        _simulate().simulation
    )

    assert "This approval validation simulation is dry-run only." in markdown
    assert "This simulation is not a real approval gate." in markdown
    assert "This simulation does not generate a real approval_id." in markdown
    assert "This simulation does not generate a real approval command." in markdown
    assert "This simulation does not authorize final dynamic preflight." in markdown
    assert "This simulation does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "simulated_command_exact_match: True" in markdown
    assert "approval_id_placeholder" in markdown


def test_markdown_omits_forbidden_actual_values_and_input_command_text() -> None:
    template = _preview().preview.approval_command_template
    markdown = render_live_order_approval_validation_simulation_markdown(
        _simulate(command=template).simulation
    )
    forbidden_actual_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
        template,
    )

    for value in forbidden_actual_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    simulation = _simulate().simulation
    serialized = str(asdict(simulation))
    rendered = repr(simulation)
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


def test_simulator_builder_does_not_accept_forbidden_real_approval_or_secret_fields() -> None:
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
            simulate_live_order_approval_validation(
                approval_gate_preview=_preview().preview,
                simulated_command_input=_preview().preview.approval_command_template,
                simulated_ttl_seconds=300,
                same_session=True,
                already_used=False,
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_simulator_module_has_no_ordering_api_or_real_approval_dependencies() -> None:
    import app.live_verification.live_order_approval_validation_simulator as module

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
