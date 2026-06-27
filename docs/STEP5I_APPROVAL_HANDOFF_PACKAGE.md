# Step 5I Approval Handoff Package

## Summary

Step 5I adds a sanitized approval handoff package for a Step 5H
`LiveOrderOperatorReviewProcedure`.

This step is no POST. The handoff package is not an order, not an approval
gate, not an approval command, and not live execution permission.

## Scope

Implemented scope:

- sanitized `LiveOrderApprovalHandoffPackage`
- sanitized `LiveOrderApprovalHandoffSection`
- fail-closed `build_live_order_approval_handoff_package`
- deterministic dry-run handoff id generation
- display-allowed field list
- display-forbidden field list
- future final dynamic preflight checklist
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5I does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- issue an approval id
- issue or display an approval gate
- generate or display an approval command
- call the one-shot live runner
- connect to read-only API, Private API, or broker code
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderOperatorReviewProcedure

The input operator review must already be a Step 5H dry-run procedure:

```text
operator_review_status: READY_FOR_OPERATOR_CHECKLIST
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

Blocked operator reviews, unsupported symbols, unsupported side, unsupported
size, unsupported execution type, live-allowed reviews, and non-dry-run reviews
fail closed.

## Output: LiveOrderApprovalHandoffPackage

The package contains only sanitized dry-run handoff fields:

```text
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
operator_review_status
handoff_status
eligible_for_operator_review
allowed_for_live
requires_human_approval
approval_gate_required
approval_gate_issued
approval_command_generated
final_dynamic_preflight_required
dry_run_only
display_allowed_fields
display_forbidden_fields
final_dynamic_preflight_items
blocked_reasons
recommended_next_step
sections
```

All packages keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
approval_gate_issued: false
approval_command_generated: false
final_dynamic_preflight_required: true
dry_run_only: true
```

## Ready Handoff Meaning

Ready means:

```text
handoff_status: READY_FOR_APPROVAL_HANDOFF_REVIEW
eligible_for_operator_review: true
allowed_for_live: false
approval_gate_issued: false
approval_command_generated: false
recommended_next_step: prepare_future_approval_gate_in_separate_step_no_post
```

This only means the sanitized package can be reviewed before a future approval
gate design. It does not issue an approval gate, does not generate approval
text, and does not authorize live POST.

## Blocked Handoff Meaning

Blocked means:

```text
handoff_status: BLOCKED_HANDOFF
eligible_for_operator_review: false
allowed_for_live: false
approval_gate_issued: false
approval_command_generated: false
recommended_next_step: fix_operator_review_blockers_no_post
```

Operator review blocked reasons and handoff-level blocked reasons are preserved
for human inspection. A blocked handoff means do not proceed.

## Display Allowed Fields

The handoff package explicitly allows only sanitized identifiers and status
fields before any future approval gate:

```text
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
executionType
operator_review_status
eligible_for_operator_review
allowed_for_live=false
approval_gate_required=true
approval_gate_issued=false
approval_command_generated=false
final_dynamic_preflight_required=true
blocked_reasons
recommended_next_step
```

## Display Forbidden Fields

The handoff package records forbidden labels so the future approval gate layer
does not accidentally display unsafe data:

```text
API key value
secret value
signature value
headers value
raw request
raw response
order ID
execution ID
position ID
clientOrderId
request URL
open price
detailed P/L
approval_id
approval command
```

Step 5I does not generate `approval_id` or approval command text. Those belong
only to a future separate step after fresh preflight.

## Final Dynamic Preflight Items

Future approval-gated execution must still re-check:

