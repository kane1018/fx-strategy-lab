# Step 5C Live Order Candidate Risk Gate

## Summary

Step 5C adds a fail-closed risk gate for Step 5B `LiveOrderCandidate`
objects. It evaluates a candidate against a sanitized
`LiveOrderCandidateRiskSnapshot` and returns a
`LiveOrderCandidateRiskDecision`.

This step is no POST. It does not connect to live APIs, Private API, broker
code, approval gates, or ledgers.

## Scope

Implemented scope:

- sanitized `LiveOrderCandidateRiskSnapshot`
- sanitized `LiveOrderCandidateRiskDecision`
- fail-closed `evaluate_live_order_candidate_risk_gate`
- deterministic local risk decision id generation
- unit tests and no-order guard coverage

## What This Step Does Not Do

Step 5C does not:

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
- display or store order, execution, or position identifiers

## Input: LiveOrderCandidate

The candidate must already be a Step 5B dry-run review candidate:

```text
status: REVIEW_REQUIRED
symbol: USD_JPY
side: BUY or SELL
size: 100
execution_type: MARKET
allowed_for_live: false
requires_human_approval: true
risk_gate_required: true
approval_gate_required: true
dry_run_only: true
```

Invalid candidate state blocks the risk decision.

## Input: LiveOrderCandidateRiskSnapshot

The risk snapshot carries sanitized state only:

```text
snapshot_id
created_at
account_assets_success
open_positions_count
active_orders_count
symbol_min_open_order_size
symbol_size_step
spread_jpy
ticker_age_seconds
market_window_allowed
maintenance_active
important_event_window_ok
ledger_unused
daily_live_attempt_count
session_live_attempt_count
result_unknown
git_clean
tests_passed
ruff_passed
secret_scan_passed
raw_response_saved
raw_response_displayed
```

The snapshot is input data only. Step 5C does not fetch account state, ticker
state, public rules, ledger state, Git state, test results, or secret scan
results.

## Output: LiveOrderCandidateRiskDecision

The decision indicates whether the candidate can move to a later human review
step:

