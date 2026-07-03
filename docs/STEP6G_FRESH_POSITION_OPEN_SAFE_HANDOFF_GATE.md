# Step 6G Fresh Position Open Safe Handoff Gate

This document records
`Step 6G-PC-OX-R-FRESH-POSITION-OPEN-SAFE-HANDOFF-GATE-C`.

## Purpose

This gate hands off a confirmed fresh open position to the later close
execution gate as planning-only state.

It does not execute actual close POST, entry POST, retry, repost, second entry
POST, ledger update, attempt counter persistence, receipt handoff, or any raw
ID/value handling.

## Previous Fresh Entry Summary

The previous fresh entry and position confirmation are carried forward only as
safe summary:

```text
fresh_entry_post_executed=true
fresh_entry_post_execution_count=1
fresh_entry_result_safe_category=RESULT_ACCEPTED_SANITIZED
fresh_entry_safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF
fresh_entry_retry_attempted=false
fresh_entry_repost_attempted=false
fresh_entry_second_post_attempted=false
previous_close_post_executed=false
ledger/receipt=false
raw/ID/value exposure=false
```

This summary is not permission to retry, repost, run a second entry POST, or
run close POST.

## Implemented Gate

Implemented in:

```text
backend/app/live_verification/live_order_real_fresh_position_open_safe_handoff_gate_controlled.py
```

The gate consumes:

- a fresh accepted entry POST safe summary;
- one runtime position safe-read result reduced to status/count only;
- the existing close order route planning-only result.

It returns only safe labels, booleans, and counts. It imports no broker,
Private API client, HTTP client, env reader, order endpoint, ledger writer,
receipt handoff, or `live_order_once` dependency.

## Current Runtime Handoff Confirmation

This run re-confirmed the current position using read-only runtime status/count
only:

```text
credential_presence_available=true
runtime_read_executed=true
runtime_position_status=ONE_POSITION_OPEN
runtime_position_count_safe=1
has_open_position=true
has_exactly_one_position=true
has_multiple_positions=false
fresh_position_open_safe=true
fresh_position_open_safe_handoff_ready=true
next_cycle_state=FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
```

## Close Route Planning

The existing close route foundation is planning-only and became ready only
because the runtime position safe read reported exactly one open position:

```text
close_route_ready=true
close_planning_allowed=true
close_execution_gate_may_be_planned=true
close_execution_allowed_now=false
close_post_executed=false
close_post_count=0
close_retry_allowed=false
close_repost_allowed=false
close_second_post_allowed=false
requires_exactly_one_position=true
close_units_fixed=100
close_order_type_safe_label=MARKET
```

This is not close execution permission.

The later close execution gate must perform fresh gate checks:

```text
close_gate_requires_new_runtime_position_read=true
close_gate_requires_new_operator_readiness=true
close_gate_requires_new_close_preview=true
close_gate_requires_new_close_confirmation=true
close_gate_must_not_reuse_entry_confirmation=true
close_gate_must_not_expose_raw_id_value=true
```

## Decision Mapping

### ONE_POSITION_OPEN

```text
fresh_position_open_safe_handoff_ready=true
next_cycle_state=FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
close_execution_gate_may_be_planned=true
close_execution_allowed_now=false
close_post_allowed_now=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C
```

### NO_POSITION

```text
fresh_position_open_safe_handoff_ready=false
next_cycle_state=FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP
close_execution_gate_may_be_planned=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-FRESH-POSITION-GONE-BEFORE-CLOSE-SAFE-STOP-GATE-C
```

### MULTIPLE_POSITIONS_BLOCKED

```text
fresh_position_open_safe_handoff_ready=false
next_cycle_state=HALTED_MANUAL_CHECK_REQUIRED
close_execution_gate_may_be_planned=false
```

Recommended next step:

```text
Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C
```

### UNKNOWN / BLOCKED

```text
fresh_position_open_safe_handoff_ready=false
next_cycle_state=HALTED
close_execution_gate_may_be_planned=false
```

## Prohibitions

This gate must not execute or expose:

```text
actual entry POST
fresh entry POST retry
repost
second entry POST
actual close POST
close order endpoint
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
python3 -m pytest -q app/tests/test_live_verification_live_order_real_fresh_position_open_safe_handoff_gate_controlled.py
```

The test suite covers fresh accepted summary, `ONE_POSITION_OPEN`, `NO_POSITION`,
multiple positions, unknown fail-closed, retry/repost/second entry blockers,
previous close POST blockers, close route planning readiness, close execution
remaining false, close POST count `0`, raw/ID/value/credential sentinels, and no
blocked imports.
