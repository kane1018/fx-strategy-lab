# Step 6G Manual Flatten Then Runtime Flat Reconciliation

This document records
`Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C`.

## Purpose

This gate confirms, read-only, that the operator manually flattened the
previous hedged/multiple position state and that runtime position status is now
flat.

It does not execute entry POST, close POST, retry, repost, second close, order
endpoint calls, `live_order_once`, ledger updates, receipt handoff, broker
writes, or raw/ID/value handling.

## Implemented Module

```text
backend/app/live_verification/live_order_real_manual_flatten_runtime_flat_reconciliation_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader,
order executor, ledger writer, receipt handoff, or `live_order_once`
dependency. It maps an already-sanitized runtime position safe-read result and
operator safe booleans into a reconciliation status.

## Operator Safe Boolean

Expected safe booleans:

```text
operator_manual_flatten_completed=true
operator_broker_ui_checked=true
operator_broker_ui_open_position_visible=false
operator_broker_ui_buy_position_visible=false
operator_broker_ui_sell_position_visible=false
operator_broker_ui_values_or_ids_provided=false
operator_can_monitor=true
```

No IDs, prices, PnL, screenshots, raw broker responses, credentials,
signatures, or headers are requested or stored.

## Current Runtime Result

The read-only runtime safe read returned:

```text
credential_presence_available=true
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
credential_value_exposed=false
signature_value_exposed=false
headers_value_exposed=false
```

## Judgement

```text
CASE=CASE 1
manual_flatten_reconciled=true
next_cycle_state=MANUAL_FLATTEN_RECONCILED_FLAT
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
fresh_cycle_allowed=false
official_settlement_route_required=true
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
```

This is not a completed Level 5 full auto cycle because operator manual
intervention was required.

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-GMO-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C
```

That step remained no-POST and confirmed a dedicated official settlement
route/parameter as review evidence only. Future actual close POST remains
forbidden until the route is implemented as a close-specific no-POST preview and
a later separate execution gate is approved.
