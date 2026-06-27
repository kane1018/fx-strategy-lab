# Step 5A Paper / Shadow / Live Connection Review

## Step 5T Update

Step 5T stays within the reviewed Paper / Shadow / Live separation. It adds a
dry-run real approval gate generation package only, with no live runner
connection, no API connection, no approval gate issuance, and no live POST. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Summary

Step 5A is a design review for connecting existing paper trading, shadow runs,
and live-order verification without crossing into live execution.

This review does not execute HTTP POST, place an order, close a position,
cancel or change an order, issue an approval id, issue an approval gate,
display an approval command, choose BUY or SELL for live trading, reset or edit
a ledger, call Private API endpoints, display credentials, display headers or
signatures, or display raw requests, raw responses, order identifiers,
execution identifiers, or position identifiers.

The recommended next implementation step is Step 5B: strategy signal to
live-order candidate dry-run model. Step 5B should remain no POST.

## Current confirmed state

The Step 4 micro-live verification completed a narrow, bounded path:

```text
new order API success -> user manual settlement -> read-only open positions 0 and active orders 0 confirmed
```

The final verified state from Step 4G-C / Step 4H is:

```text
open_positions_count: 0
active_orders_count: 0
position_status: closed
active_order_status: none
```

Step 4 confirmed one approved USD_JPY 100-unit new-order API connectivity path.
It did not validate strategy-driven live decisions, automatic trading, API
close orders, cancellation, order change, multiple order handling, larger size,
or continuous operation.

## Existing components reviewed

### Paper trading

- `backend/app/services/paper_trade_service.py`
- `backend/app/services/gmo_paper_service.py`
- `backend/app/services/signal_service.py`
- paper-related scripts under `backend/scripts/`

Observed role:

- virtual trading state
- virtual positions and trades
- virtual balance, equity, and P/L
- strategy evaluation over generated or public-market-derived data
- no real order submission
- no Private API requirement in the reviewed paper flow

### Shadow runs

- `backend/app/shadow/models.py`
- `backend/app/shadow/session.py`
- `backend/app/shadow/signals.py`
- `backend/app/shadow/risk.py`

Observed role:

- local-only candidate and risk-decision recording
- public market data snapshots and sanitized risk inputs
- virtual order and virtual result records
- fail-closed risk decisions
- explicit safety flags that reject Private API, API key, raw response, and real
  order behavior
- no broker call and no live order execution

### Live verification

- `backend/app/live_verification/precheck.py`
- `backend/app/live_verification/correlation.py`
- `backend/app/live_verification/intent.py`
- `backend/app/live_verification/dry_run.py`
- `backend/app/live_verification/order_review.py`
- `backend/app/live_verification/broker_boundary.py`
- `backend/app/live_verification/payload_candidate.py`
- `backend/app/live_verification/live_order_preflight.py`
- `backend/app/live_verification/live_order_once.py`
- `backend/app/live_verification/live_order_reject_classification.py`

Observed role:

- read-only precheck modeling
- signal, candidate, risk decision, and precheck ID correlation
- order intent construction only after allow-like risk decision and read-only
  precheck success
- dry-run state machine stopping at order review
- no-network broker boundary checks
- mocked payload candidate construction
- one-shot live runner with exact approval command, final dynamic preflight,
  ledger guard, outbound body allowlist, no retry, no loop, and sanitized result
  reporting

## Paper Trading Role

Paper trading should remain the research and simulation surface.

Allowed responsibilities:

- evaluate strategy behavior against historical, generated, or public market
  data
- create virtual trades and virtual positions
- calculate virtual P/L and performance metrics
- feed summarized outcomes into research reports
- produce candidate evidence for later shadow review

Forbidden responsibilities:

- calling Private API endpoints
- reading API key or secret values
- creating live order payloads
- invoking live-order runners
- opening, closing, canceling, or changing real orders
- authorizing live BUY or SELL decisions

## Shadow Run Role

Shadow runs should remain the local audit and decision-record surface between
research and any live candidate review.

Allowed responsibilities:

- consume public market data snapshots
- record strategy signal references
- record would-be candidate decisions
- apply risk gates and record ALLOW_SHADOW / REJECT_SHADOW style outcomes
- write sanitized events, summary, and metadata under ignored shadow exports
- prove that rejected candidates do not create virtual live results

Forbidden responsibilities:

- sending orders
- calling broker order methods
- reading or storing credentials
- storing raw Private API responses
- creating executable live HTTP requests
- bypassing approval gates

## Live Order Role

Live order code should remain a separate, human-gated, one-shot execution
surface.

Allowed responsibilities:

