# Step 5P E2E Dry-run Chain Review

## Step 5T Update

Step 5T extends the dry-run chain with a real approval gate generation package.
The package does not issue a gate, approval id, approval command, or copyable
approval text, and it does not call APIs, ledgers, `live_order_once`, or POST.
See [STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5P adds an end-to-end dry-run chain review model for the Step 5B through
Step 5O artifacts. It checks whether the fake/sanitized chain connects
consistently from `LiveOrderCandidate` through `LiveOrderOneShotExecutionRunbook`.

This step is no API and no POST. It does not execute any future live phase.

## Scope

The model lives in:

```text
backend/app/live_verification/live_order_e2e_dry_run_chain.py
```

It accepts already-built dry-run artifacts and returns a sanitized
`LiveOrderE2EDryRunChainReview` with stage summaries, check results, blocked
reasons, and a recommended next step.

## What This Step Does Not Do

- It does not execute HTTP POST.
- It does not place, add, close, cancel, or change orders.
- It does not call read-only API, public API, Private API, broker code, or
  `live_order_once`.
- It does not issue a real approval gate.
- It does not generate a real approval id.
- It does not generate, save, display, or copy a real approval command.
- It does not read or write ledger state.
- It does not display or store raw request, raw response, credentials, headers,
  signatures, order ids, execution ids, position ids, or client order ids.

## Inputs: Step 5B Through Step 5O Artifacts

The build function accepts these dry-run artifacts:

```text
LiveOrderCandidate
LiveOrderCandidateRiskDecision
LiveOrderCandidateTraceRecord
LiveOrderCandidateReviewReport
ReviewGatedSessionPolicyDecision
ReviewGatedSessionBundle
LiveOrderOperatorReviewProcedure
LiveOrderApprovalHandoffPackage
LiveOrderApprovalGateDesign
LiveOrderApprovalGatePreview
LiveOrderApprovalValidationSimulation
LiveOrderFinalDynamicPreflightDecision
LiveOrderOneShotBoundaryDecision
LiveOrderOneShotExecutionRunbook
```

These are sanitized in-memory objects. They are not API responses and are not
read from a ledger.

## Output: LiveOrderE2EDryRunChainReview

The output keeps the chain-level references and safety flags:

```text
chain_id
candidate_id
risk_decision_id
trace_id
review_id
session_policy_decision_id
bundle_id
operator_review_id
handoff_id
design_id
preview_id
simulation_id
preflight_decision_id
boundary_id
runbook_id
source_signal_id
symbol / side / size / execution_type
stages
check_results
blocked_reasons
recommended_next_step
```

## Ready Chain Meaning

`READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW` means only that the dry-run artifacts are
internally consistent as review material.

It does not mean:

- live POST is allowed
- approval gate may be issued
- a real approval command may be generated
- final dynamic preflight may be executed
- post reconciliation may be executed

The ready output uses:

```text
chain_ready=true
eligible_for_future_real_approval_planning=true
allowed_for_live=false
recommended_next_step=review_e2e_dry_run_chain_then_prepare_future_real_approval_planning_separate_step_no_post
```

## Blocked Chain Meaning

`BLOCKED_E2E_DRY_RUN_CHAIN` means at least one stage, reference, status, safety
flag, or one-shot constraint is inconsistent. The chain still remains a dry-run
review artifact.

Blocked output uses:

```text
chain_ready=false
eligible_for_future_real_approval_planning=false
allowed_for_live=false
recommended_next_step=fix_e2e_dry_run_chain_blockers_no_post
```

## Required Stages

Step 5P requires these stage names:

```text
candidate_dry_run
risk_gate
trace_record
review_report
session_policy
session_bundle
operator_review
approval_handoff
approval_gate_design
approval_gate_preview
approval_validation_simulation
final_dynamic_preflight
one_shot_boundary
execution_runbook
```

## Stage Consistency Checks

Each stage must be present and ready/pass-equivalent:

- candidate is `REVIEW_REQUIRED`
- risk gate is `PASSED_FOR_HUMAN_REVIEW`
- trace is `READY_FOR_REVIEW`
- review is `READY_FOR_HUMAN_REVIEW`
- session policy is `POLICY_PASSED_FOR_REVIEW`
- bundle is `READY_FOR_OPERATOR_REVIEW`
- operator review is `READY_FOR_OPERATOR_CHECKLIST`
- handoff is `READY_FOR_APPROVAL_HANDOFF_REVIEW`
- design is `READY_FOR_APPROVAL_GATE_DESIGN_REVIEW`
- preview is `READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW`
- validation simulation is `SIMULATED_APPROVAL_VALIDATION_PASSED`
- final dynamic preflight is `READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW`
- one-shot boundary is `READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW`
- execution runbook is `READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW`

## ID Consistency Checks

The chain checks sanitized references such as:

- `candidate_id`
- `risk_decision_id`
- `trace_id`
- `review_id`
- `session_policy_decision_id`
- `bundle_id`
- `operator_review_id`
- `handoff_id`
- `design_id`
- `preview_id`
- `simulation_id`
- `preflight_decision_id`
- `boundary_id`
- `source_signal_id`

Mismatches fail closed.

## Safety Flag Consistency Checks

Every stage must preserve:

```text
allowed_for_live=false
dry_run_only=true
approval_gate_issued=false
approval_id_generated=false
approval_command_generated=false
approval_command_copyable=false
post_executed=false
live_order_once_called=false
private_api_called=false
broker_called=false
read_only_api_called=false
```

## One-shot Constraint Consistency Checks

The chain requires:

```text
post_attempt_limit=1
retry_allowed=false
loop_allowed=false
add_order_allowed=false
change_order_allowed=false
cancel_order_allowed=false
close_order_allowed=false
post_reconciliation_required=true
```

## Check Results

`LiveOrderE2EDryRunChainCheckResult` records sanitized checks for:

- required stages
- stage statuses
- symbol / side / size / execution type consistency
- source signal consistency
- ID consistency
- `allowed_for_live=false`
- `dry_run_only=true`
- approval artifacts not generated
- POST not executed
- no API / broker / `live_order_once` calls
- one-shot constraints
- post reconciliation requirement

## Markdown Rendering

`render_live_order_e2e_dry_run_chain_markdown()` renders sanitized fields only
and includes these warnings:

```text
This E2E dry-run chain review is dry-run only.
This review does not call read-only API.
This review does not call Private API.
This review does not call live_order_once.
This review does not execute HTTP POST.
This review does not issue a real approval gate.
This review does not generate a real approval command.
This review does not authorize live POST.
allowed_for_live=false.
```

## Do-not-cross Boundaries

- Strategy signal / candidate / risk decision / trace / review / session policy
  / bundle / operator review / handoff / design / preview / validation
  simulation / preflight model / boundary / runbook / E2E chain do not directly
  POST.
- Chain ready does not permit real approval gate issuance.
- Chain ready does not permit real approval command generation.
- Chain ready does not permit final dynamic preflight execution.
- Chain ready does not permit one-shot POST or post reconciliation.

## Relationship to Future Real Approval Planning

Step 5P can be used as evidence for a future, separate planning task. Any real
approval gate, fresh final dynamic preflight, one-shot POST, post reconciliation,
and final report must remain explicit later Steps with fresh authorization and
fresh dynamic checks.

## Tests

Added tests cover:

- full safe fake chain ready state
- `allowed_for_live=false` fixed even when ready
- missing stage blocker
- blocked stage and merged blocked reasons
- candidate, risk, trace, review, source signal, symbol, side, size, and
  execution type mismatches
- unsafe approval, POST, API, retry, loop, add, change, cancel, close flags
- one-shot attempt limit and post reconciliation requirement
- required stage names and check result names
- Markdown warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5P is complete as an end-to-end dry-run chain review model. A ready chain is
review evidence only. It is not live POST permission, approval gate permission,
approval command generation permission, final dynamic preflight permission, or
post reconciliation permission.

## Step 5Q Follow-up

Step 5Q now adds the real approval readiness checkpoint model. It consumes this
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST. A ready Step 5Q checkpoint is still review evidence
only and does not authorize real approval gate issuance or live POST.

## Step 5R Follow-up

Step 5R now adds the real approval gate plan dry-run model. It consumes the Step
5Q readiness checkpoint as sanitized evidence, records the future approval gate
sequence, preserves `allowed_for_live=false`, and does not call APIs, issue
approval, generate real approval ids or commands, call `live_order_once`,
read/write ledgers, or execute POST. A ready Step 5R plan is still planning
evidence only and does not authorize real approval gate issuance or live POST.

## Step 5S Follow-up

Step 5S adds a pre-approval fresh preflight dry-run model. It consumes the Step
5R real approval gate plan plus sanitized snapshot fields for account/assets,
open positions, active orders, instrument rules, ticker/spread/age,
market/maintenance/event, API scope/order permission/IP account, previous
result, session/daily limits, Git/tests/ruff/secret scan, raw response flags,
outbound body allowlist, request/signing body equality, and pre-approval
freshness.

A ready Step 5S decision keeps `allowed_for_live=false` and is only evidence for
a future separate real approval gate generation step. Step 5S does not call APIs,
issue approval, generate real approval ids or commands, make approval text
copyable, call `live_order_once`, read/write ledgers, or execute POST.

## Step 5V Follow-up

Step 5V adds `LiveOrderRealApprovalImplementationReadinessReview` as a
sanitized, dry-run-only readiness review for a future real approval gate
implementation step. It consumes the Step 5U pre-implementation audit and keeps
`allowed_for_live=false`, `approval_gate_issued=false`,
`approval_id_generated=false`, `approval_command_generated=false`,
`approval_command_copyable=false`, `post_executed=false`, and
`live_order_once_called=false`.

A ready Step 5V review is review evidence only. It is not permission to
implement or issue a real approval gate, generate a real approval id, generate a
real approval command, call APIs, run final dynamic preflight, or execute live
POST. Future execution work still requires a separate explicit user request and
a separate safety-gated step. See
[STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md](STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md).
