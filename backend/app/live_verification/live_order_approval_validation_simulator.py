"""Approval validation simulator for Step 5L."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_COMMAND_TEMPLATE_PREFIX,
    APPROVAL_GATE_TTL_SECONDS,
    APPROVAL_ID_PLACEHOLDER,
    APPROVAL_SIDE_PLACEHOLDER,
)
from app.live_verification.live_order_approval_gate_preview import (
    LiveOrderApprovalGatePreview,
    LiveOrderApprovalGatePreviewStatus,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_APPROVAL_VALIDATION_SIMULATION_ID_PREFIX = "LOCAVS-"

_REAL_APPROVAL_ID_PATTERN = re.compile(
    r"\b(?:STEP4F|STEP4|STEP5|APPROVAL)-[A-Za-z0-9_-]+\b"
)


class LiveOrderApprovalValidationSimulationStatus(str, Enum):
    SIMULATED_APPROVAL_VALIDATION_PASSED = "SIMULATED_APPROVAL_VALIDATION_PASSED"
    BLOCKED_APPROVAL_VALIDATION_SIMULATION = "BLOCKED_APPROVAL_VALIDATION_SIMULATION"


class LiveOrderApprovalValidationSimulationBlockReason(str, Enum):
    PREVIEW_NOT_READY = "preview_not_ready"
    PREVIEW_ALLOWS_LIVE = "preview_allows_live"
    PREVIEW_NOT_DRY_RUN = "preview_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_NOT_TEMPLATE_ONLY = "approval_command_not_template_only"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT = (
        "missing_final_dynamic_preflight_requirement"
    )
    INVALID_PREVIEW_TTL_SECONDS = "invalid_preview_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    MISSING_SIMULATED_COMMAND = "missing_simulated_command"
    SIMULATED_COMMAND_MISMATCH = "simulated_command_mismatch"
    EXPIRED_TTL = "expired_ttl"
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    DIFFERENT_SESSION = "different_session"
    ALREADY_USED = "already_used"
    CONTAINS_LINE_BREAK = "contains_line_break"
    HAS_LEADING_OR_TRAILING_SPACE = "has_leading_or_trailing_space"
    CONTAINS_REPEATED_SPACES = "contains_repeated_spaces"
    MISSING_ACK_TOKEN = "missing_ack_token"
    EXTRA_TOKEN = "extra_token"
    INVALID_COMMAND_PREFIX = "invalid_command_prefix"
    LOOKS_LIKE_REAL_APPROVAL_COMMAND = "looks_like_real_approval_command"
    LOOKS_LIKE_REAL_APPROVAL_ID = "looks_like_real_approval_id"
    MISSING_APPROVAL_ID_PLACEHOLDER = "missing_approval_id_placeholder"
    MISSING_SIDE_PLACEHOLDER = "missing_side_placeholder"
    NOT_PLACEHOLDER_ONLY = "not_placeholder_only"


@dataclass(frozen=True)
class LiveOrderApprovalValidationRuleResult:
    rule_id: str
    passed: bool
    blocked_reason: str
    detail: str

    def __post_init__(self) -> None:
        _require_non_empty("rule_id", self.rule_id)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("rule result passed must be bool")
        if self.passed:
            if self.blocked_reason:
                raise LiveVerificationValidationError(
                    "passed rule result cannot contain blocked reason"
                )
        else:
            _require_non_empty("blocked_reason", self.blocked_reason)
        _require_non_empty("detail", self.detail)


@dataclass(frozen=True)
class LiveOrderApprovalValidationSimulationSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError(
                "approval validation simulation section requires lines"
            )
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderApprovalValidationSimulation:
    simulation_id: str
    created_at: datetime
    preview_id: str
    design_id: str
    handoff_id: str
    operator_review_id: str
    bundle_id: str
    review_id: str
    candidate_id: str
    risk_decision_id: str
    trace_id: str
    session_policy_decision_id: str
    source_signal_id: str
    source_type: str
    strategy_name: str
    symbol: str
    side: str
    size: int
    execution_type: str
    preview_status: str
    simulation_status: LiveOrderApprovalValidationSimulationStatus
    simulated_command_received: bool
    simulated_command_exact_match: bool
    simulated_command_template_only: bool
    simulated_command_copyable: bool
    simulated_ttl_seconds: int | None
    same_session: bool
    already_used: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    ttl_seconds: int
    exact_match_required: bool
    same_session_required: bool
    final_dynamic_preflight_required: bool
    dry_run_only: bool
    approval_id_placeholder: str
    side_placeholder: str
    ack_tokens: tuple[str, ...]
    validation_rule_results: tuple[LiveOrderApprovalValidationRuleResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderApprovalValidationSimulationSection, ...]

    def __post_init__(self) -> None:
        _validate_approval_validation_simulation(self)


@dataclass(frozen=True)
class LiveOrderApprovalValidationSimulationBuildResult:
    simulation: LiveOrderApprovalValidationSimulation
    simulation_id: str
    simulation_status: LiveOrderApprovalValidationSimulationStatus
    blocked_reasons: tuple[str, ...]
    simulated_command_exact_match: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    final_dynamic_preflight_required: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.simulation.simulation_id != self.simulation_id:
            raise LiveVerificationValidationError("simulation_id mismatch")
        if self.simulation.simulation_status is not self.simulation_status:
            raise LiveVerificationValidationError("simulation_status mismatch")
        if self.simulation.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if (
            self.simulation.simulated_command_exact_match
            is not self.simulated_command_exact_match
        ):
            raise LiveVerificationValidationError("exact match mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("simulation never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("simulation never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("simulation never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "simulation never generates approval command"
            )
        if self.approval_command_template_only is not True:
            raise LiveVerificationValidationError("simulation remains template-only")
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("simulation command is not copyable")
        if self.final_dynamic_preflight_required is not True:
            raise LiveVerificationValidationError("final dynamic preflight remains required")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def simulate_live_order_approval_validation(
    *,
    approval_gate_preview: LiveOrderApprovalGatePreview,
    simulated_command_input: str,
    simulated_ttl_seconds: int,
    same_session: bool,
    already_used: bool,
    created_at: datetime | None = None,
) -> LiveOrderApprovalValidationSimulationBuildResult:
    """Simulate fake template validation without issuing approval or execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    command_text = simulated_command_input
    safe_simulated_ttl_seconds = (
        simulated_ttl_seconds if type(simulated_ttl_seconds) is int else None
    )
    safe_same_session = same_session if type(same_session) is bool else False
    safe_already_used = already_used if type(already_used) is bool else True
    blocked_reasons = _merge_reasons(
        _preview_blocked_reasons(approval_gate_preview),
        approval_gate_preview.blocked_reasons,
        _command_blocked_reasons(
            preview=approval_gate_preview,
            command_text=command_text,
            simulated_ttl_seconds=simulated_ttl_seconds,
            same_session=same_session,
            already_used=already_used,
        ),
    )
    rule_results = _validation_rule_results(
        preview=approval_gate_preview,
        command_text=command_text,
        simulated_ttl_seconds=safe_simulated_ttl_seconds,
        same_session=safe_same_session,
        already_used=safe_already_used,
    )

    if blocked_reasons:
        simulation_status = (
            LiveOrderApprovalValidationSimulationStatus.BLOCKED_APPROVAL_VALIDATION_SIMULATION
        )
        if _preview_blocked_reasons(approval_gate_preview):
            recommended_next_step = "fix_approval_gate_preview_blockers_no_post"
        else:
            recommended_next_step = "fix_simulated_approval_validation_inputs_no_post"
        summary = "blocked fake approval validation simulation; no approval is issued"
    else:
        simulation_status = (
            LiveOrderApprovalValidationSimulationStatus.SIMULATED_APPROVAL_VALIDATION_PASSED
        )
        recommended_next_step = "prepare_future_final_dynamic_preflight_design_no_post"
        summary = (
            "simulated approval validation passed for fake template only; "
            "no approval is issued"
        )

    simulation_id = make_live_order_approval_validation_simulation_id(
        preview_id=approval_gate_preview.preview_id,
        candidate_id=approval_gate_preview.candidate_id,
        created_at=created,
        simulation_status=simulation_status,
        blocked_reasons=blocked_reasons,
        simulated_command_exact_match=command_text
        == approval_gate_preview.approval_command_template,
    )
    simulation = LiveOrderApprovalValidationSimulation(
        simulation_id=simulation_id,
        created_at=created,
        preview_id=approval_gate_preview.preview_id,
        design_id=approval_gate_preview.design_id,
        handoff_id=approval_gate_preview.handoff_id,
        operator_review_id=approval_gate_preview.operator_review_id,
        bundle_id=approval_gate_preview.bundle_id,
        review_id=approval_gate_preview.review_id,
        candidate_id=approval_gate_preview.candidate_id,
        risk_decision_id=approval_gate_preview.risk_decision_id,
        trace_id=approval_gate_preview.trace_id,
        session_policy_decision_id=approval_gate_preview.session_policy_decision_id,
        source_signal_id=approval_gate_preview.source_signal_id,
        source_type=approval_gate_preview.source_type,
        strategy_name=approval_gate_preview.strategy_name,
        symbol=approval_gate_preview.symbol,
        side=approval_gate_preview.side,
        size=approval_gate_preview.size,
        execution_type=approval_gate_preview.execution_type,
        preview_status=_enum_value(approval_gate_preview.preview_status),
        simulation_status=simulation_status,
        simulated_command_received=_has_text(command_text),
        simulated_command_exact_match=(
            command_text == approval_gate_preview.approval_command_template
        ),
        simulated_command_template_only=True,
        simulated_command_copyable=False,
        simulated_ttl_seconds=simulated_ttl_seconds,
        same_session=same_session,
        already_used=already_used,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        exact_match_required=True,
        same_session_required=True,
        final_dynamic_preflight_required=True,
        dry_run_only=True,
        approval_id_placeholder=APPROVAL_ID_PLACEHOLDER,
        side_placeholder=APPROVAL_SIDE_PLACEHOLDER,
        ack_tokens=APPROVAL_ACK_TOKENS,
        validation_rule_results=rule_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_simulation_sections(blocked_reasons),
    )
    return LiveOrderApprovalValidationSimulationBuildResult(
        simulation=simulation,
        simulation_id=simulation.simulation_id,
        simulation_status=simulation.simulation_status,
        blocked_reasons=simulation.blocked_reasons,
        simulated_command_exact_match=simulation.simulated_command_exact_match,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        final_dynamic_preflight_required=True,
        recommended_next_step=simulation.recommended_next_step,
    )


