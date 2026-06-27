"""Fake approval gate design model for Step 5J."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_handoff import (
    DISPLAY_FORBIDDEN_FIELDS as HANDOFF_DISPLAY_FORBIDDEN_FIELDS,
)
from app.live_verification.live_order_approval_handoff import (
    FINAL_DYNAMIC_PREFLIGHT_ITEMS,
    LiveOrderApprovalHandoffPackage,
    LiveOrderApprovalHandoffStatus,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_APPROVAL_GATE_DESIGN_ID_PREFIX = "LOCAGD-"
APPROVAL_GATE_TTL_SECONDS = 300
APPROVAL_ID_PLACEHOLDER = "<APPROVAL_ID_FROM_FUTURE_STEP>"
APPROVAL_SIDE_PLACEHOLDER = "<SIDE_FROM_FUTURE_STEP>"
APPROVAL_COMMAND_TEMPLATE_PREFIX = "STEP_APPROVAL_TEMPLATE"

APPROVAL_ACK_TOKENS = (
    "ACK_RISK=YES",
    "ACK_OPEN_POSITION=YES",
    "ACK_API_SCOPE=YES",
    "ACK_ORDER_PERMISSION=YES",
    "ACK_IP_ACCOUNT_CHECK=YES",
    "ACK_NO_EVENT=YES",
    "ACK_NO_RETRY=YES",
    "ACK_NO_LOOP=YES",
    "ACK_NO_ADD=YES",
    "ACK_NO_CHANGE=YES",
    "ACK_NO_CANCEL=YES",
    "ACK_NO_CLOSE=YES",
    "ACK_STOP_ON_UNKNOWN=YES",
)

APPROVAL_COMMAND_TEMPLATE_TEXT = " ".join(
    (
        APPROVAL_COMMAND_TEMPLATE_PREFIX,
        APPROVAL_ID_PLACEHOLDER,
        f"SIDE={APPROVAL_SIDE_PLACEHOLDER}",
        "SYMBOL=USD_JPY",
        "SIZE=100",
        *APPROVAL_ACK_TOKENS,
    )
)


class LiveOrderApprovalGateDesignStatus(str, Enum):
    READY_FOR_APPROVAL_GATE_DESIGN_REVIEW = "READY_FOR_APPROVAL_GATE_DESIGN_REVIEW"
    BLOCKED_APPROVAL_GATE_DESIGN = "BLOCKED_APPROVAL_GATE_DESIGN"


class LiveOrderApprovalGateDesignBlockReason(str, Enum):
    HANDOFF_NOT_READY = "handoff_not_ready"
    HANDOFF_ALLOWS_LIVE = "handoff_allows_live"
    HANDOFF_NOT_DRY_RUN = "handoff_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT = (
        "missing_final_dynamic_preflight_requirement"
    )
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"


@dataclass(frozen=True)
class LiveOrderApprovalCommandTemplate:
    template_text: str
    approval_id_placeholder: str
    side_placeholder: str
    ack_tokens: tuple[str, ...]
    template_only: bool
    copyable: bool

    def __post_init__(self) -> None:
        _require_non_empty("template_text", self.template_text)
        _require_non_empty("approval_id_placeholder", self.approval_id_placeholder)
        _require_non_empty("side_placeholder", self.side_placeholder)
        if self.template_only is not True:
            raise LiveVerificationValidationError("approval command must remain template-only")
        if self.copyable is not False:
            raise LiveVerificationValidationError("fake approval command must not be copyable")
        if self.approval_id_placeholder != APPROVAL_ID_PLACEHOLDER:
            raise LiveVerificationValidationError("unexpected approval id placeholder")
        if self.side_placeholder != APPROVAL_SIDE_PLACEHOLDER:
            raise LiveVerificationValidationError("unexpected side placeholder")
        if self.ack_tokens != APPROVAL_ACK_TOKENS:
            raise LiveVerificationValidationError("approval ack tokens mismatch")
        if not self.template_text.startswith(APPROVAL_COMMAND_TEMPLATE_PREFIX):
            raise LiveVerificationValidationError("template must use fake prefix")
        if APPROVAL_ID_PLACEHOLDER not in self.template_text:
            raise LiveVerificationValidationError("template must contain approval id placeholder")
        if APPROVAL_SIDE_PLACEHOLDER not in self.template_text:
            raise LiveVerificationValidationError("template must contain side placeholder")
        if "STEP4_APPROVE" in self.template_text or "STEP4F-" in self.template_text:
            raise LiveVerificationValidationError("template must not be real approval text")


@dataclass(frozen=True)
class LiveOrderApprovalGateDesignSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("approval gate design section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderApprovalGateDesign:
    design_id: str
    created_at: datetime
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
    handoff_status: str
    design_status: LiveOrderApprovalGateDesignStatus
    eligible_for_operator_review: bool
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
    command_template: LiveOrderApprovalCommandTemplate
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    final_dynamic_preflight_items: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderApprovalGateDesignSection, ...]

    def __post_init__(self) -> None:
        _validate_approval_gate_design(self)


@dataclass(frozen=True)
class LiveOrderApprovalGateDesignBuildResult:
    design: LiveOrderApprovalGateDesign
    design_id: str
    design_status: LiveOrderApprovalGateDesignStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.design.design_id != self.design_id:
            raise LiveVerificationValidationError("design_id mismatch")
        if self.design.design_status is not self.design_status:
            raise LiveVerificationValidationError("design_status mismatch")
        if self.design.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("design never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("design never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("design never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError("design never generates approval command")
        if self.approval_command_template_only is not True:
            raise LiveVerificationValidationError("design must remain template-only")
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("design template must not be copyable")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_approval_gate_design(
    *,
    handoff_package: LiveOrderApprovalHandoffPackage,
    created_at: datetime | None = None,
) -> LiveOrderApprovalGateDesignBuildResult:
    """Build a fake approval gate design without issuing approval or execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _design_blocked_reasons(handoff_package),
        handoff_package.blocked_reasons,
    )

    if blocked_reasons:
        design_status = LiveOrderApprovalGateDesignStatus.BLOCKED_APPROVAL_GATE_DESIGN
        recommended_next_step = "fix_handoff_blockers_no_post"
        summary = "blocked fake approval gate design; no approval gate is issued"
    else:
        design_status = (
            LiveOrderApprovalGateDesignStatus.READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
        )
        recommended_next_step = "prepare_future_fake_approval_gate_review_no_post"
        summary = "ready for fake approval gate design review only; no approval gate is issued"

    design_id = make_live_order_approval_gate_design_id(
        handoff_id=handoff_package.handoff_id,
        candidate_id=handoff_package.candidate_id,
        created_at=created,
        design_status=design_status,
        blocked_reasons=blocked_reasons,
    )
    command_template = LiveOrderApprovalCommandTemplate(
        template_text=APPROVAL_COMMAND_TEMPLATE_TEXT,
        approval_id_placeholder=APPROVAL_ID_PLACEHOLDER,
        side_placeholder=APPROVAL_SIDE_PLACEHOLDER,
        ack_tokens=APPROVAL_ACK_TOKENS,
        template_only=True,
        copyable=False,
    )
    design = LiveOrderApprovalGateDesign(
        design_id=design_id,
        created_at=created,
        handoff_id=handoff_package.handoff_id,
        operator_review_id=handoff_package.operator_review_id,
        bundle_id=handoff_package.bundle_id,
        review_id=handoff_package.review_id,
        candidate_id=handoff_package.candidate_id,
        risk_decision_id=handoff_package.risk_decision_id,
        trace_id=handoff_package.trace_id,
        session_policy_decision_id=handoff_package.session_policy_decision_id,
        source_signal_id=handoff_package.source_signal_id,
        source_type=handoff_package.source_type,
        strategy_name=handoff_package.strategy_name,
        symbol=handoff_package.symbol,
        side=handoff_package.side,
        size=handoff_package.size,
        execution_type=handoff_package.execution_type,
        handoff_status=_enum_value(handoff_package.handoff_status),
        design_status=design_status,
        eligible_for_operator_review=(
            handoff_package.eligible_for_operator_review and not blocked_reasons
        ),
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
        command_template=command_template,
        display_allowed_fields=DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=DISPLAY_FORBIDDEN_FIELDS,
        final_dynamic_preflight_items=FINAL_DYNAMIC_PREFLIGHT_ITEMS,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_design_sections(blocked_reasons, command_template),
    )
    return LiveOrderApprovalGateDesignBuildResult(
        design=design,
        design_id=design.design_id,
        design_status=design.design_status,
        blocked_reasons=design.blocked_reasons,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        recommended_next_step=design.recommended_next_step,
    )


