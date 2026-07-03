# Step 6G Operator Manual Close Reconciliation Gate

This document records
`Step 6G-PC-OX-R-CLOSEOUT-DIRTY-WORKTREE-FREEZE-AND-MANUAL-CLOSE-RECONCILIATION-C`.

## Purpose

This gate preserves the fail-closed closeout implementation and reconciles an
operator-reported manual broker UI close using safe booleans and read-only
position status/count only.

This is not a fully autonomous Level 5 cycle completion.

## Previous Entry Attempt

The previous entry attempt is carried forward only as a safe summary:

```text
previous_entry_post_executed=true
previous_entry_post_execution_count=1
previous_entry_result_safe_category=UNKNOWN_BLOCKED
previous_entry_retry_attempted=false
previous_entry_second_post_attempted=false
previous_close_post_executed=false
previous_ledger_or_receipt_executed=false
previous_raw_id_value_exposed=false
```

## Dirty Worktree Freeze

The uncommitted entry unknown/no-position closeout implementation was reviewed
as fail-closed and committed separately as implementation preservation. That
commit does not claim live closeout completion.

## Operator Manual Close Input

The operator reported a manual close from the broker UI. It is represented only
as safe booleans:

```text
operator_manual_close_reported=true
operator_manual_close_source=BROKER_UI
operator_manual_close_values_or_ids_provided=false
```

No order ID, position ID, transaction ID, account ID, raw response, actual
price, actual PnL, credential value, signature value, or header value is
required or recorded.

## Runtime Reconciliation

The read-only runtime position check returned:

```text
runtime_read_executed=true
position_status=NO_POSITION
position_count_safe=0
has_open_position=false
has_exactly_one_position=false
has_multiple_positions=false
raw_position_exposed=false
position_id_exposed=false
account_id_exposed=false
order_id_exposed=false
transaction_id_exposed=false
broker_api_response_exposed=false
```

## Decision

The reconciliation result is:

```text
manual_close_reconciled=true
manual_close_reconciliation_basis=RUNTIME_NO_POSITION
runtime_position_inconclusive=false
next_cycle_state=OPERATOR_MANUAL_CLOSE_RECONCILED
level5_full_auto_cycle_completed=false
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
actual_entry_post_allowed_now=false
close_post_allowed_now=false
fresh_cycle_may_be_planned=true
```

Fresh cycle planning is not retry/repost permission. A later fresh cycle must
require a new runtime position read, new signal, new operator readiness check,
and new entry confirmation.

## Prohibitions

This gate did not and must not execute:

```text
entry POST retry
repost
second entry POST
actual close POST
order endpoint
live_order_once
ledger update
attempt counter persistence
receipt handoff
raw request/response handling
broker/API response display
real/account/order/transaction/position/trade ID display
credential/signature/header value display
.env read
```
