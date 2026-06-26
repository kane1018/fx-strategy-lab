# Step 4 Micro-live Completion Review

## Summary

Step 4 micro-live verification is complete as a bounded verification sequence.
It reached:

```text
live order API success -> user manual settlement -> read-only open positions 0 and active orders 0 confirmed
```

This review does not execute HTTP POST, place an order, close a position, cancel
or change an order, issue an approval id, issue an approval gate, reset a
ledger, display credentials, display headers or signatures, display raw
requests or raw responses, or display order, execution, or position identifiers.

The successful live order was a user-specified BUY premise. It was not a
strategy-generated BUY/SELL decision.

## Step 5A Follow-Up

Step 5A completed a docs-only Paper / Shadow / Live connection design review in
[STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md](STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md).

Step 5A did not execute HTTP POST, place or close an order, cancel or change an
order, issue an approval id, issue an approval gate, display an approval
command, choose BUY or SELL for live trading, call Private API endpoints, check
API key or secret presence, reset or edit a ledger, or display raw requests,
raw responses, credentials, headers, signatures, order identifiers, execution
identifiers, or position identifiers.

The recommended next step is Step 5B: strategy signal to live-order candidate
dry-run model. Step 5B should remain no POST.

## Confirmed outcomes

- GMO FX Private API read-only checks can be performed with sanitized output.
- API key and API secret can be handled as `set` / `missing` only.
- USD_JPY 100 units satisfied the public symbol rule used for Step 4.
- The approval gate and exact one-line approval command stopped execution before
  live order submission.
- The approval command was made paste-safe through one-line output and `pbcopy`.
- One USD_JPY 100-unit BUY MARKET order HTTP POST was executed exactly once.
- The live order POST returned sanitized `transport_result=success` and
  `api_status_success=true`.
- Post-order read-only checks confirmed an open position appeared.
- The user then manually closed the position in the GMO Web UI.
- Post-manual-settlement read-only checks confirmed `open_positions_count=0`
  and `active_orders_count=0`.
- Retry, loop, additional order, order change, cancellation, and automatic close
  paths were not used.
- Raw response, headers, signature, credential values, order id, execution id,
  and position id were not displayed or saved.

## Final verified state

```text
open_positions_count: 0
active_orders_count: 0
position_status: closed
active_order_status: none
ledger_state: POST_COMPLETED
attempt_count: 1
result_category: success
```

This final state is based on Step 4G-C read-only confirmation after the user's
manual settlement report.

## What was intentionally not tested

- Strategy-signal-based BUY/SELL automatic decision making.
- API close order execution.
- API cancellation.
- API order change.
- Automatic stop loss.
- Automatic take profit.
- Continuous live operation.
- Multiple live orders.
- Multiple open position management.
- Larger lot sizes.
- Fully automated live trading.
- Production-grade monitoring, stop, and recovery operations.

## Safety boundaries

- The confirmed result is 100-unit new order API connectivity, not a completed
  automated trading system.
- BUY was specified by the user; the strategy system did not choose BUY.
- The close was performed manually by the user in the GMO Web UI.
- Codex did not execute the close API.
- The final read-only state confirmed `open_positions_count=0` and
  `active_orders_count=0`.
- Any next live order requires a separate task and separate explicit approval.
- Any close API verification requires a separate task and separate explicit
  approval.
- No automation work should start while a real-money position is open.
- No HTTP POST may occur without an approval gate.
- The one-task, one-POST maximum remains in force.
- Retry, loop, and additional order remain prohibited unless a future approved
  task explicitly designs a new safe boundary.

## User-side manual settlement

The user reported manually closing the USD_JPY BUY 100-unit position in the GMO
Web UI. Step 4G-C then confirmed through read-only API checks:

```text
manual_settlement_confirmed_by_api: true
position_status: closed
active_order_status: none
```

Codex did not execute a close order.

## Lessons learned

- Long approval phrases are fragile; compact one-line command approval is safer.
- Approval command output should be copy-only, not embedded in explanatory text.
- Exact-match approval, post-approval preflight, and a one-shot ledger are all
  needed; tests alone are not enough for live-adjacent workflows.
- Sanitized read-only checks are enough to confirm key state transitions without
  exposing raw API data or identifiers.
- A successful micro-live new order does not validate close-order behavior,
  strategy decision quality, or automated operations.

## Do-not-cross rules

- Do not reuse this completion review as approval for another live POST.
- Do not convert the micro-live runner into continuous trading.
- Do not increase size beyond 100 units without a separate review.
- Do not test close order API while no controlled 100-unit position exists.
- Do not store raw request, raw response, headers, signatures, credential values,
  order id, execution id, or position id.
- Do not reset or delete the one-shot ledger to enable another same-day attempt.

## Recommended next phases

Recommended order:

1. Candidate A: Paper trading / shadow run to live-order connection design
   review. No POST.
2. Candidate B: Strategy signal produces BUY/SELL candidates but does not place
   orders. No POST.
3. Candidate C: Close API specification review and fake transport
   implementation. No POST.

Do not jump directly to:

- Candidate D: API close micro-live verification.
- Candidate E: Additional small-lot live verification.

Candidate D requires an open 100-unit position, a separate approval gate, and a
one-shot execution design. Candidate E requires a separate date or explicit new
ledger policy, fresh preflight, a separate approval gate, and 100-unit size.

## Requirements before any further live POST

- `open_positions_count=0`.
- `active_orders_count=0`.
- Git clean.
- Relevant tests and ruff pass.
- No secret, raw response, or identifier contamination.
- No raw request or raw response is saved.
- Approval gate design exists.
- One-shot execution design exists.
- Stop-on-unknown design exists.
- Retry and loop remain prohibited.
- User explicitly approves the objective and risk for that specific task.

## Handoff summary

Step 4 micro-live verification has completed the narrow path of one approved
USD_JPY 100-unit BUY order, user manual settlement, and read-only confirmation
that no position or active order remains. This does not authorize automation,
additional live orders, close API execution, larger size, strategy-driven
BUY/SELL decisions, or continuous operation.
