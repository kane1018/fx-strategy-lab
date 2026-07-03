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

After the manual position risk check, `GUARDED_GENERIC_ORDER_CLOSE_PRIMITIVE`
is no longer approved as an actual close settlement primitive. A generic
opposite `SELL` / `BUY` order can create an opposite-side position instead of
settling the existing position. It must not be treated as close execution.

The route now requires a GMO FX official settlement route before actual close
execution can be considered:

```text
official_gmo_rules_alignment_checked=true
official_manual_url_recorded=true
official_trading_rules_url_recorded=true
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
```

Until the official settlement route is confirmed and represented as a
close-specific primitive, the route remains fail-closed with
`CLOSE_EXECUTION_ROUTE_BLOCKED_OFFICIAL_SETTLEMENT_ROUTE_MISSING`.

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
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
close_execution_route_ready_for_actual_post=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
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
  + guarded generic opposite order only
  + official_settlement_route_confirmed=false
  -> CLOSE_EXECUTION_ROUTE_BLOCKED_OFFICIAL_SETTLEMENT_ROUTE_MISSING

FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + close side unresolved
  -> CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_UNRESOLVED

FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + primitive missing
  -> CLOSE_EXECUTION_ROUTE_BLOCKED_PRIMITIVE_MISSING

FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
  + official close-specific settlement primitive confirmed
  + exact-one-position guard
  -> CLOSE_EXECUTION_GATE_READY_NO_POST
```

The follow-up compatibility foundation keeps the route no-POST and connects
only sanitized safe fields:

```text
CLOSE_EXECUTION_GATE_READY_NO_POST
  + close_actual_executor_compatibility_ready=true
  + close_specific_executor_preview_ready=true
  -> CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST
```

The compatibility step preserves the generic entry BUY guard. Generic entry
`SELL` remains blocked. Generic opposite orders are not settlement primitives;
`SELL` / `BUY` may be accepted for actual close only after a close-specific GMO
settlement primitive is confirmed.

## Next Step

Recommended next safe step after a generic opposite-order close risk:

```text
Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C
```

That next step is read-only reconciliation after operator manual flattening.
Any future actual close POST remains forbidden until the official GMO
settlement route is confirmed and implemented as a close-specific primitive.

The following GMO official settlement route review confirmed the dedicated
official settlement route/parameter as no-POST evidence. This does not restore
the guarded generic close primitive. Future route implementation must use a
dedicated settlement primitive and stay no-POST until a later execution gate.

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

## Official Alignment

GMO FX official materials are recorded as the authoritative basis:

```text
https://coin.z.com/corp_imgs/manual/kawasefx-trading-manual.pdf
https://coin.z.com/jp/corp/product/info/fx/#rule
```

The implementation assumes hedged buy/sell positions can coexist and are not
netted for safe route judgement. Actual close settlement requires a dedicated
official settlement route, not a generic opposite order.
