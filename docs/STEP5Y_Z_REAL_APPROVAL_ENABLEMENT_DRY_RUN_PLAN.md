# Step 5Y-Z Real Approval Enablement Dry-run Plan

## Summary

Step 5Y-Z adds a dry-run-only pre-enable planning layer after Step 5X real
approval enablement criteria. It combines the Step 5X criteria with a sanitized
market-hours/weekend guard snapshot and produces a final pre-enable go/no-go
report for possible future Step 6A planning.

This step does not enable a real approval gate. It keeps
`approval_gate_enabled=false` and `allowed_for_live=false`.

## Scope

Step 5Y-Z records:

- whether Step 5X enablement criteria are ready
- whether a sanitized market-hours snapshot is acceptable
- whether weekend, maintenance, unknown, or stale market-hours inputs block
  future planning
- go/no-go/stop conditions for a future explicit Step 6A task
- handoff conditions and blockers for Step 6A
- check results proving no API, no POST, no real approval artifact generation

## What this step does not do

Step 5Y-Z does not:

- call read-only API
- call public API
- call Private API
- call broker code
- call `live_order_once`
- read or write ledger files
- issue a real approval gate
- generate a real approval_id
- generate a real approval command
- create copyable approval text
- write approval text to a file
- use clipboard or `pbcopy`
- execute HTTP POST
- place, close, cancel, or change an order

## Input: LiveOrderRealApprovalEnablementCriteria

The plan consumes Step 5X `LiveOrderRealApprovalEnablementCriteria`.

Ready criteria can proceed to the Step 5Y-Z dry-run plan only if they still
keep:

- `allowed_for_live=false`
- `approval_gate_enabled=false`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `approval_command_executable=false`
- `usable_approval_artifacts_generated=false`
- `real_approval_artifacts_available=false`
- `dry_run_only=true`
- `post_attempt_limit=1`
- `post_executed=false`
- no API, broker, or `live_order_once` calls

Blocked Step 5X criteria are preserved as blocked Step 5Y-Z plan evidence.

## Input: Market-hours Guard Snapshot

`LiveOrderRealApprovalMarketHoursGuardSnapshot` is sanitized input only. It does
not fetch current market state and does not call any API.

Required safe values:

- `timezone=Asia/Tokyo`
- `market_hours_source=sanitized_snapshot_only`
- `market_session_state=OPEN`
- `is_weekend_jst=false`
- `market_window_allowed=true`
- `broker_maintenance_active=false`
- `holiday_or_special_close=false`
- `holiday_or_special_close_unknown=false`
- `market_hours_unknown=false`
- snapshot age within the configured max age

## Output: Enablement Dry-run Plan

`LiveOrderRealApprovalEnablementDryRunPlan` records the pre-enable plan and
final go/no-go report. A ready plan means only:

```text
READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW
GO_FOR_FUTURE_STEP6A_PLANNING_ONLY
```

It does not authorize live execution and does not authorize approval gate
issuance.

## Market-hours / Weekend Blocker

The plan blocks when any market-hours input is unsafe or unknown:

- `weekend_jst`
- `market_session_not_open`
- `market_window_not_allowed`
- `broker_maintenance_active`
- `holiday_or_special_close`
- `holiday_or_special_close_unknown`
- `market_hours_unknown`
- `market_hours_snapshot_stale`
- `invalid_market_hours_source`
- `invalid_timezone`

Market-hours blocked output uses:

```text
BLOCKED_PRE_ENABLE_MARKET_HOURS
NO_GO_MARKET_HOURS
```

## Final Pre-enable Go / No-Go

The ready go/no-go report is only planning evidence for a future separate
Step 6A request. It records:

- go conditions
- no-go conditions
- stop conditions
- future Step 6A handoff conditions
- future Step 6A blockers

Step 6A must still be explicitly requested. Step 5Y-Z does not start Step 6A.

## Safety Defaults

Step 5Y-Z hard-codes the safety defaults:

- `allowed_for_live=false`
- `approval_gate_enabled=false`
- `approval_gate_enablement_deferred_to_future_step=true`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `approval_command_executable=false`
- `usable_approval_artifacts_generated=false`
- `real_approval_artifacts_available=false`
- `dry_run_only=true`
- `requires_human_approval=true`
- `explicit_user_confirmation_required=true`
- `fresh_preflight_before_enablement_required=true`
- `implementation_readiness_review_required=true`
- `market_hours_guard_required=true`
- `weekend_blocker_required=true`
- `post_approval_final_dynamic_preflight_required=true`
- `one_shot_post_separate_step_required=true`
- `post_reconciliation_separate_step_required=true`
- `ttl_seconds=300`
- `exact_match_required=true`
- `same_session_required=true`
- `post_attempt_limit=1`
- retry, loop, add, change, cancel, and close are all false

## Markdown Rendering

The renderer includes these required warnings:

```text
This Step 5Y-Z enablement dry-run plan is dry-run only.
This plan does not enable a real approval gate.
This plan keeps approval_gate_enabled=false.
This plan keeps allowed_for_live=false.
This plan uses sanitized market-hours snapshot only.
This plan does not call read-only API.
This plan does not call public API.
This plan does not call Private API.
This plan does not call live_order_once.
This plan does not execute HTTP POST.
This plan does not issue a real approval gate.
This plan does not generate a real approval_id.
This plan does not generate a real approval command.
This plan does not provide copyable approval text.
This plan does not authorize live POST.
```

## Do-Not-Cross Boundaries

Strategy signal, candidate, risk decision, trace, review report, session policy,
bundle, operator review, handoff package, fake approval artifacts, preflight
dry-runs, one-shot boundary, execution runbook, E2E chain, real approval
readiness, planning package, pre-approval fresh preflight, generation package,
pre-implementation audit, readiness review, disabled scaffold, enablement
criteria, and this Step 5Y-Z plan must not directly connect to live POST.

## Relationship to Future Step 6A

Step 5Y-Z can only say that future Step 6A planning may be considered. It is not
permission to enable a real approval gate, issue a real approval gate, generate
real approval artifacts, run final dynamic preflight, or execute a live order.

Future Step 6A, if explicitly requested, must rerun fresh preflight and fresh
market-hours/weekend checks and must keep its own safety boundary.

## Tests

Tests cover:

- ready Step 5X criteria plus safe sanitized market-hours snapshot
- safety defaults and disabled approval artifacts
- weekend, market closed, maintenance, holiday, unknown, stale, invalid source,
  and invalid timezone blockers
- blocked Step 5X criteria preservation
- approval artifact, API, live runner, and one-shot blockers
- required go/no-go/stop/handoff/blocker condition lists
- check result coverage
- markdown warnings
- serialization safety
- forbidden builder kwargs
- no-order/no-API/no-clipboard guard coverage

## Handoff Summary

Step 5Y-Z is complete when the dry-run plan model, tests, no-order guard, and
docs pass. The next step, if explicitly requested, is future Step 6A planning.
No approval gate, approval_id, approval command, copyable command, API call,
ledger access, clipboard operation, or live POST is authorized by this step.
