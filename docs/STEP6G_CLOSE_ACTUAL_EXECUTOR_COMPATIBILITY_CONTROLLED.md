# Step 6G Close Actual Executor Compatibility Controlled

This document records
`Step 6G-PC-OX-R-CLOSE-ORDER-ACTUAL-EXECUTOR-COMPATIBILITY-NO-POST-C`.

## Purpose

This step adds a no-POST close actual executor compatibility foundation for
Level 5. It connects the close executable preview to a close-specific executor
preview without invoking any transport.

It originally fixed the executor shape mismatch, but the later manual risk
check proved that a generic opposite order must not be treated as settlement.
This document now records that the compatibility layer is fail-closed unless a
GMO FX official close-specific settlement route is confirmed.

## Implemented Module

```text
backend/app/live_verification/live_order_real_close_actual_executor_compatibility_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader,
ledger writer, receipt handoff, or `live_order_once` dependency. It only builds
safe dataclass summaries, a sanitized close-specific executor preview, and a
Level 5 no-POST transition summary.

## Boundary

The existing one-shot executor remains a generic entry path:

- generic entry `BUY` guard remains intact
- generic entry `SELL` remains blocked
- the BUY-fixed guard is not removed or broadened
- no real transport is connected by this step

Close-specific compatibility is separate:

- `close_specific_context=true`
- `generic_entry_context=false`
- `SELL` or `BUY` is not accepted from a guarded generic opposite order
- the adapter emits a ready one-shot executor preview dataclass shape only
  after a close-specific official settlement primitive is confirmed
- exact-one-position guard is required
- guarded generic close primitive is revoked for actual settlement
- fixed `100` units and `MARKET` order type are required
- `official_settlement_route_confirmed=false` blocks actual close execution

## Sanitized Close Executor Preview

The preview exposes only safe labels and booleans:

```text
execution_step=CLOSE_ORDER_ACTUAL_EXECUTOR_COMPATIBILITY_NO_POST_C
close_specific_context=true
generic_entry_context=false
runtime_position_status=ONE_POSITION_OPEN
position_count_safe=1
close_symbol_safe_label=USD_JPY
close_side_safe_label=SELL/BUY
close_units_fixed=100
close_order_type_safe_label=MARKET
approved_close_post_primitive_ready=true
approved_close_post_primitive_kind=CLOSE_SPECIFIC_APPROVED_PRIMITIVE_NO_POST
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=true/false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
one_close_post_max=true
close_retry_allowed=false
close_repost_allowed=false
close_second_post_allowed=false
entry_post_this_step=false
actual_close_post_allowed_now=false
actual_close_post_executed=false
transport_call_count=0
ledger_update_this_step=false
receipt_handoff_this_step=false
raw_exposure=false
id_exposure=false
credential_value_exposure=false
signature_value_exposure=false
headers_value_exposure=false
actual_close_post_requires_separate_close_execution_gate=true
```

The preview does not contain raw payloads, raw request/response data,
broker/API responses, account/order/transaction/position/trade IDs, credential
values, signature values, header values, market price values, or PnL values.

## Fail-Closed Guards

The compatibility preview blocks when any of the following is true:

- close-specific context is missing
- generic entry context is used
- close execution route or executable preview is not ready
- approved close primitive is not ready
- guarded generic opposite order is presented as close
- official settlement route is not confirmed
- exact-one-position guard is missing
- runtime position is not `ONE_POSITION_OPEN`
- position count is not `1`
- multiple positions are indicated
- close side is unresolved or a placeholder
- units are not `100`
- order type is not `MARKET`
- retry, repost, second close, entry POST, ledger, receipt, or transport call is
  indicated
- any raw/ID/value exposure flag is indicated

## Level 5 Connection

The Level 5 foundation now carries `close_actual_executor_compatibility`:

```text
CLOSE_EXECUTION_GATE_READY_NO_POST
  + close_actual_executor_compatibility_ready=true
  + close_specific_executor_preview_ready=true
  -> CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST

CLOSE_EXECUTION_GATE_READY_NO_POST
  + guarded generic opposite order only
  -> CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_DEPRECATED_UNSAFE_GENERIC_CLOSE

CLOSE_EXECUTION_GATE_READY_NO_POST
  + official settlement route missing
  -> CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_OFFICIAL_SETTLEMENT_ROUTE

CLOSE_EXECUTION_GATE_READY_NO_POST
  + executor compatibility blocked
  -> CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED
```

This step does not reach:

```text
CLOSE_SENT
CLOSE_POST_EXECUTED
POST_CLOSE_POSITION_CONFIRMATION
LEDGER_UPDATED
RECEIPT_HANDOFF
LEVEL5_CYCLE_COMPLETED
```

## Next Step

Recommended next safe step after the multiple-position risk:

```text
Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C
```

That next step is read-only after operator manual flattening. No further actual
close POST is allowed until the official GMO settlement route is verified and
implemented as a close-specific primitive.