def render_live_order_approval_validation_simulation_markdown(
    simulation: LiveOrderApprovalValidationSimulation,
) -> str:
    """Render a sanitized fake approval validation simulation report."""
    blocked_text = (
        ", ".join(simulation.blocked_reasons) if simulation.blocked_reasons else "none"
    )
    lines = [
        "# Live Order Approval Validation Simulation",
        "",
        "This approval validation simulation is dry-run only.",
        "This simulation is not a real approval gate.",
        "This simulation does not generate a real approval_id.",
        "This simulation does not generate a real approval command.",
        "This simulation does not authorize final dynamic preflight.",
        "This simulation does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- simulation_id: {simulation.simulation_id}",
        f"- simulation_status: {simulation.simulation_status.value}",
        f"- preview_id: {simulation.preview_id}",
        f"- summary: {simulation.summary}",
        f"- recommended_next_step: {simulation.recommended_next_step}",
        "",
        "## References",
        "",
        f"- design_id: {simulation.design_id}",
        f"- handoff_id: {simulation.handoff_id}",
        f"- operator_review_id: {simulation.operator_review_id}",
        f"- bundle_id: {simulation.bundle_id}",
        f"- review_id: {simulation.review_id}",
        f"- candidate_id: {simulation.candidate_id}",
        f"- risk_decision_id: {simulation.risk_decision_id}",
        f"- trace_id: {simulation.trace_id}",
        f"- session_policy_decision_id: {simulation.session_policy_decision_id}",
        f"- source_signal_id: {simulation.source_signal_id}",
        f"- source_type: {simulation.source_type}",
        f"- strategy_name: {simulation.strategy_name}",
        "",
        "## Candidate",
        "",
        f"- symbol: {simulation.symbol}",
        f"- side: {simulation.side}",
        f"- size: {simulation.size}",
        f"- executionType: {simulation.execution_type}",
        "",
        "## Simulation Result",
        "",
        f"- preview_status: {simulation.preview_status}",
        f"- simulated_command_received: {simulation.simulated_command_received}",
        f"- simulated_command_exact_match: {simulation.simulated_command_exact_match}",
        f"- simulated_command_template_only: {simulation.simulated_command_template_only}",
        f"- simulated_command_copyable: {simulation.simulated_command_copyable}",
        f"- simulated_ttl_seconds: {simulation.simulated_ttl_seconds}",
        f"- same_session: {simulation.same_session}",
        f"- already_used: {simulation.already_used}",
        f"- blocked_reasons: {blocked_text}",
        "",
        "## Safety Flags",
        "",
        f"- allowed_for_live: {simulation.allowed_for_live}",
        f"- requires_human_approval: {simulation.requires_human_approval}",
        f"- approval_gate_required: {simulation.approval_gate_required}",
        f"- approval_gate_issued: {simulation.approval_gate_issued}",
        f"- approval_id_generated: {simulation.approval_id_generated}",
        f"- approval_command_generated: {simulation.approval_command_generated}",
        f"- approval_command_template_only: {simulation.approval_command_template_only}",
        f"- approval_command_copyable: {simulation.approval_command_copyable}",
        f"- ttl_seconds: {simulation.ttl_seconds}",
        f"- exact_match_required: {simulation.exact_match_required}",
        f"- same_session_required: {simulation.same_session_required}",
        (
            f"- final_dynamic_preflight_required: "
            f"{simulation.final_dynamic_preflight_required}"
        ),
        f"- dry_run_only: {simulation.dry_run_only}",
        "",
        "## Placeholder Boundary",
        "",
        f"- approval_id_placeholder: {simulation.approval_id_placeholder}",
        f"- side_placeholder: {simulation.side_placeholder}",
        "",
        "## ACK Tokens",
        "",
    ]
    lines.extend(f"- {token}" for token in simulation.ack_tokens)
    lines.extend(["", "## Validation Rule Results", ""])
    lines.extend(
        (
            f"- {rule.rule_id}: passed={rule.passed}; "
            f"blocked_reason={rule.blocked_reason or 'none'}; detail={rule.detail}"
        )
        for rule in simulation.validation_rule_results
    )
    lines.extend(["", "## Sections", ""])
    for section in simulation.sections:
        lines.append(f"### {section.title}")
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_approval_validation_simulation_id(
    *,
    preview_id: str,
    candidate_id: str,
    created_at: datetime,
    simulation_status: LiveOrderApprovalValidationSimulationStatus,
    blocked_reasons: tuple[str, ...],
    simulated_command_exact_match: bool,
) -> str:
    _require_non_empty("preview_id", preview_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "preview_id": preview_id,
        "simulation_status": simulation_status.value,
        "simulated_command_exact_match": simulated_command_exact_match,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_APPROVAL_VALIDATION_SIMULATION_ID_PREFIX}{digest.upper()}"


