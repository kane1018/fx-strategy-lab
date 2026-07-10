# Integrated Engine / Strategy State

Date: 2026-07-10

Step: `FX_MULTI_AGENT_INTEGRATED_OPERATING_MODEL_SETUP_NO_POST`

This document is a compact index to existing sources of truth. It does not replace
[`PROJECT_STATUS.md`](PROJECT_STATUS.md), [`CODEX_HANDOFF.md`](CODEX_HANDOFF.md),
[`HYPOTHESIS_REGISTRY_NO_POST.md`](HYPOTHESIS_REGISTRY_NO_POST.md), the
[`E1 design contract`](E1_SHADOW_FULL_AUTO_ENGINE_NO_POST.md), or the
[`E1 runbook`](E1_SHADOW_FULL_AUTO_ENGINE_RUNBOOK_NO_POST.md). If they disagree,
the disagreement remains unresolved until the operator updates the applicable source.

## Repository snapshot

- branch: `main`
- HEAD at setup: `ccfb1a19c4fcbb219558e07f34eead66570613b9`
- origin/main at setup: `ccfb1a19c4fcbb219558e07f34eead66570613b9`
- working tree before setup: clean
- code state: E1 local-only, offline, bounded shadow full-auto engine implemented under
  `backend/app/shadow/e1/`
- formal stage: `E1_IMPLEMENTED_NOT_GATE_PASSED`

Every multi-agent round must record its own HEAD. This snapshot must not be reused as proof
that a later task still shares the same HEAD.

## Strategy state

- `current_strategy_status`: `NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE`
- research phase: `CLOSED_OUT` unless the operator explicitly reopens it
- H-01 through H-05: rejected
- H-06: frozen and unexecuted
- H-07, H-09, H-10: deferred
- H-08: blocked on data
- `performance_proof_status=false`
- `live_ready=false`
- `unattended_live_supported=false`

Implementation readiness, E1 evidence, and strategy edge are separate claims. No one may
infer strategy validity from the existence or correctness of the E1 engine.

## Active operator-selected hypothesis policy

[`OPERATOR_SELECTED_HYPOTHESIS_POLICY_REVISION_NO_POST.md`](OPERATOR_SELECTED_HYPOTHESIS_POLICY_REVISION_NO_POST.md)
is `ACTIVE`. The evaluation framework remains the research scorekeeper and risk enforcer;
the research-track multiple-testing ledger and escalation rule are unchanged. The registry
now distinguishes `OPERATOR_SELECTED_UNPROVEN` from validated research and records terminal
`EXHAUSTED` experiments without counting either state as a multiple-testing null.

The operator selected `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY` on 2026-07-10 with
registry status `OPERATOR_SELECTED_UNPROVEN`. The spec was frozen on 2026-07-11 per
[the freeze doc](STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md)
(`config_hash=sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1`,
formal test reserved forward-from-freeze, not collected). Stage 1 paper wiring
(no-POST, fake-transport-only) is operator-authorized; Stage 1 execution start still
requires operator confirmation after wiring and firing tests. The E1 gate is re-scoped to
Stage 3+ unattended-automation qualification only; Stage 1 and Stage 2 do not require E1 gate
passage. This scope change does not change the formal E1 status:
`E1_IMPLEMENTED_NOT_GATE_PASSED`. It grants no E2, E3, live, broker, credential, data-fetch,
or POST permission.

## H-11 selected premise and conditional staged-live direction

- Selected premise: [H-11 preregistration draft](STRATEGY_REGIME_ADAPTIVE_MOE_PREREGISTRATION_NO_POST_20260710.md)
- Future policy draft: [H-11 staged live policy](REGIME_ADAPTIVE_MOE_STAGED_LIVE_POLICY_NO_POST_20260710.md)
- Current stage: `SPEC_FROZEN_PRE_STAGE1` (frozen 2026-07-11); the staged-live policy still grants no live/POST permission.
- Initial model boundary: exactly three directional experts, no more than five regime axes, one
  low-capacity soft router, no online update/HMM/LightGBM/LLM, and no prediction-to-POST path.
