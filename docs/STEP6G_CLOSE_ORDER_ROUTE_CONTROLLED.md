# Step 6G Close Order Route Controlled

This document records
`Step 6G-PC-OX-R-CLOSE-ORDER-ROUTE-IMPLEMENTATION-C`.

## Purpose

This step adds a close order route foundation for Level 5. The route is a
planning-only contract. It consumes safe position status/count and allows close
planning only when exactly one position is safely reported.

It does not execute actual close POST, entry POST, retry/repost, second POST,
ledger update, attempt counter persistence, or receipt handoff.

## Implemented Module

```text
backend/app/live_verification/live_order_real_close_order_route_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader, order
endpoint, ledger writer, receipt handoff, or `live_order_once` dependency.

## Planning Rules

Close planning is allowed only for:

```text
position_status=ONE_POSITION_OPEN
position_status_checked=true
position_count_safe=1
max_open_positions=1
```

Close planning is blocked for:

- `NO_POSITION`
- `UNKNOWN_FAIL_CLOSED`
- `SOURCE_MISSING_BLOCKED`
- `MULTIPLE_POSITIONS_BLOCKED`
- `RAW_EXPOSURE_BLOCKED`
- `ID_EXPOSURE_BLOCKED`
- `VALUE_EXPOSURE_BLOCKED`
- `CREDENTIAL_UNAVAILABLE_BLOCKED`

Default/current position route remains `UNKNOWN_FAIL_CLOSED` without an
explicit checked source summary, so default close planning is blocked.

## Sealed Close Instruction

The sealed close instruction is safe-label only:

```text
safe_symbol_label=USD_JPY
safe_side_label=OPPOSITE_OF_SAFE_POSITION_SIDE
safe_units_label=100
safe_order_type_label=MARKET
position_handle_value_exposed=false
position_id_exposed=false
raw_position_exposed=false
```

This is not an executable order payload. It does not include position ID, order
ID, transaction ID, account ID, client order ID actual value, raw position,
raw request, raw response, broker/API response, credential value, signature
value, or headers value.

## Close Execution Readiness

The route returns a planning-only readiness summary:

```text
close_execution_step_may_be_planned=true/false
close_execution_requires_new_confirmation=true
close_execution_requires_time_market_operator_gate=true
close_execution_requires_position_status_current=true
close_execution_requires_exactly_one_position=true
close_execution_requires_no_retry=true
close_execution_requires_no_second_post=true
close_execution_requires_raw_id_exposure_false=true
close_execution_permission_granted_now=false
```

This is not close execution permission.

## Level 5 Connection

The Level 5 foundation now carries the close order route result alongside the
existing close route foundation:

- `EXIT_SIGNAL + ONE_POSITION_OPEN -> CLOSE_READY`
- `EXIT_SIGNAL + NO_POSITION -> HALTED`
- `EXIT_SIGNAL + UNKNOWN -> HALTED`
- `EXIT_SIGNAL + MULTIPLE/BLOCKED -> HALTED`
- `CLOSE_READY` does not execute close POST
- `CLOSE_SENT` is not reached without a separate close execution gate

## Verification

Primary tests:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_close_order_route_controlled.py
python3 -m pytest -q app/tests/test_live_verification_live_order_real_step6g_level5_fast_mvp_controlled.py
python3 -m pytest -q app/tests/test_live_verification_no_order_imports.py
```

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-POSITION-RUNTIME-SAFE-READ-CHECK-C
```

That step may only verify a current safe runtime position read as status/count.
Actual close POST, entry POST, retry/repost, second POST, ledger update,
receipt handoff, raw responses, broker/API responses, IDs, credential values,
signature values, header values, and `.env` access remain forbidden unless a
later separately approved execution gate explicitly scopes them.

The runtime safe read check returned:

```text
position_status=NO_POSITION
position_count_safe=0
close_planning_allowed=false
close_execution_allowed_now=false
```

Therefore the close execution gate is not the next step from this runtime
state. The next bounded step is the Level 5 signal/entry cycle gate.

The Level 5 signal/entry cycle gate follow-up is planning-only. With the
runtime `NO_POSITION` premise and an injected safe `ENTRY_BUY` or `ENTRY_SELL`
snapshot, the cycle can reach `ENTRY_READY`. It does not execute entry POST,
does not execute close POST, and does not change the close execution boundary.
