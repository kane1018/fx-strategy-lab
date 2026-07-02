# Step 6G Sanitized POST Result

Step 6G-PC-OX-R-RESULT-C adds a sanitized POST result and reconciliation
contract before any future real POST result is handled.

This step is not an API call, not HTTP POST, not an order endpoint call, and not
`live_order_once` execution. It only defines how a future POST result must be
reduced to safe labels, safe statuses, safe booleans, and sanitized categories.

## Scope

Allowed in this step:

- `SANITIZED_POST_RESULT_CONTRACT_ONLY`
- `SANITIZED_RESULT_READY_NO_RECEIPT`
- fixed safe POST result label
- fixed safe reconciliation label
- sanitized POST result ready safe boolean
- reconciliation ready safe boolean
- safe result category
- safe reconciliation status
- raw request stored false
- raw response stored false
- broker response exposed false
- API response exposed false
- real ID exposed false
- ledger update allowed false
- actual receipt handoff allowed false
- safe blocked reason labels
- recommended next step label

Not allowed in this step:

- API call
- HTTP POST
- order endpoint call
- `live_order_once`
- raw request generation, display, save, or return
- raw response receipt, display, save, or return
- broker response actual value display, save, parse, or return
- API response actual value display, save, parse, or return
- request body or response body display, save, or return
- endpoint actual value display, save, or return
- account ID, order ID, transaction ID, position ID, trade ID, or real ID
  display, save, or return
- credential value display, save, or return
- signature value display, save, or return
- headers value display, save, or return
- confirmation phrase actual value display, save, or return
- ledger state actual value display, save, or return
- fresh preflight execution
- final confirmation execution
- actual result receipt or handoff
- ledger update
- attempt counter persistence
- Step 6G real funds retry

## Contract

The sanitized result input accepts only safe POST guard readiness data:

- safe POST guard label
- safe POST guard status
- POST guard controlled ready boolean
- safe result contract booleans and blocked reason controls

It does not accept credential values, signature values, headers values, raw
requests, raw responses, broker/API response values, endpoint actual values,
IDs, confirmation phrase actual values, fresh preflight detail actual values, or
ledger state actual values.

The result is limited to:

- `safe_post_result_label`
- `safe_post_result_status`
- `safe_result_category`
- `safe_reconciliation_label`
- `safe_reconciliation_status`
- `sanitized_post_result_ready`
- `reconciliation_ready`
- `raw_request_stored=false`
- `raw_response_stored=false`
- `broker_response_exposed=false`
- `api_response_exposed=false`
- `real_id_exposed=false`
- `ledger_update_allowed=false`
- `actual_receipt_handoff_allowed=false`
- safe blocked reason labels

## Meaning of Ready

`sanitized_post_result_ready=true` means only that the sanitized result contract
is ready for a later review step.

It does not mean:

- POST permission
- POST execution completed
- API permission
- order endpoint permission
- `live_order_once` permission
- fresh preflight completed
- final confirmation completed
- ledger update permission
- actual receipt handoff permission
- real order permission
- Step 6G real funds retry permission

`reconciliation_ready=true` means only that the reconciliation contract is in a
safe no-receipt-handoff state.

It does not mean:

- broker UI confirmed
- ledger updated
- actual receipt handoff completed
- real order confirmed
- Step 6G real funds retry permission

## Fail-Closed Categories

The contract fails closed for:

- unknown
- failed
- unavailable
- timeout
- rejected
- partial
- ambiguous
- unmatched
- stale
- previous-turn
- reused
- unsafe exposure
- raw request present or exposure attempted
- raw response present or exposure attempted
- broker response present or exposure attempted
- API response present or exposure attempted
- real ID / account ID / order ID / transaction ID exposure attempted
- ledger update attempted
- actual receipt or handoff attempted

`RESULT_ACCEPTED_SANITIZED` is reserved for a later step that has an explicitly
reviewed, non-raw, non-ID-bearing mapping. This step does not receive or parse
any actual result.

## Post-Execution Accepted Summary

The later one-shot POST execution gate and reconciliation gate supplied the
accepted result only as a safe summary:

- `post_execution_count=1`
- `retry_attempted=false`
- `second_post_attempted=false`
- `sanitized_result_category=RESULT_ACCEPTED_SANITIZED`
- `safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF`
- `ledger_updated=false`
- `attempt_counter_persisted=false`
- `actual_receipt_handoff_executed=false`
- `raw/ID/value exposure=false`

This accepted summary does not contain raw request data, raw response data,
broker/API response data, account/order/transaction IDs, credential values,
signature values, header values, or confirmation text.

Ledger/receipt handling remains a separate safe gate. A safe ledger-like record
or review-only receipt summary may use the sanitized facts above, but a real
broker receipt or ID-backed receipt must not be fetched or handled by Codex.

## Internal Wiring

Step 6G internal wiring includes `sanitized_post_result_ready` after
`post_guard_controlled_ready` and before private transport / HTTP interface
gates.

The internal wiring fails closed for:

- missing or not-ready POST guard prerequisite
- unknown / failed / unavailable / timeout
- rejected / partial / ambiguous / unmatched
- stale / previous-turn / reused
- raw request or raw response exposure attempted or stored
- broker/API response exposure attempted or exposed
- credential / signature / headers value exposure attempted
- endpoint actual value or real ID exposure attempted
- confirmation phrase or ledger state exposure attempted
- API attempted
- POST attempted
- order endpoint called
- `live_order_once` called
- ledger update attempted or allowed
- attempt counter persistence attempted
- fresh preflight attempted
- final confirmation attempted
- actual checker execution attempted
- actual receipt or handoff attempted

Even when the contract is ready, internal wiring keeps:

- `api_call_allowed=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `ledger_update_allowed=false`
- `actual_receipt_handoff_allowed=false`
- `fresh_preflight_executed=false`
- `final_confirmation_received=false`

## Verification

The implementation is covered by:

- `backend/app/tests/test_live_verification_live_order_real_sanitized_post_result.py`
- `backend/app/tests/test_live_verification_live_order_real_post_guard_controlled.py`
- `backend/app/tests/test_live_verification_live_order_real_step6g_internal_wiring.py`
- `backend/app/tests/test_live_verification_no_order_imports.py`

The no-order guard checks that the sanitized result module imports no HTTP
client, no private API, no broker module, no env loader, no crypto library, and
no `live_order_once`.

## Next Step

Recommended next step:

`Step 6G-PC-OX-R-SAFE-SANITIZED-LEDGER-RECEIPT-EXECUTION-GATE`

The next step may only consider sanitized accepted-result facts for a safe
ledger-like record or review-only receipt summary. It must not call APIs,
execute POST, call order endpoints, call `live_order_once`, display raw
requests or raw responses, display broker/API responses, display IDs, run fresh
preflight, run final confirmation, retry/repost, or hand off actual receipts.
