# Step 6A Real Approval Gate Enablement State

## Summary

Step 6A adds a dry-run-only state model that can mark the real approval gate as
enabled for future artifact-generation review. This is a sanitized model state
only.

When every Step 6A request acknowledgement, Step 5Y-Z source plan requirement,
and sanitized safety snapshot is safe, the model may return:

```text
REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
approval_gate_enabled=true
allowed_for_live=false
```

This does not issue an approval gate, does not generate an approval ID, does not
generate an approval command, and does not authorize live POST.

## Scope

Step 6A records:

- the Step 5Y-Z dry-run plan used as source evidence
- an explicit Step 6A request acknowledgement snapshot
- a sanitized market-hours and fresh-preflight safety snapshot
- whether a future Step 6B approval artifact generation review may be considered
- blockers that stop the state before any approval artifact can exist
- handoff requirements and blockers for Step 6B
- check results proving no API, no ledger, no approval artifact, and no POST

## What this step does not do

Step 6A does not:

- call read-only API
- call public API
- call Private API
- call broker code
- call `live_order_once`
- read or write ledger files
- issue a real approval gate
- generate a real approval ID
- generate a real approval command
- create copyable approval text
- write approval text to a file
- use clipboard or `pbcopy`
- execute HTTP POST
- place, close, cancel, or change an order

## Input: Step 5Y-Z Enablement Dry-run Plan

The source plan must be `READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW` and
`GO_FOR_FUTURE_STEP6A_PLANNING_ONLY`.

It must still keep:

- `allowed_for_live=false`
- `approval_gate_enabled=false`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `approval_command_executable=false`
- `usable_approval_artifacts_generated=false`
- `real_approval_artifacts_available=false`
- `post_attempt_limit=1`
- `post_executed=false`
- no API, broker, public API, read-only API, or `live_order_once` calls

Blocked Step 5Y-Z plans remain blocked Step 6A source evidence.

## Input: Enablement Request Snapshot

`LiveOrderRealApprovalGateEnablementRequestSnapshot` is sanitized operator
intent only. It must confirm:

- explicit Step 6A user instruction received
- real-money risk understood
- no POST in Step 6A understood
- no approval ID generation in Step 6A understood
- no approval command generation in Step 6A understood
- no copyable approval text in Step 6A understood
- unknown means stop understood
- Step 6B is required for artifact generation
- Step 6C or later is required for API preflight
- Step 6D or later is required for POST
- request scope label is `enable_approval_gate_state_only_no_artifacts_no_api_no_post`

Any missing acknowledgement blocks with `BLOCKED_STEP6A_ENABLEMENT_REQUEST`.

## Input: Sanitized Safety Snapshot

`LiveOrderRealApprovalGateEnablementSafetySnapshot` is input only. It does not
fetch current market state and does not call any API.

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
- market-hours snapshot age within max age
- `fresh_pre_approval_preflight_source=sanitized_snapshot_only`
- `fresh_pre_approval_preflight_status=READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW`
- `fresh_pre_approval_preflight_passed=true`
- `fresh_pre_approval_preflight_unknown=false`
- fresh preflight snapshot age within max age
- `open_positions_count=0`
- `active_orders_count=0`
- `result_unknown=false`
- `raw_response_saved=false`
- `raw_response_displayed=false`
- `secret_scan_passed=true`

Unsafe, stale, missing, or unknown values block with
`BLOCKED_STEP6A_SAFETY_SNAPSHOT`.

## Output: Enablement State

`LiveOrderRealApprovalGateEnablementState` is a dry-run state record. Ready
output means only:

```text
REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
enablement_state_ready=true
eligible_for_future_step6b_approval_artifact_generation=true
approval_gate_enabled=true
approval_gate_enablement_scope=future_approval_artifact_generation_review_only
allowed_for_live=false
```

`approval_gate_enabled=true` is a model output only. It is not a real gate,
approval ID, command, copyable text, file, clipboard value, API call, or live
order permission.

## Blocked States

Step 6A blocks with one of these statuses:

- `BLOCKED_STEP6A_SOURCE_PLAN`
- `BLOCKED_STEP6A_ENABLEMENT_REQUEST`
- `BLOCKED_STEP6A_SAFETY_SNAPSHOT`
- `BLOCKED_STEP6A_UNSAFE_MISMATCH`

All blocked states keep:

