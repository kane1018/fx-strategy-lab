# Step 5M Final Dynamic Preflight

## Summary

Step 5M adds a dry-run final dynamic preflight model after the Step 5L approval
validation simulator.

This step is no POST. It does not execute final dynamic preflight, does not call
read-only API, does not call Private API, does not read a ledger, does not issue
an approval gate, and does not authorize live execution.

## Scope

Implemented scope:

- sanitized `LiveOrderFinalDynamicPreflightSnapshot`
- sanitized `LiveOrderFinalDynamicPreflightDecision`
- sanitized `LiveOrderFinalDynamicPreflightCheckResult`
- sanitized `LiveOrderFinalDynamicPreflightSection`
- fail-closed `evaluate_live_order_final_dynamic_preflight`
- deterministic dry-run decision id generation
- account/assets status check as sanitized input
- open positions and active orders count checks as sanitized input
- USD_JPY symbol rule checks as sanitized input
- ticker availability, spread, and ticker age checks as sanitized input
- market window, maintenance, and important-event checks as sanitized input
- ledger-unused, previous-result, and result-unknown checks as sanitized input
- Git, tests, ruff, and secret-scan checks as sanitized input
- raw response saved/displayed safety checks
- outbound body allowlist and signing-body equality checks
- final preflight age check
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5M does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- issue an approval gate
- generate an approval id
- generate an approval command
- copy approval text to a clipboard
- write approval text to a file
- execute final dynamic preflight
- call read-only API
- call Private API
- call public API
- call broker code
- call `live_order_once`
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderApprovalValidationSimulation

The approval validation simulation must already be a Step 5L fake validation
simulation:

```text
simulation_status: SIMULATED_APPROVAL_VALIDATION_PASSED
allowed_for_live: false
dry_run_only: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
final_dynamic_preflight_required: true
```

Blocked simulations, live-allowed simulations, non-dry-run simulations,
already-issued gates, generated ids or commands, and missing final dynamic
preflight requirement fail closed.

## Input: LiveOrderFinalDynamicPreflightSnapshot

The snapshot is sanitized input only. It represents values that a future real
final dynamic preflight would have to confirm, but Step 5M does not fetch them.

Required groups:

```text
account_assets_status
open_positions_count
active_orders_count
min_open_order_size
size_step
ticker_available
spread_jpy
ticker_age_seconds
market_window_allowed
maintenance_active
important_event_window_ok
ledger_unused
session_attempt_count_today
daily_live_size_total
previous_result_confirmed
result_unknown
git_clean
tests_passed
ruff_passed
secret_scan_passed
raw_response_saved
raw_response_displayed
outbound_body_allowlist_matched
request_body_equals_signing_body
final_preflight_age_seconds
```