- receive a reviewed candidate and explicit human approval
- perform fresh read-only preflight before any possible POST
- enforce one-shot ledger state
- enforce outbound body allowlist
- execute at most one HTTP POST only after exact approval and final preflight
- perform read-only reconciliation after the attempt
- stop regardless of result

Forbidden responsibilities:

- autonomous trading
- strategy-signal-direct-to-POST
- retry
- loop
- additional orders
- order change
- cancellation
- close order
- ledger reset to enable another attempt
- raw request or raw response storage

## Proposed Safe Connection Flow

The proposed connection path is:

```text
Market data -> Strategy signal -> Paper / Shadow decision record -> Live order candidate -> Risk gate -> Human approval gate -> Final dynamic preflight -> One-shot live POST -> Read-only reconciliation -> Stop
```

Required interpretation:

- market data may feed paper and shadow systems
- strategy signals may create only candidate records, not orders
- paper and shadow results may provide evidence, not execution authority
- a live order candidate is still non-executable
- the risk gate must pass before human approval is even requested
- human approval does not skip final dynamic preflight
- final dynamic preflight does not permit retry or loop
- one-shot live POST, if ever executed in a future task, must stop immediately
  after read-only reconciliation

## Live Order Candidate Schema Draft

Step 5B should implement a dry-run-only candidate model before any live POST
task is considered.

Draft fields:

```text
candidate_id
source_signal_id
source_type
shadow_run_id
paper_run_id
strategy_name
symbol
side
size
executionType
rationale
risk_inputs
risk_decision
created_at
expires_at
requires_human_approval
status
```

Suggested constraints:

```text
symbol: USD_JPY
size: 100
executionType: MARKET
requires_human_approval: true
status: DRAFT / RISK_REJECTED / READY_FOR_REVIEW / EXPIRED / STOPPED
```

`side` may be stored as a candidate value, but it must not authorize live
execution. A strategy-selected side is only evidence for review. A future live
task still needs explicit user approval and final dynamic preflight.

Forbidden fields for the candidate model:

```text
request_headers
signature
api_key
api_secret
raw_request
raw_response
order_id
execution_id
position_id
broker_response
live_post_result
```

## Required Risk Gate Before Live

Before a candidate can reach an approval gate, the risk gate should require at
least:

```text
account_assets: success
open_positions_count: 0
active_orders_count: 0
symbol_rules_ok: true
minOpenOrderSize: 100
sizeStep_allows_100: true
spread_jpy <= 0.01
market_window_allowed: true
maintenance: false
important_event_ack_required: true
git_clean: true
tests_passed: true
ruff_passed: true
secret_scan_passed: true
one_shot_ledger_unused: true
retry: false
loop: false
result_unknown: false
```

The risk gate should fail closed if any item is unknown, stale, dirty, or
unsafe. A passed risk gate should mean only "ready for human review", not
"ready to POST".

## Explicit Do-Not-Cross Boundaries

- No direct strategy signal -> HTTP POST path.
- No paper trade -> live order path.
- No shadow candidate -> live order path without risk gate and approval gate.
- No live POST before exact human approval.
- No live POST before final dynamic preflight.
- No POST if `open_positions_count > 0`.
- No POST if `active_orders_count > 0`.
- No POST if spread is above threshold.
- No POST if ticker data is missing or stale.
- No POST if Git is dirty.
- No POST if one-shot ledger is used.
- No retry.
- No loop.
- No additional order.
- No order change.
- No cancellation.
- No close order.
- No result-unknown recovery POST.
- No raw request or raw response storage.
- No credential, header, or signature display.

## Gaps and Unknowns

- Strategy-to-candidate conversion is not yet implemented as a first-class
  Step 5 model.
- The candidate schema above is a draft and has no persistence or tests yet.
- Close API behavior remains unverified.
- Continuous monitoring and production recovery rules are out of scope.
- Multi-position and multi-order management are out of scope.
- Larger size is out of scope.
- Strategy quality and profitability are not established by Step 4 or Step 5A.

## Recommended Next Steps

Recommended sequence:

1. Step 5B: implement strategy signal -> live order candidate dry-run model.
   No POST. Completed in
   [STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md](STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md).
2. Step 5C: implement candidate risk gate and fail-closed tests. No POST.
   Completed in
   [STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md](STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md).
3. Step 5D: link paper/shadow decision records to candidate records. No POST.
   Completed in [STEP5D_CANDIDATE_TRACE_RECORD.md](STEP5D_CANDIDATE_TRACE_RECORD.md).
4. Step 5E: render or report candidate review before any approval gate. No POST.
   Completed in [STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md).
5. Step 5F: evaluate review-gated session policy. No POST. Completed in
   [STEP5F_REVIEW_GATED_SESSION_POLICY.md](STEP5F_REVIEW_GATED_SESSION_POLICY.md).