- `approval_gate_enabled=false`
- `allowed_for_live=false`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `approval_command_executable=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Future Step 6B Handoff

Step 6B is still a separate explicit task. Step 6A records handoff conditions:

- user explicitly requests Step 6B
- Step 6B remains no API and no POST unless separately scoped
- Step 6B may generate approval artifact only if explicitly requested
- approval ID generation must be exact and same-session scoped
- approval command generation must be exact-match and one-line scoped
- approval command must not be generated in Step 6A
- copyable approval text must not be generated in Step 6A
- post-approval final dynamic preflight still required before any POST
- one-shot POST remains a separate future step

Step 6B blockers include missing explicit Step 6B request, stale or unknown
market/preflight state, any unexpected API/broker/live runner call, any
secret/raw/real-ID exposure risk, and any need for retry, loop, add, change,
cancel, or close.

## Step 6B Follow-up Status

Step 6B has now been implemented as
`LiveOrderRealApprovalArtifact` in
`backend/app/live_verification/live_order_real_approval_artifact_generation.py`.
It may generate internal model artifacts for future Step 6C validation:

- `approval_id_generated=true`
- `approval_command_generated=true`
- `approval_artifact_generated=true`

Those values remain internal Step 6B artifacts only. Step 6B keeps
`allowed_for_live=false`, does not issue a real approval gate, does not render
the full approval command, does not make approval text copyable, does not use
`pbcopy`, does not save approval text, does not call APIs or `live_order_once`,
and does not execute HTTP POST.

Details are in
[STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md](STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md).

## Markdown Rendering

The renderer includes these required warnings:

```text
This Step 6A approval gate enablement state is dry-run only.
This Step 6A state may set approval_gate_enabled=true only as a sanitized model output.
This Step 6A state keeps allowed_for_live=false.
This Step 6A state does not issue a real approval gate.
This Step 6A state does not generate a real approval_id.
This Step 6A state does not generate a real approval command.
This Step 6A state does not provide copyable approval text.
This Step 6A state does not call read-only API.
This Step 6A state does not call public API.
This Step 6A state does not call Private API.
This Step 6A state does not call live_order_once.
This Step 6A state does not execute HTTP POST.
This Step 6A state does not authorize live POST.
```

## Do-Not-Cross Boundaries

Strategy signal, candidate, risk decision, trace, review report, session policy,
bundle, operator review, handoff package, fake approval artifacts, preflight
dry-runs, one-shot boundary, execution runbook, E2E chain, real approval
readiness, planning package, pre-approval fresh preflight, generation package,
pre-implementation audit, readiness review, disabled scaffold, enablement
criteria, Step 5Y-Z enablement dry-run plan, and this Step 6A state must not
directly connect to live POST.

## Relationship to Future Approval Gate

Step 6A can only say that a future Step 6B approval artifact generation review
may be considered. It is not permission to issue a real approval gate, generate
real approval artifacts, run real final dynamic preflight, or execute a live
order.

Future Step 6B must be explicitly requested and must keep its own no-API/no-POST
boundary unless a later task explicitly changes that boundary.

## Tests

Tests cover:

- ready Step 5Y-Z plan plus explicit Step 6A request and safe sanitized snapshot
- request acknowledgement blockers
- market-hours, fresh-preflight, position/order, result_unknown, raw-response,
  and secret-scan blockers
- missing or blocked source plan
- source plan unsafe mismatch blockers
- future Step 6B handoff/blocker list requirements
- check result coverage
- markdown warnings
- serialization safety
- forbidden builder kwargs
- no-order/no-API/no-clipboard guard coverage

## Handoff Summary

Step 6A is complete when the enablement state model, tests, no-order guard, and
docs pass. The next step, if explicitly requested, is Step 6B approval artifact
generation review. Step 6A does not generate approval artifacts, call any API,
read or write ledger files, use clipboard, or execute live POST.

## Step 6C Follow-up Status

Step 6C has now been implemented after Step 6B. It validates the internal
approval artifact exact match, TTL 300, same session, one-line shape, ACK token
completeness, and sanitized safety snapshot. Ready validation may set
`approval_artifact_validated=true`,
`approval_command_exact_match_validated=true`,
`approval_command_ttl_validated=true`,
`approval_command_same_session_validated=true`, and
`eligible_for_step6d_api_preflight_planning=true`, and preserves
`approval_gate_enabled=true` only as Step 6A state-only enablement evidence, but
still keeps `allowed_for_live=false`.

Step 6C does not issue a real approval gate, does not render/copy/persist the
full generated or provided approval command, does not use `pbcopy`, does not
call read-only/public/Private API, broker, `live_order_once`, or ledgers, and
does not execute HTTP POST. Details:
[STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md](STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md).

## Step 6D Follow-up

Step 6D adds API preflight planning after Step 6C validation. A ready plan may
set `api_preflight_planned=true` and
`eligible_for_step6e_real_api_preflight_execution=true`, but it keeps
`allowed_for_live=false`, `api_preflight_executed=false`, all API/broker/
`live_order_once` flags false, and `post_executed=false`.

Step 6D defines future Step 6E planned checks and raw request/response handling
policy only. It does not call read-only/public/Private API, broker code,
`live_order_once`, ledgers, or HTTP POST, and it does not display/copy/save
approval commands. Details:
[STEP6D_REAL_API_PREFLIGHT_PLAN.md](STEP6D_REAL_API_PREFLIGHT_PLAN.md).

## Step 6E Follow-up

Step 6E adds read-only/preflight-only sanitized result evaluation after Step 6D.
Ready Step 6E output may mark `api_preflight_executed=true` and
`api_preflight_passed=true` only for sanitized preflight evidence, while keeping
`allowed_for_live=false`, no order endpoint, no order payload, no
`live_order_once`, no raw request/response display or save, and no HTTP POST.
The implementation pass did not run real API preflight because it was Sunday
JST. Details:
[STEP6E_REAL_API_PREFLIGHT_EXECUTION.md](STEP6E_REAL_API_PREFLIGHT_EXECUTION.md).
