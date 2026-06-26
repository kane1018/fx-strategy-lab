# Step 5F Review-gated Session Policy

## Summary

Step 5F adds a fail-closed policy model for deciding whether a sanitized Step 5E
review report and sanitized session snapshot may proceed to a future
review-gated session design.

This step is no POST. A policy pass is not live order permission, not an
approval gate, and not permission to create an approval command.

## Scope

Implemented scope:

- sanitized `ReviewGatedSessionPolicySnapshot`
- sanitized `ReviewGatedSessionPolicyDecision`
- fail-closed `evaluate_review_gated_session_policy`
- deterministic local policy decision id generation
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5F does not:

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

## Input: ReviewGatedSessionPolicySnapshot

The snapshot contains sanitized facts supplied by a future preflight/review
workflow. It does not fetch API state and does not read a ledger.

```text
snapshot_id
created_at
policy_date
initial_micro_live_completed
previous_order_result_confirmed
previous_result_unknown
open_positions_count
active_orders_count
session_count_today
daily_live_size_total
last_session_completed_at
minutes_since_last_session
session_size
max_sessions_per_day
min_minutes_between_sessions
max_daily_size_total
git_clean
tests_passed
ruff_passed
secret_scan_passed
raw_response_saved
raw_response_displayed
market_window_allowed
maintenance_active
important_event_window_ok
```

Default policy constants:

```text
session_size: 100
max_sessions_per_day: 2
min_minutes_between_sessions: 120
max_daily_size_total: 200
```

## Output: ReviewGatedSessionPolicyDecision

The decision keeps only sanitized policy fields:

```text
decision_id
review_id
candidate_id
status
policy_passed
eligible_for_review_session
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
session_size
max_sessions_per_day
min_minutes_between_sessions
max_daily_size_total
blocked_reasons
reason_summary
recommended_next_step
```

All decisions keep:

```text
allowed_for_live: false
requires_human_approval: true
approval_gate_required: true
dry_run_only: true
```

## Session Policy Rules

Step 5F evaluates:

- initial micro-live completed
- previous order result confirmed
- previous result is not unknown
- `open_positions_count=0`
- `active_orders_count=0`
- max two sessions per policy date
- at least 120 minutes between sessions after the first session
- session size exactly 100
- daily live size total plus session size not above 200
- Git clean
- tests passed
- ruff passed
- secret scan passed
- raw response not saved
- raw response not displayed
- market window allowed
- maintenance inactive
- important event window confirmed

## Pass Meaning

Policy pass means:

```text
status: POLICY_PASSED_FOR_REVIEW
policy_passed: true
eligible_for_review_session: true
allowed_for_live: false
recommended_next_step: proceed_to_review_gated_session_design_no_post
```

This only means the sanitized inputs can move to a future review-gated session
design step. It does not authorize live POST and does not authorize approval
gate issuance.

## Blocked Meaning

Blocked means:

```text
status: BLOCKED
policy_passed: false
eligible_for_review_session: false
allowed_for_live: false
recommended_next_step: fix_session_policy_inputs_no_post
```

Multiple blocked reasons are returned when multiple conditions fail.

## Fail-closed Rules

Unknown, missing, `None`, type-invalid, unsafe, or unsupported inputs block the
policy decision. Step 5F intentionally treats incomplete session state as
unsafe.

## Do-Not-Cross Boundaries

- Strategy signal does not directly POST.
- Candidate does not directly POST.
- Risk decision does not directly POST.
- Trace record does not directly POST.
- Review report does not directly POST.
- Session policy decision does not directly POST.
- Session policy decision does not issue an approval gate.
- Session policy decision does not read account, order, position, ledger, or API state.
- Any future approval gate must be a separate explicit step.

## Relationship to Future Approval Gate

Step 5F can feed a future review-gated session design. It cannot authorize live
order execution by itself. Any later approval gate must be a separate task with
fresh preflight, one-shot ledger protection, exact approval text, final dynamic
preflight, and explicit user risk acknowledgement.

## Tests

Added tests cover:

- safe review report and safe session snapshot
- fixed safety defaults
- blocked review
- unsupported review symbol, side, size, execution type
- initial micro-live not completed
- previous order result not confirmed
- previous result unknown
- open position and active order blockers
- daily session count, interval, session size, and daily size blockers
- Git, tests, ruff, secret scan, raw response blockers
- market, maintenance, and important-event blockers
- missing and invalid session input
- multiple blocked reasons
- no credential, raw response, ID, HTTP client, Private API, broker, or live runner dependency

## Handoff Summary

Step 5F is complete as a dry-run policy layer. The next step may design how to
display or operate a review-gated session, but it must remain no POST unless a
separate future task explicitly introduces fresh preflight, approval gate, and
one-shot execution controls.
