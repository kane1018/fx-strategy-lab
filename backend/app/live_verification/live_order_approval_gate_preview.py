"""Approval gate preview model for Step 5K."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_COMMAND_TEMPLATE_PREFIX,
    APPROVAL_GATE_TTL_SECONDS,
    APPROVAL_ID_PLACEHOLDER,
    LiveOrderApprovalGateDesign,
    LiveOrderApprovalGateDesignStatus,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_APPROVAL_GATE_PREVIEW_ID_PREFIX = "LOCAGP-"


class LiveOrderApprovalGatePreviewStatus(str, Enum):
    READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW = "READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW"
    BLOCKED_APPROVAL_GATE_PREVIEW = "BLOCKED_APPROVAL_GATE_PREVIEW"


class LiveOrderApprovalGatePreviewBlockReason(str, Enum):
    DESIGN_NOT_READY = "design_not_ready"
    DESIGN_ALLOWS_LIVE = "design_allows_live"
    DESIGN_NOT_DRY_RUN = "design_not_dry_run"
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
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"


@dataclass(frozen=True)
class LiveOrderApprovalGatePreviewValidationRule:
    rule_id: str
    description: str
    required: bool

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise LiveVerificationValidationError("rule_id is required")
        if not isinstance(self.description, str) or not self.description.strip():
            raise LiveVerificationValidationError("description is required")
        if self.required is not True:
            raise LiveVerificationValidationError("preview validation rules are required")


@dataclass(frozen=True)
class LiveOrderApprovalGatePreviewSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("approval gate preview section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderApprovalGatePreview:
    preview_id: str
    created_at: datetime
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
    design_status: str
    preview_status: LiveOrderApprovalGatePreviewStatus
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
    approval_command_template: str
    ack_tokens: tuple[str, ...]
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    final_dynamic_preflight_items: tuple[str, ...]
    validation_rules: tuple[LiveOrderApprovalGatePreviewValidationRule, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderApprovalGatePreviewSection, ...]

    def __post_init__(self) -> None:
        _validate_approval_gate_preview(self)


@dataclass(frozen=True)
class LiveOrderApprovalGatePreviewBuildResult:
    preview: LiveOrderApprovalGatePreview
    preview_id: str
    preview_status: LiveOrderApprovalGatePreviewStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.preview.preview_id != self.preview_id:
            raise LiveVerificationValidationError("preview_id mismatch")
        if self.preview.preview_status is not self.preview_status:
            raise LiveVerificationValidationError("preview_status mismatch")
        if self.preview.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("preview never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("preview never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("preview never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError("preview never generates approval command")
        if self.approval_command_template_only is not True:
            raise LiveVerificationValidationError("preview must remain template-only")
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("preview template must not be copyable")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_approval_gate_preview(
    *,
    approval_gate_design: LiveOrderApprovalGateDesign,
    created_at: datetime | None = None,
) -> LiveOrderApprovalGatePreviewBuildResult:
    """Build a dry-run approval gate preview without issuing approval."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _preview_blocked_reasons(approval_gate_design),
        approval_gate_design.blocked_reasons,
    )

    if blocked_reasons:
        preview_status = LiveOrderApprovalGatePreviewStatus.BLOCKED_APPROVAL_GATE_PREVIEW
        recommended_next_step = "fix_approval_gate_design_blockers_no_post"
        summary = "blocked approval gate preview; no approval gate is issued"
    else:
        preview_status = (
            LiveOrderApprovalGatePreviewStatus.READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
        )
        recommended_next_step = "review_fake_approval_gate_preview_no_post"
        summary = "ready for fake approval gate preview review only; no approval gate is issued"

    preview_id = make_live_order_approval_gate_preview_id(
        design_id=approval_gate_design.design_id,
        candidate_id=approval_gate_design.candidate_id,
        created_at=created,
        preview_status=preview_status,
        blocked_reasons=blocked_reasons,
    )
    preview = LiveOrderApprovalGatePreview(
        preview_id=preview_id,
        created_at=created,
        design_id=approval_gate_design.design_id,
        handoff_id=approval_gate_design.handoff_id,
        operator_review_id=approval_gate_design.operator_review_id,
        bundle_id=approval_gate_design.bundle_id,
        review_id=approval_gate_design.review_id,
        candidate_id=approval_gate_design.candidate_id,
        risk_decision_id=approval_gate_design.risk_decision_id,
        trace_id=approval_gate_design.trace_id,
        session_policy_decision_id=approval_gate_design.session_policy_decision_id,
        source_signal_id=approval_gate_design.source_signal_id,
        source_type=approval_gate_design.source_type,
        strategy_name=approval_gate_design.strategy_name,
        symbol=approval_gate_design.symbol,
        side=approval_gate_design.side,
        size=approval_gate_design.size,
        execution_type=approval_gate_design.execution_type,
        design_status=_enum_value(approval_gate_design.design_status),
        preview_status=preview_status,
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
        approval_command_template=approval_gate_design.command_template.template_text,
        ack_tokens=APPROVAL_ACK_TOKENS,
        display_allowed_fields=DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=DISPLAY_FORBIDDEN_FIELDS,
        final_dynamic_preflight_items=approval_gate_design.final_dynamic_preflight_items,
        validation_rules=VALIDATION_RULES,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_preview_sections(blocked_reasons),
    )
    return LiveOrderApprovalGatePreviewBuildResult(
        preview=preview,
        preview_id=preview.preview_id,
        preview_status=preview.preview_status,
        blocked_reasons=preview.blocked_reasons,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        recommended_next_step=preview.recommended_next_step,
    )


