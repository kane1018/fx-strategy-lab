# Step 5H Operator Review Procedure

## Summary

Step 5H adds a sanitized operator review procedure for a Step 5G
`ReviewGatedSessionBundle`.

This step is no POST. An operator review procedure is not an order, not an
approval, not an approval gate, and not permission to create an approval
command.

## Scope

Implemented scope:

- sanitized `LiveOrderOperatorReviewProcedure`
- sanitized `LiveOrderOperatorReviewChecklistItem`
- fail-closed `build_live_order_operator_review_procedure`
- deterministic dry-run operator review id generation
- sanitized Markdown rendering
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5H does not:

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
- create frontend UI, scheduler, cron, or automation

## Input: ReviewGatedSessionBundle

The input bundle must already be a Step 5G dry-run operation bundle:

```text
bundle_status: READY_FOR_OPERATOR_REVIEW
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
remaining_sessions_today: >= 1
remaining_daily_size: >= 100
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

Blocked bundles, unsupported symbols, unsupported side, unsupported size,
unsupported execution type, missing capacity, insufficient capacity,
live-allowed bundles, and non-dry-run bundles fail closed.

## Output: LiveOrderOperatorReviewProcedure

The procedure contains only sanitized dry-run review fields:

```text
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
bundle_status
risk_gate_passed
policy_passed
eligible_for_operator_review
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
blocked_reasons
remaining_sessions_today
remaining_daily_size
checklist_items
recommended_next_step
```

All procedures keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

## Ready Operator Review Meaning

Ready means:

```text
operator_review_status: READY_FOR_OPERATOR_CHECKLIST
eligible_for_operator_review: true
allowed_for_live: false
recommended_next_step: operator_checklist_review_no_post
```

This only means the bundle can be reviewed by a human operator as a dry-run
checklist. It does not authorize live POST and does not authorize approval gate
issuance.

## Blocked Operator Review Meaning

Blocked means:

```text
operator_review_status: BLOCKED_OPERATOR_REVIEW
eligible_for_operator_review: false
allowed_for_live: false
recommended_next_step: fix_bundle_blockers_no_post
```

Bundle blocked reasons and procedure-level blocked reasons are preserved for
human inspection. A blocked operator review means do not proceed.

## Checklist Items

Ready checklist items include:

- Confirm this is dry-run review only
- Confirm this is not an approval gate
- Confirm this does not authorize live POST
- Review symbol / side / size / executionType
- Review risk gate status
- Review session policy status
- Review remaining session capacity
- Review remaining daily size capacity
- Review blocked reasons if any
- Confirm future approval gate is a separate Step
- Confirm future final dynamic preflight is a separate Step

Blocked checklist items include:

- Review blocked reasons
- Fix or wait until blockers are cleared
- Do not proceed to approval gate
- Do not proceed to live POST

## Markdown Rendering

`render_live_order_operator_review_markdown()` renders only sanitized fields.
It includes these warnings:

```text
This operator review is dry-run only.
This review is not an approval gate.
This review does not authorize live POST.
allowed_for_live=false.
```

Rendered Markdown includes dry-run ids, source references, candidate summary,
bundle status, risk gate status, session policy status, blocked reasons,
remaining capacity, checklist items, and recommended next step. It excludes
credentials, raw responses, request data, and execution identifiers.

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Operation bundle does not directly POST.
- Operator review procedure does not directly POST.
- Operator review procedure does not issue an approval gate.
- Operator review procedure does not read account, order, position, ledger, or API state.
- Any future approval gate must be a separate explicit step.

## Relationship to Future Approval Gate

Step 5H can feed a future human review or approval design. It cannot authorize
live order execution by itself. Any later approval gate must be a separate task
with fresh preflight, one-shot ledger protection, exact approval text, final
dynamic preflight, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- ready bundle to ready operator checklist
- fixed `allowed_for_live=false`
- fixed human approval and approval gate requirements
- fixed dry-run-only behavior
- blocked bundle
- preserved blocked reasons
- live-allowed bundle failure
- dry-run flag failure
- missing human approval and approval gate requirements
- unsupported symbol, side, size, and execution type
- missing remaining session capacity
- missing remaining daily size capacity
- no remaining sessions
- insufficient remaining daily size
- ready checklist dry-run / no approval / no live POST items
- blocked checklist do-not-proceed items
- Markdown dry-run / no approval / no live POST warnings
- Markdown checklist display
- absence of credential, raw response, and identifier fields
- no dependency on HTTP clients, Private API, broker code, or live runner code

## Handoff Summary

Step 5H adds the sanitized operator review checklist layer after Step 5G
operation bundles. A ready operator review is a human-readable dry-run
procedure only. It preserves `allowed_for_live=false`, avoids approval gate
issuance, avoids API and ledger access, and never permits live POST.

The next step may design what happens after a human finishes this checklist,
but it must remain no POST unless a separate future task explicitly introduces
fresh preflight, approval gate, final dynamic preflight, and one-shot execution
controls.
