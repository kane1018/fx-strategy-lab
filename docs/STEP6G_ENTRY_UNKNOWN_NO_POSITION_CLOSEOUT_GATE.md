# Step 6G Entry Unknown No-Position Closeout Gate

This document records
`Step 6G-PC-OX-R-ENTRY-UNKNOWN-NO-POSITION-CLOSEOUT-GATE-C`.

## Purpose

This gate safely closes out a previous entry attempt only when all of the
following are true:

```text
previous_entry_post_executed=true
previous_entry_post_execution_count=1
previous_entry_result_safe_category=UNKNOWN_BLOCKED
previous_entry_retry_attempted=false
previous_entry_second_post_attempted=false
previous_close_post_executed=false
runtime_position_status=NO_POSITION
runtime_position_count_safe=0
```

Closeout here means a safe Level 5 state transition only. It is not a retry,
repost, second entry POST, close POST, ledger update, receipt handoff, or raw
broker result inspection.

## Implemented Gate

Implemented in:

```text
backend/app/live_verification/live_order_real_entry_unknown_no_position_closeout_gate_controlled.py
```

The gate consumes the previous entry safe summary, a post-entry position
confirmation result or runtime position safe-read result, and optional manual
operator UI booleans. It returns safe labels, booleans, and counts only.

Manual operator UI confirmation is represented only by safe booleans:

```text
operator_broker_ui_checked
operator_broker_ui_open_position_visible
operator_broker_ui_pending_order_visible
operator_broker_ui_can_monitor
operator_broker_ui_values_or_ids_provided
```

Screenshots, order numbers, position identifiers, actual prices, and PnL values
are not required and must not be captured by this gate.

## Level 5 State

The Level 5 cycle state machine now supports:

```text
UNKNOWN_RESULT_SAFE_STOP + NO_POSITION
  -> ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
```

`ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT` means the previous unknown/no-position
attempt may be treated as terminal for planning purposes. It does not allow a
POST in this step.

## Decision Mapping

### NO_POSITION

```text
entry_unknown_no_position=true
entry_effect_confirmed_by_position=false
entry_unknown_no_position_closeout_completed=true
next_cycle_state=ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
fresh_cycle_may_be_planned=true
actual_entry_post_allowed_now=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-LEVEL5-FRESH-CYCLE-ENTRY-GATE-C
```

That next step must be a fresh cycle, not a retry or repost. It requires a new
position read, new signal, new operator readiness check, and new entry
confirmation.

### ONE_POSITION_OPEN

The previous entry effect may be visible after all. Route to a close execution
gate candidate, but this gate still does not execute close POST.

### MULTIPLE / UNKNOWN / BLOCKED

Fail closed. Fresh entry, retry/repost, second entry, and close POST remain
blocked. Manual operator review may be recommended using safe booleans only.

## Pending Orders

No new broker pending-order API connection is created in this gate. If no
existing safe count/status route is available, the gate records:

```text
pending_order_safe_status=NOT_CHECKED_SOURCE_MISSING
pending_order_check_required_for_fresh_cycle=false
manual_ui_pending_order_check_recommended=true
```

## Prohibitions

This gate must not execute or expose:

```text
actual entry POST
retry/repost
second entry POST
actual close POST
order endpoint
live_order_once
ledger update
receipt handoff
raw request/response
broker/API response
real/account/order/transaction/position/trade ID
client order ID actual value
credential/signature/header value
actual market price
actual PnL
.env contents
```

## Current Runtime Note

During this implementation run, the safe runtime read path returned
`UNKNOWN_FAIL_CLOSED` rather than a confirmed `NO_POSITION` result. Therefore
the live closeout decision for this run is fail-closed; no retry, repost, second
entry POST, close POST, ledger update, or receipt handoff was performed.