def render_live_order_approval_gate_preview_markdown(
    preview: LiveOrderApprovalGatePreview,
) -> str:
    """Render a sanitized fake approval gate preview."""
    blocked_text = ", ".join(preview.blocked_reasons) if preview.blocked_reasons else "none"
    lines = [
        "# Live Order Approval Gate Preview",
        "",
        "This approval gate preview is dry-run only.",
        "This preview is not a real approval gate.",
        "This preview does not generate a real approval_id.",
        "This preview does not generate a real approval command.",
        "This preview is not copyable approval text.",
        "This preview does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- preview_id: {preview.preview_id}",
        f"- preview_status: {preview.preview_status.value}",
        f"- design_id: {preview.design_id}",
        f"- summary: {preview.summary}",
        f"- recommended_next_step: {preview.recommended_next_step}",
        "",
        "## References",
        "",
        f"- handoff_id: {preview.handoff_id}",
        f"- operator_review_id: {preview.operator_review_id}",
        f"- bundle_id: {preview.bundle_id}",
        f"- review_id: {preview.review_id}",
        f"- candidate_id: {preview.candidate_id}",
        f"- risk_decision_id: {preview.risk_decision_id}",
        f"- trace_id: {preview.trace_id}",
        f"- session_policy_decision_id: {preview.session_policy_decision_id}",
        f"- source_signal_id: {preview.source_signal_id}",
        f"- source_type: {preview.source_type}",
        f"- strategy_name: {preview.strategy_name}",
        "",
        "## Candidate",
        "",
        f"- symbol: {preview.symbol}",
        f"- side: {preview.side}",
        f"- size: {preview.size}",
        f"- executionType: {preview.execution_type}",
        "",
        "## Safety Flags",
        "",
        f"- design_status: {preview.design_status}",
        f"- allowed_for_live: {preview.allowed_for_live}",
        f"- requires_human_approval: {preview.requires_human_approval}",
        f"- approval_gate_required: {preview.approval_gate_required}",
        f"- approval_gate_issued: {preview.approval_gate_issued}",
        f"- approval_id_generated: {preview.approval_id_generated}",
        f"- approval_command_generated: {preview.approval_command_generated}",
        f"- approval_command_template_only: {preview.approval_command_template_only}",
        f"- approval_command_copyable: {preview.approval_command_copyable}",
        f"- ttl_seconds: {preview.ttl_seconds}",
        f"- exact_match_required: {preview.exact_match_required}",
        f"- same_session_required: {preview.same_session_required}",
        f"- final_dynamic_preflight_required: {preview.final_dynamic_preflight_required}",
        f"- dry_run_only: {preview.dry_run_only}",
        f"- blocked_reasons: {blocked_text}",
        "",
        "## Approval Command Template Preview",
        "",
        "This is a non-copyable template.",
        "Do not paste this into Codex.",
        (
            "A real approval command must be generated only in a future real approval "
            "gate step after fresh preflight."
        ),
        "",
        f"- approval_id_placeholder: {preview.approval_id_placeholder}",
        f"- approval_command_template: {preview.approval_command_template}",
        "",
        "## ACK Tokens",
        "",
    ]
    lines.extend(f"- {token}" for token in preview.ack_tokens)
    lines.extend(["", "## Validation Rules", ""])
    lines.extend(f"- {rule.rule_id}: {rule.description}" for rule in preview.validation_rules)
    lines.extend(["", "## Display Allowed Fields", ""])
    lines.extend(f"- {field}" for field in preview.display_allowed_fields)
    lines.extend(["", "## Display Forbidden Fields", ""])
    lines.extend(f"- {field}" for field in preview.display_forbidden_fields)
    lines.extend(["", "## Final Dynamic Preflight Items", ""])
    lines.extend(f"- {item}" for item in preview.final_dynamic_preflight_items)
    lines.extend(["", "## Sections", ""])
    for section in preview.sections:
        lines.append(f"### {section.title}")
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_approval_gate_preview_id(
    *,
    design_id: str,
    candidate_id: str,
    created_at: datetime,
    preview_status: LiveOrderApprovalGatePreviewStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("design_id", design_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "design_id": design_id,
        "preview_status": preview_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_APPROVAL_GATE_PREVIEW_ID_PREFIX}{digest.upper()}"


DISPLAY_ALLOWED_FIELDS = (
    "preview_id",
    "design_id",
    "handoff_id",
    "operator_review_id",
    "bundle_id",
    "review_id",
    "candidate_id",
    "risk_decision_id",
    "trace_id",
    "session_policy_decision_id",
    "source_signal_id",
    "source_type",
    "strategy_name",
    "symbol",
    "side",
    "size",
    "executionType",
    "design_status",
    "preview_status",
    "allowed_for_live=false",
    "requires_human_approval=true",
    "approval_gate_required=true",
    "approval_gate_issued=false",
    "approval_id_generated=false",
    "approval_command_generated=false",
    "approval_command_template_only=true",
    "approval_command_copyable=false",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "final_dynamic_preflight_required",
    "approval_id_placeholder",
    "approval_command_template",
    "ack_tokens",
    "validation_rules",
    "blocked_reasons",
    "recommended_next_step",
)

DISPLAY_FORBIDDEN_FIELDS = (
    "API key value",
    "secret value",
    "signature value",
    "headers value",
    "raw request",
    "raw response",
    "order ID",
    "execution ID",
    "position ID",
    "clientOrderId",
    "request URL",
    "open price",
    "detailed P/L",
    "real approval_id",
    "real approval command",
    "copyable approval command",
    "clipboard approval command",
    "approval command file",
)

VALIDATION_RULES = (
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="future_real_gate_only",
        description=(
            "real approval command must be generated only in future real approval gate step"
        ),
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="fresh_preflight_before_id",
        description="approval_id must be generated only after fresh preflight",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="one_line_command",
        description="approval command must be one line",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="exact_match",
        description="approval command must be exact match",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="same_codex_session",
        description="approval command must be pasted into the same Codex session",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="ttl_300_seconds",
        description="approval command must be within TTL 300 seconds",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="all_ack_tokens",
        description="approval command must include all required ACK tokens",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="no_extra_tokens",
        description="approval command must not contain extra tokens",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="no_line_breaks",
        description="approval command must not contain line breaks",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="no_extra_spaces",
        description="approval command must not contain extra spaces",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="not_from_preview",
        description="approval command must not be copied from Step 5K preview",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="final_preflight_after_approval",
        description="after approval, final dynamic preflight is mandatory",
        required=True,
    ),
    LiveOrderApprovalGatePreviewValidationRule(
        rule_id="no_live_post_before_final_preflight",
        description="live POST remains forbidden until final dynamic preflight passes",
        required=True,
    ),
)


