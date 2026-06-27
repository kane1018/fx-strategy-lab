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

## Step 6B Follow-up

Step 6B adds an approval artifact generation model after the Step 6A enablement
state. Ready output may set `approval_id_generated=true`,
`approval_command_generated=true`, and `approval_artifact_generated=true` only
as internal model artifacts for future Step 6C validation. Step 6B keeps
`allowed_for_live=false`, does not issue a real approval gate, does not render
or copy the full approval command, does not use `pbcopy`, does not save approval
text, does not call any API or ledger, and does not execute POST. Details:
[STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md](STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md).

## Step 6C Follow-up

Step 6C adds approval artifact validation after Step 6B. Ready validation may
set `approval_artifact_validated=true`,
`approval_command_exact_match_validated=true`,
`approval_command_ttl_validated=true`,
`approval_command_same_session_validated=true`, and
`eligible_for_step6d_api_preflight_planning=true` only as internal dry-run
validation evidence. Step 6C keeps `allowed_for_live=false`, does not issue a
real approval gate, does not render or copy the full generated/provided approval
command, does not use `pbcopy`, does not save approval text, does not call any
API or ledger, and does not execute POST. Details:
[STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md](STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md).