def render_live_order_approval_gate_design_markdown(
    design: LiveOrderApprovalGateDesign,
) -> str:
    """Render a sanitized fake approval gate design."""
    blocked_text = ", ".join(design.blocked_reasons) if design.blocked_reasons else "none"
    lines = [
        "# Live Order Approval Gate Design",
        "",
        "This approval gate design is dry-run only.",
        "This design is not an approval gate.",
        "This design does not generate a real approval_id.",
        "This design does not generate a real approval command.",
        "This design does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- design_id: {design.design_id}",
        f"- design_status: {design.design_status.value}",
        f"- handoff_id: {design.handoff_id}",
        f"- summary: {design.summary}",
        f"- recommended_next_step: {design.recommended_next_step}",
        "",
        "## References",
        "",
        f"- operator_review_id: {design.operator_review_id}",
        f"- bundle_id: {design.bundle_id}",
        f"- review_id: {design.review_id}",
        f"- candidate_id: {design.candidate_id}",
        f"- risk_decision_id: {design.risk_decision_id}",
        f"- trace_id: {design.trace_id}",
        f"- session_policy_decision_id: {design.session_policy_decision_id}",
        f"- source_signal_id: {design.source_signal_id}",
        f"- source_type: {design.source_type}",
        f"- strategy_name: {design.strategy_name}",
        "",
        "## Candidate",
        "",
        f"- symbol: {design.symbol}",
        f"- side: {design.side}",
        f"- size: {design.size}",
        f"- executionType: {design.execution_type}",
        "",
        "## Safety Flags",
        "",
        f"- handoff_status: {design.handoff_status}",
        f"- eligible_for_operator_review: {design.eligible_for_operator_review}",
        f"- allowed_for_live: {design.allowed_for_live}",
        f"- requires_human_approval: {design.requires_human_approval}",
        f"- approval_gate_required: {design.approval_gate_required}",
        f"- approval_gate_issued: {design.approval_gate_issued}",
        f"- approval_id_generated: {design.approval_id_generated}",
        f"- approval_command_generated: {design.approval_command_generated}",
        f"- approval_command_template_only: {design.approval_command_template_only}",
        f"- approval_command_copyable: {design.approval_command_copyable}",
        f"- ttl_seconds: {design.ttl_seconds}",
        f"- exact_match_required: {design.exact_match_required}",
        f"- same_session_required: {design.same_session_required}",
        f"- final_dynamic_preflight_required: {design.final_dynamic_preflight_required}",
        f"- dry_run_only: {design.dry_run_only}",
        f"- blocked_reasons: {blocked_text}",
        "",
        "## Fake Approval Command Template",
        "",
        f"- approval_id_placeholder: {design.command_template.approval_id_placeholder}",
        f"- side_placeholder: {design.command_template.side_placeholder}",
        f"- template_only: {design.command_template.template_only}",
        f"- copyable: {design.command_template.copyable}",
        f"- template: {design.command_template.template_text}",
        "",
        "## ACK Tokens",
        "",
    ]
    lines.extend(f"- {token}" for token in design.command_template.ack_tokens)
    lines.extend(["", "## Display Allowed Fields", ""])
    lines.extend(f"- {field}" for field in design.display_allowed_fields)
    lines.extend(["", "## Display Forbidden Fields", ""])
    lines.extend(f"- {field}" for field in design.display_forbidden_fields)
    lines.extend(["", "## Final Dynamic Preflight Items", ""])
    lines.extend(f"- {item}" for item in design.final_dynamic_preflight_items)
    lines.extend(["", "## Sections", ""])
    for section in design.sections:
        lines.append(f"### {section.title}")
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_approval_gate_design_id(
    *,
    handoff_id: str,
    candidate_id: str,
    created_at: datetime,
    design_status: LiveOrderApprovalGateDesignStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("handoff_id", handoff_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "design_status": design_status.value,
        "handoff_id": handoff_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_APPROVAL_GATE_DESIGN_ID_PREFIX}{digest.upper()}"


DISPLAY_ALLOWED_FIELDS = (
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
    "handoff_status",
    "design_status",
    "eligible_for_operator_review",
    "allowed_for_live=false",
    "requires_human_approval=true",
    "approval_gate_required=true",
    "approval_gate_issued=false",
    "approval_id_generated=false",
    "approval_command_generated=false",
    "approval_command_template_only=true",
    "approval_command_copyable=false",
    "ttl_seconds=300",
    "exact_match_required=true",
    "same_session_required=true",
    "final_dynamic_preflight_required=true",
    "blocked_reasons",
    "recommended_next_step",
)

DISPLAY_FORBIDDEN_FIELDS = HANDOFF_DISPLAY_FORBIDDEN_FIELDS + (
    "real approval_id",
    "real approval command",
    "copyable approval command",
    "clipboard approval command",
    "approval command file",
)


def _design_blocked_reasons(
    handoff_package: LiveOrderApprovalHandoffPackage,
) -> tuple[str, ...]:
    reasons: list[LiveOrderApprovalGateDesignBlockReason | str] = []
    if (
        handoff_package.handoff_status
        is not LiveOrderApprovalHandoffStatus.READY_FOR_APPROVAL_HANDOFF_REVIEW
    ):
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.HANDOFF_NOT_READY)
    if handoff_package.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.HANDOFF_ALLOWS_LIVE)
    if handoff_package.dry_run_only is not True:
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.HANDOFF_NOT_DRY_RUN)
    if handoff_package.requires_human_approval is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if handoff_package.approval_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if handoff_package.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if handoff_package.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if handoff_package.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    if handoff_package.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SYMBOL)
    if handoff_package.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SIDE)
    if handoff_package.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_SIZE)
    if handoff_package.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderApprovalGateDesignBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(_reason_value(reason) for reason in reasons)


