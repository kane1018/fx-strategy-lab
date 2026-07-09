"""Operator pre-trade briefing service (read-only façade, no-POST).

Single read-only entry point for the operator pre-trade caution briefing. It
orchestrates the existing pieces -- SAFE-label supply (fail-closed
normalisation) -> caution briefing generation (warning-first, NO_ACTION
default) -> render (warning-first text) -- and packages them into one bundle.

This is NOT a decision engine, NOT market-data acquisition, NOT a trading-venue
status query, NOT execution preparation. It performs NO network / private data
read / filesystem / env / secret access, NO fetch, NO POST, and never triggers
a Safe Execution & Risk Engine. It only consumes SAFE labels supplied by the
caller from INTERNAL safe state.

Invariants: no direction / recommendation / confidence / alpha / expected-profit
/ win-rate; no raw price/spread/PnL/size and no account/order/transaction/
position/trade ID; ENTRY_BUY/ENTRY_SELL/HOLD are never produced; bundles are
never truthy; ``performance_proof_status`` / ``live_ready`` stay false.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.operator_briefing_safe_label_supply import (
    InputCompleteness,
    SafeLabelSupplyRequest,
    build_briefing_inputs,
)
from app.services.operator_pre_trade_caution_briefing import (
    CautionBriefing,
    generate_caution_briefing,
    render_caution_briefing,
)

# Defence in depth: the combined text must never contain a recommendation leak.
_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "今は買い", "今は売り", "買い推奨です", "売り推奨です", "BUY推奨", "SELL推奨",
    "勝てる", "勝てます", "good setup", "favorable setup", "opportunity now",
    "live_ready=true", "performance_proof_status=true", "confidence=",
    "win_rate=", "expected_profit=",
)


@dataclass(frozen=True)
class OperatorPreTradeBriefingBundle:
    """Everything a caller needs for one PULL-style pre-trade caution briefing.
    Never truthy, never a recommendation, carries no direction / confidence /
    raw value / ID."""

    input_completeness: InputCompleteness
    supply_cautions: tuple[str, ...]
    briefing: CautionBriefing
    briefing_text: str
    is_pull_generated: bool = True
    is_recommendation: bool = False
    provides_direction: bool = False
    no_flag_is_not_permission: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:  # never truthy / never a permission
        return False


def produce_operator_pre_trade_briefing(
    request: SafeLabelSupplyRequest,
) -> OperatorPreTradeBriefingBundle:
    """Run the full read-only pipeline: normalise SAFE labels -> generate the
    warning-first caution briefing -> render it. Pure, side-effect free."""

    result = build_briefing_inputs(request)
    briefing = generate_caution_briefing(result.briefing_inputs)
    briefing_text = render_caution_briefing(briefing)
    return OperatorPreTradeBriefingBundle(
        input_completeness=result.input_completeness,
        supply_cautions=result.supply_cautions,
        briefing=briefing,
        briefing_text=briefing_text,
    )


def render_operator_pre_trade_briefing(request: SafeLabelSupplyRequest) -> str:
    """Combined warning-first text: input/supply data-quality cautions first,
    then the caution briefing. Guarded so no recommendation fragment can leak."""

    bundle = produce_operator_pre_trade_briefing(request)
    lines: list[str] = []
    lines.append("=== OPERATOR PRE-TRADE BRIEFING (read-only, not advice) ===")
    lines.append(f"[0] INPUT / SUPPLY DATA-QUALITY: {bundle.input_completeness.value}")
    if bundle.supply_cautions:
        lines.extend(f"    - {c}" for c in bundle.supply_cautions)
    else:
        lines.append("    - (no supply-level cautions)")
    lines.append(
        "    - reminder: unknown / missing / outside tested scope are cautions, "
        "not permission (no-flag != permission)."
    )
    lines.append(bundle.briefing_text)
    text = "\n".join(lines)
    lowered = text.lower()
    for fragment in _FORBIDDEN_FRAGMENTS:
        if fragment.lower() in lowered:
            raise ValueError(
                "operator pre-trade briefing produced a forbidden fragment"
            )
    return text