def _preview_blocked_reasons(
    preview: LiveOrderApprovalGatePreview,
) -> tuple[str, ...]:
    reasons: list[LiveOrderApprovalValidationSimulationBlockReason] = []
    if (
        preview.preview_status
        is not LiveOrderApprovalGatePreviewStatus.READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
    ):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_NOT_READY,
        )
    if preview.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_ALLOWS_LIVE,
        )
    if preview.dry_run_only is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_NOT_DRY_RUN,
        )
    if preview.requires_human_approval is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if preview.approval_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if preview.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if preview.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if preview.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if preview.approval_command_template_only is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
        )
    if preview.approval_command_copyable is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.APPROVAL_COMMAND_COPYABLE,
        )
    if preview.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    if preview.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.INVALID_PREVIEW_TTL_SECONDS,
        )
    if preview.exact_match_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXACT_MATCH_NOT_REQUIRED,
        )
    if preview.same_session_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.SAME_SESSION_NOT_REQUIRED,
        )
    if preview.symbol != SUPPORTED_SYMBOL:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SYMBOL,
        )
    if preview.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SIDE,
        )
    if preview.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_SIZE,
        )
    if preview.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reason.value for reason in reasons)


def _command_blocked_reasons(
    *,
    preview: LiveOrderApprovalGatePreview,
    command_text: object,
    simulated_ttl_seconds: object,
    same_session: object,
    already_used: object,
) -> tuple[str, ...]:
    reasons: list[LiveOrderApprovalValidationSimulationBlockReason] = []
    if not isinstance(command_text, str) or not command_text.strip():
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_SIMULATED_COMMAND,
        )
        return tuple(reason.value for reason in reasons)

    if command_text != preview.approval_command_template:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.SIMULATED_COMMAND_MISMATCH,
        )
    if type(simulated_ttl_seconds) is not int or simulated_ttl_seconds < 0:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.INVALID_TTL_SECONDS,
        )
    elif simulated_ttl_seconds > APPROVAL_GATE_TTL_SECONDS:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXPIRED_TTL,
        )
    if same_session is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.DIFFERENT_SESSION,
        )
    if already_used is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.ALREADY_USED,
        )
    if "\n" in command_text or "\r" in command_text:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_LINE_BREAK,
        )
    if command_text != command_text.strip():
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.HAS_LEADING_OR_TRAILING_SPACE,
        )
    if "  " in command_text:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_REPEATED_SPACES,
        )
    if not command_text.startswith(APPROVAL_COMMAND_TEMPLATE_PREFIX):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.INVALID_COMMAND_PREFIX,
        )
    if command_text.startswith("STEP4_APPROVE"):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_COMMAND,
        )
    if _REAL_APPROVAL_ID_PATTERN.search(command_text):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_ID,
        )
    if APPROVAL_ID_PLACEHOLDER not in command_text:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_APPROVAL_ID_PLACEHOLDER,
        )
    if APPROVAL_SIDE_PLACEHOLDER not in command_text:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_SIDE_PLACEHOLDER,
        )
    if (
        APPROVAL_ID_PLACEHOLDER not in command_text
        or APPROVAL_SIDE_PLACEHOLDER not in command_text
        or _REAL_APPROVAL_ID_PATTERN.search(command_text)
    ):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.NOT_PLACEHOLDER_ONLY,
        )
    tokens = tuple(command_text.split(" "))
    if "" in tokens:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
        )
    expected_tokens = tuple(preview.approval_command_template.split(" "))
    if tokens != expected_tokens:
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
        )
    ack_values = [token for token in tokens if token.startswith("ACK_")]
    for ack_token in APPROVAL_ACK_TOKENS:
        if ack_values.count(ack_token) == 0:
            _add_reason(
                reasons,
                LiveOrderApprovalValidationSimulationBlockReason.MISSING_ACK_TOKEN,
            )
        if ack_values.count(ack_token) > 1:
            _add_reason(
                reasons,
                LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
            )
    if any(token not in APPROVAL_ACK_TOKENS for token in ack_values):
        _add_reason(
            reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
        )
    return tuple(reason.value for reason in reasons)


