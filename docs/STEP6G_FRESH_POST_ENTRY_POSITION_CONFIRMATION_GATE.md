# Step 6G Fresh Post-Entry Position Confirmation Gate

This document records
`Step 6G-PC-OX-R-FRESH-POST-ENTRY-POSITION-CONFIRMATION-GATE-C`.

## Purpose

This gate confirms the effect of a fresh accepted entry POST using one
read-only runtime position safe read.

The previous fresh entry Step is carried forward only as a safe summary:

```text
fresh_cycle=true
previous_attempt_retry=false
previous_attempt_repost=false
fresh_entry_http_post_executed=true
fresh_entry_post_execution_count=1
fresh_entry_result_safe_status=ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
fresh_entry_sanitized_result_category=RESULT_ACCEPTED_SANITIZED
fresh_entry_safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF
fresh_entry_retry_attempted=false
fresh_entry_repost_attempted=false
fresh_entry_second_post_attempted=false
close_post_executed=false
ledger_updated=false
receipt_handoff_executed=false
raw/ID/value exposure=false
```

This safe summary is not permission to retry, repost, run a second entry POST,
or run close POST.

## Implemented Gate

Implemented in:

```text
backend/app/live_verification/live_order_real_fresh_post_entry_position_confirmation_gate_controlled.py
```

The gate consumes:

- a fresh accepted entry POST safe summary;
- controlled credential presence safe booleans;
- one runtime position safe-read result reduced to status/count only.

It returns only safe labels, booleans, and counts. It imports no broker,
Private API client, HTTP client, env reader, order endpoint, ledger writer,
receipt handoff, or `live_order_once` dependency.

## Decision Mapping

### ONE_POSITION_OPEN

```text
fresh_entry_effect_confirmed_by_position=true
fresh_position_confirmation_status=FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
next_cycle_state=FRESH_POSITION_OPEN_SAFE
close_planning_allowed=true
close_execution_gate_may_be_planned=true
close_execution_allowed_now=false
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
level5_full_auto_cycle_completed=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-FRESH-POSITION-OPEN-SAFE-HANDOFF-GATE-C
```

### NO_POSITION

```text
fresh_entry_effect_confirmed_by_position=false
fresh_position_confirmation_status=FRESH_ACCEPTED_BUT_NO_POSITION_VISIBLE_SAFE_STOP
next_cycle_state=FRESH_ACCEPTED_NO_POSITION_SAFE_STOP
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-FRESH-ENTRY-ACCEPTED-NO-POSITION-SAFE-STOP-GATE-C
```

### MULTIPLE_POSITIONS_BLOCKED

```text
fresh_position_confirmation_status=FRESH_MULTIPLE_POSITIONS_BLOCKED
next_cycle_state=HALTED_MANUAL_CHECK_REQUIRED
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C
```

### UNKNOWN / BLOCKED

```text
fresh_position_confirmation_status=FRESH_POSITION_UNKNOWN_FAIL_CLOSED
next_cycle_state=HALTED_UNKNOWN_POSITION
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-FRESH-POST-ENTRY-UNKNOWN-RESULT-SAFE-STOP-GATE-C
```

## Current Runtime Confirmation

This run confirmed the fresh accepted entry effect using read-only runtime
position status/count only:

```text
credential_presence_available=true
runtime_read_executed=true
position_status=ONE_POSITION_OPEN
position_count_safe=1
has_open_position=true
has_exactly_one_position=true
has_multiple_positions=false
new_entry_allowed=false
close_planning_allowed=true
close_execution_allowed_now=false
fresh_entry_effect_confirmed_by_position=true
fresh_position_confirmation_status=FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
next_cycle_state=FRESH_POSITION_OPEN_SAFE
close_execution_gate_may_be_planned=true
retry_allowed=false
repost_allowed=false
second_entry_allowed=false
close_post_allowed_now=false
level5_full_auto_cycle_completed=false
```

No fresh entry POST retry, repost, second entry POST, close POST, ledger update,
receipt handoff, raw response, broker/API response, ID, actual price/PnL,
credential value, signature value, header value, or `.env` read was performed
by this confirmation gate.

## Prohibitions

This gate must not execute or expose:

```text
fresh entry POST retry
repost
second entry POST
actual close POST
order endpoint
live_order_once
ledger update
attempt counter persistence
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

## Verification

Primary test:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_fresh_post_entry_position_confirmation_gate_controlled.py
```

The test suite covers fresh accepted result, exactly one previous POST,
`ONE_POSITION_OPEN`, `NO_POSITION`, multiple positions, unknown fail-closed,
retry/repost/second POST blockers, close POST blockers, ledger/receipt blockers,
raw/ID/value/credential sentinels, and no blocked imports.
