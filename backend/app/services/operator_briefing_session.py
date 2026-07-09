"""Operator briefing session helper (read-only manual-operation support, no-POST).

Supports an operator running the read-only pre-trade caution briefing manually
alongside their OWN external trading platform: it produces a briefing, a safe
summary, and a session-log skeleton in which the operator RECORDS their OWN
decision and reason. It never decides, never recommends, never executes.

Boundaries: pure and side-effect free. No network / private data read /
filesystem / env / secret access, NO fetch, NO POST, NO trading-venue
interaction, and it never triggers a Safe Execution & Risk Engine. It only
orchestrates the read-only briefing pipeline and stores an operator's decision.

Invariants: the AI/system NEVER produces a BUY/SELL/HOLD decision -- the
operator passes their own decision label into ``record_operator_decision`` and
this module merely stores it (with the operator's reason, for audit and
anti-hindsight). No direction / recommendation / confidence / alpha /
expected-profit / win-rate; no raw price/spread/PnL/size and no account/order/
transaction/position/trade ID; sessions are never truthy;
``performance_proof_status`` / ``live_ready`` stay false.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.services.operator_briefing_safe_label_supply import SafeLabelSupplyRequest
from app.services.operator_pre_trade_briefing_service import (
    produce_operator_pre_trade_briefing,
)


class OperatorDecisionLabel(str, Enum):
    """The OPERATOR's own recorded decision (never produced by the system)."""

    PENDING = "PENDING"
    OPERATOR_DECIDED_ENTRY_BUY = "OPERATOR_DECIDED_ENTRY_BUY"
    OPERATOR_DECIDED_ENTRY_SELL = "OPERATOR_DECIDED_ENTRY_SELL"
    OPERATOR_DECIDED_HOLD = "OPERATOR_DECIDED_HOLD"
    OPERATOR_DECIDED_NO_ACTION = "OPERATOR_DECIDED_NO_ACTION"


_RECORDABLE_DECISIONS = frozenset(
    d for d in OperatorDecisionLabel if d is not OperatorDecisionLabel.PENDING
)

_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "今は買い", "今は売り", "買い推奨です", "売り推奨です", "BUY推奨", "SELL推奨",
    "勝てる", "勝てます", "good setup", "favorable setup", "opportunity now",
    "live_ready=true", "performance_proof_status=true", "confidence=",
    "win_rate=", "expected_profit=",
)


@dataclass(frozen=True)
class BriefingSafeSummary:
    """Safe-aggregate summary of a briefing (labels / counts / booleans only)."""

    input_completeness: str
    supply_caution_count: int
    no_action_status: str
    hard_stop_present: bool
    hard_stop_reasons: tuple[str, ...]
    tested_scope_match: str
    matched_rejected_ids: tuple[str, ...]

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class OperatorBriefingSession:
    """One manual briefing session. The operator records their OWN decision;
    the system never fills it. Never truthy, never a recommendation."""

    session_label: str
    summary: BriefingSafeSummary
    briefing_text: str
    operator_decision: OperatorDecisionLabel = OperatorDecisionLabel.PENDING
    operator_reason: str = ""
    decision_is_operator_supplied: bool = True
    is_recommendation: bool = False
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


def _summarise(request: SafeLabelSupplyRequest, session_label: str) -> OperatorBriefingSession:
    bundle = produce_operator_pre_trade_briefing(request)
    b = bundle.briefing
    summary = BriefingSafeSummary(
        input_completeness=bundle.input_completeness.value,
        supply_caution_count=len(bundle.supply_cautions),
        no_action_status=b.no_action_status.value,
        hard_stop_present=b.hard_stop_present,
        hard_stop_reasons=b.hard_stop_reasons,
        tested_scope_match=b.tested_scope_match.value,
        matched_rejected_ids=b.matched_rejected_ids,
    )
    return OperatorBriefingSession(
        session_label=session_label,
        summary=summary,
        briefing_text=bundle.briefing_text,
    )


def start_operator_briefing_session(
    request: SafeLabelSupplyRequest, *, session_label: str = ""
) -> OperatorBriefingSession:
    """Produce a PULL-style briefing session (decision starts PENDING). Pure,
    read-only. The operator will record their own decision separately."""

    return _summarise(request, session_label)


def record_operator_decision(
    session: OperatorBriefingSession,
    operator_decision: OperatorDecisionLabel,
    reason: str,
) -> OperatorBriefingSession:
    """Store the OPERATOR's own decision + reason. This module never derives or
    recommends a decision; the caller (operator) supplies it. Fail-closed:
    PENDING or an empty reason is rejected."""

    if operator_decision not in _RECORDABLE_DECISIONS:
        raise ValueError(
            "operator_decision must be a concrete operator-supplied decision"
        )
    if not reason or not reason.strip():
        raise ValueError("operator must record a non-empty reason")
    return replace(
        session, operator_decision=operator_decision, operator_reason=reason.strip()
    )


def render_operator_briefing_session(session: OperatorBriefingSession) -> str:
    """Render the session log: the warning-first briefing plus a SESSION block
    recording the operator's own decision. Guarded against recommendation leaks."""

    lines: list[str] = [session.briefing_text, ""]
    lines.append("[SESSION LOG] (operator's own record; not system advice)")
    lines.append(f"    - session_label: {session.session_label or '(unset)'}")
    lines.append(f"    - input_completeness: {session.summary.input_completeness}")
    lines.append(
        f"    - supply_caution_count: {session.summary.supply_caution_count}"
    )
    lines.append(f"    - no_action_status: {session.summary.no_action_status}")
    lines.append(f"    - hard_stop_present: {session.summary.hard_stop_present}")
    lines.append(f"    - tested_scope_match: {session.summary.tested_scope_match}")
    if session.operator_decision is OperatorDecisionLabel.PENDING:
        lines.append("    - operator_decision: PENDING")
        lines.append(
            "    - operator must record their OWN decision + reason "
            "(the system does not decide; no-flag != permission; no validated edge)."
        )
    else:
        lines.append(
            f"    - operator_decision (operator-supplied): "
            f"{session.operator_decision.value}"
        )
        lines.append(f"    - operator_reason: {session.operator_reason}")
        lines.append(
            "    - note: this is the operator's own discretionary decision; "
            "the system provided context only, with no validated edge."
        )
    text = "\n".join(lines)
    lowered = text.lower()
    for fragment in _FORBIDDEN_FRAGMENTS:
        if fragment.lower() in lowered:
            raise ValueError("session render produced a forbidden fragment")
    return text