def _validation_rule_results(
    *,
    preview: LiveOrderApprovalGatePreview,
    command_text: object,
    simulated_ttl_seconds: object,
    same_session: object,
    already_used: object,
) -> tuple[LiveOrderApprovalValidationRuleResult, ...]:
    command_reasons = set(
        _command_blocked_reasons(
            preview=preview,
            command_text=command_text,
            simulated_ttl_seconds=simulated_ttl_seconds,
            same_session=same_session,
            already_used=already_used,
        )
    )
    preview_reasons = set(_preview_blocked_reasons(preview))
    return (
        _rule_result(
            "preview_ready",
            not preview_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.PREVIEW_NOT_READY,
            "approval gate preview must be ready before simulated validation",
        ),
        _rule_result(
            "exact_match",
            LiveOrderApprovalValidationSimulationBlockReason.SIMULATED_COMMAND_MISMATCH.value
            not in command_reasons
            and LiveOrderApprovalValidationSimulationBlockReason.MISSING_SIMULATED_COMMAND.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.SIMULATED_COMMAND_MISMATCH,
            "simulated command must exactly match the fake template",
        ),
        _rule_result(
            "ttl_300_seconds",
            LiveOrderApprovalValidationSimulationBlockReason.INVALID_TTL_SECONDS.value
            not in command_reasons
            and LiveOrderApprovalValidationSimulationBlockReason.EXPIRED_TTL.value
            not in command_reasons,
            _ttl_block_reason(command_reasons),
            "simulated elapsed seconds must be within 300 seconds",
        ),
        _rule_result(
            "same_codex_session",
            LiveOrderApprovalValidationSimulationBlockReason.DIFFERENT_SESSION.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.DIFFERENT_SESSION,
            "simulated command must come from the same Codex session",
        ),
        _rule_result(
            "unused_once",
            LiveOrderApprovalValidationSimulationBlockReason.ALREADY_USED.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.ALREADY_USED,
            "simulated command must not already be used",
        ),
        _rule_result(
            "all_ack_tokens",
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_ACK_TOKEN.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.MISSING_ACK_TOKEN,
            "simulated command must include every required ACK token",
        ),
        _rule_result(
            "no_extra_tokens",
            LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.EXTRA_TOKEN,
            "simulated command must not contain duplicated or unknown tokens",
        ),
        _rule_result(
            "no_line_breaks",
            LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_LINE_BREAK.value
            not in command_reasons,
            LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_LINE_BREAK,
            "simulated command must be one line",
        ),
        _rule_result(
            "no_extra_spaces",
            LiveOrderApprovalValidationSimulationBlockReason.HAS_LEADING_OR_TRAILING_SPACE.value
            not in command_reasons
            and LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_REPEATED_SPACES.value
            not in command_reasons,
            _space_block_reason(command_reasons),
            "simulated command must not contain leading, trailing, or repeated spaces",
        ),
        _rule_result(
            "template_prefix",
            LiveOrderApprovalValidationSimulationBlockReason.INVALID_COMMAND_PREFIX.value
            not in command_reasons
            and (
                LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_COMMAND.value
            )
            not in command_reasons,
            _prefix_block_reason(command_reasons),
            "simulated command must use the fake template prefix only",
        ),
        _rule_result(
            "placeholder_only",
            LiveOrderApprovalValidationSimulationBlockReason.NOT_PLACEHOLDER_ONLY.value
            not in command_reasons
            and LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_ID.value
            not in command_reasons,
            _placeholder_block_reason(command_reasons),
            "simulated command must keep approval and side placeholders",
        ),
    )


