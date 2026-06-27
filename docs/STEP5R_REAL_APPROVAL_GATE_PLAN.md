# Step 5R Real Approval Gate Plan

## Step 5T Update

Step 5T adds a dry-run real approval gate generation package after Step 5S. The
package is review evidence only: real approval id generation, real approval
command generation, approval gate issuance, final preflight, and one-shot POST
remain future separate steps. `allowed_for_live=false` is preserved. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5R adds a dry-run real approval gate planning package. It consumes the
Step 5Q `LiveOrderRealApprovalReadinessCheckpoint` as sanitized evidence and
turns it into a review-only sequence for a future real approval gate step.

Step 5R is no API, no approval, and no POST. A ready plan is only planning
evidence for a future explicit task. It does not authorize live execution.

## Scope

The model records the future sequence that would still be required before any
one-shot live order:

- stop and request explicit user instruction
- future fresh preflight before approval gate
- future real approval gate generation
- future approval command exact-match validation
- future post-approval final dynamic preflight
- future one-shot POST boundary
- future post reconciliation
- future final report and stop

## What This Step Does Not Do

Step 5R does not:

- call read-only API, public API, Private API, or broker
- call `live_order_once`
- issue a real approval gate
- generate a real `approval_id`
- generate a real approval command
- create copyable approval text
- read, write, reset, or delete ledgers
- execute final dynamic preflight
- execute HTTP POST
- place, add, change, cancel, or close orders
- display or save credentials, headers, signatures, raw requests, raw responses, or real IDs

## Input: LiveOrderRealApprovalReadinessCheckpoint

The input is the Step 5Q readiness checkpoint. It must already be ready and must
still carry the dry-run safety defaults:

- `allowed_for_live=false`
- `dry_run_only=true`
- `approval_gate_required=true`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `post_executed=false`
- `live_order_once_called=false`
- `private_api_called=false`
- `broker_called=false`
- `read_only_api_called=false`
- retry / loop / add / change / cancel / close all false

If the checkpoint is blocked or unsafe, the plan is blocked and preserves the
checkpoint blockers as sanitized reasons.

## Output: LiveOrderRealApprovalGatePlan

The output is a review-only plan. It fixes these safety defaults:

- `allowed_for_live=false`
- `requires_human_approval=true`
- `explicit_user_confirmation_required=true`
- `real_approval_gate_separate_step_required=true`
- `fresh_preflight_before_gate_required=true`
- `approval_id_generation_after_fresh_preflight_required=true`
- `approval_command_generation_after_fresh_preflight_required=true`
- `post_approval_final_dynamic_preflight_required=true`
- `one_shot_post_separate_step_required=true`
- `post_reconciliation_separate_step_required=true`
- `final_report_separate_step_required=true`
- `approval_gate_required=true`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_template_only=true`
- `approval_command_copyable=false`
- `ttl_seconds=300`
- `exact_match_required=true`
- `same_session_required=true`
- `required_ack_tokens` equal the Step 5J approval ACK token set
- `dry_run_only=true`
- `post_attempt_limit=1`
- `post_executed=false`

## Plan Ready Meaning

`READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW` means the sanitized readiness evidence
and future-step sequence are internally consistent enough for review.

It does not mean:

- approval gate may be issued now
- approval command may be generated now
- final dynamic preflight may run now
- one-shot POST may run now
- `live_order_once` may be called now

The recommended next step is to stop and wait for an explicit future user
instruction for a separate real approval gate step.

## Blocked Meaning

`BLOCKED_REAL_APPROVAL_GATE_PLAN` means at least one planning condition failed.
The plan stays fail-closed and returns sanitized `blocked_reasons`.

Blocked examples include:

- readiness checkpoint missing or blocked
- readiness checkpoint allows live execution
- approval artifact already generated
- API / broker / `live_order_once` already called
- POST already executed
- unsupported symbol / side / size / execution type
- invalid TTL
- exact match or same session not required
- ACK token missing
- retry / loop / add / change / cancel / close allowed
- missing required phase
- missing go / no-go / stop conditions

## Future Approval Gate Sequence

Step 5R separates the future real approval sequence:

1. Stop and require explicit user instruction for the future real approval gate step.
2. In that future step, run fresh preflight before generating approval artifacts.
3. Generate a real approval gate only after fresh preflight passes.
4. Validate approval command by exact match in the same session within the TTL.
5. Run post-approval final dynamic preflight.
6. Only a later one-shot boundary may decide whether one HTTP POST attempt is eligible.
7. Reconcile by sanitized read-only checks only after a future POST.
8. Report and stop.

## Go Conditions

Default go conditions require a ready Step 5Q checkpoint, explicit future user
instruction, future fresh preflight before approval gate, deferred approval id
and command generation, exact match, same session, TTL 300 seconds, all ACK
tokens, final dynamic preflight after approval, and a separate future one-shot
POST step.

## No-go Conditions

Default no-go conditions include readiness blocked, no explicit user instruction,
stale or missing fresh preflight, approval artifacts already generated, any API
/ broker / `live_order_once` call, POST already executed, order shape mismatch,
unknown future market/account state, raw response or real ID display/storage
need, or retry/loop/add/change/cancel/close need.

## Stop Conditions

Default stop conditions include missing explicit request, unsafe fresh preflight,
expired approval, exact-match failure, same-session failure, missing ACK token,
stale final dynamic preflight, result unknown, reconciliation impossible,
secret/raw response/ID exposure risk, or any need to exceed one POST attempt.

## Do-not-cross Boundaries

- Step 5R is no POST.
- Step 5R is no API.
- Step 5R is not an approval gate.
- Step 5R does not generate real approval text.
- Step 5R keeps `allowed_for_live=false`.
- Step 5R does not connect to `live_order_once`.
- Step 5R does not read or write ledgers.
- Step 5R does not lead directly from checkpoint to POST.

## Relationship to Future Real Approval Gate

Future real approval gate work must be a separate explicit Step. It must start
from fresh preflight and must not reuse Step 5R as permission to issue approval
artifacts or execute live POST.

## Tests

Tests cover:

- ready Step 5Q checkpoint to ready Step 5R plan
- fixed `allowed_for_live=false`
- blocked / missing checkpoint
- checkpoint mismatch and unsafe flags
- approval artifacts already generated
- API / broker / `live_order_once` blockers
- unsupported symbol / side / size / execution type
- TTL / exact match / same-session / ACK token requirements
- one-shot POST limit and no retry / loop / order mutation
- required phases and go / no-go / stop conditions
- Markdown dry-run / no-approval / no-live-post warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5R is complete when the plan model, tests, docs, and no-order guard pass.
A ready plan is still dry-run planning evidence only. It is not approval gate
permission, approval command permission, final dynamic preflight permission,
live POST permission, `live_order_once` permission, or post reconciliation
permission.

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
