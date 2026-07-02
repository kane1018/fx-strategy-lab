# Step 6G Fresh Preflight Runtime Controlled

Step: `Step 6G-PC-OX-R-FRESH-PREFLIGHT-RUNTIME-C`

This step implements the controlled fresh preflight runtime route. It is not
fresh preflight execution.

## Boundary

- Builds a safe runtime route for a later `FRESH-PREFLIGHT-CHECK-RETRY`.
- Aggregates public market, private read-only, local/static, final exec stack,
  post guard, and no-order guard readiness as safe summary fields.
- Returns only safe labels, statuses, booleans, counts, blocked reason labels,
  and the recommended next step.
- Does not execute fresh preflight.
- Does not execute HTTP POST.
- Does not call order endpoints.
- Does not call `live_order_once`.
- Does not obtain final confirmation.
- Does not update ledgers or persist attempt counters.
- Does not receive actual results or perform actual receipt handoff.

## Safe Runtime Summary

The runtime route may report:

- `safe_preflight_runtime_label`
- `safe_preflight_runtime_status`
- `fresh_preflight_runtime_ready`
- `public_market_check_ready`
- `private_read_only_check_ready`
- `local_static_check_ready`
- `final_exec_stack_ready`
- `post_guard_ready`
- `no_order_guard_ready`
- safe account/open-position/active-order counts
- safe blocked reason labels

It never reports raw requests, raw responses, broker/API response bodies,
endpoint values, account IDs, order IDs, transaction IDs, position IDs, trade
IDs, real IDs, credential values, signature values, header values,
confirmation phrases, ledger state values, or approval command values.

## Meaning of Ready

`fresh_preflight_runtime_ready=true` means only that the runtime route is ready
for a later fresh preflight execution step. It does not mean:

- fresh preflight has executed
- POST is allowed
- final confirmation has been received
- ledger state has changed
- actual receipt handoff has occurred
- real Step 6G can be retried

The controlled result keeps these false:

- `fresh_preflight_executed`
- `post_allowed_this_step`
- `post_executed`
- `http_post_executed`
- `order_endpoint_called`
- `live_order_once_called`
- `final_confirmation_received`
- `ledger_updated`
- `attempt_counter_persisted`
- `actual_result_receipt_received`
- `actual_receipt_handoff_executed`

## Fail-Closed Mapping

The runtime route blocks on:

- missing or not-ready public market route
- missing or not-ready private read-only route
- missing or not-ready local/static route
- missing or not-ready final exec stack
- missing or not-ready post guard
- unknown, failed, timeout, unavailable, stale, or reused runtime state
- nonzero open positions count
- nonzero active orders count
- account assets count not positive
- POST, order endpoint, `live_order_once`, final confirmation, ledger, attempt
  counter, actual receipt, or handoff attempts
- raw, broker/API, ID, credential, signature, header, confirmation phrase,
  ledger state, or approval command exposure attempts

## Runbook

Use this implementation only to prove that a safe runtime route exists for the
next retry step. Do not run fresh preflight from this step.

Next step:

```text
Step 6G-PC-OX-R-FRESH-PREFLIGHT-CHECK-RETRY
fresh preflight execution with consolidated runtime / no POST / no final confirmation execution
```

That retry step may execute fresh preflight and return a safe summary only.
It still must not execute HTTP POST, order endpoints, `live_order_once`, final
confirmation, ledger update, attempt counter persistence, actual receipt, or
actual receipt handoff.

Fresh preflight pass is still not POST permission. It only allows planning the
separate final confirmation step.