def _rule_result(
    rule_id: str,
    passed: bool,
    blocked_reason: LiveOrderApprovalValidationSimulationBlockReason,
    detail: str,
) -> LiveOrderApprovalValidationRuleResult:
    return LiveOrderApprovalValidationRuleResult(
        rule_id=rule_id,
        passed=passed,
        blocked_reason="" if passed else blocked_reason.value,
        detail=detail,
    )


def _ttl_block_reason(
    command_reasons: set[str],
) -> LiveOrderApprovalValidationSimulationBlockReason:
    if (
        LiveOrderApprovalValidationSimulationBlockReason.INVALID_TTL_SECONDS.value
        in command_reasons
    ):
        return LiveOrderApprovalValidationSimulationBlockReason.INVALID_TTL_SECONDS
    return LiveOrderApprovalValidationSimulationBlockReason.EXPIRED_TTL


def _space_block_reason(
    command_reasons: set[str],
) -> LiveOrderApprovalValidationSimulationBlockReason:
    if (
        LiveOrderApprovalValidationSimulationBlockReason.HAS_LEADING_OR_TRAILING_SPACE.value
        in command_reasons
    ):
        return (
            LiveOrderApprovalValidationSimulationBlockReason.HAS_LEADING_OR_TRAILING_SPACE
        )
    return LiveOrderApprovalValidationSimulationBlockReason.CONTAINS_REPEATED_SPACES