The snapshot keeps:

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
```

## Output: LiveOrderFinalDynamicPreflightDecision

The decision contains only sanitized dry-run fields:

```text
decision_id
snapshot_id
simulation_id
symbol
side
size
execution_type
preflight_status
preflight_passed
eligible_for_future_one_shot_review
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
check_results
blocked_reasons
recommended_next_step
sections
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
```

## Pass Meaning

Pass means:

```text
preflight_status: READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
preflight_passed: true
eligible_for_future_one_shot_review: true
allowed_for_live: false
recommended_next_step: prepare_future_one_shot_boundary_design_no_post
```

This only means sanitized dry-run final dynamic preflight inputs are ready for a
future one-shot boundary review. It does not execute final dynamic preflight,
does not authorize approval gate issuance, and does not authorize live POST.

## Blocked Meaning

Blocked means:

```text
preflight_status: BLOCKED_FINAL_DYNAMIC_PREFLIGHT
preflight_passed: false
eligible_for_future_one_shot_review: false
allowed_for_live: false
recommended_next_step: fix_final_dynamic_preflight_snapshot_no_post
```

If Step 5L approval validation is blocked, the recommended next step is:

```text
fix_approval_validation_blockers_no_post
```

Blocked reasons are preserved for human inspection. A blocked decision means do
not proceed.

## Check Results

`LiveOrderFinalDynamicPreflightCheckResult` records sanitized check outcomes:

```text
name
passed
reason
sanitized_value
expected
```

It contains no credentials, headers, signatures, raw requests, raw responses, or
real order identifiers.

## Fail-closed Rules

Step 5M blocks on:

- blocked or unsafe Step 5L simulation
- `allowed_for_live=true`
- non-dry-run flags
- approval gate, id, or command already generated
- missing final dynamic preflight requirement
- unsupported symbol, side, size, or execution type
- account/assets not success
- open positions or active orders
- invalid USD_JPY size rules
- missing ticker, missing spread, wide spread, missing/stale ticker age
- market window not allowed
- active maintenance
- important event window not confirmed
- ledger not unused
- session attempt limit reached
- daily size limit exceeded
- previous result not confirmed
- result unknown
- Git/tests/ruff/secret scan not clean
- raw response saved or displayed
- outbound body allowlist mismatch
- signing body mismatch
- missing/stale final preflight age

Unknown, missing, or unsafe dynamic inputs fail closed.

## Markdown Rendering

Markdown rendering includes these warnings:

```text
This final dynamic preflight model is dry-run only.
This model does not call read-only API.
This model does not call Private API.
This model does not execute final dynamic preflight.
This model does not authorize live POST.
allowed_for_live=false.
```

The rendered report includes only sanitized ids, order summary, check results,
blocked reasons, and recommended next step.

## Do-not-cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Operation bundle does not directly POST.
- Operator review procedure does not directly POST.
- Approval handoff package does not directly POST.
- Approval gate design does not directly POST.
- Approval gate preview does not directly POST.
- Approval validation simulation does not directly POST.
- Final dynamic preflight model does not directly POST.
- Final dynamic preflight model does not call read-only API.
- Final dynamic preflight model does not call Private API.
- Final dynamic preflight model does not read or write a ledger.
- Any future real final dynamic preflight and one-shot execution must be a
  separate explicit task.

## Relationship to Future One-shot Boundary

Step 5M can feed a future one-shot boundary design. It cannot authorize that
boundary by itself. Any later real final dynamic preflight, approval gate, or
one-shot live POST must be a separate task with fresh state checks, one-shot
ledger protection, exact approval text, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- safe Step 5L simulation plus safe snapshot pass as review-eligible only
- fixed `allowed_for_live=false`
- fixed human approval and approval gate requirements
- fixed `approval_gate_issued=false`
- fixed `approval_id_generated=false`
- fixed `approval_command_generated=false`
- fixed final dynamic preflight requirement
- blocked Step 5L simulation and preserved simulation reasons
- unsafe simulation flags
- unsafe snapshot flags
- unsupported symbol, side, size, and execution type
- account/assets failure
- open positions and active orders
- invalid min order size and size step
- ticker unavailable, missing spread, wide spread, missing/stale ticker age
- market window, maintenance, and event blockers
- ledger, session, daily size, previous result, and result unknown blockers
- Git/tests/ruff/secret scan blockers
- raw response saved/displayed blockers
- outbound body allowlist and signing-body mismatch blockers
- missing/stale final preflight age blockers
- check result coverage
- multiple blocked reasons
- Markdown dry-run / no API / no final preflight / no live POST warnings
- absence of forbidden actual values
- no dependency on HTTP clients, Private API, broker code, live runner code, or
  clipboard commands

## Handoff Summary

Step 5M adds a final dynamic preflight dry-run model after Step 5L. A passed
decision is dry-run evidence only and preserves `allowed_for_live=false`. It
does not execute final dynamic preflight, does not call APIs, does not issue an
approval gate, does not generate approval text, does not read or write ledger
state, and does not authorize live POST.

The next step may design the future one-shot boundary, but it must remain a
separate task with no live execution unless explicitly authorized in a later
real approval flow.

Step 5N now adds that one-shot boundary as a dry-run model only. A passed Step
5N boundary means the sanitized one-shot constraints are internally consistent:
`post_attempt_limit=1`, POST not executed, no runner/API/broker/read-only calls,
no retry/loop/order mutation flags, body allowlist matched, request body equals
signing body, and post reconciliation is required. It still keeps
`allowed_for_live=false`, does not issue approval, and does not authorize live
POST.
