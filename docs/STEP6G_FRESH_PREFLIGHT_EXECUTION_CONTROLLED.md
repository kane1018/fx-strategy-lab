# Step 6G Fresh Preflight Execution Controlled

Step: `Step 6G-PC-OX-R-FRESH-PREFLIGHT-EXECUTION-RUNTIME-D`

This step implements the controlled fresh preflight execution adapter and CLI.
It does not execute fresh preflight in this step.

## Command

Use this safe command in adapter-summary mode:

```bash
cd backend
python3 -m app.live_verification.run_fresh_preflight_execution_controlled --adapter-summary-only
```

The command prints only a safe summary and returns:

- exit code `0` when the adapter command boundary is ready for the next step
- exit code `2` when the adapter command boundary is blocked or not ready

The command is a safe adapter entrypoint. It is not POST permission and it is
not proof that fresh preflight has executed.

## Boundary

- Connects the execution adapter to the consolidated fresh preflight runtime
  result.
- Exposes only safe labels, statuses, booleans, counts, and blocked reason
  labels.
- Requires next-step fresh preflight to be new, current, and non-reused.
- Requires the adapter to be at-most-once with no retry after unknown,
  timeout, or failed results.
- Keeps `fresh_preflight_execution_performed=false` in this implementation
  step.
- Keeps `post_allowed_this_step=false`, `post_executed=false`,
  `http_post_executed=false`, `order_endpoint_called=false`, and
  `live_order_once_called=false`.
- Keeps `final_confirmation_received=false`.
- Keeps `ledger_updated=false` and `attempt_counter_persisted=false`.
- Keeps `actual_result_receipt_received=false` and
  `actual_receipt_handoff_executed=false`.

## Safe Summary Fields

The adapter may report:

- `safe_preflight_execution_label`
- `safe_preflight_execution_status`
- `fresh_preflight_execution_command_available`
- `fresh_preflight_execution_allowed_next_step`
- `fresh_preflight_execution_performed`
- `fresh_preflight_new_marker_required`
- `fresh_preflight_current_marker_required`
- `fresh_preflight_non_reuse_required`
- `fresh_preflight_adapter_at_most_once`
- retry policy booleans
- public market, private read-only, and local/static mapping readiness
- safe account/open-position/active-order counts
- blocked reason labels
- recommended next step

It never reports raw requests, raw responses, request bodies, response bodies,
broker/API response bodies, endpoint values, account IDs, order IDs,
transaction IDs, position IDs, trade IDs, real IDs, credential values,
signature values, header values, confirmation phrases, ledger state values, or
approval command values.

## Meaning of Adapter Ready

`fresh_preflight_execution_command_available=true` means only that the
controlled adapter/CLI boundary is ready for a later fresh preflight execution
step. It does not mean:

- fresh preflight has executed
- HTTP POST is allowed
- final confirmation has been received
- ledger state has changed
- an attempt counter has been persisted
- actual receipt handoff has occurred
- real Step 6G can be retried

## Fail-Closed Mapping

The adapter blocks on:

- missing or not-ready consolidated runtime
- missing public market mapping
- missing private read-only mapping
- missing local/static mapping
- missing safe renderer
- unknown, failed, timeout, unavailable, stale, or reused state
- missing new/current/non-reuse requirements
- retry allowed after unknown, timeout, or failed state
- fresh preflight execution attempted in this implementation step
- HTTP POST, order endpoint, or `live_order_once` attempts
- final confirmation attempts
- ledger update or attempt counter persistence attempts
- actual receipt or handoff attempts
- raw, broker/API, ID, credential, signature, header, confirmation phrase,
  ledger state, or approval command exposure attempts

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-FRESH-PREFLIGHT-CHECK-RETRY-2
fresh preflight execution with safe adapter / no POST / no final confirmation execution
```

That step may execute fresh preflight once and return a safe summary only. It
still must not execute HTTP POST, call order endpoints, call `live_order_once`,
obtain final confirmation, update ledgers, persist attempt counters, receive
actual results, or perform receipt handoff.

Fresh preflight pass is still not POST permission. It only allows planning the
separate final confirmation step.