def _design_sections(
    blocked_reasons: tuple[str, ...],
    command_template: LiveOrderApprovalCommandTemplate,
) -> tuple[LiveOrderApprovalGateDesignSection, ...]:
    if blocked_reasons:
        return (
            LiveOrderApprovalGateDesignSection(
                section_id="blocked_design",
                title="Blocked Approval Gate Design",
                lines=(
                    "Do not proceed to approval gate.",
                    "Do not generate a real approval_id.",
                    "Do not generate a real approval command.",
                    "Do not proceed to live POST.",
                    f"blocked_reasons={_blocked_text(blocked_reasons)}",
                ),
            ),
        )
    return (
        LiveOrderApprovalGateDesignSection(
            section_id="fake_gate_design",
            title="Fake Approval Gate Design",
            lines=(
                "Review fake approval gate structure only.",
                "Use placeholder approval id and side values only.",
                "Do not copy the template as an approval command.",
                f"ttl_seconds={APPROVAL_GATE_TTL_SECONDS}",
                f"template={command_template.template_text}",
            ),
        ),
        LiveOrderApprovalGateDesignSection(
            section_id="future_final_preflight",
            title="Future Final Dynamic Preflight Boundary",
            lines=(
                "Final dynamic preflight remains a separate future Step.",
                "Approval command exact match remains a separate future Step.",
                "Live POST remains a separate future Step.",
            ),
        ),
    )


