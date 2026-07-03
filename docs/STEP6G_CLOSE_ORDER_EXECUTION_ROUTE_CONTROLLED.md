# Step 6G Close Order Execution Route Controlled

This document records
`Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-ROUTE-IMPLEMENTATION-NO-POST-C`.

## Purpose

This step adds the close-specific executable route foundation for Level 5.
It is a no-POST contract that converts safe close planning state into a
sanitized executable close preview.

It does not execute actual close POST, entry POST, retry/repost, second close
POST, ledger update, attempt counter persistence, or receipt handoff.

## Implemented Module

```text
backend/app/live_verification/live_order_real_close_order_execution_route_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader,
ledger writer, receipt handoff, or `live_order_once` dependency. It only builds
safe dataclass summaries and a sanitized preview.

## Close Side Derivation

The executable preview requires a concrete close side:

```text
fresh_entry_side_safe_label=BUY -> close_side_safe_label=SELL
fresh_entry_side_safe_label=SELL -> close_side_safe_label=BUY
operator_signal_type=ENTRY_BUY -> close_side_safe_label=SELL
operator_signal_type=ENTRY_SELL -> close_side_safe_label=BUY
safe_position_side_label=BUY -> close_side_safe_label=SELL
safe_position_side_label=SELL -> close_side_safe_label=BUY
```

`OPPOSITE_OF_SAFE_POSITION_SIDE`, `UNKNOWN`, `NONE`, `MIXED`, and `MULTIPLE`
do not produce an executable preview. If multiple safe inputs disagree, the
route blocks with side mismatch. Codex does not infer BUY/SELL from raw data.

## Approved Primitive Contract

The route keeps primitive invocation deferred:

```text
close_primitive_invocation_deferred=true
actual_close_post_allowed_now=false
```

`approved_close_post_primitive_ready=true` is allowed only when a close-specific
primitive is declared, or when a guarded generic primitive is explicitly marked
as acceptable for close with all of the following safe guards:

```text
runtime_position_status=ONE_POSITION_OPEN
position_count_safe=1
has_exactly_one_position=true
has_multiple_positions=false
close_side_safe_label=SELL/BUY
close_units_fixed=100
close_order_type_safe_label=MARKET
generic_order_accepted_as_close_only_with_exact_one_position_guard=true
```

Without those guards the route remains
`CLOSE_EXECUTION_ROUTE_BLOCKED_PRIMITIVE_MISSING`.

## Sanitized Executable Preview

The preview exposes only safe labels and booleans:

```text
execution_step=CLOSE_ORDER_EXECUTION_ROUTE_IMPLEMENTATION_NO_POST_C
runtime_position_status=ONE_POSITION_OPEN
position_count_safe=1
close_symbol_safe_label=USD_JPY
close_side_safe_label=SELL/BUY
close_units_fixed=100
close_order_type_safe_label=MARKET
approved_close_post_primitive_ready=true/false
one_close_post_max=true
close_retry_allowed=false
close_repost_allowed=false
close_second_post_allowed=false
entry_post_this_step=false
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

## Level 5 Connection

The Level 5 foundation carries the close execution route result:

```text
FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + close_execution_route_ready=true
  + close_side_safe_label=SELL/BUY
  + approved_close_post_primitive_ready=true
  -> CLOSE_EXECUTION_GATE_READY_NO_POST

FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + close side unresolved
  -> CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_UNRESOLVED

FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + primitive missing
  -> CLOSE_EXECUTION_ROUTE_BLOCKED_PRIMITIVE_MISSING
```

This step does not reach `CLOSE_SENT`, `CLOSE_POST_EXECUTED`,
`POST_CLOSE_POSITION_CONFIRMATION`, `LEDGER_UPDATED`, `RECEIPT_HANDOFF`, or
`LEVEL5_CYCLE_COMPLETED`.

## Verification

Primary tests:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_close_order_execution_route_controlled.py
python3 -m pytest -q app/tests/test_live_verification_live_order_real_step6g_level5_fast_mvp_controlled.py
python3 -m pytest -q app/tests/test_live_verification_no_order_imports.py
```

## Next Step

If the current runtime position is still `ONE_POSITION_OPEN` / count `1`, the
next bounded step is:

```text
Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C-RETRY-WITH-EXECUTABLE-ROUTE
```

That later gate must perform a fresh runtime position read, operator readiness,
sanitized close preview, and a new close-specific confirmation before any
actual close POST can be considered.
