# Multi-Agent Operating Model

Date: 2026-07-10

Step: `FX_MULTI_AGENT_INTEGRATED_OPERATING_MODEL_SETUP_NO_POST`

Case: `PROJECT_SCOPED_MULTI_AGENT_COORDINATION_SETUP_AND_READONLY_PILOT`

## Purpose and fixed boundary

This operating model reduces strategy, code, and FX-safety blind spots before any implementation.
It does not authorize E2 implementation, E1 or paper execution, broker or API access, credential or
environment inspection, market-data fetch, actual POST, settlement, live execution, or trading
decisions. [`INTEGRATED_ENGINE_STRATEGY_STATE.md`](INTEGRATED_ENGINE_STRATEGY_STATE.md) is the
shared index; its linked documents remain the sources of truth.

Project configuration fixes `agents.max_threads=4` and `agents.max_depth=1`. The root integrator
may open the three read-only specialists directly in parallel. A child may not spawn another child.

## Roles and permissions

| Role | Permission | Responsibility |
| --- | --- | --- |
| root integrator | current task permission | Freeze scope and HEAD, orchestrate review, preserve dissent, decide whether consensus exists, and authorize at most one writer. |
| `strategy_researcher` | read-only | Evaluate hypotheses, statistics, falsification, data needs, and gates; detect rejected-hypothesis recycling. |
| `code_architect` | read-only | Evaluate actual code, state transitions, journals, reconciliation, tests, feasibility, and maintainability. |
| `fx_safety_auditor` | read-only with veto | Audit POST and close-route distinctions, attempts, retries, exposure, stop conditions, and permission drift. |
| `implementation_worker` | workspace-write | Make the agreed minimal change only after explicit consensus and a cleared safety veto. It is the sole writer for a task. |

The implementation worker is not used in the read-only pilot. Multiple write-capable agents must
never be active for the same task.

## Shared-snapshot protocol

Before Round 1, the root integrator performs the allowed repository sync and records:

```text
pwd
branch
git status --short
HEAD
origin/main
HEAD_equals_origin_main
working_tree_clean
```

Every specialist independently reports the HEAD it inspected. If any HEAD differs, HEAD is not
origin/main, or the tree is dirty, the round stops. The root supplies the same task statement,
shared-index path, relevant source paths, and output schema to all three specialists. Agents do
not fetch, mutate, run E1 or paper workflows, or inspect ignored evidence artifacts during this
pilot.

## Round 1: independent review

Launch `strategy_researcher`, `code_architect`, and `fx_safety_auditor` in parallel. Each response
must contain:

1. confirmed facts;
2. problem framing;
3. recommendation;
4. non-recommendations;
5. questions for the other roles;
6. unknowns;
7. operator decisions required; and
8. exact repository references.

The pilot topic is:

> E1 event and fault evidence may be mature, but the real-time calendar/business-day gate is not
> satisfied. While waiting, what preparation best improves the next decision without starting E2
> or increasing information bias?

The source conflict recorded in the shared index must be addressed explicitly; no agent may assume
that non-time evidence is complete merely because the pilot wording says it may be.

## Round 2: cross-challenge

The root integrator routes proposals without erasing their authorship:

1. Send the strategy proposal to the code architect and safety auditor for criticism.
2. Send the code/operations proposal to the strategy researcher and safety auditor for criticism.
3. Send every safety finding to the strategy researcher and code architect for revised positions.
4. Require each role to state `changed_after_challenge`, `unchanged_after_challenge`, and why.
5. Preserve unresolved objections verbatim as concise findings; do not manufacture consensus.

Cross-challenge is read-only. An agent may tighten a proposal but may not convert a readiness label,
majority vote, or absence of a detected issue into permission.

## Round 3: root integration

The root integrator reports:

- agreements;
- principal disagreements;
- adopted and rejected proposals;
- unresolved questions;
- safety veto status;
- operator decisions;
- the maximum next implementable scope; and
- boundaries that cannot be crossed.

If there is disagreement on strategy meaning, code semantics, evidence validity, or safety, no
implementation starts. A majority does not override an unresolved FX safety veto.

## Operator-owned decisions and safe labels

The following always remain operator-owned and cannot be inferred by an agent:

- reopening the research phase;
- accepting a new hypothesis or changing a frozen gate;
- accepting evidence as operationally complete;
- starting E2 or E3;
- `ENTRY_BUY`, `ENTRY_SELL`, or `HOLD`;
- actual-POST approval; and
- manual close or any live action.

An operator decision for one item does not grant any adjacent permission.

## Implementation handoff gate

The root may start `implementation_worker` only when all of the following are explicit:

- all three reviewers inspected the same clean HEAD;
- strategy objective and falsification condition are written;
- code scope, state transitions, and tests are written;
- `fx_safety_auditor` reports no unresolved veto;
- operator-owned decisions required for that scope are recorded;
- exact files and validation commands are bounded; and
- E2, paper execution, broker/API/env/credential, and POST remain excluded unless a different
  operator-approved Step expressly changes the boundary.

The implementation worker is the only writer. The root and read-only specialists review its diff;
they do not edit concurrently.

## Final report schema

The root report uses this order:

1. CASE and conclusion
2. repository snapshot
3. agents and permissions
4. shared sources
5. independent findings
6. cross-challenge changes
7. agreements and disagreements
8. adopted and rejected proposals
9. safety veto
10. operator decisions
11. maximum implementation scope and forbidden boundary
12. validation and prohibited-action confirmation
13. unresolved issues and residual risk
14. commit/push state and next Step

Every report fixes these fields to explicit booleans or safe labels: E1 gate, E2 allowed, E3 allowed,
actual POST, broker read/write, env read, raw/ID/value exposure, performance proof, live readiness,
and unattended-live support.

## Pilot loading note

Standalone project agents are loaded for spawned sessions from `.codex/agents/`, while project
configuration is loaded only for a trusted project. A running task does not provide a verified way
to reload newly created agent definitions with their declared model and sandbox. Therefore the
setup task must not substitute generic agents and call that the pilot.

After this configuration is committed, pushed, and visible from a clean `main`, start a new Codex
task with:

> Read AGENTS.md, docs/INTEGRATED_ENGINE_STRATEGY_STATE.md, and
> docs/MULTI_AGENT_OPERATING_MODEL.md. Confirm clean main and HEAD==origin/main, then run the
> documented read-only three-agent E1 waiting-period pilot through all three rounds. Do not start
> implementation_worker, E1/paper execution, data fetch, broker/API/env/credential access, or POST.
