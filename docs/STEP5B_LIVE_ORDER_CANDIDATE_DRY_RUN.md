# Step 5B Live Order Candidate Dry-run Model

## Summary

Step 5B adds a dry-run-only model that converts a sanitized strategy signal into
a `LiveOrderCandidate` review object.

This is not an order, not an approval gate, not a risk gate implementation, and
not a live runner connection. The candidate is evidence for later review only.

## Scope

Implemented scope:

- `StrategySignalInput`
- `LiveOrderCandidate`
- `LiveOrderCandidateBuildResult`
- deterministic dry-run candidate id generation
- BUY / SELL / NO_TRADE conversion rules
- blocked result handling for unsafe or incomplete strategy signals
- unit tests and no-order guard coverage

## What this step does not do

Step 5B does not:

- execute HTTP POST
- create a new order
- add to a position
- close a position
- cancel or change an order
- issue an approval id
- issue an approval gate
- display an approval command
- call the one-shot live runner
- connect to Private API
- call broker code
- read or write a ledger
- display or store credential values
- display or store raw requests or raw responses
- display or store order, execution, or position identifiers

## Input: StrategySignalInput

`StrategySignalInput` is a sanitized input object. It carries only strategy
evidence and references:

```text
source_signal_id
source_type
strategy_name
symbol
side
confidence
rationale
created_at
expires_at
market_snapshot_ref
paper_trade_ref
shadow_run_ref
```

Supported side values:

```text
BUY
SELL
NO_TRADE
```

The existing strategy engine's `hold` value is normalized to `NO_TRADE` for this
dry-run boundary.

## Output: LiveOrderCandidate

For valid BUY or SELL signals, Step 5B produces a non-executable
`LiveOrderCandidate`:

```text
candidate_id
created_at
expires_at
source_signal_id
source_type
strategy_name
symbol
side
size
execution_type
rationale
confidence
market_snapshot_ref
paper_trade_ref
shadow_run_ref
requires_human_approval
allowed_for_live
dry_run_only
status
blocked_reason
risk_gate_required
approval_gate_required
```

The local field `execution_type` represents the review value
`executionType=MARKET`. It is not an executable request body.

## Candidate Status Rules

BUY:

```text
symbol: USD_JPY
side: BUY
size: 100
executionType: MARKET
status: REVIEW_REQUIRED
allowed_for_live: false
```

SELL:

```text
symbol: USD_JPY
side: SELL
size: 100
executionType: MARKET
status: REVIEW_REQUIRED
allowed_for_live: false
```

NO_TRADE:

```text
status: BLOCKED
blocked_reason: no_trade_signal
candidate: none
allowed_for_live: false
```

Unsupported symbol:

```text
status: BLOCKED
blocked_reason: unsupported_symbol
candidate: none
allowed_for_live: false
```

Invalid confidence:

```text
status: BLOCKED
blocked_reason: invalid_confidence
candidate: none
allowed_for_live: false
```

Missing rationale:

```text
status: BLOCKED
blocked_reason: missing_rationale
candidate: none
allowed_for_live: false
```

## Safety Defaults

All Step 5B results keep these defaults:

```text
allowed_for_live: false
requires_human_approval: true
risk_gate_required: true
approval_gate_required: true
dry_run_only: true
```

Step 5B never returns `allowed_for_live=true`.

## Do-Not-Cross Boundaries

- Strategy signal does not execute a live order.
- Strategy signal does not call a live runner.
- Paper trading does not directly trigger live execution.
- Shadow run output does not directly trigger live execution.
- A candidate is not an approval.
- A candidate is not a risk gate pass.
- A candidate is not an executable request body.
- A candidate must not contain credential, header, signature, raw request, raw
  response, order id, execution id, position id, broker response, or live result
  fields.

## Relationship to Step 5C Risk Gate

Step 5B produces only a review candidate or a blocked result. Step 5C should
implement the risk gate that decides whether a candidate may move to a later
human approval review.

Step 5C must still remain no POST unless a later task explicitly changes scope.

Step 5C was later implemented in
[STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md](STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md).
The risk gate evaluates a candidate plus sanitized risk snapshot, fails closed
on unsafe or unknown input, and keeps `allowed_for_live=false` even when
`eligible_for_human_review=true`.

Step 5D was later implemented in
[STEP5D_CANDIDATE_TRACE_RECORD.md](STEP5D_CANDIDATE_TRACE_RECORD.md). The trace
record links the candidate and risk decision back to sanitized Paper / Shadow /
Strategy source references for review/reporting only. It keeps
`allowed_for_live=false` and does not issue approval gates or permit live POST.

Step 5E was later implemented in
[STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md). The
review report renders candidate / risk decision / trace data for human
inspection only, keeps `allowed_for_live=false`, and still does not issue
approval gates or permit live POST.

## Tests

Added tests cover:

- BUY and SELL candidate creation
- NO_TRADE blocking
- unsupported symbol blocking
- invalid confidence blocking
- missing rationale blocking
- fixed safety defaults
- deterministic `LOCAND-` candidate id
- absence of credential, raw response, and identifier fields
- no dependency on live runner, Private API, or broker code

## Handoff Summary

Step 5B creates a dry-run-only bridge from strategy signal evidence to a
non-executable live-order candidate. Valid BUY and SELL signals become
`REVIEW_REQUIRED` candidates for USD_JPY 100 units and MARKET review type.
NO_TRADE and unsafe inputs become blocked results. Every result keeps
`allowed_for_live=false`, requires a later risk gate, and requires a later human
approval gate.

Step 5C now provides that risk gate, Step 5D now provides the sanitized trace
record, Step 5E now provides the sanitized review report, and Step 5F now
provides the dry-run review-gated session policy. None of these steps issues
approval gates or permits live POST.
