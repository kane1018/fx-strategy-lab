# Step 5F Review-gated Session Policy

## Step 5T Update

Step 5T preserves the session policy boundary. Even with ready upstream
evidence, the generation package keeps `allowed_for_live=false` and requires a
future explicit real approval gate generation step. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

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

Step 5G was later implemented in
[STEP5G_REVIEW_GATED_SESSION_BUNDLE.md](STEP5G_REVIEW_GATED_SESSION_BUNDLE.md).
It combines a Step 5E review report and Step 5F session policy decision into a
sanitized dry-run operation bundle. A ready bundle still keeps
`allowed_for_live=false`, does not issue approval gates, and does not permit
live POST.

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

Step 5G now provides that display/operation bundle layer as a sanitized dry-run
report only. It preserves the no POST and no approval gate boundary.

Step 5H now converts the Step 5G operation bundle into a sanitized operator
review checklist. The checklist is still dry-run only, keeps
`allowed_for_live=false`, and does not issue approval gates or permit live POST.

Step 5I now converts the operator checklist into a sanitized approval handoff
package. The package is still dry-run only, keeps `approval_gate_issued=false`
and `approval_command_generated=false`, and does not permit live POST.

Step 5J now converts that handoff into a fake approval gate design. The design
is still dry-run only, keeps `approval_gate_issued=false`,
`approval_id_generated=false`, `approval_command_generated=false`, and
`approval_command_copyable=false`, and does not permit live POST.

Step 5K now converts that design into a fake approval gate preview and
validation dry-run. The preview is still dry-run only, keeps
`approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, and `approval_command_copyable=false`, does
not use clipboard or file output, and does not permit live POST.

Step 5L now converts that preview into a fake approval validation simulation.
The simulation is still dry-run only, validates fake/template-only input,
keeps `approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, does not authorize final dynamic preflight,
and does not permit live POST.

Step 5M now adds the final dynamic preflight dry-run model. Session policy pass
remains review-session eligibility only; Step 5M adds another fail-closed
sanitized boundary and still does not execute preflight, issue approval, or
permit live POST.

Step 5N now adds the one-shot live boundary dry-run model. Session policy pass
and final dynamic preflight pass can feed the boundary as sanitized references
only; Step 5N still performs no API call, no approval issuance, no POST, and no
live permission.

Step 5O now adds the one-shot execution runbook dry-run model. Session policy
decisions can feed the runbook as sanitized references only; Step 5O still
performs no API call, no approval issuance, no POST, and no live permission.

Step 5P now adds the E2E dry-run chain review model. Session policy decisions
are checked as one stage in the Step 5B through Step 5O sanitized chain. The
review verifies stage/status, ID, order-shape, source signal, safety flag, and
one-shot constraint consistency, keeps `allowed_for_live=false`, and does not
call APIs, issue approval, generate approval commands, call `live_order_once`,
or execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. Session policy
decisions remain planning inputs only; Step 5R defines the future approval
sequence and one-shot boundary without issuing approval, running preflight,
calling APIs, calling `live_order_once`, or allowing live POST.

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
