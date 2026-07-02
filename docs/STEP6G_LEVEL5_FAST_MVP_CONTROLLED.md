# Step 6G Level 5 Fast MVP Controlled

This document records the Level 5 fast-track MVP foundation sprint.

## Purpose

Level 5 minimum cycle:

```text
signal -> safety gate -> 100-unit entry -> position check -> exit signal ->
100-unit close -> no-position check -> one cycle complete
```

This sprint implements only the safe foundation contracts. It does not execute
entry POST, close POST, retry, repost, second POST, ledger update, attempt
counter persistence, actual receipt handoff, broker/private API writes, or raw
ID/value handling.

## Implemented Module

```text
backend/app/live_verification/live_order_real_step6g_level5_fast_mvp_controlled.py
```

Implemented contracts:

- safe sanitized ledger-like record
- review-only receipt summary
- position read-only status
- close route foundation
- Level 5 cycle state machine
- signal MVP contract
- fixed fast-track config
- safe summary renderer

The module imports no broker, private API, HTTP client, env reader, order
endpoint, ledger writer, receipt handoff, or `live_order_once` dependency.

## Fixed Fast-Track Config

- `symbol=USD_JPY`
- `units=100`
- `max_open_positions=1`
- `max_entry_orders_per_cycle=1`
- `max_close_orders_per_cycle=1`
- `retry_allowed=false`
- `repost_allowed=false`
- `second_post_allowed=false`
- `human_monitoring_required=true`
- `operator_confirmation_required_for_actual_post=true`
- `time_market_gate_required=true`
- `kill_switch_required=true`

Unsafe overrides fail closed.

## Safe Ledger-Like Record

The safe record accepts only the sanitized accepted POST summary:

- `post_execution_count=1`
- `sanitized_result_category=RESULT_ACCEPTED_SANITIZED`
- `safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF`
- `retry_attempted=false`
- `second_post_attempted=false`
- `ledger_updated=false`
- `receipt_handoff_executed=false`
- `raw/ID/value exposure=false`

It does not write a production ledger and does not store broker IDs, order IDs,
raw responses, credentials, signatures, headers, or confirmation text.

## Review-Only Receipt Summary

The receipt summary is review-only:

- `receipt_summary_ready=true`
- `actual_receipt_handoff_executed=false`
- `raw_response_required=false`
- `real_id_required=false`
- `broker_api_response_required=false`
- `manual_broker_ui_check_recommended=true`

If a real broker receipt, broker/API response, order ID, transaction ID, or
raw response is required, Codex must stop.

## Position Read-Only Status Contract

The position contract handles only safe status/count fields:

- `NO_POSITION`
- `ONE_POSITION_OPEN`
- `UNKNOWN`
- `BLOCKED`

Rules:

- `new_entry_allowed=true` only with checked `NO_POSITION`
- `close_allowed=true` only with checked `ONE_POSITION_OPEN`
- unknown position blocks entry and close
- multiple positions become `BLOCKED`
- raw position/account/order/transaction IDs and position values remain hidden

No real position source is wired in this sprint.

Follow-up route wiring:

- `backend/app/live_verification/live_order_real_position_read_only_controlled.py`
  now provides a standalone safe position read-only route.
- The Level 5 foundation can consume that route result and map it into the
  existing position, signal, cycle, and close-route contracts.
- `NO_POSITION` allows entry planning only.
- `ONE_POSITION_OPEN` allows close planning only.
- multiple positions, unknown, source missing, raw exposure, ID exposure, value
  exposure, or credential exposure block entry and close planning.
- The real position source is still not connected by default; source missing
  remains fail-closed.
- Actual close POST remains prohibited.

## Close Route Foundation

The close route foundation is a no-POST readiness contract:

- `close_post_executed=false`
- `close_post_count=0`
- `close_retry_allowed=false`
- `close_second_post_allowed=false`
- `close_requires_position_status=ONE_POSITION_OPEN`
- `close_size_fixed=100`
- unknown/no/multiple position blocks close
- raw ID/response/broker response requirement blocks close

It does not implement or execute close POST.

## Cycle State Machine

States:

```text
IDLE
ENTRY_SIGNAL
ENTRY_SENT
ENTRY_ACCEPTED_SANITIZED
POSITION_CHECK_PENDING
POSITION_OPEN_SAFE
EXIT_SIGNAL
CLOSE_READY
CLOSE_SENT
CLOSED_SAFE
HALTED
```

Safety rules:

- entry requires no position and daily limits OK
- sanitized accepted entry must be followed by position check
- unknown/missing/blocked position after entry halts
- second entry attempt halts
- exit to close requires one open position
- close accepted requires no-position confirmation before `CLOSED_SAFE`
- `HALTED` has no automatic recovery
- retry and second POST remain false

## Signal MVP

Signal types:

- `ENTRY_BUY`
- `ENTRY_SELL`
- `EXIT`
- `HOLD`
- `BLOCKED`

Rule MVP:

- `UPTREND` + no position -> `ENTRY_BUY`
- `DOWNTREND` + no position -> `ENTRY_SELL`
- one open position + `TAKE_PROFIT` / `STOP_LOSS` / `MAX_HOLD_TIME` -> `EXIT`
- otherwise `HOLD`

Signals never execute POST directly and never expose actual market raw values.

## Verification

Primary test:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_step6g_level5_fast_mvp_controlled.py
```

The test suite covers safe record, review-only receipt, position status,
close-route no-POST behavior, cycle state transitions, signal decisions, fixed
config, no retry/repost/second POST, and raw/ID/value non-exposure.

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-POSITION-READ-ONLY-SOURCE-CONNECTION-C
```

That step may only connect a position read-only source if the source can return
safe status/count fields without raw/ID/value, credential, signature, header, or
broker/API response exposure. If safe position source wiring is not possible,
stop and keep close execution blocked.
