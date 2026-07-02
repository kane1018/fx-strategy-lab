# Step 6G Position Read-Only Controlled

This document records `Step 6G-PC-OX-R-POSITION-READ-ONLY-ROUTE-WIRING-C`.

## Purpose

This step adds a controlled position read-only route for the Level 5 fast-track
MVP. The route handles safe position status/count only:

- `NO_POSITION`
- `ONE_POSITION_OPEN`
- `MULTIPLE_POSITIONS_BLOCKED`
- `UNKNOWN_FAIL_CLOSED`
- `SOURCE_MISSING_BLOCKED`
- `RAW_EXPOSURE_BLOCKED`
- `ID_EXPOSURE_BLOCKED`
- `VALUE_EXPOSURE_BLOCKED`
- `CREDENTIAL_UNAVAILABLE_BLOCKED`

It does not execute actual HTTP POST, close POST, retry, repost, second POST,
ledger update, attempt counter persistence, or receipt handoff.

## Implemented Module

```text
backend/app/live_verification/live_order_real_position_read_only_controlled.py
```

The route imports no broker, Private API client, HTTP client, env reader, order
endpoint, ledger writer, receipt handoff, or `live_order_once` dependency.

## Safe Output

The route returns only safe labels, booleans, and counts:

- `position_status_checked`
- `position_status`
- `position_count_safe`
- `has_open_position`
- `has_exactly_one_position`
- `has_multiple_positions`
- `new_entry_allowed`
- `close_planning_allowed`
- `close_execution_allowed_now=false`
- `max_open_positions=1`
- raw/ID/value/credential/signature/header/broker response exposure flags fixed false

`NO_POSITION` allows new entry planning and blocks close planning.
`ONE_POSITION_OPEN` blocks new entry planning and allows close planning only.
`MULTIPLE_POSITIONS_BLOCKED`, unknown, source missing, or exposure attempts
block both entry and close planning.

## Source Wiring Decision

Existing read-only candidates exist in the repository, including the sanitized
preflight contract and Private read-only helper code. This step does not connect
the real source because doing so would cross into credential/Private API/client
boundary work. Instead, it implements the contract with fake/safe source
summaries and keeps the default route `SOURCE_MISSING_BLOCKED`.

The follow-up source-connection step added
`backend/app/live_verification/live_order_real_position_read_only_source_controlled.py`.
The route now defaults to that controlled sanitized source summary instead of
remaining `SOURCE_MISSING_BLOCKED`. Without an explicit checked source summary,
the default status is `UNKNOWN_FAIL_CLOSED`, so entry and close planning remain
blocked. It still does not import the Private API client, HTTP client, env
reader, broker code, or scripts directly.

The source summary may supply only safe count/status without returning raw
position objects, broker/API responses, position IDs, account IDs, order IDs,
transaction IDs, prices, PnL, credential values, signature values, or header
values.

## Level 5 Connection

`backend/app/live_verification/live_order_real_step6g_level5_fast_mvp_controlled.py`
can consume the controlled route result and map it into the existing Level 5
position, signal, cycle, and close-route contracts.

Rules:

- position unknown blocks entry and close and can halt the cycle
- no position blocks close planning
- one position enables close planning only
- multiple positions blocks close planning
- second entry remains blocked when one position is already open
- close execution is still not implemented or permitted

## Verification

Primary tests:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_position_read_only_controlled.py
python3 -m pytest -q app/tests/test_live_verification_live_order_real_step6g_level5_fast_mvp_controlled.py
python3 -m pytest -q app/tests/test_live_verification_no_order_imports.py
```

## Next Step

If a safe source returns one position exactly:

```text
Step 6G-PC-OX-R-CLOSE-ORDER-ROUTE-IMPLEMENTATION-C
```

That follow-up has now added a close planning route. It consumes this position
route result and allows close planning only when the status is
`ONE_POSITION_OPEN`, checked, and `position_count_safe=1`. Default
`UNKNOWN_FAIL_CLOSED`, `NO_POSITION`, multiple/source-missing states, and
exposure-blocked states still block close planning.

Actual POST, close POST, retry/repost, ledger update, receipt handoff, raw
responses, broker/API responses, IDs, credential values, signature values,
header values, and `.env` access remain prohibited unless a separate explicitly
approved Step allows a narrower action.

The runtime safe read check follow-up confirmed current status/count as:

```text
position_status=NO_POSITION
position_count_safe=0
position_status_checked=true
```

The result allows only later entry-cycle planning. Close planning and close
execution remain blocked until a future runtime read reports exactly one open
position.
