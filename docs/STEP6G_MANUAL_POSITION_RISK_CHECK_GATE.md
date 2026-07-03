# Step 6G Manual Position Risk Check Gate

This document records
`Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C`.

## Purpose

This gate handles the post-close multiple-position risk state after one
accepted entry POST and one accepted close POST. It is read-only and records
safe status/count fields only.

It does not execute entry POST, close POST, retry, repost, second close,
ledger update, attempt counter persistence, receipt handoff, broker/private
writes, or raw/ID/value handling.

## Implemented Module

```text
backend/app/live_verification/live_order_real_manual_position_risk_check_gate_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader,
order executor, ledger writer, receipt handoff, or `live_order_once`
dependency. It consumes a sanitized runtime position safe-read result and safe
operator booleans only.

## Current Safe Runtime Result

The manual risk check was reached because post-close confirmation returned:

```text
position_status=MULTIPLE_POSITIONS_BLOCKED
position_count_safe=2
has_exactly_one_position=false
has_multiple_positions=true
close_effect_confirmed_by_no_position=false
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
```

This is not `NO_POSITION`. The Level 5 minimal cycle is not complete.

## Manual Risk Gate Mapping

```text
MULTIPLE_POSITIONS_BLOCKED + count=2
  -> MULTIPLE_POSITIONS_CONFIRMED
  -> HALTED_MANUAL_FLATTEN_REQUIRED

NO_POSITION + count=0
  -> ALREADY_FLAT
  -> runtime flat reconciliation path only

ONE_POSITION_OPEN + count=1
  -> SINGLE_POSITION_STILL_OPEN
  -> manual operator check required

UNKNOWN / blocked
  -> UNKNOWN_FAIL_CLOSED
```

Every branch keeps:

```text
actual_entry_post_allowed_now=false
actual_close_post_allowed_now=false
retry_allowed=false
repost_allowed=false
second_close_allowed=false
ledger_update_allowed=false
receipt_handoff_allowed=false
fresh_cycle_allowed=false
```

## Generic Close Primitive Revocation

The previous guarded generic close primitive is revoked for actual settlement:

```text
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
```

A generic opposite `SELL` / `BUY` order must be treated as a possible new
opposite-side position, not as settlement of an existing position.

## Safe Operator Boundary

Operator UI input, when used, is limited to booleans:

```text
operator_broker_ui_checked=true/false
operator_broker_ui_buy_position_visible=true/false
operator_broker_ui_sell_position_visible=true/false
operator_broker_ui_multiple_positions_visible=true/false
operator_broker_ui_values_or_ids_provided=false
operator_can_monitor=true/false
```

The gate does not request or store IDs, prices, PnL, screenshots, raw broker
responses, credentials, signatures, or headers.

## Next Step

Recommended next step when multiple positions are confirmed:

```text
Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C
```

The operator manually returns the account to flat in the broker UI. Codex then
performs read-only `NO_POSITION` / count `0` reconciliation only. No retry,
repost, second close, entry POST, ledger, or receipt handoff is allowed.

## Manual Flatten Follow-up Result

The follow-up runtime flat reconciliation confirmed:

```text
operator_manual_flatten_completed=true
position_status=NO_POSITION
position_count_safe=0
manual_flatten_reconciled=true
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
fresh_cycle_allowed=false
official_settlement_route_required=true
```

The generic opposite-order close primitive remains revoked. The next bounded
step is GMO official settlement route review, still no-POST.
