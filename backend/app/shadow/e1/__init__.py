"""E1 full-auto shadow lane (finite, local-only, no network, no real order)."""

from app.shadow.e1.contracts import (
    E1Policy,
    EngineDecision,
    EngineLabel,
    FaultInjection,
    FaultKind,
    FrozenHypothesisRegistry,
    FrozenHypothesisSpec,
    HypothesisLabel,
    MarketFrame,
    build_hypothesis_decision,
    build_settlement_decision,
)
from app.shadow.e1.engine import E1ShadowFullAutoEngine, build_e1_shadow_engine
from app.shadow.e1.qualification import (
    E1EvidenceWindow,
    E1GateReport,
    evaluate_e1_to_e2_review_gate,
    summarize_e1_bundle,
    summarize_e1_journal,
)

__all__ = [
    "E1EvidenceWindow",
    "E1GateReport",
    "E1Policy",
    "E1ShadowFullAutoEngine",
    "EngineDecision",
    "EngineLabel",
    "FaultInjection",
    "FaultKind",
    "FrozenHypothesisRegistry",
    "FrozenHypothesisSpec",
    "HypothesisLabel",
    "MarketFrame",
    "build_hypothesis_decision",
    "build_e1_shadow_engine",
    "build_settlement_decision",
    "evaluate_e1_to_e2_review_gate",
    "summarize_e1_bundle",
    "summarize_e1_journal",
]