6. Step 5G: combine review report and session policy decision into a sanitized
   operation bundle. No POST. Completed in
   [STEP5G_REVIEW_GATED_SESSION_BUNDLE.md](STEP5G_REVIEW_GATED_SESSION_BUNDLE.md).
7. Step 5H: convert the operation bundle into a sanitized operator checklist.
   No POST. Completed in
   [STEP5H_OPERATOR_REVIEW_PROCEDURE.md](STEP5H_OPERATOR_REVIEW_PROCEDURE.md).
8. Step 5I: convert the operator checklist into a sanitized approval handoff
   package. No POST. Completed in
   [STEP5I_APPROVAL_HANDOFF_PACKAGE.md](STEP5I_APPROVAL_HANDOFF_PACKAGE.md).
9. Step 5J: convert the approval handoff package into a fake approval gate
   design. No POST and no real approval gate. Completed in
   [STEP5J_APPROVAL_GATE_DESIGN.md](STEP5J_APPROVAL_GATE_DESIGN.md).
10. Step 5K: convert the fake approval gate design into a non-copyable preview
   and validation dry-run. No POST, no real approval gate, and no real approval
   command. Completed in [STEP5K_APPROVAL_GATE_PREVIEW.md](STEP5K_APPROVAL_GATE_PREVIEW.md).
11. Step 5L or later: consider a separate real approval gate or one-shot live task only after fresh
   preflight, exact approval gate, final dynamic preflight, and explicit user
   risk approval.

Do not proceed directly to another live POST from Step 5A.

## Handoff Summary

Step 5A completed a docs-only design review. Step 5B then added the first
dry-run-only live-order candidate model, Step 5C added a fail-closed risk gate
for sanitized candidate review eligibility, Step 5D added the sanitized
candidate / risk decision trace record, and Step 5E added the sanitized review
report. Step 5F added the review-gated session policy for evaluating post-
micro-live session constraints without POST. Step 5G added the sanitized
review-gated session operation bundle without POST. Step 5H added the sanitized
operator review checklist without POST. Step 5I added the sanitized approval
handoff package without POST or approval command generation. Paper trading
remains simulation, shadow remains local risk/audit recording, and live order
execution remains a separate human-approved one-shot path. The safe bridge is
candidate-based: strategy and shadow may produce non-executable evidence,
Step 5C may mark a candidate eligible for human review only, Step 5D may record
the review trace only, Step 5E may render a dry-run report only, Step 5F may
evaluate session policy only, Step 5G may render an operation bundle only,
Step 5H may render an operator checklist only, Step 5I may render approval
handoff material only, Step 5J may render a fake approval gate design only,
Step 5K may render a non-copyable approval gate preview and validation dry-run
only, Step 5L may simulate fake/template-only approval validation only, and
only a future separately approved task may perform final dynamic preflight and
at most one live POST.

Step 5M now adds the final dynamic preflight dry-run model. It evaluates only
sanitized snapshot inputs, keeps `allowed_for_live=false`, does not call any
API, does not read or write ledger state, does not issue approval, and does not
permit live POST.

Step 5N now adds the one-shot live boundary dry-run model. It keeps
`allowed_for_live=false`, `post_attempt_limit=1`, `post_executed=false`, no
runner/API/broker/read-only calls, no retry/loop/order mutation flags, no
approval issuance, and no live POST permission.

Step 5O now adds the one-shot execution runbook dry-run model. It packages the
future real approval gate, fresh final dynamic preflight, one-shot HTTP POST,
post reconciliation, and final report sequence as review-only phases. It still
keeps `allowed_for_live=false`, does not issue approval, does not call APIs or
`live_order_once`, and does not execute live POST.

Step 5P now adds the E2E dry-run chain review model. It connects Step 5B
through Step 5O artifacts as sanitized references only, checks stage/status,
ID, symbol, side, size, execution type, source signal, safety flag, and
one-shot constraint consistency, keeps `allowed_for_live=false`, and does not
call APIs, issue approval, generate approval commands, call `live_order_once`,
or execute POST.

Step 5Q now adds the real approval readiness checkpoint model. It consumes the
Step 5P E2E dry-run chain review as sanitized evidence, requires operator
acknowledgements and future-step separation, records go/no-go/stop conditions,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

Step 5R now adds the real approval gate plan dry-run model. It consumes the
Step 5Q readiness checkpoint as sanitized evidence, separates the future fresh
preflight, real approval gate, exact-match approval validation, final dynamic
preflight, one-shot boundary, post reconciliation, and final report phases,
keeps `allowed_for_live=false`, and does not call APIs, issue approval,
generate real approval ids or commands, call `live_order_once`, read/write
ledgers, or execute POST.

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
