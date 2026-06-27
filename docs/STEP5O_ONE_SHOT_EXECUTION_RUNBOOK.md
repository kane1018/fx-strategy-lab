# Step 5O One-shot Execution Runbook

## Step 5T Update

Step 5T keeps one-shot execution as a future separate step. Its generation
package only records approval gate generation prerequisites and stop
conditions, while `allowed_for_live=false`, `approval_gate_issued=false`, and
POST execution remain fixed to safe values. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5O adds a dry-run one-shot execution runbook model after the Step 5N
one-shot live boundary decision.

This step is no API and no POST. It does not call read-only API, does not call
Private API, does not call broker code, does not call `live_order_once`, does not
issue a real approval gate, and does not authorize live execution.

## Scope

Implemented scope:

- sanitized `LiveOrderOneShotExecutionRunbook`
- sanitized `LiveOrderOneShotExecutionRunbookPhase`
- sanitized `LiveOrderOneShotExecutionRunbookStep`
- sanitized `LiveOrderOneShotExecutionRunbookCheckResult`
- fail-closed `build_live_order_one_shot_execution_runbook`
- deterministic dry-run runbook id generation
- required future phases for approval, preflight, single attempt, reconciliation,
  and final report
- go / no-go / stop condition definitions
- one-shot attempt boundary: `post_attempt_limit=1`
- no retry / no loop / no add / no change / no cancel / no close checks
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5O does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- call read-only API, Private API, public API, or broker code
- call `live_order_once`
- issue a real approval gate
- generate a real approval id
- generate or display a real approval command
- copy approval text to clipboard
- write approval text to a file
- execute final dynamic preflight
- execute post reconciliation
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderOneShotBoundaryDecision

The input must already be a Step 5N dry-run boundary decision:

```text
boundary_status: READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
boundary_passed: true
eligible_for_future_one_shot_live_review: true
allowed_for_live: false
dry_run_only: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
post_attempt_limit: 1
post_executed: false
live_order_once_called: false
private_api_called: false
broker_called: false
read_only_api_called: false
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
```

Blocked or unsafe Step 5N decisions fail closed. Existing Step 5N blocked
reasons are preserved in the Step 5O runbook.

## Output: LiveOrderOneShotExecutionRunbook

The runbook contains only sanitized dry-run fields:

```text
runbook_id
boundary_id
preflight_decision_id
snapshot_id
simulation_id
preview_id
design_id
handoff_id
operator_review_id
bundle_id
review_id
candidate_id
risk_decision_id
trace_id
session_policy_decision_id
source_signal_id
source_type
strategy_name
symbol
side
size
execution_type
runbook_status
runbook_ready
eligible_for_future_execution_planning
allowed_for_live
requires_human_approval
approval_gate_required
approval_gate_issued
approval_id_generated
approval_command_generated
approval_command_template_only
approval_command_copyable
final_dynamic_preflight_required
dry_run_only
post_attempt_limit
post_executed
live_order_once_called
private_api_called
broker_called
read_only_api_called
retry_allowed
loop_allowed
add_order_allowed
change_order_allowed
cancel_order_allowed
close_order_allowed
post_reconciliation_required
phases
go_conditions
no_go_conditions
stop_conditions
check_results
blocked_reasons
recommended_next_step
```

