# Step 5T Real Approval Gate Generation Package

## Step 5U Update

Step 5U adds a dry-run real approval pre-implementation safety audit on top of
this generation package. The audit independently checks that approval artifact
generation remains deferred, no API/broker/`live_order_once`/POST path has been
used, `allowed_for_live=false` is preserved, TTL/exact match/same session/ACK
requirements are intact, and residual risks/manual confirmations/implementation
blockers are visible.

See
[STEP5U_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT.md](STEP5U_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT.md).

## Summary

Step 5T adds a dry-run `LiveOrderRealApprovalGateGenerationPackage`.
It consumes the Step 5S `LiveOrderPreApprovalFreshPreflightDecision` and
organizes the sanitized package that a future, separate real approval gate
generation step would need.

Step 5T is no API and no POST. It does not issue an approval gate, does not
generate a real `approval_id`, does not generate a real approval command, and
does not create copyable approval text.

## Scope

Implemented scope:

- `LiveOrderRealApprovalGateGenerationPackage`
- `LiveOrderRealApprovalGateGenerationPackageStatus`
- `LiveOrderRealApprovalGateGenerationPackagePhase`
- `LiveOrderRealApprovalGateGenerationPackageCheckResult`
- `LiveOrderRealApprovalGateGenerationPackageBuildResult`
- `LiveOrderRealApprovalGateGenerationPackageBlockReason`
- `build_live_order_real_approval_gate_generation_package`
- `render_live_order_real_approval_gate_generation_package_markdown`
- `make_live_order_real_approval_gate_generation_package_id`
- required phases
- required ACK token list
- display allowed and forbidden fields
- go/no-go/stop conditions
- fail-closed package constraint checks

## What This Step Does Not Do

Step 5T does not:

- call read-only API, public API, Private API, or broker
- call `live_order_once`
- execute pre-approval fresh preflight against live services
- execute final dynamic preflight against live services
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

## Input: LiveOrderPreApprovalFreshPreflightDecision

The Step 5S decision must be ready:

```text
preflight_status: READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
preflight_passed: true
eligible_for_future_real_approval_gate_generation: true
allowed_for_live: false
dry_run_only: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_copyable: false
symbol: USD_JPY
side: BUY or SELL
size: 100
executionType: MARKET
```

Blocked Step 5S decisions still produce a blocked package for audit, and their
sanitized `blocked_reasons` are preserved.

## Output: LiveOrderRealApprovalGateGenerationPackage

The package contains sanitized references and policy facts only:

```text
package_id
pre_approval_preflight_decision_id
snapshot_id
plan_id
checkpoint_id
chain_id
candidate_id
risk_decision_id
trace_id
session_policy_decision_id
symbol
side
size
executionType
package_status
package_ready
eligible_for_future_real_approval_gate_generation
allowed_for_live=false
approval_id_generation_deferred_to_future_step
approval_command_generation_deferred_to_future_step
ttl_seconds
exact_match_required
same_session_required
required_ack_tokens
approval_id_placeholder_label
approval_command_template_label
approval_command_display_mode
phases
go_conditions
no_go_conditions
stop_conditions
check_results
blocked_reasons
recommended_next_step
```

## Ready Package Meaning

Ready means:

```text
package_status: READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
package_ready: true
eligible_for_future_real_approval_gate_generation: true
allowed_for_live: false
recommended_next_step: stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_generation_step
```

This means the sanitized package is ready for human review only. It is not
approval gate permission, approval id permission, approval command permission,
live POST permission, or `live_order_once` permission.

## Blocked Package Meaning

Blocked means:

```text
package_status: BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE
package_ready: false
eligible_for_future_real_approval_gate_generation: false
allowed_for_live: false
recommended_next_step: fix_pre_approval_fresh_preflight_blockers_no_post
```

The package preserves Step 5S blocked reasons and adds package constraint
blockers when deferral, TTL, exact match, same session, ACK tokens, phases, or
display rules are unsafe.

## Approval Gate Generation Sequence

The required phases are:

```text
confirm_pre_approval_fresh_preflight_ready
stop_before_real_approval_gate_generation
future_generate_real_approval_id
future_generate_real_approval_command
future_display_real_approval_gate
future_validate_exact_match_approval
future_post_approval_final_dynamic_preflight
future_one_shot_post_separate_step
future_post_reconciliation
future_final_report_and_stop
```

Step 5T only records this sequence. It does not execute it.

## Approval ID Generation Deferral

Step 5T uses only:

