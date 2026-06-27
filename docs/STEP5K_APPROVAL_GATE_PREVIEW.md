# Step 5K Approval Gate Preview

## Summary

Step 5K adds a dry-run approval gate preview model for a Step 5J
`LiveOrderApprovalGateDesign`.

This step is no POST. The preview is not a real approval gate, not a real
approval id, not a real approval command, not copyable approval text, and not
live execution permission.

## Scope

Implemented scope:

- sanitized `LiveOrderApprovalGatePreview`
- sanitized `LiveOrderApprovalGatePreviewValidationRule`
- sanitized `LiveOrderApprovalGatePreviewSection`
- fail-closed `build_live_order_approval_gate_preview`
- deterministic dry-run preview id generation
- placeholder-only approval id preview
- non-copyable approval command template preview
- required ACK token list preview
- TTL 300 seconds preview
- exact-match and same-session validation rules
- final dynamic preflight boundary preview
- display-allowed field list
- display-forbidden field list
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5K does not:

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
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderApprovalGateDesign

The input design must already be a Step 5J dry-run design:

```text
design_status: READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
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

Blocked designs, unsupported symbols, unsupported side, unsupported size,
unsupported execution type, live-allowed designs, non-dry-run designs,
already-issued gates, already-generated ids or commands, copyable command
templates, invalid TTL, missing exact-match rules, missing same-session rules,
and missing final dynamic preflight requirement fail closed.

## Output: LiveOrderApprovalGatePreview

The preview contains only sanitized dry-run fields:

```text
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
design_status
preview_status
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
approval_command_template
ack_tokens
display_allowed_fields
display_forbidden_fields
final_dynamic_preflight_items
validation_rules
blocked_reasons
recommended_next_step
sections
```

All previews keep:

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

## Ready Preview Meaning

Ready means:

```text
preview_status: READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
recommended_next_step: review_fake_approval_gate_preview_no_post
```

This only means the fake approval gate preview can be reviewed. It does not
issue an approval gate, does not generate a real approval id, does not generate
a real approval command, does not produce copyable approval text, and does not
authorize live POST.

## Blocked Preview Meaning

Blocked means:

```text
preview_status: BLOCKED_APPROVAL_GATE_PREVIEW
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
recommended_next_step: fix_approval_gate_design_blockers_no_post
```

Design blocked reasons and preview-level blocked reasons are preserved for
human inspection. A blocked preview means do not proceed.

## Approval ID Placeholder

Step 5K uses only this placeholder:

```text
<APPROVAL_ID_FROM_FUTURE_STEP>
```

It is not an actual approval id. It is not an exchange, order, execution,
position, or client order identifier. Step 5K never generates a real approval
id.

## Approval Command Template Preview

Step 5K previews the Step 5J fake template only:

```text
STEP_APPROVAL_TEMPLATE <APPROVAL_ID_FROM_FUTURE_STEP> SIDE=<SIDE_FROM_FUTURE_STEP> SYMBOL=USD_JPY SIZE=100 ...
```

The previewed template is not a real approval command. It is not copyable. It
must not be pasted into Codex as approval. A future real approval gate, if
implemented, must be a separate explicit Step after fresh preflight.

## Validation Rules

The preview records future validation rules only:

```text
future_real_gate_only
fresh_preflight_before_id
one_line_command
exact_match
same_codex_session
ttl_300_seconds
all_ack_tokens
no_extra_tokens
no_line_breaks
no_extra_spaces
not_from_preview
final_preflight_after_approval
no_live_post_before_final_preflight
```

Step 5K does not validate a user approval command because it never generates or
accepts a real approval command. The rules are review material for a future
real approval gate implementation.

## ACK Tokens

The fake template records the future ACK token shape:

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

Step 5K records these tokens for preview review only. It does not collect user
approval and does not treat any text as approval.

## Final Dynamic Preflight Boundary

The preview carries forward the Step 5J final dynamic preflight checklist:

```text
account/assets: success
open_positions_count=0
active_orders_count=0
spread_jpy <= 0.01
ledger unused
Git clean
tests pass
secret scan pass
outbound body allowlist matches
request body == signing body
```

Step 5K records this list only. It does not run final dynamic preflight.

## Markdown Rendering

Rendered Markdown must include:

```text
This approval gate preview is dry-run only.
This preview is not a real approval gate.
This preview does not generate a real approval_id.
This preview does not generate a real approval command.
This preview is not copyable approval text.
This preview does not authorize live POST.
allowed_for_live=false.
```

It also states that the template is non-copyable and must not be pasted into
Codex as approval.

Rendered Markdown includes dry-run ids, source references, candidate summary,
safety flags, placeholder values, fake template text, ACK token names,
validation rule names, display allowed fields, display forbidden labels, final
dynamic preflight item names, blocked reasons, and recommended next step. It
excludes credential values, raw response values, request data values, and
execution identifier values.

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
- Approval gate preview does not issue an approval gate.
- Approval gate preview does not generate a real approval id.
- Approval gate preview does not generate a real approval command.
- Approval gate preview does not create copyable approval text.
- Approval gate preview does not use clipboard or file output for approval text.
- Approval gate preview does not read account, order, position, ledger, or API state.
- Any future real approval gate must be a separate explicit step.

## Relationship to Future Real Approval Gate

Step 5K can feed a future real approval gate implementation review. It cannot
authorize live order execution by itself. Any later approval gate must be a
separate task with fresh preflight, one-shot ledger protection, exact approval
text, final dynamic preflight, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- ready design to ready fake approval gate preview
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
- blocked design
- preserved blocked reasons
- live-allowed design failure
- dry-run flag failure
- missing human approval and approval gate requirements
- already-issued approval gate failure
- already-generated approval id failure
- already-generated approval command failure
- non-template command failure
- copyable command failure
- invalid TTL failure
- missing exact-match or same-session requirement
- missing final dynamic preflight requirement
- unsupported symbol, side, size, and execution type
- placeholder-only approval id preview
- fake approval command template is not real and is not copyable
- required ACK tokens
- validation rules
- display allowed field list
- display forbidden field list
- final dynamic preflight item list
- Markdown dry-run / no real approval gate / no real approval id / no real command / no copyable approval text / no live POST warnings
- absence of forbidden actual values
- no dependency on HTTP clients, Private API, broker code, live runner code, approval gate builders, or clipboard commands

## Handoff Summary

Step 5K adds the fake approval gate preview layer after Step 5J approval gate
design. A ready preview is a human-readable dry-run preview only. It preserves
`allowed_for_live=false`, keeps `approval_gate_issued=false`, keeps
`approval_id_generated=false`, keeps `approval_command_generated=false`, keeps
the fake command template non-copyable, avoids clipboard and file output, avoids
API and ledger access, and never permits live POST.

The next step may review how a real approval gate would be implemented, but it
must remain a separate task with fresh preflight. Step 5K itself does not
generate approval ids or approval commands.

Step 5L now provides the fake approval validation simulator layer in
[STEP5L_APPROVAL_VALIDATION_SIMULATOR.md](STEP5L_APPROVAL_VALIDATION_SIMULATOR.md).
It validates fake/template-only input against this preview's rules only. A
passed simulation is not a real approval gate, does not generate a real approval
id or command, does not authorize final dynamic preflight, and does not
authorize live POST.

Step 5M now adds the final dynamic preflight dry-run model after the fake
approval validation simulator. Approval gate preview remains non-copyable and
non-executable; Step 5M only evaluates sanitized final preflight snapshot inputs.

Step 5N now adds the one-shot live boundary dry-run model. Approval gate preview
remains non-copyable and non-executable; Step 5N only evaluates sanitized
one-shot constraints and does not issue approval or execute POST.

Step 5O now adds the one-shot execution runbook dry-run model. Approval gate
preview remains non-copyable and non-executable; the runbook does not create a
real approval command and does not authorize live POST.

Step 5P now adds the E2E dry-run chain review model. Fake approval preview
artifacts remain non-copyable sanitized evidence only; Step 5P checks them in
the Step 5B through Step 5O chain, keeps `allowed_for_live=false`, and does not
call APIs, issue approval, generate approval commands, call `live_order_once`,
or execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. Fake approval
previews remain non-copyable evidence; Step 5R keeps real approval artifacts
ungenerated and only records the future sequence that would be needed in a
separate explicit task.

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
