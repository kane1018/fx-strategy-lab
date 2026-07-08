"""Operator pre-trade caution briefing (read-only, safe-aggregate, no-POST).

Implements the frozen design
``OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709``.

This is NOT a trade recommender, NOT an alpha/auto engine, NOT edge proof, and
NOT a permission. The operator makes the ENTRY decision; this module only turns
SAFE, ALREADY-LABELLED inputs (exposure / orders / risk budget / execution
readiness / market-state categories — provided by the caller, never fetched)
into a warning-first, PULL-style caution briefing.

Hard invariants enforced here:
- Pure & deterministic. No trading-venue / network / credential / filesystem /
  env access, no runtime private data read, no POST, no execution, never
  triggers a Safe Execution & Risk Engine. It only reads SAFE LABELS passed in.
- Output is safe-aggregate only: safe labels, safe categories, safe counts,
  booleans, and constant human text. It carries NO raw price / spread / PnL /
  size and NO account / order / transaction / position / trade ID.
- NO direction (never up/down or buy/sell), NO recommendation, NO confidence /
  alpha / expected-profit / win-rate score.
- NO_ACTION is the default; ``no-flag != permission`` and ``not advice`` /
  ``no validated edge`` are stated every time. ENTRY_BUY / ENTRY_SELL / HOLD
  stay operator safe labels and are never produced here.
- ``performance_proof_status`` / ``live_ready`` stay false; briefing objects
  are never truthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Safe-label inputs (all provided by the caller from INTERNAL safe state;
# this module never fetches or reads any market/venue/price source)
# ---------------------------------------------------------------------------


class ExposureSafeLabel(str, Enum):
    FLAT = "FLAT"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS_OPEN = "MULTIPLE_POSITIONS_OPEN"
    EXPOSURE_UNKNOWN = "EXPOSURE_UNKNOWN"


class RiskBudgetSafeStatus(str, Enum):
    WITHIN_BUDGET = "WITHIN_BUDGET"
    NEAR_LIMIT = "NEAR_LIMIT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_UNKNOWN = "BUDGET_UNKNOWN"


class SafeExecutionReadiness(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    READINESS_UNKNOWN = "READINESS_UNKNOWN"


class TrendStateLabel(str, Enum):
    # Direction-FREE by design (never up/down).
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    TREND_STATE_UNKNOWN = "TREND_STATE_UNKNOWN"


class VolatilitySafeCategory(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    VOLATILITY_UNKNOWN = "VOLATILITY_UNKNOWN"


class SpreadSafeCategory(str, Enum):
    NORMAL = "NORMAL"
    WIDE = "WIDE"
    ABNORMAL = "ABNORMAL"
    SPREAD_UNKNOWN = "SPREAD_UNKNOWN"


class LiquiditySafeCategory(str, Enum):
    NORMAL = "NORMAL"
    THIN = "THIN"
    LIQUIDITY_UNKNOWN = "LIQUIDITY_UNKNOWN"


class TimeOfDaySafeCategory(str, Enum):
    TOKYO = "TOKYO"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OFF_HOURS = "OFF_HOURS"
    TIME_OF_DAY_UNKNOWN = "TIME_OF_DAY_UNKNOWN"


class EventProximitySafeLabel(str, Enum):
    NONE = "NONE"
    NEAR_SCHEDULED_EVENT = "NEAR_SCHEDULED_EVENT"
    EVENT_PROXIMITY_UNKNOWN = "EVENT_PROXIMITY_UNKNOWN"


# ---------------------------------------------------------------------------
# Derived safe-label outputs
# ---------------------------------------------------------------------------


class NoActionStatus(str, Enum):
    NO_ACTION_DEFAULT = "NO_ACTION_DEFAULT"
    NO_ACTION_STRONGLY_INDICATED = "NO_ACTION_STRONGLY_INDICATED"


class TestedScopeMatch(str, Enum):
    RESEMBLES_REJECTED = "RESEMBLES_REJECTED"
    OUTSIDE_TESTED_SCOPE = "OUTSIDE_TESTED_SCOPE"
    NOT_ASSESSED = "NOT_ASSESSED"


# Rejected-ledger descriptive tags (mirrors HYPOTHESIS_REGISTRY_NO_POST.md).
# Matching is DESCRIPTIVE and produces a CAUTION only -- never a signal, never
# a direction, never a "safe to trade" verdict.
_REJECTED_LEDGER: tuple[tuple[str, frozenset[str]], ...] = (
    ("H-01_M5_TECHNICAL", frozenset({"m5", "technical", "trend", "breakout",
                                     "mean_reversion", "dual_confirmation"})),
    ("H-02_H1_TREND_RIDE", frozenset({"h1", "trend", "trend_continuation",
                                      "atr_ride"})),
    ("H-03_SESSION_MOMENTUM", frozenset({"session_open", "session", "momentum"})),
    ("H-04_GOTOBI_FIX_DRIFT", frozenset({"gotobi", "tokyo_fix", "session",
                                         "calendar"})),
    ("H-05_VOL_REGIME_BREAKOUT", frozenset({"breakout", "high_vol", "volatility",
                                            "trend_continuation", "regime"})),
)

# ---------------------------------------------------------------------------
# Constant human text (safe; never a recommendation)
# ---------------------------------------------------------------------------

STANDING_DISCLAIMER: tuple[str, ...] = (
    "この briefing は売買推奨ではない（not advice）。",
    "システムに検証済みの優位性は無い（no validated edge / "
    "NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE）。",
    "警告が無いことは「実行して良い」を意味しない（no-flag != permission）。",
    "最終判断は operator が行う。ENTRY_BUY / ENTRY_SELL / HOLD は operator の判断。",
)

FORBIDDEN_CLAIMS_REMINDER: tuple[str, ...] = (
    "本 briefing は方向（上下・売り買い）を示さない。",
    "確信度スコア・勝率・期待利益・アルファ値・売買の推奨は提示しない。",
    "これは自動売買でも実行でもない（briefing は執行しない）。",
)

PRE_ENTRY_CHECKLIST: tuple[str, ...] = (
    "disclaimer を読んだ（優位性なし / not advice / no-flag != permission）。",
    "NO_ACTION の該当理由を確認した。",
    "hard-stop 条件に該当していない。",
    "tested-scope / rejected 照合を確認した（棄却領域か・未検証領域か）。",
    "risk budget / exposure が上限内。",
    "この判断は自分（operator）の裁量であり、システムの検証済み優位性に基づかない。",
    "決定理由を記録する。",
)

OPERATOR_DECISION_PROMPT = (
    "operator: あなた自身の判断を safe label で入力してください "
    "（ENTRY_BUY / ENTRY_SELL / HOLD）。この briefing は決定しません。"
)
OPERATOR_REASON_PROMPT = (
    "operator: 判断理由を記録してください（後日レビュー用・後付け合理化の抑止）。"
)

# Fragments that would only appear if a recommendation/leak occurred. The
# renderer asserts NONE of these appear in its output (defence in depth).
_FORBIDDEN_OUTPUT_FRAGMENTS: tuple[str, ...] = (
    "今は買い", "今は売り", "買い推奨です", "売り推奨です", "BUY推奨", "SELL推奨",
    "勝てる", "勝てます", "edgeあり", "エッジあり", "good setup", "favorable setup",
    "opportunity now", "live_ready=true", "performance_proof_status=true",
    "confidence=", "win_rate=", "expected_profit=",
)


@dataclass(frozen=True)
class BriefingInputs:
    """Caller-supplied SAFE labels only (from internal safe state; never fetched)."""

    exposure: ExposureSafeLabel = ExposureSafeLabel.EXPOSURE_UNKNOWN
    pending_order_safe_count: int = 0
    risk_budget: RiskBudgetSafeStatus = RiskBudgetSafeStatus.BUDGET_UNKNOWN
    safe_execution_readiness: SafeExecutionReadiness = (
        SafeExecutionReadiness.READINESS_UNKNOWN
    )
    trend_state: TrendStateLabel = TrendStateLabel.TREND_STATE_UNKNOWN
    volatility: VolatilitySafeCategory = VolatilitySafeCategory.VOLATILITY_UNKNOWN
    spread: SpreadSafeCategory = SpreadSafeCategory.SPREAD_UNKNOWN
    liquidity: LiquiditySafeCategory = LiquiditySafeCategory.LIQUIDITY_UNKNOWN
    time_of_day: TimeOfDaySafeCategory = TimeOfDaySafeCategory.TIME_OF_DAY_UNKNOWN
    event_proximity: EventProximitySafeLabel = (
        EventProximitySafeLabel.EVENT_PROXIMITY_UNKNOWN
    )
    uncertainty_high: bool = True  # fail-closed: assume high uncertainty
    # Descriptive safe tags for the operator's intended context (for matching
    # against the rejected ledger). Empty => NOT_ASSESSED.
    intended_context_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CautionBriefing:
    """Warning-first, safe-aggregate caution briefing. Never truthy, never a
    recommendation, carries no direction / confidence / raw value / ID."""

    disclaimer: tuple[str, ...]
    no_action_status: NoActionStatus
    no_action_reasons: tuple[str, ...]
    hard_stop_present: bool
    hard_stop_reasons: tuple[str, ...]
    tested_scope_match: TestedScopeMatch
    matched_rejected_ids: tuple[str, ...]
    tested_scope_note: str
    exposure: ExposureSafeLabel
    pending_order_safe_count: int
    risk_budget: RiskBudgetSafeStatus
    safe_execution_readiness: SafeExecutionReadiness
    risk_warnings: tuple[str, ...]
    trend_state: TrendStateLabel
    volatility: VolatilitySafeCategory
    spread: SpreadSafeCategory
    liquidity: LiquiditySafeCategory
    time_of_day: TimeOfDaySafeCategory
    event_proximity: EventProximitySafeLabel
    pre_entry_checklist: tuple[str, ...]
    uncertainty_notes: tuple[str, ...]
    forbidden_claims_reminder: tuple[str, ...]
    operator_decision_prompt: str
    operator_reason_prompt: str
    is_pull_generated: bool = True
    is_recommendation: bool = False
    provides_direction: bool = False
    no_flag_is_not_permission: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:  # never truthy / never a permission
        return False


def _hard_stops(inputs: BriefingInputs) -> tuple[str, ...]:
    reasons: list[str] = []
    if inputs.spread is SpreadSafeCategory.ABNORMAL:
        reasons.append("HARD_STOP_SPREAD_ABNORMAL")
    if inputs.event_proximity is EventProximitySafeLabel.NEAR_SCHEDULED_EVENT:
        reasons.append("HARD_STOP_EVENT_PROXIMITY")
    if inputs.uncertainty_high:
        reasons.append("HARD_STOP_HIGH_UNCERTAINTY")
    if inputs.risk_budget is RiskBudgetSafeStatus.BUDGET_EXCEEDED:
        reasons.append("HARD_STOP_RISK_BUDGET_EXCEEDED")
    if inputs.exposure is ExposureSafeLabel.EXPOSURE_UNKNOWN:
        reasons.append("HARD_STOP_INTERNAL_STATE_UNKNOWN")
    if inputs.safe_execution_readiness is SafeExecutionReadiness.NOT_READY:
        reasons.append("HARD_STOP_SAFE_EXECUTION_NOT_READY")
    if inputs.safe_execution_readiness is (
        SafeExecutionReadiness.READINESS_UNKNOWN
    ):
        reasons.append("HARD_STOP_SAFE_EXECUTION_READINESS_UNKNOWN")
    return tuple(reasons)


def _risk_warnings(inputs: BriefingInputs) -> tuple[str, ...]:
    warnings: list[str] = []
    if inputs.spread is SpreadSafeCategory.WIDE:
        warnings.append("WARN_SPREAD_WIDE")
    if inputs.volatility is VolatilitySafeCategory.HIGH:
        warnings.append("WARN_HIGH_VOLATILITY")
    if inputs.liquidity is LiquiditySafeCategory.THIN:
        warnings.append("WARN_THIN_LIQUIDITY")
    if inputs.risk_budget is RiskBudgetSafeStatus.NEAR_LIMIT:
        warnings.append("WARN_RISK_BUDGET_NEAR_LIMIT")
    if inputs.pending_order_safe_count > 0:
        warnings.append("WARN_PENDING_ORDERS_PRESENT")
    if inputs.exposure in (
        ExposureSafeLabel.ONE_POSITION_OPEN,
        ExposureSafeLabel.MULTIPLE_POSITIONS_OPEN,
    ):
        warnings.append("WARN_POSITION_ALREADY_OPEN")
    return tuple(warnings)


def _match_rejected_ledger(
    tags: tuple[str, ...],
) -> tuple[TestedScopeMatch, tuple[str, ...], str]:
    if not tags:
        return (
            TestedScopeMatch.NOT_ASSESSED,
            (),
            "意図文脈タグ未提供のため照合不能。照合不能は「実行して良い」ではない "
            "（unknown / no validated edge / no-flag != permission）。",
        )
    tag_set = {t.strip().lower() for t in tags if t.strip()}
    matched = tuple(
        hid for hid, hyp_tags in _REJECTED_LEDGER if tag_set & hyp_tags
    )
    if matched:
        return (
            TestedScopeMatch.RESEMBLES_REJECTED,
            matched,
            "この文脈は過去に棄却された仮説に類似する（当該領域で robust edge は "
            "見つからなかった）。これは注意喚起であり、方向・可否の指示ではない。",
        )
    return (
        TestedScopeMatch.OUTSIDE_TESTED_SCOPE,
        (),
        "検証済み範囲の外（未検証・unknown）。未検証は「実行して良い」ではない "
        "（no validated edge / no-flag != permission）。",
    )


def generate_caution_briefing(inputs: BriefingInputs) -> CautionBriefing:
    """Turn SAFE labels into a warning-first caution briefing. Deterministic,
    read-only, no side effects. NO_ACTION is the default; hard-stops escalate
    it. Never produces a direction / recommendation / confidence / raw value."""

    hard_stops = _hard_stops(inputs)
    status = (
        NoActionStatus.NO_ACTION_STRONGLY_INDICATED
        if hard_stops
        else NoActionStatus.NO_ACTION_DEFAULT
    )
    no_action_reasons: tuple[str, ...] = (
        hard_stops
        if hard_stops
        else ("NO_ACTION_DEFAULT_SETUP_NOT_A_PERMISSION",)
    )
    match, matched_ids, note = _match_rejected_ledger(inputs.intended_context_tags)
    uncertainty_notes = (
        "不確実性・未検証領域が存在する。確信度スコアは提示しない（不確実性で代替）。",
        "market-state は状態の記述であり、方向や行動の示唆ではない。",
    )
    return CautionBriefing(
        disclaimer=STANDING_DISCLAIMER,
        no_action_status=status,
        no_action_reasons=no_action_reasons,
        hard_stop_present=bool(hard_stops),
        hard_stop_reasons=hard_stops,
        tested_scope_match=match,
        matched_rejected_ids=matched_ids,
        tested_scope_note=note,
        exposure=inputs.exposure,
        pending_order_safe_count=inputs.pending_order_safe_count,
        risk_budget=inputs.risk_budget,
        safe_execution_readiness=inputs.safe_execution_readiness,
        risk_warnings=_risk_warnings(inputs),
        trend_state=inputs.trend_state,
        volatility=inputs.volatility,
        spread=inputs.spread,
        liquidity=inputs.liquidity,
        time_of_day=inputs.time_of_day,
        event_proximity=inputs.event_proximity,
        pre_entry_checklist=PRE_ENTRY_CHECKLIST,
        uncertainty_notes=uncertainty_notes,
        forbidden_claims_reminder=FORBIDDEN_CLAIMS_REMINDER,
        operator_decision_prompt=OPERATOR_DECISION_PROMPT,
        operator_reason_prompt=OPERATOR_REASON_PROMPT,
    )


def render_caution_briefing(briefing: CautionBriefing) -> str:
    """Render the briefing as warning-first ordered text (safe only). Guards
    that no recommendation/leak fragment can appear."""

    lines: list[str] = []
    lines.append("=== OPERATOR PRE-TRADE CAUTION BRIEFING (not advice) ===")
    lines.append("[1] DISCLAIMER")
    lines.extend(f"    - {d}" for d in briefing.disclaimer)
    lines.append(f"[2] NO_ACTION STATUS: {briefing.no_action_status.value}")
    lines.extend(f"    - {r}" for r in briefing.no_action_reasons)
    lines.append(
        f"[3] HARD-STOP: present={briefing.hard_stop_present}"
    )
    lines.extend(f"    - {r}" for r in briefing.hard_stop_reasons)
    lines.append(
        f"[4] TESTED-SCOPE / REJECTED-LEDGER: {briefing.tested_scope_match.value}"
    )
    if briefing.matched_rejected_ids:
        lines.append(
            "    - resembles: " + ", ".join(briefing.matched_rejected_ids)
        )
    lines.append(f"    - {briefing.tested_scope_note}")
    lines.append("[5] RISK / EXPOSURE / BUDGET (internal safe state; no live query)")
    lines.append(f"    - exposure: {briefing.exposure.value}")
    lines.append(
        f"    - pending_order_safe_count: {briefing.pending_order_safe_count}"
    )
    lines.append(f"    - risk_budget: {briefing.risk_budget.value}")
    lines.append(
        f"    - safe_execution_readiness: {briefing.safe_execution_readiness.value}"
    )
    lines.extend(f"    - {w}" for w in briefing.risk_warnings)
    lines.append("[6] MARKET-STATE (descriptive, direction-free)")
    lines.append(f"    - trend_state: {briefing.trend_state.value}")
    lines.append(f"    - volatility: {briefing.volatility.value}")
    lines.append(f"    - spread: {briefing.spread.value}")
    lines.append(f"    - liquidity: {briefing.liquidity.value}")
    lines.append(f"    - time_of_day: {briefing.time_of_day.value}")
    lines.append(f"    - event_proximity: {briefing.event_proximity.value}")
    lines.append("[7] PRE-ENTRY CHECKLIST")
    lines.extend(f"    [ ] {c}" for c in briefing.pre_entry_checklist)
    lines.append("[8] UNCERTAINTY NOTES")
    lines.extend(f"    - {u}" for u in briefing.uncertainty_notes)
    lines.extend(f"    - {r}" for r in briefing.forbidden_claims_reminder)
    lines.append("[9] OPERATOR FINAL DECISION")
    lines.append(f"    - {briefing.operator_decision_prompt}")
    lines.append(f"    - {briefing.operator_reason_prompt}")
    lines.append(
        "    - reminder: no-flag != permission; final decision is the operator's."
    )
    text = "\n".join(lines)
    lowered = text.lower()
    for fragment in _FORBIDDEN_OUTPUT_FRAGMENTS:
        if fragment.lower() in lowered:
            raise ValueError(
                "caution briefing renderer produced a forbidden fragment"
            )
    return text