```text
decision_id
candidate_id
status
risk_gate_passed
eligible_for_human_review
allowed_for_live
requires_human_approval
approval_gate_required
dry_run_only
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

## Pass Meaning

Pass means:

```text
status: PASSED_FOR_HUMAN_REVIEW
risk_gate_passed: true
eligible_for_human_review: true
allowed_for_live: false
recommended_next_step: proceed_to_candidate_review_no_post
```

Step 5C pass means only "this candidate may move to a later human review
surface." It does not mean live POST is allowed.

## Block Reasons

Candidate reasons include:

```text
invalid_candidate_status
candidate_already_allowed_for_live
candidate_not_dry_run
missing_human_approval_requirement
missing_risk_gate_requirement
missing_approval_gate_requirement
unsupported_symbol
unsupported_side
unsupported_size
unsupported_execution_type
```

Risk snapshot reasons include:

```text
account_assets_unavailable
open_position_exists
active_order_exists
missing_symbol_rules
min_order_size_too_large
size_step_mismatch
missing_spread
spread_too_wide
missing_ticker_age
ticker_too_old
market_window_not_allowed
maintenance_active
important_event_window_not_confirmed
ledger_already_used
daily_attempt_exists
session_attempt_exists
result_unknown_state
git_not_clean
tests_not_passed
ruff_not_passed
secret_scan_not_passed
raw_response_saved
raw_response_displayed
missing_required_risk_input
invalid_risk_input
```

Multiple failures return multiple blocked reasons.

## Fail-Closed Rules

Unknown, missing, invalid, or unsafe input blocks the decision. In block state:

```text
status: BLOCKED
risk_gate_passed: false
eligible_for_human_review: false
allowed_for_live: false
recommended_next_step: fix_inputs_or_wait_no_post
```

## Do-Not-Cross Boundaries

- Strategy signal does not execute a live order.
- Candidate does not execute a live order.
- Risk gate pass does not execute a live order.
- Risk gate pass does not issue an approval gate.
- Paper or shadow output does not directly trigger live execution.
- Approval gate and final dynamic preflight remain separate future steps.

## Relationship to Step 5D/5E

Step 5C feeds Step 5D candidate trace records. Step 5D links the candidate and
risk decision to sanitized Paper / Shadow / Strategy source references for
review and audit only. A Step 5D `READY_FOR_REVIEW` trace still keeps
`allowed_for_live=false` and does not issue an approval gate.

Step 5E was later implemented in
[STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md). It
renders candidate / risk decision / trace data as a sanitized dry-run review
report only. It keeps `allowed_for_live=false` and does not issue approval
gates or permit live POST.

Step 5G and Step 5H now extend this no-POST review path with a sanitized
operation bundle and operator checklist. They keep `allowed_for_live=false`,
do not issue approval gates, and do not permit live POST.

Step 5I now extends the same no-POST path with a sanitized approval handoff
package. It does not issue approval gates, does not generate approval commands,
and does not permit live POST.

Any future live POST path must still require a separate approval gate, final
dynamic preflight, one-shot ledger protection, and explicit user authorization.

## Tests

Added tests cover:

- safe BUY and SELL candidates passing for human review only
- pass decisions keeping `allowed_for_live=false`
- candidate safety flag failures
- account/order state failures
- symbol rule failures
- spread and ticker age failures
- market, maintenance, and event failures
- ledger, attempt, and result unknown failures
- Git, tests, ruff, and secret scan failures
- raw response saved/displayed failures
- missing and invalid risk input failures
- multiple blocked reasons
- absence of credential, raw response, and identifier fields
- no dependency on HTTP clients, Private API, broker code, or live runner code

## Handoff Summary

Step 5C creates a fail-closed risk decision layer between a Step 5B
`LiveOrderCandidate` and any future human review surface. A passed risk decision
means the candidate may move to human review only. It is not live POST
permission, not approval gate issuance, and not final preflight.

Step 5D now records the candidate / risk decision / Paper / Shadow / Strategy
trace relationship for later review/reporting, while preserving the same no
POST and `allowed_for_live=false` boundary.

Step 5E now renders that relationship into a sanitized human-readable report,
again without approval gate issuance or live POST permission.

Step 5F now evaluates that report against review-gated session policy constraints
such as max two sessions per day, at least two hours between sessions, 100-unit
session size, and 200-unit daily cap. It remains no POST and keeps
`allowed_for_live=false`.

Step 5G now turns the Step 5E review report plus Step 5F policy decision into a
sanitized operation bundle with remaining session and daily-size capacity. It
remains no POST, no approval gate, and `allowed_for_live=false`.

Step 5H, Step 5I, and Step 5J now extend the same no-POST path with a sanitized
operator checklist, an approval handoff package, and a fake approval gate design.
Step 5J still uses placeholders only, keeps the fake command template
non-copyable, and does not issue a real approval gate or permit live POST.

Step 5K now extends that path with a fake approval gate preview and validation
dry-run. It keeps `allowed_for_live=false`, keeps the template non-copyable,
does not generate a real approval id or command, does not use clipboard or file
output, and does not permit live POST.

Step 5L now extends that path with a fake approval validation simulator. It
checks fake/template-only input and validation-rule outcomes only. It keeps
`allowed_for_live=false`, generates no real approval id or command, issues no
approval gate, runs no final dynamic preflight, and does not permit live POST.

Step 5M now adds the final dynamic preflight dry-run model. Risk decisions still
do not directly POST; Step 5M only evaluates sanitized downstream state and
preflight snapshot values while preserving `allowed_for_live=false`.

Step 5N now adds the one-shot live boundary dry-run model. Risk decisions still
do not directly POST; Step 5N only verifies sanitized one-shot constraints such
as attempt limit, no retry/loop/order mutation flags, body/signing equality,
and reconciliation requirement while preserving `allowed_for_live=false`.

Step 5O now adds the one-shot execution runbook dry-run model. Risk decisions
remain non-executable references in the runbook; Step 5O defines future phases
and stop conditions but does not issue approval, call APIs, call
`live_order_once`, or authorize live POST.

Step 5P now adds the E2E dry-run chain review model. Risk decisions are checked
only as sanitized references in the Step 5B through Step 5O chain; Step 5P
verifies stage/status, ID, order-shape, source signal, safety flag, and
one-shot constraint consistency while preserving `allowed_for_live=false`. It
does not call APIs, issue approval, generate approval commands, call
`live_order_once`, or execute POST.
