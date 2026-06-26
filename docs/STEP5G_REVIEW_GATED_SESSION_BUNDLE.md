# Step 5G Review-gated Session Bundle

## Summary

Step 5G adds a sanitized operation bundle model for combining a Step 5E
`LiveOrderCandidateReviewReport` and a Step 5F
`ReviewGatedSessionPolicyDecision`.

This step is no POST. A ready bundle is not live order permission, not an
approval gate, and not permission to create an approval command.

## Scope

Implemented scope:

- sanitized `ReviewGatedSessionBundle`
- fail-closed `build_review_gated_session_bundle`
- deterministic dry-run bundle id generation
- sanitized Markdown rendering
- remaining session and remaining daily size calculations
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5G does not:

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

## Input: LiveOrderCandidateReviewReport

The review report must already be a Step 5E dry-run report:

```text
review_status: READY_FOR_HUMAN_REVIEW
eligible_for_human_review: true
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

Blocked reviews, unsupported symbols, unsupported side, unsupported size,
unsupported execution type, live-allowed reports, and non-dry-run reports fail
closed.

## Input: ReviewGatedSessionPolicyDecision

The session policy decision must already be a Step 5F dry-run decision:

```text
status: POLICY_PASSED_FOR_REVIEW
policy_passed: true
eligible_for_review_session: true
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

Blocked policy decisions can still be represented in a bundle, but the bundle is
blocked and cannot become an operator review candidate.

## Output: ReviewGatedSessionBundle

The bundle contains only sanitized dry-run operation fields:

```text
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
review_status
policy_status
risk_gate_passed
eligible_for_human_review
policy_passed
eligible_for_review_session
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
blocked_reasons
session_size
session_count_today
max_sessions_per_day
remaining_sessions_today
daily_live_size_total
max_daily_size_total
remaining_daily_size
min_minutes_between_sessions
minutes_since_last_session
next_session_time_hint
recommended_next_step
```

All bundles keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

## Ready Bundle Meaning

Ready means:

```text
bundle_status: READY_FOR_OPERATOR_REVIEW
eligible_for_review_session: true
allowed_for_live: false
recommended_next_step: operator_review_no_post
```

This only means the sanitized review report and session policy decision can be
shown together as a dry-run operator review bundle. It does not authorize live
POST and does not authorize approval gate issuance.

## Blocked Bundle Meaning

Blocked means:

```text
bundle_status: BLOCKED_BUNDLE
eligible_for_review_session: false
allowed_for_live: false
recommended_next_step: fix_blocked_reasons_no_post
```

Review blocked reasons, policy blocked reasons, and bundle-level mismatch or
capacity reasons are merged for human inspection.

## Remaining Capacity

Step 5G calculates:

```text
remaining_sessions_today = max_sessions_per_day - session_count_today
remaining_daily_size = max_daily_size_total - daily_live_size_total
```

Unknown, missing, or negative remaining capacity blocks the bundle. The bundle
does not fetch this state itself; a future preflight/review layer must supply
sanitized counts.

## Markdown Rendering

`render_review_gated_session_bundle_markdown()` renders only sanitized fields.
It includes these warnings:

```text
This operation bundle is dry-run only.
This bundle is not an approval gate.
This bundle does not authorize live POST.
allowed_for_live=false.
```

Rendered Markdown includes dry-run ids, source references, candidate status,
review status, policy status, blocked reasons, remaining session capacity,
remaining daily size capacity, and recommended next step. It excludes
credentials, raw responses, request data, and execution identifiers.

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Operation bundle does not directly POST.
- Operation bundle does not issue an approval gate.
- Operation bundle does not read account, order, position, ledger, or API state.
- Any future approval gate must be a separate explicit step.

## Relationship to Future Approval Gate

Step 5G can feed a future operator review or approval design. It cannot
authorize live order execution by itself. Any later approval gate must be a
separate task with fresh preflight, one-shot ledger protection, exact approval
text, final dynamic preflight, and explicit user risk acknowledgement.

Step 5H was later implemented in
[STEP5H_OPERATOR_REVIEW_PROCEDURE.md](STEP5H_OPERATOR_REVIEW_PROCEDURE.md). It
converts a Step 5G bundle into a sanitized operator checklist for review only.
The checklist keeps `allowed_for_live=false`, does not issue approval gates, and
does not permit live POST.

## Tests

Added tests cover:

- ready review report + passed session policy decision
- fixed `allowed_for_live=false`
- fixed human approval and approval gate requirements
- fixed dry-run-only behavior
- blocked review report
- blocked session policy decision
- merged blocked reasons
- review id mismatch
- live-allowed flag failures
- dry-run flag failures
- missing human approval and approval gate requirements
- unsupported symbol, side, size, and execution type
- remaining sessions calculation
- remaining daily size calculation
- missing capacity inputs
- negative remaining capacity inputs
- Markdown dry-run / no approval / no live POST warnings
- Markdown remaining capacity display
- absence of credential, raw response, and identifier fields
- no dependency on HTTP clients, Private API, broker code, or live runner code

## Handoff Summary

Step 5G adds the sanitized operation bundle layer after Step 5E review reports
and Step 5F session policy decisions. A ready bundle is a human-readable
dry-run operation report only. It preserves `allowed_for_live=false`, avoids
approval gate issuance, avoids API and ledger access, and never permits live
POST.

Step 5H now provides the human operator checklist layer for this bundle. It
remains no POST and no approval gate. Any future live task still requires fresh
preflight, approval gate, final dynamic preflight, and one-shot execution
controls as a separate explicit step.