- Existing periods are development-only. Formal test is not reserved and may not be reconstructed
  from previously inspected data.
- Future live intent is only `CONDITIONAL_STAGE2_SUPERVISED_LIVE`: frozen spec and config hash,
  separately authorized Stage 1 wiring and execution, at least two weeks and 20 paper trades plus
  policy conditions, operator review, separate Stage 2 procedure, separate major-incident resume
  policy, and per-trade Step 6G current-turn confirmation are all required in order.
- Research remains `CLOSED_OUT`; H-11 selection does not alter the research null ledger or escalation rule.
- Source conflicts fail closed under AGENTS.md and ACTIVE policy §7. The warning-only caution briefing
  remains direction/confidence-free and does not ingest H-11 output.

## Confirmed safety and stage boundaries

- actual POST permission: false
- entry POST: false
- settlement POST: false
- POST count for this setup Step: 0
- retry / repost / second POST: false
- broker read / broker write: false
- Private API / Public market GET / data fetch: false
- credential or env read: false
- raw request / raw response / broker response inspected: false
- raw / ID / value exposure: false
- generic close / generic opposite close: unavailable
- E1 gate passed: false
- E2 allowed: false
- E3 allowed: false

`ENTRY_BUY`, `ENTRY_SELL`, `HOLD`, actual-POST approval, and manual close remain operator-owned
safe labels or actions. No agent may generate or exercise them on the operator's behalf.

## E1 gate and remaining conditions

The frozen code thresholds are 14 calendar days, 10 event-recorded business days, at least
100 virtual entries, 100 virtual settlements, 300 qualified NO_ACTION events, five complete
exercises for every required fault category, three successful kill exercises, three successful
dead-man exercises, zero reconcile mismatches, zero safety violations, High incidents equal to
zero, and no more than two Medium incidents with complete post-mortems.

Calendar and business-day evidence is calculated from journal append-time `recorded_at`; a
synthetic timestamp, accelerated clock, or test run cannot shorten it. Even a blocker-free
technical report only becomes `E1_EVIDENCE_COMPLETE_E2_REVIEW_REQUIRED`; it never grants E2
execution permission.

## Unresolved source conflict

The setup request states that event, fault, kill, and dead-man evidence counts are sufficient,
with only calendar and business-day gates remaining. Current repository sources at the setup
HEAD instead state that required duration, event counts, fault, kill/dead-man, and reconcile
operational evidence are not yet satisfied. This setup did not read ignored local E1 artifacts,
run E1, or fetch data, so the narrower claim is not repository-confirmed.

Until an operator-authorized, sanitized evidence review updates the applicable source of truth:

- keep the formal status `E1_IMPLEMENTED_NOT_GATE_PASSED`;
- do not claim that non-time evidence counts are complete;
- do not use the conflict to start E2 or implementation; and
- preserve both the request claim and the repository claim as distinct facts.

## Known code / strategy collision points

- The engine can validate execution infrastructure but cannot establish statistical edge.
- The hypothesis registry is closed out while E1 infrastructure evidence can continue to accrue;
  E1 activity must not silently reopen rejected research.
- Gate counts validate contract behavior, not profitability or live execution quality.
- Historical Step 6G simulation/docs claims are not E1 evidence and are not broker proof.
- The API capability sheet is unknown-default and cannot feed E1, E2, hard-guard, or live permission.

## Next operator decisions

1. Decide whether to authorize a separate sanitized review of ignored E1 evidence artifacts to
   resolve the non-time-count conflict. That review must remain local-only, read-only, no-POST,
   and must not expose raw values or identifiers.
2. After the actual calendar and business-day thresholds are met, decide whether to open a
   dedicated E1 evidence review. Do not pre-authorize E2 implementation.
3. Decide separately whether and when the closed research phase may be reopened under a new
   mechanism-first preregistration; rejected hypotheses may not be repackaged.
