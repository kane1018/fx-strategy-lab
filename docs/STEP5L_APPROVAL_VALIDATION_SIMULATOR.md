# Step 5L Approval Validation Simulator

## Step 5T Update

Step 5T is still dry-run and does not perform real approval validation. It
packages future real approval gate generation requirements, while actual
approval id and approval command generation remain deferred to a later explicit
step. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5L adds a dry-run approval validation simulator for a Step 5K
`LiveOrderApprovalGatePreview`.

This step is no POST. The simulator validates fake/template-only approval text
against the Step 5K preview rules. It is not a real approval gate, does not
generate a real approval id, does not generate a real approval command, does
not copy text to the clipboard, does not save approval text to a file, and does
not authorize final dynamic preflight or live execution.

## Scope

Implemented scope:

- sanitized `LiveOrderApprovalValidationSimulation`
- sanitized `LiveOrderApprovalValidationRuleResult`
- sanitized `LiveOrderApprovalValidationSimulationSection`
- fail-closed `simulate_live_order_approval_validation`
- deterministic dry-run simulation id generation
- fake template exact-match simulation
- 300 second TTL simulation
- same-session and unused-command simulation
- required ACK token simulation
- no extra token, no newline, and no extra space simulation
- placeholder-only checks for approval id and side values
- fake-prefix checks
- real-approval-shaped text blocking
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5L does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- generate a real approval id
- issue or display a real approval gate
- generate or display a real approval command
- produce copyable approval text
- copy approval text to a clipboard
- write approval text to `/tmp` or any file
- call the one-shot live runner
- connect to read-only API, Private API, or broker code
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- run final dynamic preflight
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderApprovalGatePreview

The input preview must already be a Step 5K dry-run preview:

```text
preview_status: READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
ttl_seconds: 300
exact_match_required: true
same_session_required: true
final_dynamic_preflight_required: true
dry_run_only: true
```

Blocked previews, live-allowed previews, non-dry-run previews, already-issued
gates, already-generated ids or commands, copyable command templates, invalid
TTL, missing exact-match rules, missing same-session rules, missing final
dynamic preflight requirement, and unsupported order shape fail closed.

## Simulated Input

The simulator accepts fake/template-only validation inputs:

```text
simulated_command_input
simulated_ttl_seconds
same_session
already_used
```

`simulated_command_input` must exactly equal the Step 5K fake template text,
including the fake prefix and placeholders:

```text
STEP_APPROVAL_TEMPLATE <APPROVAL_ID_FROM_FUTURE_STEP> SIDE=<SIDE_FROM_FUTURE_STEP> SYMBOL=USD_JPY SIZE=100 ...
```

This is still a fake template. It is not a real approval command and must not be
copied into Codex as approval.

## Output: LiveOrderApprovalValidationSimulation

The simulation contains only sanitized dry-run fields:

```text
simulation_id
preview_id
design_id
handoff_id
operator_review_id
bundle_id
review_id
candidate_id
risk_decision_id
trace_id
session_policy_decision_id
source_signal_id
source_type
strategy_name
symbol
side
size
execution_type
preview_status
simulation_status
simulated_command_received
simulated_command_exact_match
simulated_command_template_only
simulated_command_copyable
simulated_ttl_seconds
same_session
already_used
allowed_for_live
requires_human_approval
approval_gate_required
approval_gate_issued
approval_id_generated
approval_command_generated
approval_command_template_only
approval_command_copyable
ttl_seconds
exact_match_required
same_session_required
final_dynamic_preflight_required
dry_run_only
approval_id_placeholder
side_placeholder
ack_tokens
validation_rule_results
blocked_reasons
recommended_next_step
sections
```

