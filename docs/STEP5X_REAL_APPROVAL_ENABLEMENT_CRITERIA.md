# Step 5X Real Approval Enablement Criteria

## Summary

Step 5X adds `LiveOrderRealApprovalEnablementCriteria`, a dry-run-only criteria
model for future real approval gate enablement planning.

The model consumes the Step 5W `LiveOrderRealApprovalDisabledScaffold` and
records the sanitized conditions that would need to be true before a separate
future step could even consider enabling a real approval gate.

## Scope

This step defines:

- future enablement requirements
- enablement go conditions
- enablement no-go conditions
- kill switch conditions
- approval_id generation conditions
- approval command generation conditions
- sanitized check results
- sanitized markdown rendering
- no-order/no-API guard coverage

## What This Step Does Not Do

Step 5X does not:

- set `approval_gate_enabled=true`
- call read-only API, public API, Private API, broker, or `live_order_once`
- execute HTTP POST
- issue a real approval gate
- generate a real approval_id
- generate a real approval command
- create copyable approval text
- copy approval text to the clipboard
- save approval text to a file
- read or write ledgers
- authorize live execution

## Input: LiveOrderRealApprovalDisabledScaffold

The input is the Step 5W disabled scaffold. The criteria model requires it to be
ready, dry-run-only, not live-enabled, still disabled, and still free of usable
approval artifacts.

Blocked Step 5W scaffolds can still produce a blocked Step 5X criteria record
for auditability, but cannot become eligible for future real approval gate
enablement planning.

## Output: LiveOrderRealApprovalEnablementCriteria

The criteria record carries sanitized IDs, candidate shape, criteria status,
future requirements, go/no-go conditions, kill switch conditions, and approval
artifact generation conditions.

The output always keeps:

- `allowed_for_live=false`
- `approval_gate_enabled=false`
- `approval_gate_issued=false`
- `approval_id_generated=false`
- `approval_command_generated=false`
- `approval_command_copyable=false`
- `approval_command_executable=false`
- `usable_approval_artifacts_generated=false`
- `real_approval_artifacts_available=false`
- `post_executed=false`
- `live_order_once_called=false`

## Ready Criteria Meaning

`READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW` means the criteria are
internally consistent and can be reviewed as evidence for a future separate
enablement planning step.

It does not mean:

- `approval_gate_enabled=true` is allowed now
- real approval gate issuance is allowed
- a real approval_id can be generated
- a real approval command can be generated
- approval text can be copied or pasted
- live POST is authorized

## Blocked Criteria Meaning

`BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA` means one or more disabled-scaffold
or criteria guarantees failed. The result remains sanitized and fail-closed,
and `allowed_for_live=false` plus `approval_gate_enabled=false` are preserved.

Blocked reasons can include:

- disabled scaffold missing, blocked, or not eligible
- scaffold already allows live execution
- approval gate already enabled or issued
- real approval artifact already generated
- unsupported symbol, side, size, or execution type
- missing ACK token or display forbidden field coverage
- API/live runner/post flag already called
- future enablement not deferred
- missing go/no-go/kill-switch conditions

## Future Enablement Requirements

Step 5X records the minimum future conditions for any separate enablement step:

- explicit future user instruction required
- fresh pre-approval preflight must be re-run
- implementation readiness review must be rechecked
- disabled scaffold must be rechecked
- enablement safety audit must be separate future step
- `approval_gate_enabled` may only change in a future explicit step
- real approval_id generation must remain separate
- real approval command generation must remain separate
- post-enable final dynamic preflight required
- one-shot POST remains separate
- post reconciliation remains separate

## Enablement Go Conditions

The criteria require, at minimum:

- disabled scaffold ready
- explicit user instruction present in a future step
- fresh preflight rerun in the future step
- implementation readiness rechecked in the future step
- no blocked reasons
- approval artifacts still not generated
- `approval_gate_enabled` still false before that future enablement step
- no API, broker, or `live_order_once` calls
- post not executed
- one-shot constraints preserved

## Enablement No-Go Conditions

The criteria block future enablement planning if any unsafe condition appears,
including missing explicit future instruction, stale preflight, existing blocked
reasons, existing approval artifacts, enabled approval gate, prior API/live
runner calls, executed post, raw response or real ID exposure risk, or any need
for retry, loop, add, change, cancel, or close behavior.

## Kill Switch Conditions

The kill switch list includes unknown status, `result_unknown`, stale preflight,
unverifiable exact match, unverifiable same-session requirement, unenforceable
TTL, incomplete ACK list, secret/raw/real ID exposure risk, unexpected API shape,
any need to exceed one POST attempt, and any need for retry, loop, add, change,
cancel, or close behavior.

## Approval Artifact Conditions

Step 5X only records future conditions for real approval_id and real approval
command generation. It does not generate either artifact.

Approval_id generation remains limited to a future explicit approval gate
enablement step with fresh preflight, no blocked reasons, no exposure risk, and
same-session guarantees.

Approval command generation remains limited to a future explicit step after an
approval_id is generated in that same future step, with TTL 300 seconds, exact
match, all ACK tokens, one-line command, and no copyable approval text before
that future step.

## Markdown Rendering

The markdown renderer is sanitized and includes these warnings:

```text
This real approval gate enablement criteria model is dry-run only.
This criteria model does not enable a real approval gate.
This criteria model keeps approval_gate_enabled=false.
This criteria model does not call read-only API.
This criteria model does not call Private API.
This criteria model does not call live_order_once.
This criteria model does not execute HTTP POST.
This criteria model does not issue a real approval gate.
This criteria model does not generate a real approval_id.
This criteria model does not generate a real approval command.
This criteria model does not provide copyable approval text.
This criteria model does not authorize live POST.
approval_gate_enabled=false.
allowed_for_live=false.
```

## Do-Not-Cross Boundaries

Strategy signal, candidate, risk decision, trace, review report, session policy,
bundle, operator review, handoff, fake approval artifacts, preflight dry-runs,
one-shot boundary, execution runbook, E2E chain, real approval readiness,
planning package, pre-approval fresh preflight, real approval generation
package, pre-implementation audit, readiness review, disabled scaffold, and
enablement criteria must not directly connect to live POST.

## Relationship to Future Enablement

Step 5X is criteria only. Future real approval gate enablement, if ever
requested, must be a separate explicit task with a fresh preflight, a fresh
safety review, and a new implementation decision. Step 5X is not permission to
enable a gate or issue approval artifacts.

Step 5Y-Z follows Step 5X by adding a sanitized market-hours/weekend blocker
and final pre-enable go/no-go dry-run plan. Step 5Y-Z still keeps
`approval_gate_enabled=false`, `allowed_for_live=false`, and does not issue a
real approval gate, generate approval ids or commands, call APIs, read ledgers,
use clipboard, or execute POST.

## Tests

Tests cover:

- ready Step 5W scaffold to ready enablement criteria
- safety defaults fixed false/true as required
- blocked Step 5W scaffold preservation
- real artifact and enablement flag blockers
- unsupported order shape blockers
- TTL, ACK, exact match, and display forbidden field blockers
- no API, no POST, and one-shot constraint blockers
- required future/go/no-go/kill-switch/artifact condition lists
- markdown warnings
- serialization safety
- forbidden builder kwargs
- no-order/no-API/no-clipboard guard coverage

## Handoff Summary

Step 5X is complete when the criteria model, tests, no-order guard, and docs
pass. The next step, if explicitly requested, must still treat real approval
gate enablement as separate future work. No approval gate, approval_id, approval
command, API call, ledger access, or live POST is authorized by this step.

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