```text
API key / secret presence: set/missing only
account/assets: success
open_positions_count=0
active_orders_count=0
USD_JPY minOpenOrderSize=100
USD_JPY sizeStep=1
public ticker bid/ask retrieval success
spread_jpy <= 0.01
ticker_age_seconds within threshold
market window allowed
maintenance=false
important_event_window_ok=true
ledger unused
daily/session attempt count within policy
previous result confirmed
result_unknown=false
Git clean
tests pass
ruff pass
secret scan pass
raw_response_saved=false
raw_response_displayed=false
outbound body allowlist matches
request body == signing body
final_preflight_age <= 30 seconds
```

Step 5I records this list only. It does not run final dynamic preflight.

## Markdown Rendering

`render_live_order_approval_handoff_markdown()` renders only sanitized fields.
It includes these warnings:

```text
This approval handoff is dry-run only.
This handoff is not an approval gate.
This handoff does not generate approval_id or approval command.
This handoff does not authorize live POST.
allowed_for_live=false.
```

Rendered Markdown includes dry-run ids, source references, candidate summary,
safety flags, display allowed fields, display forbidden labels, final dynamic
preflight item names, blocked reasons, and recommended next step. It excludes
credential values, raw response values, request data values, and execution
identifier values.

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
- Approval handoff package does not issue an approval gate.
- Approval handoff package does not generate approval command text.
- Approval handoff package does not read account, order, position, ledger, or API state.
- Any future approval gate must be a separate explicit step.

## Relationship to Future Approval Gate

Step 5I can feed a future approval gate design. It cannot authorize live order
execution by itself. Any later approval gate must be a separate task with fresh
preflight, one-shot ledger protection, exact approval text, final dynamic
preflight, and explicit user risk acknowledgement.

Step 5J was later implemented in [STEP5J_APPROVAL_GATE_DESIGN.md](STEP5J_APPROVAL_GATE_DESIGN.md).
It converts this handoff package into a fake approval gate design only. Step 5J
uses a placeholder approval id, a non-copyable template, TTL/exact-match design
flags, and final dynamic preflight boundaries, while still preserving
`allowed_for_live=false` and avoiding any real approval gate or live POST.

## Tests

Added tests cover:

- ready operator review to ready approval handoff package
- fixed `allowed_for_live=false`
- fixed human approval and approval gate requirements
- fixed `approval_gate_issued=false`
- fixed `approval_command_generated=false`
- fixed final dynamic preflight requirement
- fixed dry-run-only behavior
- blocked operator review
- preserved blocked reasons
- live-allowed operator review failure
- dry-run flag failure
- missing human approval and approval gate requirements
- unsupported symbol, side, size, and execution type
- display allowed field list
- display forbidden field list
- final dynamic preflight item list
- Markdown dry-run / no approval gate / no approval id / no live POST warnings
- absence of forbidden actual values
- no dependency on HTTP clients, Private API, broker code, live runner code, or approval gate builders

## Handoff Summary

Step 5I adds the sanitized approval handoff package layer after Step 5H operator
review procedures. A ready handoff is a human-readable dry-run package only. It
preserves `allowed_for_live=false`, keeps `approval_gate_issued=false`, keeps
`approval_command_generated=false`, avoids approval gate issuance, avoids API
and ledger access, and never permits live POST.

The next step may design an approval gate, but it must remain a separate task
with fresh preflight. Step 5I itself does not generate approval ids or approval
commands.

Step 5J now provides that fake approval gate design layer. It still does not
issue real approval ids, does not generate a real approval command, does not
copy approval text, and does not authorize live POST.

Step 5K now provides the fake approval gate preview layer for that design. It
still does not issue real approval ids, does not generate a real approval
command, does not copy approval text, does not write approval text to a file,
and does not authorize live POST.

Step 5L now provides the fake approval validation simulator layer for that
preview. It still does not issue real approval ids, does not generate a real
approval command, does not copy or write approval text, does not authorize final
dynamic preflight, and does not authorize live POST.

Step 5M now adds the final dynamic preflight dry-run model. Approval handoff
packages remain non-executable review material; Step 5M keeps approval gate
issuance, approval id generation, approval command generation, and live POST
outside this phase.
