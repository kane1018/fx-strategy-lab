# Step 5S Pre-approval Fresh Preflight

## Step 5T Update

Step 5T adds a dry-run real approval gate generation package on top of this
decision. It keeps `allowed_for_live=false`, defers real approval id and real
approval command generation to a future separate step, does not issue an
approval gate, does not create copyable approval text, and does not call APIs,
`live_order_once`, ledgers, or POST. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5S adds a dry-run pre-approval fresh preflight model. It consumes the Step
5R `LiveOrderRealApprovalGatePlan` and a sanitized
`LiveOrderPreApprovalFreshPreflightSnapshot`, then returns a fail-closed
`LiveOrderPreApprovalFreshPreflightDecision`.

Step 5S is no API, no approval, and no POST. A passed Step 5S decision only
means sanitized pre-approval inputs are ready for a future, separate real
approval gate generation step.

## Scope

Implemented scope:

- sanitized `LiveOrderPreApprovalFreshPreflightSnapshot`
- sanitized `LiveOrderPreApprovalFreshPreflightDecision`
- sanitized `LiveOrderPreApprovalFreshPreflightCheckResult`
- sanitized `LiveOrderPreApprovalFreshPreflightSection`
- fail-closed `evaluate_live_order_pre_approval_fresh_preflight`
- deterministic dry-run decision id generation
- Step 5R plan readiness and safety checks
- account/assets status as sanitized input
- open positions and active orders count as sanitized input
- USD_JPY symbol rule checks as sanitized input
- ticker availability, spread, and ticker age as sanitized input
- market window, maintenance, and important-event checks as sanitized input
- API scope, order permission, and IP/account checks as sanitized input
- previous-result and result-unknown checks as sanitized input
- session and daily size limit checks as sanitized input
- Git, tests, ruff, and secret-scan checks as sanitized input
- raw response saved/displayed safety checks
- outbound body allowlist and signing-body equality checks
- pre-approval fresh preflight age check
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5S does not:

- call read-only API, public API, Private API, or broker
- call `live_order_once`
- execute pre-approval fresh preflight against live services
- issue a real approval gate
- generate a real `approval_id`
- generate a real approval command
- create copyable approval text
- copy approval text to a clipboard
- write approval text to a file
- read, write, reset, or delete ledgers
- execute HTTP POST
- place, add, change, cancel, or close orders
- display or save credentials, headers, signatures, raw requests, raw responses, or real IDs

## Input: LiveOrderRealApprovalGatePlan

The Step 5R plan must be ready and must still carry the dry-run safety defaults:

```text
plan_status: READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW
plan_ready: true
allowed_for_live: false
dry_run_only: true
fresh_preflight_before_gate_required: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_copyable: false
approval_id_generation_after_fresh_preflight_required: true
approval_command_generation_after_fresh_preflight_required: true
```

Blocked or unsafe plans fail closed. Existing Step 5R `blocked_reasons` are
preserved as sanitized reasons.

## Input: LiveOrderPreApprovalFreshPreflightSnapshot

The snapshot is sanitized input only. It represents values that a future real
pre-approval fresh preflight would have to confirm, but Step 5S does not fetch
them.

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
api_scope_checked
order_permission_checked
ip_account_check_passed
previous_result_confirmed
result_unknown
session_attempt_count_today
daily_live_size_total
git_clean
tests_passed
ruff_passed
secret_scan_passed
raw_response_saved
raw_response_displayed
outbound_body_allowlist_matched
request_body_equals_signing_body
pre_approval_fresh_preflight_age_seconds
```

The snapshot keeps:

```text
allowed_for_live: false
requires_human_approval: true
explicit_user_confirmation_required: true
approval_gate_required: true
approval_gate_planned: true
approval_gate_issued: false
approval_id_generation_planned: true
approval_id_generated: false
approval_command_generation_planned: true
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
fresh_preflight_before_gate_required: true
post_approval_final_dynamic_preflight_required: true
dry_run_only: true
```

## Output: LiveOrderPreApprovalFreshPreflightDecision

The decision contains only sanitized dry-run fields:

```text
decision_id
snapshot_id
plan_id
checkpoint_id
chain_id
symbol
side
size
execution_type
preflight_status
preflight_passed
eligible_for_future_real_approval_gate_generation
allowed_for_live
requires_human_approval
approval_gate_required
approval_gate_issued
approval_id_generated
approval_command_generated
approval_command_copyable
check_results
blocked_reasons
recommended_next_step
sections
```

All decisions keep:

```text
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_copyable: false
dry_run_only: true
```

## Pass Meaning

Pass means:

```text
preflight_status: READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
preflight_passed: true
eligible_for_future_real_approval_gate_generation: true
allowed_for_live: false
recommended_next_step: prepare_future_real_approval_gate_generation_separate_step_no_post
```

This only means sanitized dry-run pre-approval inputs are ready for a future
separate approval gate generation step. It does not issue an approval gate, does
not generate a real `approval_id`, does not generate approval command text, and
does not authorize live POST.

## Blocked Meaning

Blocked means:

```text
preflight_status: BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT
preflight_passed: false
eligible_for_future_real_approval_gate_generation: false
allowed_for_live: false
```

If the Step 5R plan is blocked, the recommended next step is:

```text
fix_real_approval_gate_plan_blockers_no_post
```

If snapshot inputs are blocked, the recommended next step is:

```text
fix_pre_approval_fresh_preflight_snapshot_no_post
```

## Check Results

`LiveOrderPreApprovalFreshPreflightCheckResult` records sanitized check
outcomes:

```text
name
passed
reason
sanitized_value
expected
```

The checks cover plan readiness, allowed-for-live false, approval artifacts not
generated, account/assets success, open positions zero, active orders zero,
instrument rules, ticker availability, spread threshold, ticker freshness,
market/maintenance/event, API scope/order permission/IP account, previous
result, result unknown false, session/daily limits, Git/tests/ruff/secret scan,
raw response flags, outbound body allowlist, request/signing body equality, and
pre-approval freshness.

## Do-not-cross Boundaries

- Step 5S is no POST.
- Step 5S is no API.
- Step 5S is no ledger read or write.
- Step 5S is not an approval gate.
- Step 5S does not generate approval text.
- Step 5S keeps `allowed_for_live=false`.
- Step 5S does not connect to `live_order_once`.
- Step 5S does not lead directly from plan to POST.

## Relationship to Future Approval Gate

A future real approval gate step must be a separate explicit task. That future
task may use a Step 5S pass as dry-run evidence, but it must still generate the
real approval gate and command separately, validate exact user approval, run
post-approval final dynamic preflight, and remain bounded by one-shot execution
rules.

## Tests

Tests cover:

- ready Step 5R plan plus safe snapshot to ready Step 5S decision
- fixed `allowed_for_live=false`
- missing or blocked Step 5R plan
- plan unsafe flags
- approval artifacts already generated
- unsupported symbol / side / size / execution type
- account/assets, positions, active orders, and instrument rules
- ticker availability, spread, ticker age, and pre-approval age
- market, maintenance, event, API scope, order permission, and IP/account checks
- previous result, result unknown, session limit, and daily size limit
- Git, tests, ruff, secret scan, raw response flags, body allowlist, and signing-body equality
- Markdown dry-run / no-approval / no-live-post warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5S is complete when the model, tests, docs, and no-order guard pass. A
ready decision is still dry-run pre-approval evidence only. It is not approval
gate permission, approval command permission, final dynamic preflight
permission, live POST permission, `live_order_once` permission, or post
reconciliation permission.

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