```text
approval_id_placeholder_label: <APPROVAL_ID_GENERATED_IN_FUTURE_REAL_GATE_STEP>
approval_id_generation_deferred_to_future_step: true
approval_id_generated: false
```

Real approval id generation is deferred to a future separate step.

## Approval Command Generation Deferral

Step 5T uses only:

```text
approval_command_template_label: <APPROVAL_COMMAND_GENERATED_IN_FUTURE_REAL_GATE_STEP>
approval_command_display_mode: non_copyable_label_only
approval_command_generation_deferred_to_future_step: true
approval_command_generated: false
approval_command_copyable: false
```

Real approval command generation is deferred to a future separate step.

## TTL / Exact Match / Same Session

The package fixes the future approval constraints:

```text
ttl_seconds: 300
exact_match_required: true
same_session_required: true
```

Changing any of these values blocks the package.

## Required ACK Tokens

The required ACK token set is recorded as sanitized planned policy:

```text
ACK_RISK=YES
ACK_OPEN_POSITION=YES
ACK_API_SCOPE=YES
ACK_ORDER_PERMISSION=YES
ACK_IP_ACCOUNT_CHECK=YES
ACK_NO_EVENT=YES
ACK_NO_RETRY=YES
ACK_NO_LOOP=YES
ACK_NO_ADD=YES
ACK_NO_CHANGE=YES
ACK_NO_CANCEL=YES
ACK_NO_CLOSE=YES
ACK_STOP_ON_UNKNOWN=YES
```

Step 5T does not assemble these into a copyable command.

## Display Allowed Fields

The package may display sanitized references, status, planned constraints,
placeholder labels, ACK token names, phases, conditions, check results, blocked
reasons, and recommended next step.

## Display Forbidden Fields

The package forbids credential values, header values, signature values, raw
requests, raw responses, order IDs, execution IDs, position IDs,
`clientOrderId`, request URLs, open price, detailed P/L, real approval ids, real
approval commands, and copyable approval command text.

## Go Conditions

Go conditions are dry-run package review conditions only:

- pre-approval fresh preflight decision is ready
- explicit future user instruction is required before real approval gate generation
- approval id generation is deferred to a future separate step
- approval command generation is deferred to a future separate step
- exact match is required
- same Codex session is required
- TTL is 300 seconds
- all ACK tokens are required
- future approval command must be a single exact line
- post-approval final dynamic preflight is required
- one-shot POST remains a separate future step

## No-go Conditions

No-go conditions include blocked or stale pre-approval fresh preflight, already
generated approval artifacts, any API or `live_order_once` call, any executed
POST, shape mismatch, raw response or real ID display/storage requirement, and
any need for retry, loop, add, change, cancel, or close.

## Stop Conditions

Stop conditions include no explicit future request, stale pre-approval,
premature approval id or command generation, inability to guarantee exact match
or same session, incomplete ACK set, secret/raw/ID exposure risk,
`result_unknown`, or need for more than one POST attempt.

## Markdown Rendering

The Markdown renderer includes these warnings:

```text
This real approval gate generation package is dry-run only.
This package does not call read-only API.
This package does not call public API.
This package does not call Private API.
This package does not call live_order_once.
This package does not execute HTTP POST.
This package does not issue a real approval gate.
This package does not generate a real approval_id.
This package does not generate a real approval command.
This package does not provide copyable approval text.
This package does not authorize live POST.
allowed_for_live=false.
```

## Do-not-cross Boundaries

Step 5T is not an approval gate and not an execution step. It does not connect
to APIs, does not read ledgers, does not create approval artifacts, and does not
authorize live POST.

## Relationship to Future Real Approval Gate Generation Step

A ready Step 5T package can be used as sanitized review evidence for a future
separate real approval gate generation task. That future task must still be
explicitly requested by the user and must perform its own fresh checks and
safety gates. Step 5T itself stops after package creation.

## Tests

Tests cover:

- ready Step 5S decision to ready Step 5T package
- blocked Step 5S decision preservation
- unsafe decision flags
- unsupported symbol, side, size, and execution type
- deferral, TTL, exact match, same session, ACK token, placeholder, display mode, phase, and condition blockers
- required phases and check results
- Markdown warnings
- absence of actual credential, raw response, real ID, and real command values
- no-order guard coverage

## Handoff Summary

Step 5T completes the dry-run real approval gate generation package. The package
is review evidence only. Next work, if explicitly requested, must be a separate
future real approval gate generation step; Step 5T does not generate approval
artifacts and does not permit live POST.

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