All runbooks keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
final_dynamic_preflight_required: true
dry_run_only: true
post_attempt_limit: 1
post_executed: false
live_order_once_called: false
private_api_called: false
broker_called: false
read_only_api_called: false
retry_allowed: false
loop_allowed: false
add_order_allowed: false
change_order_allowed: false
cancel_order_allowed: false
close_order_allowed: false
post_reconciliation_required: true
```

## Ready Runbook Meaning

Ready means:

```text
runbook_status: READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW
runbook_ready: true
eligible_for_future_execution_planning: true
allowed_for_live: false
recommended_next_step: review_runbook_then_prepare_future_real_approval_gate_separate_step_no_post
```

This only means the dry-run execution procedure is internally consistent. It is
not approval gate permission, not final dynamic preflight permission, and not
live POST permission.

## Blocked Runbook Meaning

Blocked means:

```text
runbook_status: BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK
runbook_ready: false
eligible_for_future_execution_planning: false
allowed_for_live: false
```

Blocked Step 5N boundary reasons are preserved. Runbook-specific reasons are
added when one-shot constraints, phases, or go/no-go/stop conditions are unsafe.

## Execution Phases

Required dry-run phases:

1. `real_approval_gate_separate_step`
2. `fresh_final_dynamic_preflight_separate_step`
3. `one_shot_http_post_separate_step`
4. `post_reconciliation_separate_step`
5. `final_report_and_stop`

These phases are instructions for future separate tasks only. Step 5O does not
execute any of them.

## Go Conditions

The runbook requires go conditions for:

- one-shot boundary passed
- future separate real approval gate
- future separate fresh final dynamic preflight
- `post_attempt_limit=1`
- no retry / loop / add / change / cancel / close
- outbound body allowlist matched
- request body equals signing body
- post reconciliation required
- raw response display and storage forbidden

## No-go Conditions

The runbook blocks on:

- any blocked reason
- unknown status
- stale preflight
- result unknown
- existing position or active order
- spread too wide
- maintenance active
- important event window not confirmed
- Git / tests / ruff / secret scan not clean
- request body and signing body mismatch
- raw response display or storage needed

## Stop Conditions

The runbook stops on:

- same error repeated without new evidence
- stale final dynamic preflight
- expired approval
- result unknown
- unknown post result
- impossible reconciliation
- unexpected API response shape
- secret, raw response, or ID exposure risk
- need for retry / loop / add / change / cancel / close
- need to exceed one POST attempt

## One-shot Constraints

Step 5O preserves:

```text
post_attempt_limit: 1
post_executed: false
retry_allowed: false
loop_allowed: false
add_order_allowed: false
change_order_allowed: false
cancel_order_allowed: false
close_order_allowed: false
```

Ready runbooks still do not execute or authorize the one-shot attempt.

## Post Reconciliation Plan

The post reconciliation phase is a future plan only. Step 5O does not execute it.

Future reconciliation must be sanitized, must avoid raw response display/storage,
and must not display order, execution, position, or client order identifiers.

## Markdown Rendering

`render_live_order_one_shot_execution_runbook_markdown()` renders only sanitized
fields. It includes these warnings:

```text
This one-shot execution runbook is dry-run only.
This runbook does not call read-only API.
This runbook does not call Private API.
This runbook does not call live_order_once.
This runbook does not execute HTTP POST.
This runbook does not issue a real approval gate.
This runbook does not generate a real approval command.
This runbook does not authorize live POST.
allowed_for_live=false.
```

## Do-not-cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Operation bundle does not directly POST.
- Operator review does not directly POST.
- Handoff, design, preview, validation simulation, preflight model, boundary, and
  runbook do not directly POST.
- Runbook does not issue approval gates.
- Runbook does not read account, order, position, ledger, public API, or Private
  API state.
- Any future real approval gate, fresh dynamic preflight, one-shot POST, post
  reconciliation, and final report must be separate explicit steps with fresh
  user authorization.

## Relationship to Future Real Approval Gate / Fresh Preflight / One-shot POST

Step 5O packages the future sequence:

```text
real approval gate -> fresh final dynamic preflight -> one-shot HTTP POST ->
post reconciliation -> final report and stop
```

The package is dry-run only. It cannot be used as a live runner, approval gate,
approval command, final dynamic preflight, or POST executor.

## Tests

Added tests cover:

- passed Step 5N boundary + safe runbook constraints
- fixed `allowed_for_live=false`
- no live POST permission
- blocked Step 5N boundary decisions
- unsafe boundary flags
- unsupported symbol, side, size, and execution type
- invalid attempt limit and already-executed flags
- no runner, Private API, broker, or read-only API call flags
- no retry, loop, add, change, cancel, or close flags
- post reconciliation requirement
- required phases
- missing phase and forbidden phase action blockers
- missing go / no-go / stop blockers
- go / no-go / stop required constraints
- Markdown warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5O is complete as a dry-run one-shot execution runbook model. Next work, if
requested, should remain a separate task. A ready runbook is not live POST
permission and not approval gate permission. Any future execution must still
perform a real approval gate, fresh final dynamic preflight, one-shot execution,
post reconciliation, and final report as explicit separate steps.

Step 5P now adds the E2E dry-run chain review model. Execution runbooks remain
sanitized dry-run evidence only; Step 5P checks the Step 5B through Step 5O
chain for stage/status, ID, order-shape, source signal, safety flag, and
one-shot constraint consistency. It keeps `allowed_for_live=false`, does not
issue approval, does not generate approval commands, does not call APIs or
`live_order_once`, and does not execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. Execution runbooks
remain review-only; Step 5R translates readiness evidence into a future approval
gate plan without executing any runbook phase, calling APIs, calling
`live_order_once`, or issuing approval artifacts.

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

## Step 5W Follow-up

Step 5W adds a disabled real approval gate scaffold dry-run model. It consumes
the Step 5V `LiveOrderRealApprovalImplementationReadinessReview` and creates
`LiveOrderRealApprovalDisabledScaffold` as sanitized review evidence for a
future separate enablement planning step.

Ready scaffolds use
`READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW`,
`scaffold_ready=true`, and `eligible_for_future_enablement_planning=true`, but
this is not live execution permission and not approval gate enablement. Step 5W
keeps `allowed_for_live=false`, `approval_gate_enabled=false`,
`approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, `approval_command_copyable=false`,
`approval_command_executable=false`, `usable_approval_artifacts_generated=false`,
`real_approval_artifacts_available=false`, `post_attempt_limit=1`,
`post_executed=false`, and `live_order_once_called=false`.