def _validate_approval_gate_design(design: LiveOrderApprovalGateDesign) -> None:
    _require_non_empty("design_id", design.design_id)
    if not design.design_id.startswith(LIVE_ORDER_APPROVAL_GATE_DESIGN_ID_PREFIX):
        raise LiveVerificationValidationError("design_id must be dry-run id")
    _ensure_aware(design.created_at)
    for name, value in (
        ("handoff_id", design.handoff_id),
        ("operator_review_id", design.operator_review_id),
        ("bundle_id", design.bundle_id),
        ("review_id", design.review_id),
        ("candidate_id", design.candidate_id),
        ("risk_decision_id", design.risk_decision_id),
        ("trace_id", design.trace_id),
        ("session_policy_decision_id", design.session_policy_decision_id),
        ("source_signal_id", design.source_signal_id),
        ("source_type", design.source_type),
        ("strategy_name", design.strategy_name),
        ("symbol", design.symbol),
        ("side", design.side),
        ("execution_type", design.execution_type),
        ("handoff_status", design.handoff_status),
        ("summary", design.summary),
        ("recommended_next_step", design.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(design.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if design.design_status not in set(LiveOrderApprovalGateDesignStatus):
        raise LiveVerificationValidationError("unsupported design status")
    if type(design.eligible_for_operator_review) is not bool:
        raise LiveVerificationValidationError("eligible_for_operator_review must be bool")
    if design.allowed_for_live is not False:
        raise LiveVerificationValidationError("design never allows live execution")
    if design.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if design.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if design.approval_gate_issued is not False:
        raise LiveVerificationValidationError("design never issues approval gate")
    if design.approval_id_generated is not False:
        raise LiveVerificationValidationError("design never generates approval id")
    if design.approval_command_generated is not False:
        raise LiveVerificationValidationError("design never generates approval command")
    if design.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if design.approval_command_copyable is not False:
        raise LiveVerificationValidationError("fake approval command must not be copyable")
    if design.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("approval gate design TTL must remain 300")
    if design.exact_match_required is not True:
        raise LiveVerificationValidationError("approval exact match remains required")
    if design.same_session_required is not True:
        raise LiveVerificationValidationError("same-session approval remains required")
    if design.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if design.dry_run_only is not True:
        raise LiveVerificationValidationError("approval gate design must be dry-run only")
    if not design.display_allowed_fields:
        raise LiveVerificationValidationError("design requires display allowed fields")
    if not design.display_forbidden_fields:
        raise LiveVerificationValidationError("design requires display forbidden fields")
    if not design.final_dynamic_preflight_items:
        raise LiveVerificationValidationError("design requires final preflight items")
    if not design.sections:
        raise LiveVerificationValidationError("design requires sections")
    if (
        design.design_status
        is LiveOrderApprovalGateDesignStatus.READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
    ):
        if not design.eligible_for_operator_review:
            raise LiveVerificationValidationError("ready design must be eligible")
        if design.blocked_reasons:
            raise LiveVerificationValidationError("ready design cannot be blocked")
    else:
        if design.eligible_for_operator_review:
            raise LiveVerificationValidationError("blocked design cannot be eligible")
        if not design.blocked_reasons:
            raise LiveVerificationValidationError("blocked design requires reasons")


def _add_reason(
    reasons: list[LiveOrderApprovalGateDesignBlockReason | str],
    reason: LiveOrderApprovalGateDesignBlockReason,
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


def _reason_value(value: LiveOrderApprovalGateDesignBlockReason | str) -> str:
    if isinstance(value, LiveOrderApprovalGateDesignBlockReason):
        return value.value
    return value


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
