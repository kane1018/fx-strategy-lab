# Step 5J Approval Gate Design

## Step 5T Update

Step 5T moves from fake design lineage to a dry-run real approval gate
generation package. It still does not issue the gate, generate the id, generate
the command, copy command text, or authorize POST. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5J adds a fake approval gate design model for a Step 5I
`LiveOrderApprovalHandoffPackage`.

This step is no POST. The design is not an approval gate, not a real approval
id, not a real approval command, and not live execution permission.

## Scope

Implemented scope:

- sanitized `LiveOrderApprovalGateDesign`
- sanitized `LiveOrderApprovalCommandTemplate`
- sanitized `LiveOrderApprovalGateDesignSection`
- fail-closed `build_live_order_approval_gate_design`
- deterministic dry-run design id generation
- fake approval id placeholder
- fake approval command template
- required ACK token list
- approval TTL and exact-match design flags
- display-allowed field list
- display-forbidden field list
- future final dynamic preflight checklist boundary
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5J does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- issue a real approval id
- issue or display a real approval gate
- generate or display a real approval command
- produce a copyable approval command
- copy an approval command to a clipboard
- write an approval command file
- call the one-shot live runner
- connect to read-only API, Private API, or broker code
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI, scheduler, cron, or automation

## Input: LiveOrderApprovalHandoffPackage

The input handoff must already be a Step 5I dry-run package:

```text
handoff_status: READY_FOR_APPROVAL_HANDOFF_REVIEW
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
approval_gate_issued: false
approval_command_generated: false
final_dynamic_preflight_required: true
dry_run_only: true
```

Blocked handoffs, unsupported symbols, unsupported side, unsupported size,
unsupported execution type, live-allowed handoffs, non-dry-run handoffs,
already-issued gates, already-generated approval commands, and missing final
dynamic preflight requirement fail closed.

## Output: LiveOrderApprovalGateDesign

The design contains only sanitized dry-run fields:

```text
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
handoff_status
design_status
eligible_for_operator_review
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
command_template
display_allowed_fields
display_forbidden_fields
final_dynamic_preflight_items
blocked_reasons
recommended_next_step
sections
```

All designs keep:

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

## Ready Design Meaning

Ready means:

```text
design_status: READY_FOR_APPROVAL_GATE_DESIGN_REVIEW
eligible_for_operator_review: true
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
approval_command_template_only: true
approval_command_copyable: false
recommended_next_step: prepare_future_fake_approval_gate_review_no_post
```

This only means the fake approval gate structure can be reviewed. It does not
issue an approval gate, does not generate a real approval id, does not generate
a real approval command, and does not authorize live POST.

## Blocked Design Meaning

Blocked means:

```text
design_status: BLOCKED_APPROVAL_GATE_DESIGN
eligible_for_operator_review: false
allowed_for_live: false
approval_gate_issued: false
approval_id_generated: false
approval_command_generated: false
recommended_next_step: fix_handoff_blockers_no_post
```

Handoff blocked reasons and design-level blocked reasons are preserved for
human inspection. A blocked design means do not proceed.

## Approval ID Placeholder

Step 5J uses only this placeholder:

```text
<APPROVAL_ID_FROM_FUTURE_STEP>
```

It is not an actual approval id. It is not a `STEP4F-` id. Step 5J never
generates a real approval id.

## Approval Command Template

Step 5J uses a fake template prefix:

```text
STEP_APPROVAL_TEMPLATE <APPROVAL_ID_FROM_FUTURE_STEP> SIDE=<SIDE_FROM_FUTURE_STEP> SYMBOL=USD_JPY SIZE=100 ...
```

The template is not a real approval command. It is not copyable. It does not
start with the historical live approval command prefix. It must not be pasted
back as approval. A future real approval gate, if implemented, must be a
separate explicit Step after fresh preflight.

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

Step 5J records these tokens for design review only. It does not collect user
approval and does not validate a real approval command.

## Display Allowed Fields

The design explicitly allows only sanitized identifiers, candidate summary,
status flags, fake template metadata, blocked reasons, and recommended next
step.

## Display Forbidden Fields