All simulations keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
ttl_seconds: 300
exact_match_required: true
same_session_required: true
final_dynamic_preflight_required: true
dry_run_only: true
```

## Passed Simulation Meaning

Passed means:

```text
simulation_status: SIMULATED_APPROVAL_VALIDATION_PASSED
simulated_command_exact_match: true
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
recommended_next_step: prepare_future_final_dynamic_preflight_design_no_post
```

This only means a fake/template-only validation simulation passed. It does not
authorize a real approval gate, does not generate a real approval id, does not
generate a real approval command, does not authorize final dynamic preflight,
and does not authorize live POST.

## Blocked Simulation Meaning

Blocked means:

```text
simulation_status: BLOCKED_APPROVAL_VALIDATION_SIMULATION
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
recommended_next_step: fix_simulated_approval_validation_inputs_no_post
```

Preview-level blocked reasons and simulation-level blocked reasons are
preserved for human inspection. A blocked simulation means do not proceed.

## Simulated Validation Rules

The simulator evaluates:

```text
preview_ready
exact_match
ttl_300_seconds
same_codex_session
unused_once
all_ack_tokens
no_extra_tokens
no_line_breaks
no_extra_spaces
template_prefix
placeholder_only
```

All rules are fake-template validation only. They do not collect user approval.

## Do-Not-Cross Boundaries

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
- Approval validation simulation does not issue an approval gate.
- Approval validation simulation does not generate a real approval id.
- Approval validation simulation does not generate a real approval command.
- Approval validation simulation does not create copyable approval text.
- Approval validation simulation does not use clipboard or file output.
- Approval validation simulation does not read account, order, position, ledger, or API state.
- Any future real approval gate must be a separate explicit step.

## Relationship to Future Final Dynamic Preflight

Step 5L can feed a future final dynamic preflight design review. It cannot
authorize that preflight by itself. Any later real approval gate or final
dynamic preflight must be a separate task with fresh preflight, one-shot ledger
protection, exact approval text, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- exact fake-template match pass
- fixed `allowed_for_live=false`
- fixed human approval and approval gate requirements
- fixed `approval_gate_issued=false`
- fixed `approval_id_generated=false`
- fixed `approval_command_generated=false`
- fixed `approval_command_template_only=true`
- fixed `approval_command_copyable=false`
- fixed TTL 300 seconds
- fixed exact-match and same-session requirements
- fixed final dynamic preflight requirement
- blocked preview
- preserved blocked reasons
- live-allowed preview failure
- dry-run flag failure
- missing human approval and approval gate requirements
- already-issued approval gate failure
- already-generated approval id failure
- already-generated approval command failure
- non-template command failure
- copyable command failure
- invalid preview TTL failure
- missing exact-match or same-session requirement
- missing final dynamic preflight requirement
- unsupported symbol, side, size, and execution type
- missing or mismatched simulated command
- TTL 300 boundary
- expired TTL failure
- different session failure
- already-used failure
- newline, leading/trailing space, and repeated-space failure
- missing, duplicated, or extra ACK/token failure
- invalid fake prefix failure
- real-approval-shaped command or id failure
- missing approval id or side placeholder failure
- validation rule results
- Markdown dry-run / no real approval gate / no real approval id / no real command / no final preflight / no live POST warnings
- absence of forbidden actual values and command text
- no dependency on HTTP clients, Private API, broker code, live runner code, approval gate builders, or clipboard commands

## Handoff Summary

Step 5L adds a fake approval validation simulator after Step 5K approval gate
preview. A passed simulation is dry-run evidence only. It preserves
`allowed_for_live=false`, keeps `approval_gate_issued=false`, keeps
`approval_id_generated=false`, keeps `approval_command_generated=false`, keeps
the fake command template non-copyable, avoids clipboard and file output, avoids
API and ledger access, and never permits final dynamic preflight or live POST.

The next step may design final dynamic preflight handling, but it must remain a
separate task with no live execution unless explicitly authorized in a later
real approval flow.

Step 5M now adds that final dynamic preflight handling as a dry-run model only.
A passed Step 5M decision means sanitized final preflight inputs are ready for
future one-shot boundary review. It does not execute final dynamic preflight,
does not call APIs, does not issue approval, and does not authorize live POST.

Step 5N now adds that future one-shot boundary as a dry-run model only. A passed
Step 5N decision means sanitized one-shot constraints are ready for review; it
does not issue approval, does not call `live_order_once`, does not call APIs, and
does not authorize live POST.

Step 5O now adds the one-shot execution runbook dry-run model. A ready runbook
means only that the future execution procedure is review-ready; it does not
validate real approval, run final dynamic preflight, call APIs, or execute live
POST.

Step 5P now adds the E2E dry-run chain review model. Fake validation simulation
results remain dry-run evidence only; Step 5P checks them with the other Step
5B through Step 5O artifacts as sanitized references, keeps
`allowed_for_live=false`, and does not call APIs, issue approval, generate
approval commands, call `live_order_once`, or execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. Approval validation
simulation results remain fake evidence only; Step 5R does not validate a real
approval command, run final dynamic preflight, call APIs, call `live_order_once`,
or execute POST.

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