def _prefix_block_reason(
    command_reasons: set[str],
) -> LiveOrderApprovalValidationSimulationBlockReason:
    if (
        LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_COMMAND.value
        in command_reasons
    ):
        return (
            LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_COMMAND
        )
    return LiveOrderApprovalValidationSimulationBlockReason.INVALID_COMMAND_PREFIX


def _placeholder_block_reason(
    command_reasons: set[str],
) -> LiveOrderApprovalValidationSimulationBlockReason:
    if (
        LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_ID.value
        in command_reasons
    ):
        return LiveOrderApprovalValidationSimulationBlockReason.LOOKS_LIKE_REAL_APPROVAL_ID
    return LiveOrderApprovalValidationSimulationBlockReason.NOT_PLACEHOLDER_ONLY


def _simulation_sections(
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderApprovalValidationSimulationSection, ...]:
    if blocked_reasons:
        return (
            LiveOrderApprovalValidationSimulationSection(
                section_id="blocked_simulation",
                title="Blocked Approval Validation Simulation",
                lines=(
                    "Do not proceed to real approval gate.",
                    "Do not generate a real approval_id.",
                    "Do not generate a real approval command.",
                    "Do not proceed to final dynamic preflight.",
                    "Do not proceed to live POST.",
                    f"blocked_reasons={_blocked_text(blocked_reasons)}",
                ),
            ),
        )
    return (
        LiveOrderApprovalValidationSimulationSection(
            section_id="passed_simulation",
            title="Passed Fake Validation Simulation",
            lines=(
                "The fake template validation rules passed in simulation only.",
                "No real approval gate was issued.",
                "No real approval_id was generated.",
                "No real approval command was generated.",
                "No final dynamic preflight was authorized.",
                "Live POST remains forbidden.",
            ),
        ),
    )