The design records forbidden labels so a future approval gate layer does not
accidentally display unsafe data:

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
real approval_id
real approval command
copyable approval command
clipboard approval command
approval command file
```

## Final Dynamic Preflight Boundary

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

Step 5J records this list only. It does not run final dynamic preflight.

## Markdown Rendering

`render_live_order_approval_gate_design_markdown()` renders only sanitized
fields. It includes these warnings:

```text
This approval gate design is dry-run only.
This design is not an approval gate.
This design does not generate a real approval_id.
This design does not generate a real approval command.
This design does not authorize live POST.
allowed_for_live=false.
```

Rendered Markdown includes dry-run ids, source references, candidate summary,
safety flags, fake placeholder values, ACK token names, display allowed fields,
display forbidden labels, final dynamic preflight item names, blocked reasons,
and recommended next step. It excludes credential values, raw response values,
request data values, and execution identifier values.

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
- Approval gate design does not issue an approval gate.
- Approval gate design does not generate a real approval id.
- Approval gate design does not generate a real approval command.
- Approval gate design does not read account, order, position, ledger, or API state.
- Any future real approval gate must be a separate explicit step.

## Relationship to Future Real Approval Gate

Step 5J can feed a future real approval gate implementation review. It cannot
authorize live order execution by itself. Any later approval gate must be a
separate task with fresh preflight, one-shot ledger protection, exact approval
text, final dynamic preflight, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- ready handoff to ready fake approval gate design
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
- blocked handoff
- preserved blocked reasons
- live-allowed handoff failure
- dry-run flag failure
- missing human approval and approval gate requirements
- already-issued approval gate failure
- already-generated approval command failure
- missing final dynamic preflight requirement
- unsupported symbol, side, size, and execution type
- fake approval id placeholder is not a real `STEP4F-` id
- fake approval command template is not a real command and is not copyable
- required ACK tokens
- display allowed field list
- display forbidden field list
- final dynamic preflight item list
- Markdown dry-run / no approval gate / no approval id / no approval command / no live POST warnings
- absence of forbidden actual values
- no dependency on HTTP clients, Private API, broker code, live runner code, or approval gate builders

## Handoff Summary

Step 5J adds the fake approval gate design layer after Step 5I approval handoff
packages. A ready design is a human-readable dry-run design only. It preserves
`allowed_for_live=false`, keeps `approval_gate_issued=false`, keeps
`approval_id_generated=false`, keeps `approval_command_generated=false`, keeps
the fake command template non-copyable, avoids API and ledger access, and never
permits live POST.

The next step may review how a real approval gate would be implemented, but it
must remain a separate task with fresh preflight. Step 5J itself does not
generate approval ids or approval commands.

Step 5K now provides that review layer in
[STEP5K_APPROVAL_GATE_PREVIEW.md](STEP5K_APPROVAL_GATE_PREVIEW.md). It converts
this design into a fake approval gate preview and validation-rule dry-run only.
It keeps `allowed_for_live=false`, keeps the fake command template
non-copyable, avoids real approval id and command generation, avoids clipboard
and file output, and does not authorize live POST.

Step 5L now provides the validation simulation layer in
[STEP5L_APPROVAL_VALIDATION_SIMULATOR.md](STEP5L_APPROVAL_VALIDATION_SIMULATOR.md).
It validates fake/template-only input against the preview rules only. It keeps
`allowed_for_live=false`, avoids real approval id and command generation, avoids
clipboard and file output, does not authorize final dynamic preflight, and does
not authorize live POST.

Step 5M now adds the final dynamic preflight dry-run model. Approval gate design
remains fake/template-only; Step 5M does not turn it into a real approval gate
and does not execute final dynamic preflight.

Step 5N now adds the one-shot live boundary dry-run model. Approval gate design
remains fake/template-only; Step 5N does not turn it into a real approval gate,
does not call the live runner, and does not execute HTTP POST.

Step 5O now adds the one-shot execution runbook dry-run model. Approval gate
design remains fake/template-only; the runbook only describes a future real
approval phase and does not issue approval or execute HTTP POST.

Step 5P now adds the E2E dry-run chain review model. Fake approval gate design
artifacts remain template-only sanitized evidence; Step 5P checks them in the
Step 5B through Step 5O chain, keeps `allowed_for_live=false`, and does not call
APIs, issue real approval, generate approval commands, call `live_order_once`,
or execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. Fake approval gate
design remains template-only evidence; Step 5R plans a future real approval gate
sequence but does not issue a gate, generate a real approval id, generate a real
approval command, call APIs, or execute POST.

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