def _preview_blocked_reasons(
    design: LiveOrderApprovalGateDesign,
) -> tuple[str, ...]:
    reasons: list[LiveOrderApprovalGatePreviewBlockReason | str] = []
    if (
        design.design_status
        is not LiveOrderApprovalGateDesignStatus.READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
    ):
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_READY)
    if design.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.DESIGN_ALLOWS_LIVE)
    if design.dry_run_only is not True:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.DESIGN_NOT_DRY_RUN)
    if design.requires_human_approval is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if design.approval_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if design.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if design.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if design.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if design.approval_command_template_only is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
        )
    if design.approval_command_copyable is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.APPROVAL_COMMAND_COPYABLE,
        )
    if design.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    if design.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.INVALID_TTL_SECONDS)
    if design.exact_match_required is not True:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.EXACT_MATCH_NOT_REQUIRED)
    if design.same_session_required is not True:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.SAME_SESSION_NOT_REQUIRED)
    if design.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SYMBOL)
    if design.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SIDE)
    if design.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_SIZE)
    if design.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderApprovalGatePreviewBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(_reason_value(reason) for reason in reasons)


def _preview_sections(
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderApprovalGatePreviewSection, ...]:
    if blocked_reasons:
        return (
            LiveOrderApprovalGatePreviewSection(
                section_id="blocked_preview",
                title="Blocked Approval Gate Preview",
                lines=(
                    "Do not proceed to real approval gate.",
                    "Do not generate a real approval_id.",
                    "Do not generate a real approval command.",
                    "Do not copy approval text.",
                    "Do not proceed to live POST.",
                    f"blocked_reasons={_blocked_text(blocked_reasons)}",
                ),
            ),
        )
    return (
        LiveOrderApprovalGatePreviewSection(
            section_id="preview_display",
            title="Preview Display",
            lines=(
                "Review sanitized approval gate preview fields only.",
                "Treat the approval command template as non-copyable.",
                "Do not paste this preview into Codex as approval.",
                f"ttl_seconds={APPROVAL_GATE_TTL_SECONDS}",
            ),
        ),
        LiveOrderApprovalGatePreviewSection(
            section_id="future_validation",
            title="Future Validation Rules",
            lines=(
                "Real approval command generation remains a separate future Step.",
                "Exact match validation remains a separate future Step.",
                "Final dynamic preflight remains a separate future Step.",
                "Live POST remains a separate future Step.",
            ),
        ),
    )