Step 5W records future enablement requirements, disabled reasons, and check
results for disabled gate state, deferred approval id/command generation, TTL
300, exact match, same session, ACK tokens, display forbidden fields, no
API/broker calls, no POST, and one-shot constraints. It does not call read-only
API, public API, Private API, broker, `live_order_once`, ledgers, clipboard, or
POST, and it does not generate usable approval artifacts. Details:
[STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md](STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md).

## Step 5X Handoff Update

Step 5X adds `LiveOrderRealApprovalEnablementCriteria`, consuming the Step 5W
`LiveOrderRealApprovalDisabledScaffold` to define sanitized future enablement
requirements, go/no-go conditions, kill switch conditions, and approval artifact
generation preconditions. It keeps `approval_gate_enabled=false`,
`allowed_for_live=false`, `approval_gate_issued=false`,
`approval_id_generated=false`, `approval_command_generated=false`,
`approval_command_copyable=false`, `approval_command_executable=false`,
`post_attempt_limit=1`, `post_executed=false`, and no API/broker/live_order_once
calls. Step 5X is no API / no POST and does not enable a real approval gate or
generate real approval artifacts. Details:
[STEP5X_REAL_APPROVAL_ENABLEMENT_CRITERIA.md](STEP5X_REAL_APPROVAL_ENABLEMENT_CRITERIA.md).

## Step 5Y-Z Follow-up

Step 5Y-Z adds a real approval enablement dry-run plan with a sanitized
market-hours/weekend blocker and final pre-enable go/no-go report. It consumes
Step 5X criteria plus a sanitized snapshot only. Ready output remains planning
evidence for a future explicit Step 6A request and keeps `approval_gate_enabled=false`,
`allowed_for_live=false`, no real approval artifacts, no API calls, no ledger access,
no clipboard use, and no POST. Details:
[STEP5Y_Z_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN.md](STEP5Y_Z_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN.md).

## Step 6A Follow-up

Step 6A adds a real approval gate enablement state model after the Step 5Y-Z
pre-enable plan. Safe output may set `approval_gate_enabled=true` only as a
sanitized model state for future Step 6B artifact-generation review. Step 6A
keeps `allowed_for_live=false`, does not issue a real approval gate, does not
generate approval_id or approval command artifacts, does not create copyable
approval text, does not call any API or ledger, and does not execute POST.
Details:
[STEP6A_REAL_APPROVAL_GATE_ENABLEMENT_STATE.md](STEP6A_REAL_APPROVAL_GATE_ENABLEMENT_STATE.md).
