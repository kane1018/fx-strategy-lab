# Step 5N One-shot Live Boundary

## Summary

Step 5N adds a dry-run one-shot live boundary model after the Step 5M final
dynamic preflight decision.

This step is no POST. It does not call read-only API, does not call Private API,
does not call `live_order_once`, does not issue an approval gate, and does not
authorize live execution.

## Scope

Implemented scope:

- sanitized `LiveOrderOneShotBoundaryDecision`
- sanitized `LiveOrderOneShotBoundaryCheckResult`
- sanitized `LiveOrderPostReconciliationPlan`
- fail-closed `build_live_order_one_shot_boundary`
- deterministic dry-run boundary id generation
- one-shot attempt boundary: `post_attempt_limit=1`
- no retry / no loop / no add / no change / no cancel / no close checks
- sanitized body field allowlist and forbidden field names
- request-body/signing-body equality boundary by sanitized labels only
- post-POST reconciliation plan as design only
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5N does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- call read-only API, Private API, public API, or broker code
- call `live_order_once`
- issue an approval gate
- generate an approval id
- generate or display an approval command
- copy approval text to clipboard
- write approval text to a file
- execute final dynamic preflight
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderFinalDynamicPreflightDecision

The input must already be a Step 5M dry-run decision:

```text
preflight_status: READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
preflight_passed: true
eligible_for_future_one_shot_review: true
allowed_for_live: false
dry_run_only: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
final_dynamic_preflight_required: true
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
```

Blocked or unsafe Step 5M decisions fail closed. Existing Step 5M blocked
reasons are preserved in the Step 5N boundary decision.

## Output: LiveOrderOneShotBoundaryDecision

The boundary decision contains only sanitized dry-run fields:

```text
boundary_id
preflight_decision_id
snapshot_id
simulation_id
candidate_id
risk_decision_id
trace_id
session_policy_decision_id
symbol
side
size
execution_type
boundary_status
boundary_passed
eligible_for_future_one_shot_live_review
allowed_for_live
requires_human_approval
approval_gate_required
approval_gate_issued
approval_id_generated
approval_command_generated
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
body_fields_allowlist
body_fields_forbidden
post_reconciliation_plan
check_results
blocked_reasons
recommended_next_step
```

All decisions keep:

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
```

## One-shot Boundary Rules

Step 5N requires:

```text
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
outbound_body_allowlist_matched: true
request_body_equals_signing_body: true
post_reconciliation_required: true
```

Any mismatch blocks the boundary. A passed boundary still does not authorize
live POST.

## Body Boundary

Step 5N does not generate a real request body. It records sanitized field names
and labels only.

Allowed field names:

```text
symbol
side
size
executionType
```

Forbidden field names include:

```text
apiKey
secret
signature
headers
orderId
executionId
positionId
clientOrderId
rawRequest
rawResponse
retryCount
loopCount
closeOrder
cancelOrder
changeOrder
```

The request and signing body fingerprints are labels only:

```text
sanitized_request_body_fields_only_no_values
sanitized_signing_body_fields_only_no_values
```

## Post Reconciliation Plan

`LiveOrderPostReconciliationPlan` is a future-execution plan only. Step 5N does
not execute it.

The plan requires:

```text
read_only_after_post_required: true
account_assets_check_required: true
open_positions_check_required: true
active_orders_check_required: true
result_unknown_check_required: true
raw_response_storage_forbidden: true
raw_response_display_forbidden: true
order_id_display_forbidden: true
execution_id_display_forbidden: true
position_id_display_forbidden: true
```

## Pass Meaning

Pass means:

```text
boundary_status: READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
boundary_passed: true
eligible_for_future_one_shot_live_review: true
allowed_for_live: false
recommended_next_step: prepare_future_real_approval_gate_or_one_shot_execution_plan_separate_step_no_post
```

This only means the sanitized future one-shot boundary is internally consistent.
It is not approval gate permission and not live POST permission.

## Blocked Meaning

Blocked means:

```text
boundary_status: BLOCKED_ONE_SHOT_LIVE_BOUNDARY
boundary_passed: false
eligible_for_future_one_shot_live_review: false
allowed_for_live: false
```

Blocked Step 5M preflight reasons are preserved. Boundary-specific reasons are
added when one-shot, body, or reconciliation constraints are unsafe.

## Markdown Rendering

`render_live_order_one_shot_boundary_markdown()` renders only sanitized fields.
It includes these warnings:

```text
This one-shot live boundary model is dry-run only.
This model does not call read-only API.
This model does not call Private API.
This model does not call live_order_once.
This model does not execute HTTP POST.
This model does not authorize live POST.
allowed_for_live=false.
```

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Operation bundle does not directly POST.
- Approval simulator / preview / handoff / final dynamic preflight do not POST.
- One-shot boundary does not directly POST.
- One-shot boundary does not issue approval gates.
- One-shot boundary does not read account, order, position, ledger, or API state.
- Any future real approval gate and one-shot execution must be separate explicit
  steps with fresh dynamic preflight and exact user approval.

## Relationship to Future Execution

Step 5N is the last dry-run boundary layer before designing a separate real
approval/execution task. It can describe the constraints that a future real task
must enforce, but it cannot perform that task.

## Tests

Added tests cover:

- ready Step 5M preflight decision + safe boundary inputs
- fixed `allowed_for_live=false`
- no POST permission
- blocked Step 5M preflight decisions
- unsafe preflight flags
- unsupported symbol, side, size, and execution type
- invalid attempt limit and already-executed flags
- no runner, Private API, broker, or read-only API call flags
- no retry, loop, add, change, cancel, or close flags
- body allowlist and signing-body equality
- post reconciliation requirement
- Markdown warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5N is complete as a dry-run boundary model. Next work, if requested, should
be a separate design or execution-preparation step. It must not reuse Step 5N as
live POST permission, and it must keep approval gate issuance and real execution
behind explicit future user authorization.

Step 5O now adds that execution-preparation layer as a dry-run runbook package.
It defines future real approval gate, fresh final dynamic preflight, one-shot
HTTP POST, post reconciliation, and final report phases, but it does not execute
those phases. A ready Step 5O runbook is not approval gate permission and not
live POST permission; it keeps `allowed_for_live=false`.

Step 5P now adds the E2E dry-run chain review model. One-shot boundary
decisions remain sanitized dry-run evidence only; Step 5P checks them with the
other Step 5B through Step 5O artifacts, keeps `allowed_for_live=false`, and
does not call APIs, issue approval, generate approval commands, call
`live_order_once`, or execute POST.