def _validate_approval_gate_preview(preview: LiveOrderApprovalGatePreview) -> None:
    _require_non_empty("preview_id", preview.preview_id)
    if not preview.preview_id.startswith(LIVE_ORDER_APPROVAL_GATE_PREVIEW_ID_PREFIX):
        raise LiveVerificationValidationError("preview_id must be dry-run id")
    _ensure_aware(preview.created_at)
    for name, value in (
        ("design_id", preview.design_id),
        ("handoff_id", preview.handoff_id),
        ("operator_review_id", preview.operator_review_id),
        ("bundle_id", preview.bundle_id),
        ("review_id", preview.review_id),
        ("candidate_id", preview.candidate_id),
        ("risk_decision_id", preview.risk_decision_id),
        ("trace_id", preview.trace_id),
        ("session_policy_decision_id", preview.session_policy_decision_id),
        ("source_signal_id", preview.source_signal_id),
        ("source_type", preview.source_type),
        ("strategy_name", preview.strategy_name),
        ("symbol", preview.symbol),
        ("side", preview.side),
        ("execution_type", preview.execution_type),
        ("design_status", preview.design_status),
        ("approval_id_placeholder", preview.approval_id_placeholder),
        ("approval_command_template", preview.approval_command_template),
        ("summary", preview.summary),
        ("recommended_next_step", preview.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(preview.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if preview.preview_status not in set(LiveOrderApprovalGatePreviewStatus):
        raise LiveVerificationValidationError("unsupported preview status")
    if preview.allowed_for_live is not False:
        raise LiveVerificationValidationError("preview never allows live execution")
    if preview.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if preview.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if preview.approval_gate_issued is not False:
        raise LiveVerificationValidationError("preview never issues approval gate")
    if preview.approval_id_generated is not False:
        raise LiveVerificationValidationError("preview never generates approval id")
    if preview.approval_command_generated is not False:
        raise LiveVerificationValidationError("preview never generates approval command")
    if preview.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if preview.approval_command_copyable is not False:
        raise LiveVerificationValidationError("preview command template must not be copyable")
    if preview.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("approval gate preview TTL must remain 300")
    if preview.exact_match_required is not True:
        raise LiveVerificationValidationError("approval exact match remains required")
    if preview.same_session_required is not True:
        raise LiveVerificationValidationError("same-session approval remains required")
    if preview.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if preview.dry_run_only is not True:
        raise LiveVerificationValidationError("approval gate preview must be dry-run only")
    if preview.approval_id_placeholder != APPROVAL_ID_PLACEHOLDER:
        raise LiveVerificationValidationError("preview must use approval id placeholder")
    if not preview.approval_command_template.startswith(APPROVAL_COMMAND_TEMPLATE_PREFIX):
        raise LiveVerificationValidationError("preview template must use fake prefix")
    if "STEP4_APPROVE" in preview.approval_command_template:
        raise LiveVerificationValidationError("preview must not contain real approval command")
    if "STEP4F-" in preview.approval_command_template:
        raise LiveVerificationValidationError("preview must not contain real approval id")
    if preview.ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("preview ack tokens mismatch")
    if not preview.display_allowed_fields:
        raise LiveVerificationValidationError("preview requires display allowed fields")
    if not preview.display_forbidden_fields:
        raise LiveVerificationValidationError("preview requires display forbidden fields")
    if not preview.final_dynamic_preflight_items:
        raise LiveVerificationValidationError("preview requires final preflight items")
    if not preview.validation_rules:
        raise LiveVerificationValidationError("preview requires validation rules")
    if not preview.sections:
        raise LiveVerificationValidationError("preview requires sections")
    if (
        preview.preview_status
        is LiveOrderApprovalGatePreviewStatus.READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
    ):
        if preview.blocked_reasons:
            raise LiveVerificationValidationError("ready preview cannot be blocked")
    else:
        if not preview.blocked_reasons:
            raise LiveVerificationValidationError("blocked preview requires reasons")


def _add_reason(
    reasons: list[LiveOrderApprovalGatePreviewBlockReason | str],
    reason: LiveOrderApprovalGatePreviewBlockReason,
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


def _reason_value(value: LiveOrderApprovalGatePreviewBlockReason | str) -> str:
    if isinstance(value, LiveOrderApprovalGatePreviewBlockReason):
        return value.value
    return value


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
