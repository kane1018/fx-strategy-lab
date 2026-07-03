# Step 6G Position Runtime Safe Read Check

This document records
`Step 6G-PC-OX-R-POSITION-RUNTIME-SAFE-READ-CHECK-C`.

## Result

The runtime read-only position check completed as safe status/count only:

```text
credential_presence_checked=true
credential_presence_available=true
all_required_credentials_present=true
runtime_read_executed=true
position_source_checked=true
position_status_checked=true
position_status=NO_POSITION
position_count_safe=0
has_open_position=false
has_exactly_one_position=false
has_multiple_positions=false
new_entry_allowed=true
close_planning_allowed=false
close_execution_allowed_now=false
max_open_positions=1
```

No raw response, raw position object, broker/API response, position ID, account
ID, order ID, transaction ID, trade ID, price value, PnL value, credential
value, signature value, header value, ledger update, or receipt handoff was
displayed, saved, or returned.

## Runtime Mapper

The safe mapper is:

```text
backend/app/live_verification/live_order_real_position_runtime_safe_read_controlled.py
```

It maps an already-sanitized runtime count into the same read-only position
route and close route contracts used by Level 5. It imports no broker, Private
API, HTTP, env, order endpoint, ledger, receipt, or `live_order_once` dependency.

## Routing Decision

For this check:

```text
NO_POSITION -> entry planning may be possible later
NO_POSITION -> close planning blocked
NO_POSITION -> close execution gate blocked
```

Actual entry POST, actual close POST, retry/repost, second POST, ledger update,
receipt handoff, raw/ID/value exposure, credential/signature/header exposure,
and `.env` access remain prohibited.

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-LEVEL5-SIGNAL-ENTRY-CYCLE-GATE-C
```

That follow-up is now implemented as a planning-only signal/entry cycle gate.
It uses injected safe labels, not raw market data or actual market values.
`NO_POSITION + ENTRY_BUY/ENTRY_SELL` can reach `ENTRY_READY`, while actual entry
POST, close POST, retry/repost, second POST, ledger update, receipt handoff,
raw/ID/value exposure, credential/signature/header exposure, and `.env` access
remain prohibited.

## Post-Entry Follow-Up

The later post-entry position confirmation gate reused the same safe
status/count boundary after the previous entry execution Step returned
`unknown/blocked` as a safe result category. The runtime read was executed once
and returned:

```text
position_status=NO_POSITION
position_count_safe=0
entry_effect_confirmed_by_position=false
position_confirmation_status=NO_POSITION_AFTER_ENTRY_POST
```

That follow-up did not retry entry POST, run a second entry POST, run close
POST, update a ledger, hand off a receipt, expose raw responses, expose
broker/API responses, expose IDs, expose credential/signature/header values, or
read `.env` files. Details:
[STEP6G_POST_ENTRY_POSITION_CONFIRMATION_GATE.md](STEP6G_POST_ENTRY_POSITION_CONFIRMATION_GATE.md).

The next closeout gate may only move `UNKNOWN_RESULT_SAFE_STOP` to
`ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT` after another safe runtime position
result confirms `NO_POSITION` / count `0`. If the runtime read is unknown,
blocked, or inconclusive, the closeout gate fails closed and does not permit a
fresh cycle, retry/repost, second entry POST, or close POST.