def _validate_approval_validation_simulation(
    simulation: LiveOrderApprovalValidationSimulation,
) -> None:
    _require_non_empty("simulation_id", simulation.simulation_id)
    if not simulation.simulation_id.startswith(
        LIVE_ORDER_APPROVAL_VALIDATION_SIMULATION_ID_PREFIX
    ):
        raise LiveVerificationValidationError("simulation_id must be dry-run id")
    _ensure_aware(simulation.created_at)
    for name, value in (
        ("preview_id", simulation.preview_id),
        ("design_id", simulation.design_id),
        ("handoff_id", simulation.handoff_id),
        ("operator_review_id", simulation.operator_review_id),
        ("bundle_id", simulation.bundle_id),
        ("review_id", simulation.review_id),
        ("candidate_id", simulation.candidate_id),
        ("risk_decision_id", simulation.risk_decision_id),
        ("trace_id", simulation.trace_id),
        ("session_policy_decision_id", simulation.session_policy_decision_id),
        ("source_signal_id", simulation.source_signal_id),
        ("source_type", simulation.source_type),
        ("strategy_name", simulation.strategy_name),
        ("symbol", simulation.symbol),
        ("side", simulation.side),
        ("execution_type", simulation.execution_type),
        ("preview_status", simulation.preview_status),
        ("approval_id_placeholder", simulation.approval_id_placeholder),
        ("side_placeholder", simulation.side_placeholder),
        ("summary", simulation.summary),
        ("recommended_next_step", simulation.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(simulation.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if (
        simulation.simulated_ttl_seconds is not None
        and type(simulation.simulated_ttl_seconds) is not int
    ):
        raise LiveVerificationValidationError("simulated_ttl_seconds must be int")
    for name, value in (
        ("simulated_command_received", simulation.simulated_command_received),
        ("simulated_command_exact_match", simulation.simulated_command_exact_match),
        ("simulated_command_template_only", simulation.simulated_command_template_only),
        ("simulated_command_copyable", simulation.simulated_command_copyable),
        ("same_session", simulation.same_session),
        ("already_used", simulation.already_used),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")
    if simulation.simulation_status not in set(
        LiveOrderApprovalValidationSimulationStatus
    ):
        raise LiveVerificationValidationError("unsupported simulation status")
    if simulation.allowed_for_live is not False:
        raise LiveVerificationValidationError("simulation never allows live execution")
    if simulation.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if simulation.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if simulation.approval_gate_issued is not False:
        raise LiveVerificationValidationError("simulation never issues approval gate")
    if simulation.approval_id_generated is not False:
        raise LiveVerificationValidationError("simulation never generates approval id")
    if simulation.approval_command_generated is not False:
        raise LiveVerificationValidationError(
            "simulation never generates approval command"
        )
    if simulation.approval_command_template_only is not True:
        raise LiveVerificationValidationError("simulation command remains template-only")
    if simulation.approval_command_copyable is not False:
        raise LiveVerificationValidationError("simulation command must not be copyable")
    if simulation.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("simulation TTL must remain 300")
    if simulation.exact_match_required is not True:
        raise LiveVerificationValidationError("exact match remains required")
    if simulation.same_session_required is not True:
        raise LiveVerificationValidationError("same-session remains required")
    if simulation.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if simulation.dry_run_only is not True:
        raise LiveVerificationValidationError("simulation must be dry-run only")
    if simulation.approval_id_placeholder != APPROVAL_ID_PLACEHOLDER:
        raise LiveVerificationValidationError("unexpected approval id placeholder")
    if simulation.side_placeholder != APPROVAL_SIDE_PLACEHOLDER:
        raise LiveVerificationValidationError("unexpected side placeholder")
    if simulation.ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("simulation ack tokens mismatch")
    if not simulation.validation_rule_results:
        raise LiveVerificationValidationError("simulation requires rule results")
    if not simulation.sections:
        raise LiveVerificationValidationError("simulation requires sections")
    if (
        simulation.simulation_status
        is LiveOrderApprovalValidationSimulationStatus.SIMULATED_APPROVAL_VALIDATION_PASSED
    ):
        if simulation.blocked_reasons:
            raise LiveVerificationValidationError("passed simulation cannot be blocked")
        if not simulation.simulated_command_exact_match:
            raise LiveVerificationValidationError("passed simulation requires exact match")
        if simulation.same_session is not True:
            raise LiveVerificationValidationError("passed simulation requires same session")
        if simulation.already_used is not False:
            raise LiveVerificationValidationError("passed simulation requires unused input")
    else:
        if not simulation.blocked_reasons:
            raise LiveVerificationValidationError("blocked simulation requires reasons")


def _add_reason(
    reasons: list[LiveOrderApprovalValidationSimulationBlockReason],
    reason: LiveOrderApprovalValidationSimulationBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _blocked_text(reasons: tuple[str, ...]) -> str:
    return ", ".join(reasons) if reasons else "none"


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
