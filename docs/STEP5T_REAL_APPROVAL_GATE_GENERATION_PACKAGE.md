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
