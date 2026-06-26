# Step 5E Candidate Review Report

## Summary

Step 5E adds a sanitized review/reporting model for Step 5B
`LiveOrderCandidate`, Step 5C `LiveOrderCandidateRiskDecision`, and Step 5D
`LiveOrderCandidateTraceRecord`.

This step is no POST. The review report is not an order, not an approval gate,
and not live execution permission.

## Scope

Implemented scope:

- sanitized `LiveOrderCandidateReviewReport`
- sanitized `LiveOrderCandidateReviewSection`
- sanitized `LiveOrderCandidateReviewBuildResult`
- fail-closed `build_live_order_candidate_review_report`
- deterministic local review id generation
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5E does not:

- execute HTTP POST
- create, add, close, cancel, or change an order
- issue an approval id
- issue or display an approval gate
- display an approval command
- call the one-shot live runner
- connect to read-only API, Private API, or broker code
- read or write a ledger
- read `.env` or environment secrets
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, position, or client order identifiers
- create frontend UI

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

## Input: LiveOrderCandidateTraceRecord

The trace record must be the Step 5D output linking the candidate, risk
decision, and sanitized source references:

```text
trace_id
candidate_id
risk_decision_id
source_signal_id
source_type
strategy_name
paper_trade_ref
shadow_run_ref
trace_status
eligible_for_human_review
allowed_for_live: false
approval_gate_required: true
dry_run_only: true
blocked_reasons
recommended_next_step
```

## Output: LiveOrderCandidateReviewReport

The review report keeps only sanitized review fields:

```text
review_id
created_at
candidate_id
risk_decision_id
trace_id
source_signal_id
source_type
strategy_name
paper_trade_ref
shadow_run_ref
symbol
side
size
execution_type
candidate_status
risk_status
trace_status
review_status
risk_gate_passed
eligible_for_human_review
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
blocked_reasons
summary
recommended_next_step
sections
```

All review reports keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

## Ready Review Meaning

Ready review means:

```text
review_status: READY_FOR_HUMAN_REVIEW
risk_gate_passed: true
eligible_for_human_review: true
allowed_for_live: false
recommended_next_step: show_to_user_for_review_no_post
```

This only means the sanitized report may be shown to a human for inspection. It
does not issue an approval gate and does not permit live POST.

## Blocked Review Meaning

Blocked review means:

```text
review_status: BLOCKED_REVIEW
risk_gate_passed: false
eligible_for_human_review: false
allowed_for_live: false
recommended_next_step: fix_blocked_reasons_no_post
```

Blocked reasons from the risk decision and trace record are merged so a human
can see why the report is not ready.

## Markdown Rendering

`render_live_order_candidate_review_markdown()` renders only sanitized fields.
It includes these warnings:

```text
This review report is dry-run only.
This report is not an approval gate.
This report does not authorize live POST.
allowed_for_live=false.
```

Rendered Markdown includes dry-run ids, source references, symbol, side, size,
status values, blocked reasons, and recommended next step. It excludes
credentials, raw responses, request data, and execution identifiers.

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Review report does not issue an approval gate.
- Review report does not read account, order, position, ledger, or API state.
- Any future approval gate must be a separate explicit step.

## Relationship to Future Approval Gate

Step 5E can feed a future human review surface. It cannot authorize live order
execution by itself. Any later approval gate must be a separate task with fresh
preflight, one-shot ledger protection, exact approval text, and explicit user
risk acknowledgement.

Step 5F adds a review-gated session policy layer after this review report. Step
5F policy pass still keeps `allowed_for_live=false`; it only means a future
review-gated session design may be considered without POST.

Step 5G was later implemented in
[STEP5G_REVIEW_GATED_SESSION_BUNDLE.md](STEP5G_REVIEW_GATED_SESSION_BUNDLE.md).
It combines this review report with the Step 5F session policy decision into a
sanitized operation bundle for human inspection only. It still keeps
`allowed_for_live=false` and does not issue approval gates or permit live POST.

## Tests

Added tests cover:

- ready candidate + passed risk decision + ready trace
- blocked risk decision
- blocked trace
- merged blocked reasons
- candidate id mismatch
- risk decision id mismatch
- missing trace id
- live-allowed flag failures
- dry-run flag failures
- missing human approval and approval gate requirements
- unsupported symbol, side, size, and execution type
- fixed `allowed_for_live=false`
- Markdown dry-run / no approval / no live POST warnings
- absence of credential, raw response, and identifier fields
- no dependency on HTTP clients, Private API, broker code, or live runner code

## Handoff Summary

Step 5E adds the sanitized report layer for candidate review. It turns
candidate / risk decision / trace data into a human-readable dry-run report,
while preserving `allowed_for_live=false` and avoiding approval gate issuance,
API access, ledger access, and live POST.

Step 5F follows this layer with dry-run session constraints. It does not connect
the review report directly to approval gate issuance or live POST.

Step 5G follows with a dry-run operation bundle that summarizes review status,
policy status, blocked reasons, and remaining capacity without creating an
approval gate or live POST path.
