# Step 5Q Real Approval Readiness Checkpoint

## Summary

Step 5Q adds a dry-run checkpoint for deciding whether the Step 5P end-to-end
dry-run chain is ready to be reviewed before any future real approval gate
planning.

This checkpoint does not place orders, does not issue an approval gate, and does
not authorize live POST. It keeps `allowed_for_live=false`.

## Scope

Step 5Q consumes only sanitized Step 5P evidence:

- `LiveOrderE2EDryRunChainReview`
- operator acknowledgement flags
- future-step separation flags

The output is `LiveOrderRealApprovalReadinessCheckpoint`, a dry-run review
record for go / no-go / stop conditions.

## What This Step Does Not Do

Step 5Q does not:

- call read-only API
- call Private API
- call public API
- call broker code
- call `live_order_once`
- read or write ledger files
- generate an approval id
- issue an approval gate
- generate a real approval command
- copy an approval command
- execute final dynamic preflight
- execute HTTP POST
- perform post reconciliation

## Input: LiveOrderE2EDryRunChainReview

The checkpoint requires a ready Step 5P chain:

- `chain_ready=true`
- `eligible_for_future_real_approval_planning=true`
- `allowed_for_live=false`
- `dry_run_only=true`
- no approval artifacts generated
- no API / broker / `live_order_once` calls
- `post_attempt_limit=1`
- `post_executed=false`
- retry / loop / add / change / cancel / close disabled
- post reconciliation remains required as a future separate step

Unsupported symbol, side, size, or execution type blocks the checkpoint.

## Output: LiveOrderRealApprovalReadinessCheckpoint

The checkpoint records sanitized review fields:

- Step 5P chain and stage ids
- source signal reference
- candidate / risk / trace / review / session policy references
- symbol, side, size, execution type
- readiness status
- go conditions
- no-go conditions
- stop conditions
- check results
- blocked reasons
- recommended next step

It does not include credentials, headers, signatures, raw requests, raw
responses, order ids, execution ids, position ids, or client order ids.

## Ready Checkpoint Meaning

`READY_FOR_REAL_APPROVAL_READINESS_REVIEW` means:

- the sanitized Step 5P dry-run chain is internally consistent
- the operator acknowledged the full chain, real-money risk, no auto-post,
  future-step separation, and unknown-means-stop rule
- future real approval gate planning may be discussed in a later explicit task

It does not mean:

- live POST is allowed
- approval gate may be issued now
- approval command may be generated now
- final dynamic preflight may be executed now
- one-shot POST may be executed now

## Blocked Checkpoint Meaning

`BLOCKED_REAL_APPROVAL_READINESS` means at least one required condition failed.
The model returns all safe blocked reasons it can determine. Blocked checkpoints
remain dry-run records only.

## Operator Acknowledgement Requirements

Ready state requires all operator acknowledgement flags:

- operator reviewed the full Step 5P chain
- operator understands real-money risk
- operator understands no auto-post
- operator understands future steps are separate
- operator understands unknown means stop

Missing acknowledgement is fail-closed.

## Future Step Separation

Ready state requires all future steps to remain separate:

- real approval gate
- fresh final dynamic preflight
- one-shot POST
- post reconciliation
- final report and stop

Step 5Q never proceeds into those steps.

## Go Conditions

The default go conditions require a ready E2E dry-run chain, all operator
acknowledgements, explicit user confirmation before any future real approval
gate step, fresh preflight in a future step, one-shot POST in a future step,
post reconciliation in a future step, and unknown-means-stop.

## No-go Conditions

The default no-go conditions include any blocker, non-ready chain, any
`allowed_for_live=true`, approval artifact generation, API / broker /
`live_order_once` calls, executed POST, missing acknowledgement, unknown result,
stale or unknown future market/account state, or any need to display/store raw
response or real ids.

## Stop Conditions

The default stop conditions include missing explicit future-step request,
missing acknowledgement, chain mismatch, stale preflight risk, result unknown,
secret/raw response/id exposure risk, retry/loop/add/change/cancel/close need,
or any need to exceed one POST attempt.

## Check Results

The checkpoint records sanitized checks for:

- E2E chain ready
- `allowed_for_live=false`
- approval artifacts not generated
- POST not executed
- no API / broker / `live_order_once` calls
- one-shot constraints
- future-step separation
- operator acknowledgements
- explicit user confirmation requirement
- unknown-means-stop

## Markdown Rendering

`render_live_order_real_approval_readiness_markdown()` includes these warnings:

```text
This real approval readiness checkpoint is dry-run only.
This checkpoint does not call read-only API.
This checkpoint does not call Private API.
This checkpoint does not call live_order_once.
This checkpoint does not execute HTTP POST.
This checkpoint does not issue a real approval gate.
This checkpoint does not generate a real approval command.
This checkpoint does not authorize live POST.
allowed_for_live=false.
```

## Do-not-cross Boundaries

- Step 5Q does not directly or indirectly POST.
- Step 5Q does not call `live_order_once`.
- Step 5Q does not connect to Private API, public API, read-only API, or broker.
- Step 5Q does not issue approval artifacts.
- Step 5Q does not read or change ledgers.
- Step 5Q does not copy or save approval command text.

## Relationship to Future Real Approval Gate

Step 5Q can only produce review evidence for a future explicit real approval
gate planning step. A future real approval flow would still require a separate
task, fresh dynamic preflight, explicit approval gate, one-shot boundary, post
reconciliation, and final stop/report.

## Tests

Tests cover:

- ready Step 5P chain + acknowledgements
- fixed `allowed_for_live=false`
- missing / blocked chain
- approval artifact, API, POST, retry, loop, add, change, cancel, close blockers
- unsupported symbol / side / size / execution type
- missing operator acknowledgements
- missing future-step separation
- go / no-go / stop conditions
- check result names
- Markdown warnings
- serialization/repr secret and raw-response exclusion
- no-order guard coverage

## Handoff Summary

Step 5Q is complete when the checkpoint model, tests, docs, and no-order guard
pass. A ready checkpoint is still dry-run readiness evidence only. It is not
approval gate permission, approval command permission, final preflight
permission, live POST permission, or post reconciliation permission.

## Step 5R Follow-up

Step 5R now adds the real approval gate plan dry-run model. It consumes the
Step 5Q readiness checkpoint as sanitized evidence, separates future fresh
preflight, real approval gate generation, approval command exact-match
validation, post-approval final dynamic preflight, one-shot boundary, post
reconciliation, and final report phases, keeps `allowed_for_live=false`, and
does not call APIs, issue approval, generate real approval ids or commands,
call `live_order_once`, read/write ledgers, or execute POST. A ready Step 5R
plan is planning evidence only and does not authorize real approval gate
issuance, approval command generation, final dynamic preflight, or live POST.
