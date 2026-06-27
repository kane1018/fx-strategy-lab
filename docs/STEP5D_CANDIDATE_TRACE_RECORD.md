# Step 5D Candidate Trace Record

## Summary

Step 5D adds a dry-run trace record that links sanitized Paper / Shadow /
Strategy signal references to a Step 5B `LiveOrderCandidate` and a Step 5C
`LiveOrderCandidateRiskDecision`.

This step is no POST. The trace record is not an order, not an approval, and not
live execution permission.

## Scope

Implemented scope:

- sanitized `LiveOrderCandidateTraceRecord`
- sanitized `LiveOrderCandidateTraceBuildResult`
- fail-closed `build_live_order_candidate_trace_record`
- deterministic local trace id generation
- candidate / risk decision id matching
- Paper / Shadow / Strategy source reference preservation
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5D does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- issue an approval id
- issue or display an approval gate
- call the one-shot live runner
- connect to Private API
- call broker code
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers

## Input: LiveOrderCandidate

The candidate must already be a Step 5B dry-run candidate:

```text
candidate_id
source_signal_id
source_type
strategy_name
paper_trade_ref
shadow_run_ref
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

Step 5D requires a `source_signal_id` and at least one sanitized Paper / Shadow
reference through `paper_trade_ref`, `shadow_run_ref`, `paper_decision_ref`, or
`shadow_decision_ref`.

## Input: LiveOrderCandidateRiskDecision

The risk decision must be the Step 5C output for the same candidate:

```text
decision_id
candidate_id
status
risk_gate_passed
eligible_for_human_review
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
blocked_reasons
recommended_next_step
```

`candidate.candidate_id` must match `risk_decision.candidate_id`.

## Output: LiveOrderCandidateTraceRecord

The trace record keeps only sanitized review fields:

```text
trace_id
created_at
source_signal_id
source_type
strategy_name
paper_trade_ref
shadow_run_ref
paper_decision_ref
shadow_decision_ref
review_batch_id
candidate_id
risk_decision_id
risk_status
risk_gate_passed
eligible_for_human_review
symbol
side
size
execution_type
candidate_status
trace_status
blocked_reasons
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
recommended_next_step
```

All trace records keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

## Trace Relationship

Step 5D links:

- `source_signal_id`
- `paper_trade_ref` / `paper_decision_ref`
- `shadow_run_ref` / `shadow_decision_ref`
- `candidate_id`
- `risk_decision_id`
- `risk_status`
- `risk_gate_passed`

This allows review and audit tooling to explain which Paper / Shadow /
Strategy evidence produced a candidate and how the risk gate evaluated it.

## Ready-For-Review Meaning

Ready for review means:

```text
trace_status: READY_FOR_REVIEW
risk_gate_passed: true
eligible_for_human_review: true
allowed_for_live: false
recommended_next_step: proceed_to_candidate_review_no_post
```

This only means the candidate can be shown in a later human review/reporting
surface. It does not issue an approval gate and does not permit live POST.

## Blocked Trace Meaning

If Step 5C blocks the risk decision, Step 5D can still create an audit trace:

```text
trace_status: BLOCKED_TRACE_RECORDED
risk_gate_passed: false
eligible_for_human_review: false
allowed_for_live: false
recommended_next_step: fix_risk_inputs_or_wait_no_post
```

The Step 5C blocked reasons are preserved for review. A blocked risk decision is
not human-review eligible.

## Fail-Closed Rules

Trace construction blocks on:

```text
candidate_id_mismatch
candidate_already_allowed_for_live
risk_decision_allows_live
candidate_not_dry_run
risk_decision_not_dry_run
missing_human_approval_requirement
missing_approval_gate_requirement
missing_source_signal_id
missing_paper_shadow_reference
unsupported_symbol
unsupported_side
unsupported_size
unsupported_execution_type
```

Fail-closed trace output keeps:

```text
trace_status: BLOCKED
risk_gate_passed: false
eligible_for_human_review: false
allowed_for_live: false
recommended_next_step: fix_trace_inputs_no_post
```

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Paper output does not directly POST.
- Shadow output does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Trace record does not issue an approval gate.
- Trace record does not read account, order, position, ledger, or API state.
- Any later live path must remain a separate task with fresh preflight,
  one-shot ledger protection, and explicit approval.

## Relationship to Step 5E Review/Reporting

Step 5D prepares the trace model that Step 5E can render or report. Step 5E
should remain no POST and should show sanitized candidate, risk, and trace
relationships without exposing credentials, raw responses, or execution
identifiers.

Step 5E was later implemented in
[STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md). It
renders candidate / risk decision / trace data as a sanitized dry-run review
report only, keeps `allowed_for_live=false`, and does not issue approval gates
or permit live POST.

## Tests

Added tests cover:

- ready trace from valid candidate + passed risk decision + Paper ref
- ready trace from valid candidate + passed risk decision + Shadow ref
- ready trace from both Paper and Shadow refs
- blocked risk decision audit trace
- preservation of risk blocked reasons
- candidate id mismatch
- live-allowed flag failures
- dry-run flag failures
- missing human approval and approval gate requirements
- missing source signal
- missing Paper / Shadow reference
- unsupported symbol, side, size, and execution type
- fixed `allowed_for_live=false`
- absence of credential, raw response, and identifier fields
- no dependency on HTTP clients, Private API, broker code, or live runner code

## Handoff Summary

Step 5D adds the dry-run trace layer between Step 5C risk decisions and a future
Step 5E review/reporting surface. It records how a Paper / Shadow / Strategy
source led to a candidate and risk decision, but it keeps `allowed_for_live=false`
and never issues an approval gate or live POST.

Step 5E now provides that sanitized review report surface, with the same no POST
and no approval gate boundary.

Step 5F now evaluates a sanitized review report plus sanitized session snapshot
against review-gated session policy rules. A Step 5F pass still keeps
`allowed_for_live=false` and does not issue approval gates or permit live POST.

Step 5G now combines the Step 5E review report and Step 5F session policy
decision into a sanitized operation bundle. A ready bundle is operator review
material only; it still keeps `allowed_for_live=false` and does not issue
approval gates or permit live POST.

Step 5H now turns that bundle into a sanitized operator checklist. The checklist
is still review material only, keeps `allowed_for_live=false`, and does not
issue approval gates or permit live POST.

Step 5I now turns the operator checklist into a sanitized approval handoff
package. The package is still review material only, keeps
`approval_gate_issued=false` and `approval_command_generated=false`, and does
not permit live POST.

Step 5J now turns that handoff into a fake approval gate design. The design is
still review material only, uses placeholder approval id and side values, keeps
the fake command template non-copyable, keeps `approval_gate_issued=false`,
keeps `approval_id_generated=false`, keeps `approval_command_generated=false`,
and does not permit live POST.
