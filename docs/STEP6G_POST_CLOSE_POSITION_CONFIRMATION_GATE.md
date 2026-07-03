# Step 6G Post-Close Position Confirmation Gate

This document records
`Step 6G-PC-OX-R-POST-CLOSE-POSITION-CONFIRMATION-GATE-C`.

## Purpose

This gate confirms the effect of a previous single accepted close POST using
only a sanitized runtime position safe-read result.

Close accepted status is not treated as proof that the position is closed.
Level 5 minimal cycle completion requires a post-close runtime safe read with
`NO_POSITION` and `position_count_safe=0`.

## Implemented Module

```text
backend/app/live_verification/live_order_real_post_close_position_confirmation_gate_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader,
ledger writer, receipt handoff, or `live_order_once` dependency. It only maps a
previous entry/close safe summary plus a sanitized runtime position safe-read
result into safe status/count booleans.

## Previous Entry / Close Summary Contract

The gate requires all of the following before Level 5 completion can be
considered:

- fresh entry POST executed exactly once
- fresh entry result `RESULT_ACCEPTED_SANITIZED`
- close POST executed exactly once
- close result `RESULT_ACCEPTED_SANITIZED`
- close safe reconciliation status `RECONCILIATION_READY_NO_RECEIPT_HANDOFF`
- fresh retry/repost/second entry false
- close retry/repost/second close false
- ledger update false
- receipt handoff false
- raw/ID/value exposure false

If any of these conditions is not satisfied, the gate fails closed and does not
allow retry, repost, second close, entry POST, ledger, or receipt handoff.

## Runtime Position Mapping

The gate maps the runtime safe-read result as follows:

```text
NO_POSITION + count=0
  -> LEVEL5_MINIMAL_CYCLE_COMPLETED

ONE_POSITION_OPEN + count=1
  -> CLOSE_ACCEPTED_POSITION_STILL_VISIBLE_SAFE_STOP

MULTIPLE_POSITIONS_BLOCKED
  -> HALTED_MANUAL_CHECK_REQUIRED

UNKNOWN_FAIL_CLOSED or blocked states
  -> HALTED_UNKNOWN_POSITION
```

This step forces `new_entry_allowed=false`, `close_planning_allowed=false`, and
`close_execution_allowed_now=false`, even when the underlying safe-read route
could otherwise make a planning recommendation.

## Current Run Result

The post-close runtime safe read was executed once after the accepted close
summary.

Safe result:

```text
credential_presence_available=true
runtime_read_executed=true
position_source_checked=true
position_status_checked=true
position_status=MULTIPLE_POSITIONS_BLOCKED
position_count_safe=2
has_open_position=false
has_exactly_one_position=false
has_multiple_positions=true
raw_position_exposed=false
position_id_exposed=false
account_id_exposed=false
order_id_exposed=false
transaction_id_exposed=false
broker_api_response_exposed=false
credential_value_exposed=false
signature_value_exposed=false
headers_value_exposed=false
```

Judgement:

```text
CASE=CASE 3
post_close_position_status=POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED
next_cycle_state=HALTED_MANUAL_CHECK_REQUIRED
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
retry_allowed=false
repost_allowed=false
second_close_allowed=false
entry_post_this_step=false
ledger_receipt_executed=false
raw_id_value_exposure=false
```

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C
```

That next step must remain read-only and operator-safe. It must not execute
entry POST, close POST, retry, repost, second close, ledger update, receipt
handoff, or expose raw/ID/value fields.

## Manual Risk Follow-up

The manual risk gate records that `MULTIPLE_POSITIONS_BLOCKED` / count `2` is
not `NO_POSITION` and does not complete the Level 5 cycle.

It also revokes the previous generic opposite-order close assumption:

```text
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
```

Any future actual close POST is forbidden until a GMO FX official settlement
route is confirmed and implemented as a close-specific primitive. The safe
next step is manual flattening by the operator followed by read-only flat
reconciliation.
