# Step 6G Position Read-Only Source Controlled

This document records
`Step 6G-PC-OX-R-POSITION-READ-ONLY-SOURCE-CONNECTION-C`.

## Purpose

This step connects the Level 5 position read-only route to a controlled
sanitized source summary. The source adapter accepts safe count/status only and
does not expose raw position objects, broker/API responses, IDs, credential
values, signature values, or header values.

## Implemented Module

```text
backend/app/live_verification/live_order_real_position_read_only_source_controlled.py
```

The module imports no broker, Private API client, HTTP client, env reader, order
endpoint, ledger writer, receipt handoff, or `live_order_once` dependency.

## Source Candidate Decision

Existing source candidates were found:

- `backend/scripts/check_private_readonly_connection.py`
- `backend/app/private_api/readonly_client.py`

They are useful real read-only candidates, but they live at the credential,
signing, HTTP, and schema boundary. The Level 5 default route does not import
those modules directly. Instead, this step connects the route to a controlled
sanitized source summary that can represent the safe output of that boundary:

- `position_source_ready`
- `position_source_connected`
- `position_source_read_only`
- `position_source_checked`
- `position_status`
- `position_count_safe`

This keeps the route ready for a later explicit runtime read-only execution
step without bringing raw response, ID, or credential surfaces into Level 5.

## Safe Status Handling

The source adapter maps safe count/status as follows:

- `NO_POSITION`: entry planning allowed, close planning blocked
- `ONE_POSITION_OPEN`: entry planning blocked, close planning allowed
- `MULTIPLE_POSITIONS_BLOCKED`: entry and close planning blocked
- `UNKNOWN_FAIL_CLOSED`: entry and close planning blocked
- `SOURCE_MISSING_BLOCKED`: entry and close planning blocked

Exposure attempts are blocked as:

- `RAW_EXPOSURE_BLOCKED`
- `ID_EXPOSURE_BLOCKED`
- `VALUE_EXPOSURE_BLOCKED`
- `CREDENTIAL_UNAVAILABLE_BLOCKED`

Close execution remains blocked in every case:

```text
close_execution_allowed_now=false
actual_http_post_executed=false
close_post_executed=false
retry_attempted=false
second_post_attempted=false
ledger_updated=false
receipt_handoff_executed=false
```

## Route And Level 5 Connection

`live_order_real_position_read_only_controlled.py` now uses the controlled
source summary as its default/current source. The default route is no longer
`SOURCE_MISSING_BLOCKED`, but it remains fail-closed as `UNKNOWN_FAIL_CLOSED`
until an explicit safe source summary supplies a checked count/status.

The Level 5 foundation consumes the controlled route result:

- no position allows entry planning and blocks close planning
- one position blocks entry and enables close planning only
- multiple positions block entry and close
- unknown/source missing block entry and close
- second entry remains blocked when one position is open

## Not Implemented

This step does not execute real Private API reads, actual HTTP POST, close POST,
retry/repost, ledger update, attempt counter persistence, or receipt handoff.
It also does not create or expose a sealed position handle. Future close route
work must still solve ID handling without rendering, logging, storing, or
returning the ID value.

## Verification

Primary tests:

```text
python3 -m pytest -q app/tests/test_live_verification_live_order_real_position_read_only_source_controlled.py
python3 -m pytest -q app/tests/test_live_verification_live_order_real_position_read_only_controlled.py
python3 -m pytest -q app/tests/test_live_verification_live_order_real_step6g_level5_fast_mvp_controlled.py
python3 -m pytest -q app/tests/test_live_verification_no_order_imports.py
```

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-CLOSE-ORDER-ROUTE-IMPLEMENTATION-C
```

That step may implement close route planning and sealed handle design only. It
must still prohibit actual close POST, actual entry POST, retry/repost, second
POST, ledger update, receipt handoff, raw responses, broker/API responses, IDs,
credential values, signature values, header values, and `.env` access.

The close route follow-up is now implemented as planning-only. The next bounded
step should confirm a current runtime safe position read as status/count before
any later close execution gate can be considered:

```text
Step 6G-PC-OX-R-POSITION-RUNTIME-SAFE-READ-CHECK-C
```

That runtime safe read check completed with safe status/count only:

```text
position_source_checked=true
position_status=NO_POSITION
position_count_safe=0
```

No raw position object, broker/API response, IDs, credential values, signature
values, header values, or `.env` file access were displayed, saved, or returned.
